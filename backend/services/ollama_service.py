"""Shared local Ollama transport for planning and analysis.

The backend uses Ollama only over localhost and keeps model-specific prompting
outside this module. Structured requests receive one repair retry when the
model returns malformed JSON.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Optional

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:3b"
DEFAULT_TIMEOUT = 120.0


class OllamaError(RuntimeError):
    """Ollama returned an error or unusable response."""


class OllamaUnavailable(OllamaError):
    """The local Ollama server could not be reached."""


def extract_json(text: str) -> str:
    """Return the first balanced JSON object in ``text``."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()

    start = text.find("{")
    if start == -1:
        raise OllamaError(f"no JSON object found in response: {text[:200]!r}")

    depth = 0
    in_str = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_str:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_str = False
        else:
            if char == '"':
                in_str = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
    raise OllamaError("unbalanced JSON braces in response")


class OllamaClient:
    """Small synchronous client for the local Ollama chat API."""

    def __init__(
        self,
        *,
        host: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self.host = (host or os.environ.get("OLLAMA_HOST", DEFAULT_HOST)).rstrip("/")
        self.model = model or os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL)
        self.timeout = timeout or float(os.environ.get("OLLAMA_TIMEOUT", DEFAULT_TIMEOUT))
        self._available: Optional[bool] = None

    @property
    def name(self) -> str:
        return f"ollama:{self.model}"

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            request = urllib.request.Request(f"{self.host}/api/tags", method="GET")
            with urllib.request.urlopen(request, timeout=min(self.timeout, 5.0)) as response:
                self._available = response.status == 200
        except (urllib.error.URLError, OSError, ValueError):
            self._available = False
        return self._available

    def chat_text(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        num_predict: int = 1024,
    ) -> str:
        return self._chat(
            system_prompt,
            user_prompt,
            json_format=False,
            num_predict=num_predict,
        )

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        num_predict: int = 2048,
        repair_retries: int = 1,
    ) -> dict[str, Any]:
        prompt = user_prompt
        last_error: Optional[Exception] = None
        for attempt in range(repair_retries + 1):
            content = self._chat(
                system_prompt,
                prompt,
                json_format=True,
                num_predict=num_predict,
            )
            try:
                return json.loads(extract_json(content))
            except (json.JSONDecodeError, OllamaError) as exc:
                last_error = exc
                if attempt >= repair_retries:
                    break
                prompt = (
                    f"{user_prompt}\n\nYour previous response was invalid JSON: {exc}. "
                    "Return one valid JSON object only."
                )
        raise OllamaError(f"invalid JSON response after retry: {last_error}")

    def _chat(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        json_format: bool,
        num_predict: int,
    ) -> str:
        if not self.is_available():
            raise OllamaUnavailable(f"Ollama not reachable at {self.host}")

        payload: dict[str, Any] = {
            "model": self.model,
            "stream": False,
            "options": {"temperature": 0, "num_predict": num_predict},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if json_format:
            payload["format"] = "json"

        request = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            self._available = False
            raise OllamaUnavailable(f"Ollama request failed: {exc}") from exc
        except (OSError, ValueError) as exc:
            raise OllamaError(f"Ollama request failed: {exc}") from exc

        content = (body.get("message") or {}).get("content", "").strip()
        if not content:
            raise OllamaError("empty response content from Ollama")
        return content
