from __future__ import annotations

import json
import unittest
import urllib.error
from unittest.mock import patch

from backend.services.ollama_service import OllamaClient, OllamaUnavailable


class _Response:
    def __init__(self, body: dict | None = None, status: int = 200) -> None:
        self._body = body or {}
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self) -> bytes:
        return json.dumps(self._body).encode("utf-8")


class OllamaClientTests(unittest.TestCase):
    def test_json_request_returns_object(self) -> None:
        responses = [
            _Response(status=200),
            _Response({"message": {"content": '{"answer": 42}'}}),
        ]
        with patch("urllib.request.urlopen", side_effect=responses):
            result = OllamaClient().chat_json("system", "user")
        self.assertEqual(result, {"answer": 42})

    def test_json_request_repairs_malformed_response_once(self) -> None:
        responses = [
            _Response(status=200),
            _Response({"message": {"content": "not json"}}),
            _Response({"message": {"content": '{"fixed": true}'}}),
        ]
        with patch("urllib.request.urlopen", side_effect=responses) as request:
            result = OllamaClient().chat_json("system", "user", repair_retries=1)
        self.assertEqual(result, {"fixed": True})
        self.assertEqual(request.call_count, 3)

    def test_unavailable_server_fails_before_chat(self) -> None:
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("offline"),
        ):
            with self.assertRaises(OllamaUnavailable):
                OllamaClient().chat_text("system", "user")


if __name__ == "__main__":
    unittest.main()
