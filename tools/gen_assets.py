#!/usr/bin/env python3
"""Generates every resource for Spartan Weaponry: Voidscape into src/main/resources.

- Models, weapon attributes, lang and weapon-type tags: cloned from tools/template (the Spartan Toolkit
  output of an existing addon) with the material and namespace swapped.
- Textures: Spartan's iron weapon textures, with every neutral-grey (metal) pixel gradient-mapped by
  luminance onto a palette sampled from Voidscape's own sword texture. Handles, strings and gems
  (anything coloured) stay untouched, and alpha is kept.
- Recipes: Voidscape-style smithing upgrades (netherite -> voidic crystal -> corrupt).
- Repair and trait tags.
Needs ImageMagick (magick). Run from the project root:  python3 tools/gen_assets.py
"""
import json
import os
import re
import shutil
import subprocess
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, 'tools', 'template')
RES = os.path.join(ROOT, 'src', 'main', 'resources')
SPARTAN_JAR = os.path.join(ROOT, 'libs', 'spartanweaponry-3.2.1.jar')
MODID = 'spartanweaponryvoidscape'
TEMPLATE_MODID = 'spartanweaponryaquaculture'
TEMPLATE_MATERIAL = 'neptunium'

# Palettes sampled from Voidscape's textures/item/<material>/sword.png, darkest to lightest.
MATERIALS = {
    'voidic_crystal': {
        'display': 'Voidic Crystal',
        'palette': ['#1C1144', '#260F54', '#421B7C', '#561B92', '#7320AE', '#B03BD5', '#EC6FFB', '#FBC2FA'],
        'repair': ['voidscape:voidic_crystal'],
        'traits': ['voidtouched'],
        'upgrade_from': 'spartanweaponry:netherite_{type}',
        'addition': 'voidscape:voidic_crystal',
    },
    'corrupt': {
        'display': 'Corrupt',
        'palette': ['#1F1820', '#272029', '#333140', '#414247', '#4F5256', '#6D7072', '#7320AE', '#B03BD5'],
        'repair': ['voidscape:tendril'],
        'traits': ['deep_voidtouched', 'corruption'],
        'upgrade_from': MODID + ':voidic_crystal_{type}',
        'addition': 'voidscape:tendril',
    },
}
# name, description (Spartan reads tooltip.<modid>.trait.<id>.desc; keep in sync with the Java traits)
TRAITS = {
    'voidtouched': ('Voidtouched', '+30% damage while in the Void'),
    'deep_voidtouched': ('Deep Voidtouched', '+40% damage while in the Void'),
    'corruption': ('Corruption', 'Hits inflict Wither for 3 seconds'),
}


def hex_rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def gradient(palette, t):
    """t in [0,1] -> colour interpolated along the palette."""
    pts = [hex_rgb(c) for c in palette]
    pos = t * (len(pts) - 1)
    i = min(int(pos), len(pts) - 2)
    f = pos - i
    return tuple(round(pts[i][k] + (pts[i + 1][k] - pts[i][k]) * f) for k in range(3))


def recolor(png_bytes, palette, out_path):
    txt = subprocess.run(['magick', 'png:-', 'txt:-'], input=png_bytes, capture_output=True, check=True).stdout.decode()
    lines = txt.splitlines()
    header, pixels = lines[0], []
    greys = []
    for line in lines[1:]:
        m = re.match(r'(\d+),(\d+): \(([\d.]+),([\d.]+),([\d.]+)(?:,([\d.]+))?\)', line)
        if not m:
            continue
        x, y, r, g, b = int(m[1]), int(m[2]), float(m[3]), float(m[4]), float(m[5])
        a = float(m[6]) if m[6] is not None else 255.0
        pixels.append([x, y, r, g, b, a])
        if a > 0 and r == g == b:
            greys.append(r)
    lo, hi = (min(greys), max(greys)) if greys else (0, 255)
    out = [header]
    for x, y, r, g, b, a in pixels:
        if a > 0 and r == g == b:
            t = 0.0 if hi == lo else (r - lo) / (hi - lo)
            r, g, b = gradient(palette, t)
        out.append(f'{x},{y}: ({round(r)},{round(g)},{round(b)},{round(a)})')
    subprocess.run(['magick', 'txt:-', out_path], input='\n'.join(out).encode(), check=True)


def clone_tree(src_rel, dst_rel, material):
    src_dir = os.path.join(TEMPLATE, src_rel)
    for name in sorted(os.listdir(src_dir)):
        if not name.startswith(TEMPLATE_MATERIAL + '_'):
            continue
        text = open(os.path.join(src_dir, name)).read()
        text = text.replace(TEMPLATE_MODID, MODID).replace(TEMPLATE_MATERIAL, material)
        dst = os.path.join(RES, dst_rel, name.replace(TEMPLATE_MATERIAL, material, 1))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, 'w').write(text)


