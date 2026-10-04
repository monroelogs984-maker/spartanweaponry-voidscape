#!/usr/bin/env python3
"""Builds src/main/resources/logo.png (512x256) for the mod list and README.

Three of the mod's own weapon textures, scaled up 8x with nearest-neighbour, over a vertical gradient in
the mod's palette, with the title in crisp un-antialiased text and a hard drop shadow. Needs ImageMagick (magick).

Usage: python3 tools/make_logo.py "<small title>" "<big title>" <dark hex> <light hex> <texture> <texture> <texture>
Textures are paths relative to src/main/resources/assets/<modid>/textures/item/ (without .png).
"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, 'src', 'main', 'resources')
FONT = 'Adwaita-Sans-ExtraBold'


def run(*args):
    subprocess.run(['magick', *args], check=True)


def pixel_text(text, size, out):
    """Crisp text (no anti-aliasing) with a hard 3px drop shadow, matching the pixel-art icons."""
    run('-background', 'none', '+antialias', '-font', FONT, '-pointsize', str(size), '-fill', 'white',
        f'label:{text}', '-trim', '+repage',
        '(', '+clone', '-fill', '#0B0B12', '-colorize', '100', ')',
        '-background', 'none', '(', '-clone', '1', '-repage', '+3+3', ')', '-delete', '1',
        '+swap', '-layers', 'merge', '+repage', out)


def main():
    small, big, dark, light, *textures = sys.argv[1:]
    modid = next(d for d in os.listdir(os.path.join(RES, 'assets')))
    tex_dir = os.path.join(RES, 'assets', modid, 'textures', 'item')
    with tempfile.TemporaryDirectory() as tmp:
        bg = os.path.join(tmp, 'bg.png')
        run('-size', '512x256', f'gradient:{light}-{dark}', '(', '-size', '512x256', 'radial-gradient:none-#00000090', ')',
            '-compose', 'over', '-composite', bg)
        canvas = bg
        for i, tex in enumerate(textures[:3]):
            icon = os.path.join(tmp, f'icon{i}.png')
            run(os.path.join(tex_dir, tex + '.png'), '-filter', 'point', '-resize', '128x128', icon)
            shadow = os.path.join(tmp, f'shadow{i}.png')
            run(icon, '-fill', '#000000', '-colorize', '100', '-channel', 'A', '-evaluate', 'multiply', '0.45', '+channel', shadow)
            nxt = os.path.join(tmp, f'c{i}.png')
            x = 64 + i * 128
            run(canvas, shadow, '-geometry', f'+{x + 6}+{18 + 6}', '-composite', icon, '-geometry', f'+{x}+18', '-composite', nxt)
            canvas = nxt
        small_png, big_png = os.path.join(tmp, 's.png'), os.path.join(tmp, 'b.png')
        pixel_text(small, 24, small_png)
        pixel_text(big, 44, big_png)
        out = os.path.join(RES, 'logo.png')
        run(canvas, small_png, '-gravity', 'north', '-geometry', '+0+152', '-composite',
            big_png, '-gravity', 'north', '-geometry', '+0+186', '-composite', out)
    print('wrote', os.path.relpath(out, ROOT))


if __name__ == '__main__':
    main()
