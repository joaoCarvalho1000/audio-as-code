"""Beat-domain automation evaluated on the audio sample clock."""

from __future__ import annotations

import numpy as np

from .model import Automation, Song


def _point_times(song: Song, beats: np.ndarray) -> np.ndarray:
    """Convert ordered knots in one tempo sweep, preserving integration order."""
    changes = iter(song.tempo_map)
    change = next(changes, None)
    seconds, previous, bpm = 0.0, 0.0, song.bpm
    times = []
    for beat in beats:
        while change is not None and change.beat <= beat:
            seconds += (change.beat - previous) * 60 / bpm
            previous, bpm = change.beat, change.bpm
            change = next(changes, None)
        times.append(seconds + (beat - previous) * 60 / bpm)
    return np.array(times)


def automation_values(song: Song, lane: Automation, start: int, stop: int) -> np.ndarray:
    """Absolute values, linear in beats or stepped; endpoints hold before/after the lane."""
    points = lane.points
    beats = np.array([point.beat for point in points])
    values = np.array([point.value for point in points])
    times = np.arange(start, stop, dtype=np.float64) / song.sample_rate
    if lane.interpolation == "step":
        point_times = _point_times(song, beats)
        indices = np.searchsorted(point_times, times, side="right") - 1
        return values[np.maximum(indices, 0)]
    # Add tempo boundaries as interpolation knots so a straight line in beats
    # keeps its musical slope when the number of seconds per beat changes.
    knots = np.unique(np.concatenate((beats, [change.beat for change in song.tempo_map])))
    knot_values = np.interp(knots, beats, values)
    knot_times = _point_times(song, knots)
    return np.interp(times, knot_times, knot_values)
