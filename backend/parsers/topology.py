"""Physical topology of a split keyboard, derived from its parsed layout.

The `.vil` matrix says nothing about how the board *looks* — it is just rows of
keycodes. Two boards with identical key counts can store their halves in
opposite column order, split at different row indices, and stagger their
columns differently. This module turns a parsed `Layout` into the geometry the
frontend needs to draw it.

Resolution order:

1. **Registry hit by `uid`** — a board we know by hand. Exact, includes the
   cosmetic geometry (column stagger, thumb rotation) that cannot be inferred.
2. **Inference** — for any board we have not seen. Gets the structural facts
   right (split point, column count, mirroring, thumb rows) and renders flat,
   without stagger.

So plugging in a new keyboard Just Works, and adding a `PROFILES` entry later
only upgrades its looks.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .vial import Layout

# Probe rows for the mirroring heuristic — the right half of a QWERTY-ish board
# reads index-finger-first when stored in display order.
_RIGHT_HAND_PROBES = (
    ("KC_Y", "KC_U", "KC_I", "KC_O", "KC_P"),
    ("KC_H", "KC_J", "KC_K", "KC_L"),
    ("KC_N", "KC_M"),
)


@dataclass(frozen=True)
class Geometry:
    """Cosmetic per-column / per-thumb offsets, in `rem`.

    All arrays are indexed by *display* position within the left half, running
    pinky → index. The right half reuses them reversed, so a symmetric board
    only ever describes one hand.

    Empty arrays mean "draw flat" — structurally correct, just not pretty.
    """

    col_offsets: list[float] = field(default_factory=list)
    thumb_rotate: list[float] = field(default_factory=list)  # degrees
    thumb_shift: list[float] = field(default_factory=list)


@dataclass(frozen=True)
class Topology:
    name: str
    slug: str  # CSS hook: `data-board` on the .keyboard wrapper
    rows: int
    cols: int
    split: int  # first row index belonging to the right half
    mirror_right: bool  # right half is stored outer→inner, reverse it to draw
    thumb_rows: list[int]  # absolute row indices that are thumb clusters
    geometry: Geometry
    inferred: bool  # True when this came from inference, not the registry


# --- known boards -----------------------------------------------------------
#
# `uid` is stable per firmware build, so it is the natural key. The stagger
# numbers below were eyeballed against each board's real key positions; tweak
# them freely, nothing else depends on the exact values.

_BEEKEEB_36 = Topology(
    name="beekeeb Painter Pro (36-key)",
    slug="beekeeb-36",
    rows=8,
    cols=6,
    split=4,
    mirror_right=True,
    thumb_rows=[3, 7],
    geometry=Geometry(
        # pinky sits low, middle finger reaches highest — classic column stagger
        col_offsets=[0.95, 0.35, 0.0, 0.35, 0.55],
        thumb_rotate=[-5.0, -11.0, -18.0],
        thumb_shift=[0.0, 0.2, 0.75],
    ),
    inferred=False,
)

_BORNE = Topology(
    name="borne",
    slug="borne",
    rows=10,
    cols=7,
    split=5,
    mirror_right=False,
    thumb_rows=[4, 9],
    geometry=Geometry(),
    inferred=False,
)

PROFILES: dict[int, Topology] = {
    16002279599986889074: _BEEKEEB_36,
    5010774632021243529: _BORNE,
}


# --- inference --------------------------------------------------------------


def _live_mask(layout: Layout, row_index: int) -> list[bool]:
    """Which columns of `row_index` hold a real key on *any* layer.

    A slot is `None` only where the board has no physical key there, so this
    is the matrix skeleton rather than anything layer-specific.
    """
    mask: list[bool] = []
    width = max((len(lr.rows[row_index].keys) for lr in layout.layers), default=0)
    for c in range(width):
        live = False
        for layer in layout.layers:
            keys = layer.rows[row_index].keys
            if c < len(keys) and keys[c] is not None:
                live = True
                break
        mask.append(live)
    return mask


def _infer_mirror(layout: Layout, split: int) -> bool:
    """Decide whether the right half is stored outer→inner.

    Primary signal: where the right hand's letters land. On a board stored in
    display order, Y comes before P; on a mirrored one, P comes first. This is
    unambiguous when it fires, and it is the common case.

    Fallback for non-QWERTY layouts: compare the two halves' matrix skeletons.
    If the right skeleton equals the left one it is stored symmetrically (so it
    needs mirroring); if it equals the reversed left it is already in display
    order. A palindromic skeleton tells us nothing — default to no mirroring,
    which is what a plain rectangular board wants.
    """
    base = layout.layers[0]

    for probe in _RIGHT_HAND_PROBES:
        for r in range(split, len(base.rows)):
            keys = base.rows[r].keys
            positions = [keys.index(k) for k in probe if k in keys]
            if len(positions) >= 3:
                # Stored ascending → already display order; descending → mirrored.
                return positions == sorted(positions, reverse=True)

    left_masks = [_live_mask(layout, r) for r in range(split)]
    right_masks = [_live_mask(layout, r) for r in range(split, len(base.rows))]
    if len(left_masks) != len(right_masks):
        return False
    reversed_left = [list(reversed(m)) for m in left_masks]
    if right_masks == reversed_left and right_masks != left_masks:
        return False
    return right_masks == left_masks and right_masks != reversed_left


def _infer_thumb_rows(layout: Layout, split: int, total_rows: int) -> list[int]:
    """Rows holding markedly fewer keys than their half's widest row.

    A thumb cluster is the defining example: 3 keys on a board whose letter
    rows carry 5-7. The 0.75 cutoff is loose enough to catch a 4-key cluster
    under a 6-wide row without swallowing a merely-gappy letter row.
    """
    thumbs: list[int] = []
    for half_start, half_end in ((0, split), (split, total_rows)):
        counts = {r: sum(_live_mask(layout, r)) for r in range(half_start, half_end)}
        if not counts:
            continue
        widest = max(counts.values())
        if widest == 0:
            continue
        thumbs.extend(r for r, n in counts.items() if 0 < n <= widest * 0.75)
    return sorted(thumbs)


def infer(layout: Layout) -> Topology:
    """Best-effort geometry for a board that is not in `PROFILES`."""
    base = layout.layers[0] if layout.layers else None
    if base is None or not base.rows:
        return Topology(
            name="unknown",
            slug="unknown",
            rows=0,
            cols=0,
            split=0,
            mirror_right=False,
            thumb_rows=[],
            geometry=Geometry(),
            inferred=True,
        )

    rows = len(base.rows)
    cols = max(len(r.keys) for r in base.rows)
    # Split boards store the two halves back to back, so the midpoint is the
    # boundary. A non-split board degrades gracefully: the "right half" simply
    # renders as the bottom rows, still in the correct order.
    split = rows // 2

    return Topology(
        name=f"unknown ({rows}×{cols})",
        slug="unknown",
        rows=rows,
        cols=cols,
        split=split,
        mirror_right=_infer_mirror(layout, split),
        thumb_rows=_infer_thumb_rows(layout, split, rows),
        geometry=Geometry(),
        inferred=True,
    )


def resolve(layout: Layout) -> Topology:
    """Registry lookup by `uid`, falling back to inference."""
    known = PROFILES.get(layout.uid)
    if known is not None:
        return known
    return infer(layout)
