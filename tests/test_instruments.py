import json
from dataclasses import FrozenInstanceError, replace
from typing import get_args

import pytest
from pydantic import ValidationError

from audio_as_code import (
    Note,
    Song,
    Tone,
    Track,
    get_instrument,
    instrument_catalog,
    list_instruments,
    render_audio,
)
from audio_as_code.cli import main
from audio_as_code.instruments import ENGINES, FAMILIES, INSTRUMENTS, Instrument


def test_catalog_contract_and_score_schema_stay_in_sync():
    available = {item.id for item in list_instruments()}
    assert available == set(get_args(Instrument))
    assert available == set(
        Song.model_json_schema()["$defs"]["Track"]["properties"]["instrument"]["enum"]
    )
    assert len({item.id for item in INSTRUMENTS}) == len(INSTRUMENTS)
    assert len(FAMILIES) == 8 and len(ENGINES) == 5
    families = {item.id for item in FAMILIES}
    engines = {item.id for item in ENGINES}
    assert {item.family for item in INSTRUMENTS} == families
    assert {item.engine for item in INSTRUMENTS} == engines
    assert all(item.tone_controls or item.default_decay_seconds is None for item in INSTRUMENTS)
    for item in list_instruments():
        assert (item.midi_note is None) != (item.midi_program is None)
        assert item.engine in {engine.id for engine in ENGINES if engine.status == "available"}


@pytest.mark.parametrize("instrument", [item.id for item in list_instruments()])
def test_every_advertised_voice_actually_renders(instrument):
    info = get_instrument(instrument)
    song = Song(
        beats=1,
        sample_rate=22050,
        tracks=[
            Track(
                name="Catalog voice",
                instrument=instrument,
                notes=[Note(pitch="C4")],
                tone=Tone() if info.tone_controls else None,
            ),
        ],
    )
    result = render_audio(song)
    assert not result.report["audio"]["silent"]
    assert result.report["audio"]["clipped_samples"] == 0


@pytest.mark.parametrize("instrument", ["piano", "violin", "flute", "timpani", "bass_guitar"])
def test_planned_entries_are_discoverable_but_never_accepted_as_playable(instrument, monkeypatch):
    import audio_as_code.instruments as catalog

    planned = replace(get_instrument(instrument), status="planned")
    monkeypatch.setattr(catalog, "_BY_ID", {**catalog._BY_ID, instrument: planned})
    monkeypatch.setattr(
        catalog,
        "INSTRUMENTS",
        tuple(planned if item.id == instrument else item for item in INSTRUMENTS),
    )
    assert get_instrument(instrument).status == "planned"
    assert instrument not in {item.id for item in list_instruments()}
    with pytest.raises(ValidationError, match="planned and cannot be rendered yet") as error:
        Track(name="Future voice", instrument=instrument)
    assert error.value.errors()[0]["loc"] == ("instrument",)


def test_filters_and_meaningful_errors():
    assert {item.id for item in list_instruments(family="plucked_strings")} == {
        "guitar",
        "electric_guitar",
        "bass_guitar",
        "harp",
        "ukulele",
        "banjo",
        "mandolin",
    }
    assert {
        item.id
        for item in list_instruments(family="keyboards", engine="string", include_planned=True)
    } == {"piano", "harpsichord"}
    assert {item.id for item in list_instruments(family="woodwinds")} == {
        "flute",
        "clarinet",
        "saxophone",
        "oboe",
        "bassoon",
        "recorder",
    }
    assert {item.id for item in list_instruments(engine="modal")} == {
        "electric_piano",
        "cymbal",
        "tambourine",
        "marimba",
        "xylophone",
        "vibraphone",
        "glockenspiel",
        "bell",
        "kalimba",
        "celesta",
    }
    with pytest.raises(ValueError, match="unknown instrument family"):
        list_instruments(family="strings_typo")
    with pytest.raises(ValueError, match="unknown synthesis engine"):
        list_instruments(engine="sampler")
    with pytest.raises(ValueError, match="unknown instrument"):
        get_instrument("pinao")


def test_basic_drums_are_not_misrepresented_as_membrane_models():
    for name in ["kick", "snare", "hat"]:
        assert get_instrument(name).engine == "electronic"
    assert {item.id for item in list_instruments(engine="membrane")} == {
        "toms",
        "congas",
        "bongos",
        "timpani",
    }
    assert get_instrument("bass").family == "electronic"
    assert get_instrument("bass_guitar").family == "plucked_strings"


def test_catalog_metadata_cannot_be_mutated_accidentally():
    with pytest.raises(FrozenInstanceError):
        get_instrument("guitar").status = "planned"
    data = instrument_catalog()
    data["instruments"][0]["status"] = "planned"
    assert get_instrument("guitar").status == "available"


def test_cli_discovery_and_unknown_score_errors(tmp_path, capsys):
    assert main(["instruments"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["synthesis_policy"] == "code_only"
    assert result["counts"] == {"available": 49, "planned": 0}
    assert main(["instruments", "--all", "--family", "bowed_strings"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["counts"] == {"available": 4, "planned": 0}
    assert main(["instruments", "--engine", "missing"]) == 2
    assert json.loads(capsys.readouterr().err)["error"] == "operation_failed"
    score = tmp_path / "piano.json"
    score.write_text('{"tracks": [{"name": "Piano", "instrument": "pinao"}]}')
    assert main(["validate", str(score)]) == 2
    error = json.loads(capsys.readouterr().err)
    assert error["issues"][0]["path"] == ["tracks", 0, "instrument"]
    assert "unknown instrument" in error["issues"][0]["message"]
