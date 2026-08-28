from io import BytesIO

import httpx
import pytest
from mido import Message, MetaMessage, MidiFile, MidiTrack

from abachiwave.core.config import Settings
from abachiwave.schemas.song_specs import SongSpecData
from abachiwave.services.audio_to_midi_provider import (
    AudioToMidiProviderError,
    AudioToMidiProviderResponseError,
    AudioToMidiProviderTimeoutError,
    AudioToMidiProviderUnavailableError,
    AudioToMidiRequest,
    BasicPitchHttpAudioToMidiProvider,
    LocalMonophonicWavToMidiProvider,
    UnknownAudioToMidiProviderError,
    YourMT3VocalPipelineProvider,
    basic_pitch_default_params,
    build_audio_to_midi_provider,
    resolve_audio_to_midi_provider_name,
    resolve_basic_pitch_params,
    resolve_yourmt3_params,
    yourmt3_default_params,
)
from abachiwave.services.midi_document import parse_midi_document


def test_basic_pitch_http_provider_sends_versioned_thresholds_and_returns_midi() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url == "http://basic-pitch.test/v1/transcriptions"
        assert b'name="onset_threshold"' in request.content
        assert b"0.61" in request.content
        assert b'name="midi_tempo"' in request.content
        assert b"132" in request.content
        assert b"fixture.wav" in request.content
        return httpx.Response(
            200,
            content=_midi_bytes(),
            headers={
                "X-Basic-Pitch-Version": "0.4.0",
                "X-Note-Count": "1",
                "X-Model-Runtime": "tflite",
            },
        )

    provider = BasicPitchHttpAudioToMidiProvider(
        "http://basic-pitch.test/",
        timeout_seconds=12,
        transport=httpx.MockTransport(handler),
    )
    generated = provider.extract_midi(
        AudioToMidiRequest(
            audio_bytes=b"RIFF fixture WAVE",
            filename="fixture.wav",
            song_spec=_song_spec(),
            provider_params={"onset_threshold": 0.61},
        )
    )

    assert len(requests) == 1
    assert generated.data.startswith(b"MThd")
    assert generated.provider_name == "spotify_basic_pitch"
    assert generated.provider_version == "0.4.0"
    assert generated.provider_params["onset_threshold"] == 0.61
    assert generated.provider_usage == {"note_count": 1, "service_runtime": "tflite"}
    document = parse_midi_document(generated.data)
    assert [(note.pitch, note.velocity) for note in document.note_events] == [(69, 90)]


def test_basic_pitch_http_provider_rejects_service_version_drift_and_invalid_midi() -> None:
    def wrong_version(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_midi_bytes(),
            headers={"X-Basic-Pitch-Version": "0.5.0"},
        )

    provider = BasicPitchHttpAudioToMidiProvider(
        "http://basic-pitch.test",
        timeout_seconds=12,
        transport=httpx.MockTransport(wrong_version),
    )
    with pytest.raises(AudioToMidiProviderResponseError, match="version does not match"):
        provider.extract_midi(_request())

    def invalid_midi(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"not midi",
            headers={"X-Basic-Pitch-Version": "0.4.0"},
        )

    provider = BasicPitchHttpAudioToMidiProvider(
        "http://basic-pitch.test",
        timeout_seconds=12,
        transport=httpx.MockTransport(invalid_midi),
    )
    with pytest.raises(AudioToMidiProviderResponseError, match="invalid MIDI"):
        provider.extract_midi(_request())


def test_basic_pitch_parameters_are_canonical_and_reject_unknown_values() -> None:
    defaults = basic_pitch_default_params()
    resolved = resolve_basic_pitch_params(
        {
            "onset_threshold": 0.42,
            "minimum_frequency_hz": 50,
            "maximum_frequency_hz": 900,
            "melodia_trick": False,
        }
    )

    assert resolved == {
        **defaults,
        "onset_threshold": 0.42,
        "minimum_frequency_hz": 50.0,
        "maximum_frequency_hz": 900.0,
        "melodia_trick": False,
    }
    with pytest.raises(ValueError, match="unknown Basic Pitch provider parameters"):
        resolve_basic_pitch_params({"ignored_threshold": 0.5})
    with pytest.raises(ValueError, match="minimum_frequency_hz must be below"):
        resolve_basic_pitch_params(
            {"minimum_frequency_hz": 900, "maximum_frequency_hz": 900}
        )
    with pytest.raises(ValueError, match="melodia_trick must be a boolean"):
        resolve_basic_pitch_params({"melodia_trick": "false"})


@pytest.mark.parametrize(
    ("raised_error", "expected_error", "message"),
    [
        (
            httpx.ReadTimeout("fixture timeout"),
            AudioToMidiProviderTimeoutError,
            "timed out",
        ),
        (
            httpx.ConnectError("fixture disconnect"),
            AudioToMidiProviderUnavailableError,
            "unavailable",
        ),
    ],
)
def test_basic_pitch_http_provider_classifies_transport_failures(
    raised_error: httpx.RequestError,
    expected_error: type[AudioToMidiProviderError],
    message: str,
) -> None:
    def fail_transport(_request: httpx.Request) -> httpx.Response:
        raise raised_error

    provider = BasicPitchHttpAudioToMidiProvider(
        "http://basic-pitch.test",
        timeout_seconds=0.01,
        transport=httpx.MockTransport(fail_transport),
    )

    with pytest.raises(expected_error, match=message):
        provider.extract_midi(_request())


