"""Ollama-backed LLM planner model (Phase 7).

A :class:`PlannerModel` that asks a local Ollama server (default model
``qwen2.5:3b``) to convert a user request into a JSON execution plan. Used by
``PlannerService`` as the primary planner, with the heuristic stub as fallback.

Design:
- Pure stdlib HTTP (``urllib``) -> no extra pip dependency, fully local.
- Calls Ollama ``/api/chat`` with ``format="json"`` + ``temperature=0`` for
  deterministic, parseable JSON.
- Defensive ``_extract_json`` recovers the first balanced ``{...}`` block in case
  the model wraps output in prose/markdown despite ``format=json``.
- ``is_available`` probes ``/api/tags`` so the service can fall back cleanly when
  Ollama is not running.

Everything runs locally; after a one-time ``ollama pull qwen2.5:3b`` the app is
fully offline.

Config (env):
- ``OLLAMA_HOST``    default ``http://localhost:11434``
- ``OLLAMA_MODEL``   default ``qwen2.5:3b``
- ``OLLAMA_TIMEOUT`` default ``30`` (seconds)
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Optional

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:3b"
DEFAULT_TIMEOUT = 120.0  # generous: covers cold-start model load on CPU

_SYSTEM_PROMPT = (
    "You are a strict JSON planning module. You convert the user's request into a "
    "single JSON execution plan that matches the provided schema. Output JSON ONLY "
    "with no markdown, no code fences, and no commentary."
)


class OllamaError(RuntimeError):
    """Ollama returned an error or unparseable response."""


class OllamaUnavailable(OllamaError):
    """The Ollama server could not be reached."""


def _extract_json(text: str) -> str:
    """Return the first balanced ``{...}`` block in ``text`` (defensive parse)."""
    text = (text or "").strip()
    if text.startswith("```"):
        # strip ```json ... ``` fences
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
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
    raise OllamaError("unbalanced JSON braces in response")


class OllamaPlannerModel:
    """PlannerModel that delegates planning to a local Ollama LLM."""

    def __init__(
        self,
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

    # ------------------------------------------------------------------ #
    def is_available(self) -> bool:
        """Return True if the Ollama server responds (cached after first probe)."""
        if self._available is not None:
            return self._available
        try:
            req = urllib.request.Request(f"{self.host}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=min(self.timeout, 5.0)) as resp:
                self._available = resp.status == 200
        except (urllib.error.URLError, OSError, ValueError):
            self._available = False
        return self._available

    # ------------------------------------------------------------------ #
    def generate(self, prompt: str, user_query: str, context: dict[str, Any]) -> str:
        """Return a raw JSON plan string produced by the LLM."""
        if not self.is_available():
            raise OllamaUnavailable(f"Ollama not reachable at {self.host}")

        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0, "num_predict": 512},
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.host}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            self._available = False
            raise OllamaUnavailable(f"Ollama request failed: {exc}") from exc
        except (OSError, ValueError) as exc:
            raise OllamaError(f"Ollama request failed: {exc}") from exc

        content = (body.get("message") or {}).get("content", "")
        if not content:
            raise OllamaError("empty response content from Ollama")

        # Validate it is JSON (raise to trigger fallback if not).
        raw = _extract_json(content)
        json.loads(raw)  # parse check
        return raw
