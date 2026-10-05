"""Validated mix revisions over the existing score controls; no additional mix state."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated

from pydantic import Field, StrictBool, model_validator

from .model import Number, ScoreModel, Song


class MixEdit(ScoreModel):
    """One exact-name group or master edit, applied in batch order.

    ``trim_db`` scales gain and its automation together. Absolute ``gain``/``pan``
    require explicit ``replace_automation`` to remove an existing matching lane.
    """

    tracks: tuple[Annotated[str, Field(strict=True, min_length=1)], ...] = ()
    master: StrictBool = False
    gain: Annotated[Number, Field(ge=0, le=1)] | None = None
    trim_db: Number | None = None
    pan: Annotated[Number, Field(ge=-1, le=1)] | None = None
    replace_automation: StrictBool = False

    @model_validator(mode="after")
    def validate_edit(self) -> MixEdit:
        if bool(self.tracks) == self.master:
            raise ValueError("select nonempty tracks or master=True, exclusively")
        if len(set(self.tracks)) != len(self.tracks):
            raise ValueError("track selection contains duplicate names")
        if self.gain is not None and self.trim_db is not None:
            raise ValueError("gain is absolute; choose gain or relative trim_db, not both")
        if self.gain is None and self.trim_db is None and self.pan is None:
            raise ValueError("an edit requires gain, trim_db or pan")
        if self.master and self.pan is not None:
            raise ValueError("master has no pan control")
        if self.replace_automation and self.gain is None and self.pan is None:
            raise ValueError("replace_automation applies only to absolute gain or pan")
        return self


@dataclass(frozen=True)
class MixResult:
    """Revalidated score and a JSON-compatible report of score settings, not audio."""

    song: Song
    report: dict


def _validated(song: Song) -> Song:
    if not isinstance(song, Song):
        raise ValueError("song must be a Song")
    return Song.model_validate(song.model_dump())


def _selection(song: Song, names: Sequence[str], label: str) -> tuple[str, ...]:
    if isinstance(names, (str, bytes)) or not isinstance(names, Sequence):
        raise ValueError(f"{label} must be a sequence of exact track names")
    names = tuple(names)
    if any(not isinstance(name, str) for name in names):
        raise ValueError(f"{label} must contain exact track names")
    if len(set(names)) != len(names):
        raise ValueError(f"{label} contains duplicate track names")
    known = {track.name for track in song.tracks}
    unknown = [name for name in names if name not in known]
    if unknown:
        raise ValueError(
            f"unknown track names in {label}: {unknown!r}; available: {sorted(known)!r}"
        )
    return names


def _settings(owner: dict, gain_key: str) -> dict:
    gain = owner[gain_key]
    return {
        "gain": gain,
        "gain_db": 20 * math.log10(gain) if gain > 0 else None,
        "gain_source": "automation"
        if any(lane["parameter"] == gain_key for lane in owner["automation"])
        else "static",
        **(
            {
                "pan": owner["pan"],
                "pan_source": "automation"
                if any(lane["parameter"] == "pan" for lane in owner["automation"])
                else "static",
            }
            if "pan" in owner
            else {}
        ),
        "automation": [
            {**lane, "points": [dict(point) for point in lane["points"]]}
            for lane in owner["automation"]
        ],
    }


def inspect_mix(song: Song) -> dict:
    """Return score settings only. Null gain_db means zero, never negative infinity."""
    data = _validated(song).model_dump(mode="json")
    return {
        "kind": "score_mix_settings",
        "master": _settings(data, "master_gain"),
        "tracks": [
            {"name": track["name"], "instrument": track["instrument"], **_settings(track, "gain")}
            for track in data["tracks"]
        ],
    }


def _edit_owner(owner: dict, edit: MixEdit, gain_key: str, label: str) -> None:
    if edit.trim_db is not None:
        try:
            factor = 10 ** (edit.trim_db / 20)
        except OverflowError:
            factor = math.inf

        def scale(value: float) -> float:
            # Zero remains zero, including when a very large boost was requested.
            if value == 0:
                return 0.0
            value_after = value * factor
            if not math.isfinite(value_after) or value_after > 1:
                raise ValueError(
                    f"{label}: trim_db={edit.trim_db} would exceed gain 1; "
                    "lower the requested boost or attenuate other tracks instead"
                )
            if value_after == 0:
                raise ValueError(f"{label}: trim_db underflows gain; use gain=0 to silence")
            return value_after

        owner[gain_key] = scale(owner[gain_key])
        for lane in owner["automation"]:
            if lane["parameter"] == gain_key:
                for point in lane["points"]:
                    point["value"] = scale(point["value"])
    for key, value in ((gain_key, edit.gain), ("pan", edit.pan)):
        if value is None:
            continue
        matching = any(lane["parameter"] == key for lane in owner["automation"])
        if matching and not edit.replace_automation:
            raise ValueError(
                f"{label}: {key} has automation; use trim_db to preserve a gain envelope "
                "or replace_automation=True to replace the matching lane explicitly"
            )
        owner[key] = value
        owner["automation"] = [lane for lane in owner["automation"] if lane["parameter"] != key]


def apply_mix(song: Song, edits: Sequence[MixEdit]) -> MixResult:
    """Apply an ordered, all-or-nothing batch and report every target's before/after.

    Exact, case-sensitive track names are the score's identity. Groups are explicit
    name lists; no substring, instrument-ID, or fuzzy matching is performed.
    """
    song = _validated(song)
    if not isinstance(edits, Sequence) or isinstance(edits, (str, bytes)):
        raise ValueError("edits must be a sequence of MixEdit instances")
    data = song.model_dump(mode="json")
    changes = []
    for index, edit in enumerate(edits):
        if not isinstance(edit, MixEdit):
            raise ValueError("edits must contain MixEdit instances")
        edit = MixEdit.model_validate(edit.model_dump())
        names = _selection(song, edit.tracks, "tracks")
        owners = [data] if edit.master else [t for t in data["tracks"] if t["name"] in names]
        gain_key = "master_gain" if edit.master else "gain"
        for owner in owners:
            label = "master" if edit.master else owner["name"]
            before = _settings(owner, gain_key)
            _edit_owner(owner, edit, gain_key, label)
            after = _settings(owner, gain_key)
            changes.append(
                {
                    "edit_index": index,
                    "scope": "master" if edit.master else "track",
                    "name": label,
                    "before": before,
                    "after": after,
                }
            )
    result = Song.model_validate(data)
    return MixResult(
        song=result,
        report={
            "kind": "score_mix_edit",
            "edits": [edit.model_dump(mode="json", exclude_none=True) for edit in edits],
            "changes": changes,
            "before": inspect_mix(song),
            "after": inspect_mix(result),
        },
    )


def audition_song(song: Song, *, solo: Sequence[str] = (), mute: Sequence[str] = ()) -> Song:
    """Return a disposable score with excluded tracks silenced; mute wins over solo.

    An empty solo selection includes all tracks. Keep the source score to restore
    levels: no mute/solo state is added to score JSON. Gain points are zeroed in
    place, preserving timing, lane shape metadata, track order and note seeds.
    """
    song = _validated(song)
    solo = _selection(song, solo, "solo")
    mute = _selection(song, mute, "mute")
    data = song.model_dump(mode="json")
    for track in data["tracks"]:
        if track["name"] in mute or (solo and track["name"] not in solo):
            track["gain"] = 0.0
            for lane in track["automation"]:
                if lane["parameter"] == "gain":
                    for point in lane["points"]:
                        point["value"] = 0.0
    return Song.model_validate(data)
