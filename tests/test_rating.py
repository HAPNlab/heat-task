"""The slider's ticks and the marker's snap stops must line up."""

import pytest

from heat_task import config
from heat_task.task.rating_scale import move_along_track, rating_to_x, snap_rating


def test_ticks_span_the_track():
    assert rating_to_x(config.RATING_MIN) == pytest.approx(-config.SLIDER_HALF_W)
    assert rating_to_x(config.RATING_MAX) == pytest.approx(config.SLIDER_HALF_W)


@pytest.mark.parametrize("value", range(config.RATING_MIN, config.RATING_MAX + 1))
def test_marker_snaps_onto_each_tick(value):
    tick_x = rating_to_x(value)
    assert snap_rating(tick_x + 0.01) == (value, tick_x)


def test_track_stops_at_both_ends():
    assert move_along_track(0.0, 5.0) == config.SLIDER_HALF_W
    assert move_along_track(0.0, -5.0) == -config.SLIDER_HALF_W


def test_reversing_after_overshoot_moves_at_once():
    x = move_along_track(config.SLIDER_HALF_W, 1.0)  # push well past the end
    assert move_along_track(x, -0.1) == pytest.approx(config.SLIDER_HALF_W - 0.1)
