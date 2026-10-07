from collections.abc import Sequence
from typing import Any, Literal, TypedDict, cast

import httpx

from app.core.config import settings


class OllamaMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


class OllamaServiceError(RuntimeError):
    """Raised when Ollama cannot provide a valid response."""


class OllamaClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        configured_base_url = base_url or str(settings.OLLAMA_BASE_URL)
        self.base_url = configured_base_url.rstrip("/")
        self.model = model if model is not None else settings.OLLAMA_MODEL
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.OLLAMA_TIMEOUT_SECONDS
        )
        self._transport = transport

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        timeout = httpx.Timeout(
            self.timeout_seconds,
            connect=min(5.0, self.timeout_seconds),
        )

        try:
            with httpx.Client(
                base_url=self.base_url,
                timeout=timeout,
                transport=self._transport,
            ) as client:
                response = client.request(method, path, json=json)
                response.raise_for_status()
                raw_payload: object = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise OllamaServiceError("Ollama request failed") from error

        if not isinstance(raw_payload, dict):
            raise OllamaServiceError("Ollama returned an invalid response")
        return cast(dict[str, Any], raw_payload)

    def list_models(self) -> list[str]:
        payload = self._request("GET", "/api/tags")
        raw_models = payload.get("models")
        if not isinstance(raw_models, list):
            raise OllamaServiceError("Ollama returned an invalid model list")

        model_names: list[str] = []
        for raw_model in raw_models:
            if not isinstance(raw_model, dict):
                continue
            name = raw_model.get("name")
            if isinstance(name, str) and name:
                model_names.append(name)

        return sorted(set(model_names))

    def chat(
        self,
        *,
        messages: Sequence[OllamaMessage],
        response_format: str | dict[str, Any] | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [dict(message) for message in messages],
            "stream": False,
            "think": False,
            "options": {"temperature": 0},
        }
        if response_format is not None:
            payload["format"] = response_format

        response = self._request("POST", "/api/chat", json=payload)
        message = response.get("message")
        if not isinstance(message, dict):
            raise OllamaServiceError("Ollama returned an invalid chat response")

        content = message.get("content")
        if not isinstance(content, str):
            raise OllamaServiceError("Ollama returned an invalid chat response")
        return content
