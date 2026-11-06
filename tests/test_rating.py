"""The slider's ticks and the marker's snap stops must line up."""

import pytest

from heat_task import config
from heat_task.task.display import rating_to_x
from heat_task.task.rating import snap_rating


def test_ticks_span_the_track():
    assert rating_to_x(config.RATING_MIN) == pytest.approx(-config.SLIDER_HALF_W)
    assert rating_to_x(config.RATING_MAX) == pytest.approx(config.SLIDER_HALF_W)


@pytest.mark.parametrize("value", range(config.RATING_MIN, config.RATING_MAX + 1))
def test_marker_snaps_onto_each_tick(value):
    tick_x = rating_to_x(value)
    assert snap_rating(tick_x + 0.01) == (value, tick_x)
