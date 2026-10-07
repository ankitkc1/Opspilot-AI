import json
from typing import Any, cast

import httpx
import pytest

from app.services.ollama import OllamaClient, OllamaMessage, OllamaServiceError


def test_list_models_returns_sorted_unique_names() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "models": [
                    {"name": "qwen3:4b"},
                    {"name": "all-minilm:latest"},
                    {"name": "qwen3:4b"},
                    {"missing": "name"},
                ]
            },
        )

    client = OllamaClient(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    )

    assert client.list_models() == ["all-minilm:latest", "qwen3:4b"]


def test_chat_disables_thinking_and_streaming() -> None:
    captured_payload: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        payload = cast(dict[str, Any], json.loads(request.content))
        captured_payload.update(payload)
        return httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": '{"ok":true}'}},
        )

    client = OllamaClient(
        base_url="http://ollama.test",
        model="qwen3:4b",
        transport=httpx.MockTransport(handler),
    )
    messages: list[OllamaMessage] = [
        {"role": "user", "content": "Return JSON."},
    ]

    content = client.chat(
        messages=messages,
        response_format={
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
        },
    )

    assert content == '{"ok":true}'
    assert captured_payload["model"] == "qwen3:4b"
    assert captured_payload["messages"] == messages
    assert captured_payload["stream"] is False
    assert captured_payload["think"] is False
    assert captured_payload["options"] == {"temperature": 0}
    assert captured_payload["format"]["type"] == "object"


def test_connection_error_is_wrapped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    client = OllamaClient(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(OllamaServiceError, match="Ollama request failed"):
        client.list_models()


def test_timeout_is_wrapped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client = OllamaClient(
        base_url="http://ollama.test",
        timeout_seconds=1,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(OllamaServiceError, match="Ollama request failed"):
        client.list_models()


def test_invalid_chat_response_is_rejected() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": None}})

    client = OllamaClient(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(OllamaServiceError, match="invalid chat response"):
        client.chat(messages=[{"role": "user", "content": "Hello"}])