def test_audio_to_midi_provider_factory_keeps_local_fallback_and_rejects_unknown() -> None:
    settings = Settings(AUDIO_TO_MIDI_PROVIDER_NAME="local_monophonic_wav_to_midi")
    assert isinstance(build_audio_to_midi_provider(settings), LocalMonophonicWavToMidiProvider)
    assert isinstance(
        build_audio_to_midi_provider(settings, provider_name="spotify_basic_pitch"),
        BasicPitchHttpAudioToMidiProvider,
    )
    with pytest.raises(UnknownAudioToMidiProviderError):
        build_audio_to_midi_provider(settings, provider_name="missing")


def _request() -> AudioToMidiRequest:
    return AudioToMidiRequest(
        audio_bytes=b"RIFF fixture WAVE",
        filename="fixture.wav",
        song_spec=_song_spec(),
        provider_params={},
    )


def _song_spec() -> SongSpecData:
    return SongSpecData(
        title="Provider fixture",
        language="English",
        genre=["Pop"],
        mood="bright",
        theme="testing",
        story_arc="start to finish",
        narrative_perspective="first person",
        target_duration_seconds=180,
        tempo_bpm=132,
        key="C major",
        time_signature="4/4",
        energy_curve="steady",
        vocal_style="clear",
        instrumentation=["piano"],
        song_structure=["verse", "chorus"],
        structure_sections=[],
        constraints=[],
    )


def _midi_bytes() -> bytes:
    midi = MidiFile(type=1, ticks_per_beat=480)
    meta = MidiTrack()
    meta.append(MetaMessage("set_tempo", tempo=500_000, time=0))
    midi.tracks.append(meta)
    track = MidiTrack()
    track.append(Message("note_on", note=69, velocity=90, time=0))
    track.append(Message("note_off", note=69, velocity=0, time=480))
    midi.tracks.append(track)
    buffer = BytesIO()
    midi.save(file=buffer)
    return buffer.getvalue()


def test_yourmt3_provider_sends_pipeline_params_and_returns_midi() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url == "http://yourmt3.test/v1/transcriptions"
        assert b'name="duration_scale"' in request.content
        assert b"0.9" in request.content
        assert b'name="use_pyin_pitch"' in request.content
        assert b"true" in request.content
        return httpx.Response(
            200,
            content=_midi_bytes(),
            headers={
                "X-MT3-Infer-Version": "0.2.0",
                "X-Note-Count": "1",
                "X-Model-Runtime": "cpu",
            },
        )

    provider = YourMT3VocalPipelineProvider(
        "http://yourmt3.test/",
        timeout_seconds=30,
        transport=httpx.MockTransport(handler),
    )
    generated = provider.extract_midi(
        AudioToMidiRequest(
            audio_bytes=b"RIFF fixture WAVE",
            filename="hum.wav",
            song_spec=_song_spec(),
            provider_params={"duration_scale": 0.9},
        )
    )

    assert len(requests) == 1
    assert generated.provider_name == "yourmt3_vocal_pipeline"
    assert generated.provider_params == {"duration_scale": 0.9, "use_pyin_pitch": True}
    assert generated.provider_usage["note_count"] == 1
    assert generated.filename == "hum-yourmt3-melody.mid"
    assert generated.data.startswith(b"MThd")


def test_yourmt3_provider_rejects_a_version_mismatch() -> None:
    def wrong_version(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=_midi_bytes(), headers={"X-MT3-Infer-Version": "0.1.0"}
        )

    provider = YourMT3VocalPipelineProvider(
        "http://yourmt3.test",
        timeout_seconds=5,
        transport=httpx.MockTransport(wrong_version),
    )

    with pytest.raises(AudioToMidiProviderResponseError):
        provider.extract_midi(
            AudioToMidiRequest(
                audio_bytes=b"RIFF fixture WAVE",
                filename="hum.wav",
                song_spec=_song_spec(),
                provider_params={},
            )
        )


def test_yourmt3_default_params_carry_the_selected_duration_scale() -> None:
    assert yourmt3_default_params() == {"duration_scale": 0.85, "use_pyin_pitch": True}
    assert resolve_yourmt3_params({"duration_scale": 0.7})["duration_scale"] == 0.7
    with pytest.raises(ValueError, match="unknown YourMT3 provider parameters"):
        resolve_yourmt3_params({"onset_threshold": 0.6})


def test_provider_routing_only_redirects_humming_uploads() -> None:
    routed = Settings(
        AUDIO_TO_MIDI_PROVIDER_NAME="spotify_basic_pitch",
        HUMMING_AUDIO_TO_MIDI_PROVIDER_NAME="yourmt3_vocal_pipeline",
        TASK_TIMEOUT_SECONDS=900,
    )

    assert resolve_audio_to_midi_provider_name("humming", routed) == "yourmt3_vocal_pipeline"
    for kind in ("reference", "scratch", "other"):
        assert resolve_audio_to_midi_provider_name(kind, routed) == "spotify_basic_pitch"


def test_provider_routing_is_inert_until_configured() -> None:
    unrouted = Settings(AUDIO_TO_MIDI_PROVIDER_NAME="spotify_basic_pitch")

    for kind in ("humming", "reference", "scratch", "other"):
        assert resolve_audio_to_midi_provider_name(kind, unrouted) == "spotify_basic_pitch"


def test_build_audio_to_midi_provider_returns_the_vocal_pipeline() -> None:
    provider = build_audio_to_midi_provider(
        Settings(YOURMT3_SERVICE_URL="http://yourmt3.test"),
        provider_name="yourmt3_vocal_pipeline",
    )

    assert isinstance(provider, YourMT3VocalPipelineProvider)
    assert provider.name == "yourmt3_vocal_pipeline"
