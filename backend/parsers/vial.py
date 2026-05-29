"""Vial `.vil` JSON loader.

Parses the JSON config produced by the Vial keymap editor into typed dataclasses.
Read-only; never writes back to disk.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_PROTOCOLS = {6}


class VialParseError(Exception):
    """Raised when the .vil file is malformed or its schema is unsupported."""


@dataclass(frozen=True)
class Row:
    row: int
    keys: list[str | None]  # None for -1 slots (no physical key)


@dataclass(frozen=True)
class Layer:
    index: int
    rows: list[Row]


@dataclass(frozen=True)
class TapDance:
    index: int
    tap: str
    hold: str
    double_tap: str
    tap_hold: str
    tap_term_ms: int


@dataclass(frozen=True)
class Combo:
    index: int
    triggers: list[str]  # KC_NO filtered out — 1-4 active trigger keys
    output: str


@dataclass(frozen=True)
class Macro:
    """A single Vial macro entry.

    `actions` is the raw list-of-lists from the .vil — Vial encodes each
    step as ``["tap", "KC_X"]`` / ``["down", "KC_LSHIFT"]`` /
    ``["text", "hello"]`` / ``["delay", 200]`` etc. We keep the raw form
    instead of normalizing to a struct because (a) the action vocabulary
    is open-ended and (b) the only consumer right now is the tooltip,
    which can render whatever it gets.
    """
    index: int
    actions: list


@dataclass(frozen=True)
class Layout:
    vial_protocol: int
    uid: int
    layers: list[Layer]
    tap_dance: list[TapDance]
    combo: list[Combo]
    macros: list[Macro]


def parse(path: Path) -> Layout:
    """Load and validate a .vil file.

    Raises VialParseError on malformed JSON or unsupported protocol.
    """
    p = Path(path)
    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError as e:
        raise VialParseError(f"invalid json in {p}: {e}") from e
    except FileNotFoundError as e:
        raise VialParseError(f"file not found: {p}") from e

    proto = data.get("vial_protocol")
    if proto not in SUPPORTED_PROTOCOLS:
        raise VialParseError(
            f"vial_protocol {proto!r} unsupported (expect one of {SUPPORTED_PROTOCOLS})"
        )

    layers: list[Layer] = []
    for li, raw_layer in enumerate(data.get("layout", [])):
        rows = [
            Row(row=ri, keys=[None if k == -1 else k for k in raw_row])
            for ri, raw_row in enumerate(raw_layer)
        ]
        layers.append(Layer(index=li, rows=rows))

    tap_dance: list[TapDance] = []
    for ti, td in enumerate(data.get("tap_dance", [])):
        # Each TD entry: [tap, hold, double_tap, tap_hold, tap_term_ms]
        tap_dance.append(
            TapDance(
                index=ti,
                tap=td[0],
                hold=td[1],
                double_tap=td[2],
                tap_hold=td[3],
                tap_term_ms=td[4],
            )
        )

    combos: list[Combo] = []
    for ci, c in enumerate(data.get("combo", [])):
        # Each combo entry: [trig1, trig2, trig3, trig4, output]
        triggers = [k for k in c[:4] if k != "KC_NO"]
        combos.append(Combo(index=ci, triggers=triggers, output=c[4]))

    # Vial keeps a fixed-size macro array; entries are lists of action arrays.
    # Empty inner lists mean "macro N is unset" — preserve the index so the
    # frontend can correlate a MACRO{N} keycode to its definition (or lack
    # thereof) without doing arithmetic on positions.
    macros: list[Macro] = []
    for mi, raw_actions in enumerate(data.get("macro", [])):
        actions_list = raw_actions if isinstance(raw_actions, list) else []
        macros.append(Macro(index=mi, actions=actions_list))

    return Layout(
        vial_protocol=proto,
        uid=data.get("uid", 0),
        layers=layers,
        tap_dance=tap_dance,
        combo=combos,
        macros=macros,
    )
