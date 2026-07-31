import json

import httpx
import pytest

from abachiwave.schemas.song_specs import SongSpecData
from abachiwave.services.text_provider import (
    InvalidProviderOutputError,
    OpenAICompatibleTextProvider,
    TextGenerationRequest,
)


def _request() -> TextGenerationRequest:
    return TextGenerationRequest(
        system_prompt="Return a SongSpec",
        user_prompt="A night ride song",
        output_model=SongSpecData,
        schema_name="song_spec_v1",
        candidate_count=1,
        params={"temperature": 0.2},
    )


@pytest.mark.asyncio
async def test_openai_compatible_provider_validates_and_repairs_fenced_json() -> None:
    content = SongSpecData(
        theme="Night ride",
        genre=["indie rock"],
        language="en",
        tempo_bpm=128,
        key="E major",
        time_signature="4/4",
        target_duration_seconds=210,
        mood_curve={"verse": "restrained", "chorus": "hopeful"},
        song_structure=["verse", "chorus"],
    ).model_dump(mode="json")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer secret"
        payload = json.loads(request.content)
        assert payload["response_format"]["type"] == "json_schema"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": f"```json\n{json.dumps(content)}\n```"}}],
                "usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 18,
                    "total_tokens": 30,
                },
            },
        )

    provider = OpenAICompatibleTextProvider(
        api_base_url="https://provider.test/v1",
        api_key="secret",
        model="test-model",
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    )
    result = await provider.generate(_request())

    assert result.candidates == [content]
    assert result.usage == {
        "input_tokens": 12,
        "output_tokens": 18,
        "total_tokens": 30,
    }


@pytest.mark.asyncio
async def test_openai_compatible_provider_rejects_unstructured_output() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Here is a nice song idea."}}]},
        )

    provider = OpenAICompatibleTextProvider(
        api_base_url="https://provider.test/v1",
        api_key="secret",
        model="test-model",
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(InvalidProviderOutputError):
        await provider.generate(_request())
