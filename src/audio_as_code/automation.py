"""Beat-domain automation evaluated on the audio sample clock."""

from __future__ import annotations

import numpy as np

from .model import Automation, Song


def automation_values(song: Song, lane: Automation, start: int, stop: int) -> np.ndarray:
    """Absolute values, linear in beats or stepped; endpoints hold before/after the lane."""
    points = lane.points
    beats = np.array([point.beat for point in points])
    values = np.array([point.value for point in points])
    times = np.arange(start, stop, dtype=np.float64) / song.sample_rate
    if lane.interpolation == "step":
        point_times = np.array([song.beat_to_seconds(beat) for beat in beats])
        indices = np.searchsorted(point_times, times, side="right") - 1
        return values[np.maximum(indices, 0)]
    # Add tempo boundaries as interpolation knots so a straight line in beats
    # keeps its musical slope when the number of seconds per beat changes.
    knots = np.unique(np.concatenate((beats, [change.beat for change in song.tempo_map])))
    knot_values = np.interp(knots, beats, values)
    knot_times = [song.beat_to_seconds(beat) for beat in knots]
    return np.interp(times, knot_times, knot_values)
