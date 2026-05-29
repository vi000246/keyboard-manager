#!/usr/bin/env python3
"""Analyze ~/keystat-counts.json and produce sorted reports for keyboard layout design.

Reports:
  1. Single-key frequency (no modifiers) — base layer placement
  2. Modifier-combo frequency — layer / thumb-cluster candidates
  3. Per-app comparison (terminal / editor / browser) — app-specific layer signals
  4. Leader-style high-frequency keys after `,` (best-effort, sequences unavailable)
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

DATA = Path(os.path.expanduser("~/keystat-counts.json"))

APP_BUCKETS: dict[str, list[str]] = {
    "terminal": [
        "com.googlecode.iterm2",
        "dev.warp.Warp-Stable",
        "com.apple.Terminal",
        "com.github.wez.wezterm",
    ],
    "editor": [
        "org.vim.MacVim",
        "md.obsidian",
        "notion.id",
        "com.apple.TextEdit",
    ],
    "browser": [
        "com.brave.Browser",
        "org.mozilla.firefox",
        "org.qutebrowser.qutebrowser",
        "com.google.chrome.for.testing",
    ],
    "chat": [
        "jp.naver.line.mac",
        "com.apple.MobileSMS",
        "com.apple.mail",
    ],
    "launcher": [
        "com.raycast.macos",
        "org.hammerspoon.Hammerspoon",
    ],
}

# Keys we consider "movement" so we can flag them out of single-key reports if useful.
NAV_KEYS = {"left", "right", "up", "down", "home", "end", "pageup", "pagedown"}
EDIT_KEYS = {"delete", "forwarddelete", "return", "escape", "tab", "space"}


def load() -> dict:
    with DATA.open() as f:
        return json.load(f)


def is_modifier_combo(key: str) -> bool:
    return "+" in key


def split_mods(key: str) -> tuple[frozenset[str], str]:
    parts = key.split("+")
    base = parts[-1]
    mods = frozenset(parts[:-1])
    return mods, base


def aggregate(data: dict) -> tuple[Counter, Counter, dict[str, Counter]]:
    """Return (single_keys, mod_combos, per_app_counters)."""
    single: Counter = Counter()
    mods: Counter = Counter()
    per_app: dict[str, Counter] = defaultdict(Counter)

    for app, keys in data.items():
        if app == "__meta" or not isinstance(keys, dict):
            continue
        for key, count in keys.items():
            per_app[app][key] += count
            if is_modifier_combo(key):
                mods[key] += count
            else:
                single[key] += count
    return single, mods, per_app


def format_table(rows: list[tuple[str, int]], total: int, title: str, top_n: int = 40) -> str:
    out = [f"\n## {title}\n"]
    out.append(f"{'rank':>4}  {'count':>7}  {'%':>6}  key")
    out.append("-" * 60)
    for i, (k, c) in enumerate(rows[:top_n], 1):
        pct = (c / total * 100) if total else 0.0
        out.append(f"{i:>4}  {c:>7}  {pct:>5.2f}%  {k}")
    return "\n".join(out)


def report_single(single: Counter) -> str:
    total = sum(single.values())
    rows = single.most_common()
    return format_table(rows, total, f"Single-key frequency (total={total})", top_n=50)


def report_mods(mods: Counter) -> str:
    total = sum(mods.values())
    rows = mods.most_common()
    out = [format_table(rows, total, f"Modifier-combo frequency (total={total})", top_n=60)]

    # Specifically called out by the user.
    callouts = {
        "cmd+ctrl+arrows": [k for k in mods if k.startswith("cmd+ctrl+") and k.split("+")[-1] in {"left", "right", "up", "down"}],
        "cmd+ctrl+1-4": [k for k in mods if k.startswith("cmd+ctrl+") and k.split("+")[-1] in {"1", "2", "3", "4"}],
        "ctrl+hjkl": [k for k in mods if k.startswith("ctrl+") and k.split("+")[-1] in {"h", "j", "k", "l"} and "cmd" not in k and "alt" not in k],
        "cmd+ctrl+hjkl": [k for k in mods if k.startswith("cmd+ctrl+") and k.split("+")[-1] in {"h", "j", "k", "l"}],
    }
    out.append("\n### Callout buckets")
    for name, ks in callouts.items():
        total_n = sum(mods[k] for k in ks)
        detail = ", ".join(f"{k}={mods[k]}" for k in sorted(ks, key=lambda x: -mods[x]))
        out.append(f"  {name:<22} total={total_n}  ({detail or '—'})")

    # Aggregate by modifier-set (regardless of base key) and by base key (regardless of mod).
    by_mod: Counter = Counter()
    by_base: Counter = Counter()
    for k, c in mods.items():
        mset, base = split_mods(k)
        by_mod["+".join(sorted(mset))] += c
        by_base[base] += c

    out.append("\n### Modifier-set totals (which mod combos you actually hold)")
    for ms, c in by_mod.most_common():
        out.append(f"  {c:>6}  {ms}")

    out.append("\n### Base-key totals across all modifier combos (which keys you reach for under mods)")
    for b, c in by_base.most_common(30):
        out.append(f"  {c:>6}  {b}")

    return "\n".join(out)


def report_per_app(per_app: dict[str, Counter]) -> str:
    out = ["\n## Per-app comparison (buckets)"]
    bucket_counters: dict[str, Counter] = {b: Counter() for b in APP_BUCKETS}
    for bucket, apps in APP_BUCKETS.items():
        for app in apps:
            if app in per_app:
                bucket_counters[bucket].update(per_app[app])

    # Top single keys per bucket (no modifiers) and top mod combos per bucket.
    for bucket, c in bucket_counters.items():
        single = Counter({k: v for k, v in c.items() if not is_modifier_combo(k)})
        modc = Counter({k: v for k, v in c.items() if is_modifier_combo(k)})
        out.append(f"\n### {bucket}  (total keystrokes={sum(c.values())})")
        out.append("  top single keys:")
        for k, v in single.most_common(15):
            out.append(f"    {v:>5}  {k}")
        out.append("  top mod combos:")
        for k, v in modc.most_common(15):
            out.append(f"    {v:>5}  {k}")

    # Differential: keys that are dramatically more frequent in browser than terminal/editor.
    out.append("\n### Browser-leaning keys (browser share much higher than terminal+editor)")
    bro = bucket_counters["browser"]
    term = bucket_counters["terminal"]
    edt = bucket_counters["editor"]
    bro_total = max(sum(bro.values()), 1)
    other_total = max(sum(term.values()) + sum(edt.values()), 1)
    diffs = []
    for k, v in bro.items():
        if v < 5:
            continue
        bro_share = v / bro_total
        other_share = (term.get(k, 0) + edt.get(k, 0)) / other_total
        if bro_share > other_share * 2:
            diffs.append((k, v, bro_share - other_share))
    diffs.sort(key=lambda x: -x[2])
    for k, v, d in diffs[:25]:
        out.append(f"    +{d*100:>5.2f}pp  count={v}  {k}")

    out.append("\n### Terminal/editor-leaning keys (much higher than browser)")
    diffs2 = []
    for k in set(list(term.keys()) + list(edt.keys())):
        v = term.get(k, 0) + edt.get(k, 0)
        if v < 10:
            continue
        bro_share = bro.get(k, 0) / bro_total
        other_share = v / other_total
        if other_share > bro_share * 2:
            diffs2.append((k, v, other_share - bro_share))
    diffs2.sort(key=lambda x: -x[2])
    for k, v, d in diffs2[:25]:
        out.append(f"    +{d*100:>5.2f}pp  count={v}  {k}")

    return "\n".join(out)


def report_leader(per_app: dict[str, Counter]) -> str:
    """Best-effort: the dataset is per-keystroke counts, not sequences, so we
    can only show comma counts and the top keys in vim-like apps as a proxy."""
    out = ["\n## Leader (`,`) proxy report"]
    vim_apps = ["org.vim.MacVim", "com.googlecode.iterm2", "md.obsidian", "org.qutebrowser.qutebrowser"]
    for app in vim_apps:
        if app not in per_app:
            continue
        c = per_app[app]
        comma = c.get(",", 0)
        total = sum(c.values())
        out.append(f"\n  {app}  total={total}  comma={comma}  comma_share={comma/total*100 if total else 0:.2f}%")
        # Top non-modifier keys as candidates likely to follow leader.
        single = Counter({k: v for k, v in c.items() if not is_modifier_combo(k)})
        for k, v in single.most_common(10):
            out.append(f"      {v:>4}  {k}")
    out.append("\n  NOTE: this dataset does not record key sequences, so `,xx` mappings cannot be measured directly. Use the top keys in vim-like apps as candidate landing keys.")
    return "\n".join(out)


def main() -> int:
    data = load()
    single, mods, per_app = aggregate(data)

    meta = data.get("__meta", {})
    print(f"# Keystat report")
    print(f"  source: {DATA}")
    print(f"  window: {meta.get('startedAt')} → {meta.get('lastFlush')}")
    print(f"  apps with data: {len(per_app)}")
    print(f"  unique single keys: {len(single)}")
    print(f"  unique mod combos:  {len(mods)}")
    print(f"  total single-key strokes: {sum(single.values())}")
    print(f"  total mod-combo strokes:  {sum(mods.values())}")

    print(report_single(single))
    print(report_mods(mods))
    print(report_per_app(per_app))
    print(report_leader(per_app))
    return 0


if __name__ == "__main__":
    sys.exit(main())
