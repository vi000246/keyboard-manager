#!/usr/bin/env python3
"""Transfer a Vial `.vil` config between two symmetric 3x5+3 split keyboards.

Originally written to port a "keyboard 36key" layout onto a "beekeeb" board.
Both must be symmetric 3x5+3 splits (3 letter rows of 5 + a 3-key thumb row
per hand). It copies all 6 layers, tap dances, combos and macros.

WHY THIS ISN'T A DUMB COPY
--------------------------
The two boards store their matrix differently, so keycodes can't be copied
1:1. This script handles three differences, all verified against the home row
(which both boards had populated identically):

  1. Row layout / column count differ.
       source (36key): 10 rows x 7 cols. Left = rows 0-4, right = rows 5-9.
                        top letter row is row1/row6 (row0/row5 unused).
       target (beekeeb): 8 rows x 6 cols. Left = rows 0-3, right = rows 4-7.
                         col 0 is always -1 (no physical key).

  2. Right hand is stored MIRRORED on the target.
       source right home row  = H J K L ;
       target right home row  = ; L K J H   -> reverse cols 1-5 for right hand.
     Left hand keeps the same column order on both.

  3. The target's factory LEFT half was shifted down one row (letters crammed
     low, top row left blank). We remap to the correct symmetric positions:
       target row0 <- source top    (QWERT)
       target row1 <- source home    (ASDFG, with home-row mods)
       target row2 <- source bottom  (ZXCVB)
       target row3 <- source L-thumb (3 keys at cols 3-5)

GLOBAL DATA
-----------
tap_dance / combo / macro are copied into the target's own slot counts (the
target usually has MORE slots; extra slots keep their defaults). Array LENGTHS
are never changed -- they're fixed by each board's firmware and Vial validates
them on import. uid, settings, key_override, encoder_layout and alt_repeat_key
are left as the target's.

SAFETY
------
The target's -1 "no physical key" skeleton is preserved exactly, so every
transferred key lands on a real key. Run with --check to print a report and
verify the skeleton matches before trusting the output.

USAGE
-----
  python3 vil_transfer.py SOURCE.vil TARGET.vil OUTPUT.vil [--check]

  SOURCE  the layout you want to copy FROM (36key-style: 10 rows x 7 cols)
  TARGET  the keyboard you want to copy ONTO (beekeeb-style: 8 rows x 6 cols,
          provides firmware array sizes, uid, settings)
  OUTPUT  file to write; import this into Vial (File > Import Keymap)
"""
import argparse
import json
import sys


def left_letter(row):   # 7-col source row -> 6-col target row, same order
    return [-1] + row[1:6]


def right_letter(row):  # reverse cols 1-5 (target stores right hand mirrored)
    return [-1] + list(reversed(row[1:6]))


def left_thumb(row):    # source row4 thumbs at cols 3-5 -> target cols 3-5
    return [-1, -1, -1] + row[3:6]


def right_thumb(row):   # source row9 thumbs at cols 1-3 -> reversed -> target cols 3-5
    return [-1] + list(reversed(row[1:6]))


def map_layer(sl):
    """Map one source layer (10 rows x 7 cols) to a target layer (8 rows x 6 cols)."""
    return [
        left_letter(sl[1]),    # target row0 <- source top    (QWERT)
        left_letter(sl[2]),    # target row1 <- source home   (ASDFG)
        left_letter(sl[3]),    # target row2 <- source bottom (ZXCVB)
        left_thumb(sl[4]),     # target row3 <- source L-thumb (TAB/SPACE/ESC)
        right_letter(sl[6]),   # target row4 <- source top    (YUIOP)
        right_letter(sl[7]),   # target row5 <- source home   (HJKL;)
        right_letter(sl[8]),   # target row6 <- source bottom (NM,./)
        right_thumb(sl[9]),    # target row7 <- source R-thumb (BSPC/ENT/DEL)
    ]


def transfer(src, dst):
    out = dict(dst)  # keep target uid, protocols, settings, firmware array sizes

    layout = list(dst["layout"])
    for i in range(len(src["layout"])):          # copy every source layer
        layout[i] = map_layer(src["layout"][i])
    out["layout"] = layout

    for key in ("tap_dance", "combo", "macro"):  # fill within target's slot counts
        merged = list(dst[key])
        for i in range(len(src[key])):
            if i < len(merged):
                merged[i] = src[key][i]
        out[key] = merged
    return out


def check(out, dst, n_layers):
    print("--- check ---")
    print("layers filled:", n_layers)
    print("base layer (L0) rows:")
    for r in out["layout"][0]:
        print("  ", r)
    widths = {len(r) for L in out["layout"] for r in L}
    print("row widths (should be one value):", widths)
    mism = [
        (li, ri, ci)
        for li in range(n_layers)
        for ri in range(len(dst["layout"][li]))
        for ci in range(len(dst["layout"][li][ri]))
        if (dst["layout"][li][ri][ci] == -1) != (out["layout"][li][ri][ci] == -1)
    ]
    print("skeleton (-1) mismatches vs target:", mism if mism else "none")
    # tap_dance/combo entries end with a timing/keycode payload; only the
    # keycode slots decide "used". macro is a list of steps.
    used_slice = {"tap_dance": 4, "combo": 4, "macro": None}
    for key in ("tap_dance", "combo", "macro"):
        n = used_slice[key]
        nz = [i for i, v in enumerate(out[key])
              if (bool(v) if n is None else any(x != "KC_NO" for x in v[:n]))]
        print(f"{key} non-default idx:", nz)
    if mism:
        print("WARNING: skeleton mismatch -- some keys land on non-existent slots!")
        return False
    return True


def main():
    ap = argparse.ArgumentParser(description="Transfer a Vial .vil between two symmetric 3x5+3 splits.")
    ap.add_argument("source", help="layout to copy FROM (36key-style, 10x7)")
    ap.add_argument("target", help="keyboard to copy ONTO (beekeeb-style, 8x6)")
    ap.add_argument("output", help="output .vil to write")
    ap.add_argument("--check", action="store_true", help="print a verification report")
    args = ap.parse_args()

    with open(args.source) as f:
        src = json.load(f)
    with open(args.target) as f:
        dst = json.load(f)

    out = transfer(src, dst)

    with open(args.output, "w") as f:
        json.dump(out, f)
    print("wrote", args.output)

    if args.check and not check(out, dst, len(src["layout"])):
        sys.exit(1)


if __name__ == "__main__":
    main()
