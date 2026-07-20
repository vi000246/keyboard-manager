"""Topology resolution: registry hits and inference for unknown boards.

The inference path is what makes plugging in a new keyboard work without code
changes, so it is tested against both real sample boards independently of the
hand-written profiles — if inference ever regresses, these catch it even though
`resolve()` would still return the right thing from the registry.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.parsers import topology
from backend.parsers.vial import parse

SAMPLES = Path(__file__).resolve().parents[2] / "sample"


@pytest.fixture(scope="module")
def borne():
    return parse(SAMPLES / "mylayout.vil")


@pytest.fixture(scope="module")
def beekeeb():
    return parse(SAMPLES / "beekeeb-36key.vil")


def test_registry_hit_beekeeb(beekeeb):
    t = topology.resolve(beekeeb)
    assert not t.inferred
    assert t.slug == "beekeeb-36"
    assert (t.rows, t.cols, t.split) == (8, 6, 4)
    assert t.mirror_right is True
    assert t.thumb_rows == [3, 7]


def test_registry_hit_borne(borne):
    t = topology.resolve(borne)
    assert not t.inferred
    assert t.slug == "borne"
    assert (t.rows, t.cols, t.split) == (10, 7, 5)
    assert t.mirror_right is False


def test_unknown_uid_falls_back_to_inference(beekeeb):
    """A board absent from PROFILES must still resolve to usable geometry."""
    stranger = type(beekeeb)(
        vial_protocol=beekeeb.vial_protocol,
        uid=1,  # not in PROFILES
        layers=beekeeb.layers,
        tap_dance=beekeeb.tap_dance,
        combo=beekeeb.combo,
        macros=beekeeb.macros,
    )
    t = topology.resolve(stranger)
    assert t.inferred
    assert (t.rows, t.cols, t.split) == (8, 6, 4)
    assert t.mirror_right is True


@pytest.mark.parametrize(
    "fixture_name,rows,cols,split,mirror,thumbs",
    [
        ("beekeeb", 8, 6, 4, True, [3, 7]),
        ("borne", 10, 7, 5, False, [4, 9]),
    ],
)
def test_inference_matches_handwritten_profile(
    request, fixture_name, rows, cols, split, mirror, thumbs
):
    layout = request.getfixturevalue(fixture_name)
    t = topology.infer(layout)
    assert (t.rows, t.cols, t.split) == (rows, cols, split)
    assert t.mirror_right is mirror
    assert t.thumb_rows == thumbs


def test_mirror_detection_is_content_based(beekeeb, borne):
    """The two boards store the right hand in opposite order.

    beekeeb's right half runs P→Y (outer→inner) so it must be reversed to
    draw; borne's runs Y→P and must not be. This is the one fact that cannot
    be derived from row/column counts alone.
    """
    bk_row = beekeeb.layers[0].rows[4].keys
    bn_row = borne.layers[0].rows[6].keys
    assert bk_row.index("KC_P") < bk_row.index("KC_Y")
    assert bn_row.index("KC_Y") < bn_row.index("KC_P")

    assert topology.infer(beekeeb).mirror_right is True
    assert topology.infer(borne).mirror_right is False


def test_geometry_arrays_cover_the_letter_columns(beekeeb):
    """Stagger data must line up with the columns actually drawn.

    beekeeb has 6 matrix columns but column 0 holds no physical key, so 5 get
    rendered — a mismatch here would silently stagger the wrong finger.
    """
    t = topology.resolve(beekeeb)
    assert len(t.geometry.col_offsets) == 5
    assert len(t.geometry.thumb_rotate) == 3
    assert len(t.geometry.thumb_shift) == 3


def test_empty_layout_degrades_quietly(beekeeb):
    empty = type(beekeeb)(
        vial_protocol=6, uid=99, layers=[], tap_dance=[], combo=[], macros=[]
    )
    t = topology.resolve(empty)
    assert t.inferred
    assert t.rows == 0
