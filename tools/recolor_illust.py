"""デジタル庁のイラスト素材（PNG）を、サイトの色（ネイビー・緑・薄緑・白）に塗り直す。

使い方:
    python3 tools/recolor_illust.py <元のPNG> <出力PNG> [幅=1200] [肌の色=white|light]

素材で使われている色ごとに、どの色に塗るかを決めておき（COLOR_MAP）、各画素を一番近い元の色に
合わせてから塗り替える。肌は、背景に薄緑の形があるイラストでは白、白い背景のイラストでは薄緑にする
（顔が背景に溶けないように）。Pillow が必要（サイトの build.py は標準ライブラリのみのまま）。
素材を改変して公開するので、pages/about.html に出典と改変内容を書く（利用規約）。
"""

import sys
from PIL import Image

NAVY, GREEN, LIGHT, WHITE = (0x1F, 0x3A, 0x6E), (0x13, 0xA5, 0x65), (0xC4, 0xF0, 0xD6), (0xFF, 0xFF, 0xFF)
SKIN = "skin"

# 素材の色 → 塗る色
COLOR_MAP = {
    (0xFF, 0xFF, 0xFF): WHITE,
    (0xF0, 0xA5, 0x9B): LIGHT, (0xA5, 0xBF, 0xAE): LIGHT,          # 背景の形
    (0x1D, 0x2A, 0x68): NAVY, (0x0F, 0x19, 0x46): NAVY,            # 紺の服・髪
    (0x49, 0x32, 0x2F): NAVY, (0x44, 0x23, 0x23): NAVY,            # 茶色の髪
    (0xAE, 0x7A, 0x41): NAVY, (0x4D, 0x4D, 0x4D): NAVY,            # 明るい茶の髪・スマホ
    (0x17, 0x75, 0x75): GREEN, (0x16, 0x64, 0x64): GREEN,          # 青緑の服
    (0xF9, 0x54, 0x28): GREEN, (0x8D, 0xB6, 0xE8): GREEN,          # 橙・水色の服
    (0x98, 0x98, 0x98): LIGHT, (0xF5, 0xEE, 0xE3): WHITE,          # 灰色（車いす・PC）・生成りの服
    (0xFF, 0xB6, 0x95): SKIN, (0xFF, 0x97, 0x7F): SKIN, (0xFF, 0xCB, 0x87): SKIN,
    (0xFF, 0xD2, 0xC8): SKIN, (0xFF, 0x9D, 0x85): SKIN, (0x98, 0x5C, 0x35): SKIN,
}


def main():
    src, out = sys.argv[1], sys.argv[2]
    width = int(sys.argv[3]) if len(sys.argv) > 3 else 1200
    skin = LIGHT if len(sys.argv) > 4 and sys.argv[4] == "light" else WHITE

    im = Image.open(src).convert("RGBA")
    alpha = im.getchannel("A")
    keys = list(COLOR_MAP)
    pal = Image.new("P", (1, 1))
    pal.putpalette([v for k in keys for v in k] + [0] * (768 - 3 * len(keys)))
    q = im.convert("RGB").quantize(palette=pal, dither=Image.Dither.NONE)
    targets = [skin if COLOR_MAP[k] == SKIN else COLOR_MAP[k] for k in keys]
    q.putpalette([v for t in targets for v in t] + [0] * (768 - 3 * len(targets)))
    rgb = q.convert("RGBA")
    rgb.putalpha(alpha)

    # 白い余白を切る
    bbox = Image.eval(rgb.convert("L"), lambda v: 255 if v < 250 else 0).getbbox()
    if bbox:
        rgb = rgb.crop(bbox)
    rgb.thumbnail((width, width), Image.LANCZOS)
    rgb.save(out, optimize=True)
    print(out, rgb.size)


if __name__ == "__main__":
    main()