def main():
    for sub in ('assets', 'data'):
        shutil.rmtree(os.path.join(RES, sub), ignore_errors=True)

    weapon_types = sorted({re.sub(r'^' + TEMPLATE_MATERIAL + r'_|\.json$', '', n)
                           for n in os.listdir(os.path.join(TEMPLATE, 'data', TEMPLATE_MODID, 'recipes'))})
    with zipfile.ZipFile(SPARTAN_JAR) as spartan:
        iron_textures = {n.rsplit('/', 1)[1][len('iron_'):-4]: n for n in spartan.namelist()
                         if re.match(r'assets/spartanweaponry/textures/item/iron_[a-z_0-9]+\.png$', n)}

        lang = {}
        template_lang = json.load(open(os.path.join(TEMPLATE, 'assets', TEMPLATE_MODID, 'lang', 'en_us.json')))
        for material, spec in MATERIALS.items():
            clone_tree(f'assets/{TEMPLATE_MODID}/models/item', f'assets/{MODID}/models/item', material)
            clone_tree(f'data/{TEMPLATE_MODID}/weapon_attributes', f'data/{MODID}/weapon_attributes', material)

            # Textures: every texture any model references for this material.
            tex_dir = os.path.join(RES, 'assets', MODID, 'textures', 'item')
            os.makedirs(tex_dir, exist_ok=True)
            referenced = set()
            for model in os.listdir(os.path.join(RES, 'assets', MODID, 'models', 'item')):
                if model.startswith(material + '_'):
                    textures = json.load(open(os.path.join(RES, 'assets', MODID, 'models', 'item', model))).get('textures', {})
                    referenced |= {v.split('item/', 1)[1] for v in textures.values() if v.startswith(MODID + ':item/')}
            for tex in sorted(referenced):
                key = tex[len(material) + 1:]
                if key not in iron_textures:
                    raise SystemExit(f'no Spartan iron texture for {tex}')
                recolor(spartan.read(iron_textures[key]), spec['palette'], os.path.join(tex_dir, tex + '.png'))

            # Smithing recipes, Voidscape style (template is kept, like Voidscape's own upgrades).
            for wtype in weapon_types:
                recipe = {
                    'type': 'voidscape:smithing',
                    'template': {'item': 'voidscape:voidic_template'},
                    'base': {'item': spec['upgrade_from'].format(type=wtype)},
                    'addition': {'item': spec['addition']},
                    'result': {'item': f'{MODID}:{material}_{wtype}'},
                }
                path = os.path.join(RES, 'data', MODID, 'recipes', f'{material}_{wtype}.json')
                os.makedirs(os.path.dirname(path), exist_ok=True)
                json.dump(recipe, open(path, 'w'), indent=2)

            # Repair tag, trait tag.
            for rel, values in ((f'data/{MODID}/tags/items/repair/{material}.json', spec['repair']),
                                (f'data/{MODID}/tags/spartanweaponry/weapon_traits/{material}.json',
                                 [f'{MODID}:{t}' for t in spec['traits']])):
                path = os.path.join(RES, rel)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                json.dump({'values': values}, open(path, 'w'), indent=2)

            for key, value in template_lang.items():
                if TEMPLATE_MATERIAL in key:
                    lang[key.replace(TEMPLATE_MODID, MODID).replace(TEMPLATE_MATERIAL, material)] = \
                        value.replace('Neptunium', spec['display'])

        lang['itemGroup.' + MODID] = 'Spartan Weaponry: Voidscape'
        for trait, (name, desc) in TRAITS.items():
            lang[f'tooltip.{MODID}.trait.{trait}'] = name
            lang[f'tooltip.{MODID}.trait.{trait}.desc'] = desc
        path = os.path.join(RES, 'assets', MODID, 'lang', 'en_us.json')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        json.dump(dict(sorted(lang.items())), open(path, 'w'), indent=2)

        # Weapon-type tags (spartanweaponry:longswords etc.) so Spartan treats them as its own types.
        tag_dir = os.path.join(TEMPLATE, 'data', 'spartanweaponry', 'tags', 'items')
        for name in os.listdir(tag_dir):
            values = []
            for value in json.load(open(os.path.join(tag_dir, name)))['values']:
                for material in MATERIALS:
                    values.append(value.replace(TEMPLATE_MODID, MODID).replace(TEMPLATE_MATERIAL, material))
            path = os.path.join(RES, 'data', 'spartanweaponry', 'tags', 'items', name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            json.dump({'replace': False, 'values': values}, open(path, 'w'), indent=2)

    counts = {d: sum(len(f) for _, _, f in os.walk(os.path.join(RES, d))) for d in ('assets', 'data')}
    print(f'{len(weapon_types)} weapon types x {len(MATERIALS)} materials; files: {counts}')


if __name__ == '__main__':
    main()
