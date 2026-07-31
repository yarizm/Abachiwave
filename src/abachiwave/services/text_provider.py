import json
from dataclasses import dataclass
from typing import Protocol

import httpx
from pydantic import BaseModel, ValidationError


class TextProviderError(RuntimeError):
    code = "text_provider_error"


class TextProviderUnavailableError(TextProviderError):
    code = "provider_unavailable"


class TextProviderTimeoutError(TextProviderError):
    code = "provider_timeout"


class InvalidProviderOutputError(TextProviderError):
    code = "invalid_provider_output"


@dataclass(frozen=True)
class TextGenerationRequest:
    system_prompt: str
    user_prompt: str
    output_model: type[BaseModel]
    schema_name: str
    candidate_count: int
    params: dict[str, object]


@dataclass(frozen=True)
class TextGenerationResult:
    candidates: list[dict[str, object]]
    usage: dict[str, object]


class TextGenerationProvider(Protocol):
    name: str
    version: str

    async def generate(self, request: TextGenerationRequest) -> TextGenerationResult: ...


class LocalDeterministicTextProvider:
    name = "local_deterministic"
    version = "1"

    def __init__(self, fallback_candidates: list[BaseModel]) -> None:
        self._fallback_candidates = fallback_candidates

    async def generate(self, request: TextGenerationRequest) -> TextGenerationResult:
        if not self._fallback_candidates:
            raise InvalidProviderOutputError("No deterministic candidate was prepared")
        candidates = [
            request.output_model.model_validate(
                self._fallback_candidates[index % len(self._fallback_candidates)].model_dump()
            ).model_dump(mode="json")
            for index in range(request.candidate_count)
        ]
        return TextGenerationResult(
            candidates=candidates,
            usage={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        )


class OpenAICompatibleTextProvider:
    name = "openai_compatible"
    version = "chat-completions-v1"

    def __init__(
        self,
        *,
        api_base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_base_url = api_base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    async def generate(self, request: TextGenerationRequest) -> TextGenerationResult:
        candidates: list[dict[str, object]] = []
        usage: dict[str, object] = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }
        for _index in range(request.candidate_count):
            response_data = await self._request_candidate(request)
            choices = response_data.get("choices")
            if not isinstance(choices, list) or not choices:
                raise InvalidProviderOutputError("Provider response did not contain choices")
            choice = choices[0]
            if not isinstance(choice, dict):
                raise InvalidProviderOutputError("Provider choice was not an object")
            message = choice.get("message")
            if not isinstance(message, dict) or not isinstance(message.get("content"), str):
                raise InvalidProviderOutputError("Provider response did not contain text content")
            candidates.append(
                _validate_structured_content(message["content"], request.output_model)
            )
            _merge_usage(usage, response_data.get("usage"))
        return TextGenerationResult(candidates=candidates, usage=usage)

    async def _request_candidate(self, request: TextGenerationRequest) -> dict[str, object]:
        temperature = request.params.get("temperature", 0.7)
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "temperature": temperature,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": request.schema_name,
                    "strict": True,
                    "schema": request.output_model.model_json_schema(),
                },
            },
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    f"{self._api_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
        except httpx.TimeoutException as error:
            raise TextProviderTimeoutError("Text provider request timed out") from error
        except httpx.HTTPError as error:
            raise TextProviderUnavailableError("Text provider request failed") from error
        try:
            data = response.json()
        except ValueError as error:
            raise InvalidProviderOutputError("Provider returned invalid JSON") from error
        if not isinstance(data, dict):
            raise InvalidProviderOutputError("Provider response was not an object")
        return data


def _validate_structured_content(content: str, model: type[BaseModel]) -> dict[str, object]:
    try:
        return model.model_validate_json(content).model_dump(mode="json")
    except ValidationError as first_error:
        repaired = _extract_json_object(content)
        if repaired is None:
            raise InvalidProviderOutputError(
                "Provider output did not match the schema"
            ) from first_error
        try:
            return model.model_validate_json(repaired).model_dump(mode="json")
        except ValidationError as second_error:
            raise InvalidProviderOutputError(
                "Provider output did not match the schema after one repair attempt"
            ) from second_error


def _extract_json_object(content: str) -> str | None:
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            stripped = "\n".join(lines[1:-1]).strip()
            if stripped.lower().startswith("json"):
                stripped = stripped[4:].lstrip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end <= start:
        return None
    candidate = stripped[start : end + 1]
    try:
        decoded = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return candidate if isinstance(decoded, dict) else None


def _merge_usage(total: dict[str, object], raw_usage: object) -> None:
    if not isinstance(raw_usage, dict):
        return
    aliases = {
        "input_tokens": ("input_tokens", "prompt_tokens"),
        "output_tokens": ("output_tokens", "completion_tokens"),
        "total_tokens": ("total_tokens",),
    }
    for target, source_names in aliases.items():
        value = next((raw_usage[name] for name in source_names if name in raw_usage), 0)
        if isinstance(value, int):
            current = total[target]
            total[target] = (current if isinstance(current, int) else 0) + value
