import json
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from freebuff2api.app import app
from freebuff2api.app import _error_response, _finalize_run_with_client
from freebuff2api.codebuff import CodebuffAccountPool, CodebuffError, FreebuffRun
from freebuff2api.config import Settings


class FinalizeFailingClient:
    def __init__(self) -> None:
        self.settings = Settings(
            codebuff_token="token",
            local_api_key=None,
            debug=False,
        )

    async def record_run_step(self, *args, **kwargs) -> None:
        raise CodebuffError("network error", 502)

    async def finish_run(self, *args, **kwargs) -> None:
        raise AssertionError("finish_run should not be called")


class AppErrorTests(unittest.TestCase):
    def test_v1_models_requires_configured_api_key(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with TestClient(app) as client:
                response = client.get("/v1/models")

        self.assertEqual(response.status_code, 503)
        self.assertIn("FREEBUFF_API_KEY", response.json()["detail"])

    def test_v1_models_accepts_configured_api_key(self) -> None:
        with patch.dict("os.environ", {"FREEBUFF_API_KEY": "local-key"}, clear=True):
            with TestClient(app) as client:
                response = client.get(
                    "/v1/models",
                    headers={"Authorization": "Bearer local-key"},
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["object"], "list")

    def test_codebuff_error_returns_openai_style_json_response(self) -> None:
        response = _error_response(CodebuffError("network error", 502))
        body = json.loads(response.body)

        self.assertEqual(response.status_code, 502)
        self.assertIn("network error", body["error"]["message"])
        self.assertEqual(body["error"]["upstream_message"], "network error")
        self.assertEqual(body["error"]["type"], "upstream_error")

    def test_chat_completions_rejects_oversized_body(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "FREEBUFF_API_KEY": "local-key",
                "FREEBUFF_TOKEN": "token",
                "FREEBUFF_MAX_REQUEST_BODY_BYTES": "1000",
            },
            clear=True,
        ), patch.object(
            CodebuffAccountPool, "validate_accounts", new_callable=AsyncMock
        ):
            with TestClient(app) as client:
                response = client.post(
                    "/v1/chat/completions",
                    json={
                        "model": "deepseek/deepseek-v4-flash",
                        "messages": [{"role": "user", "content": "x" * 5000}],
                    },
                    headers={"Authorization": "Bearer local-key"},
                )

        self.assertEqual(response.status_code, 413)
        body = response.json()
        self.assertEqual(body["error"]["code"], "request_body_too_large")
        self.assertIn("请求体过大", body["error"]["message"])

    def test_anthropic_messages_rejects_oversized_body(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "FREEBUFF_API_KEY": "local-key",
                "FREEBUFF_TOKEN": "token",
                "FREEBUFF_MAX_REQUEST_BODY_BYTES": "1000",
            },
            clear=True,
        ), patch.object(
            CodebuffAccountPool, "validate_accounts", new_callable=AsyncMock
        ):
            with TestClient(app) as client:
                response = client.post(
                    "/v1/messages",
                    json={
                        "model": "deepseek/deepseek-v4-flash",
                        "max_tokens": 100,
                        "messages": [{"role": "user", "content": "x" * 5000}],
                    },
                    headers={"Authorization": "Bearer local-key"},
                )

        self.assertEqual(response.status_code, 413)
        self.assertIn("Request body too large", response.json()["error"]["message"])

    def test_finalize_skips_management_calls_and_does_not_raise(self) -> None:
        client = FinalizeFailingClient()
        run = FreebuffRun(
            run_id="run-1",
            agent_id="agent-1",
            started_at="2026-05-24T00:00:00.000Z",
        )

        # 精简版（对齐 Worker 1.7.0）：finalize 不再调用 record_step / finish_run，
        # 即使客户端这些方法抛错也不应触发调用或异常。
        self.asyncio_run(_finalize_run_with_client(client, run, None))
        # 若无异常即通过（finish_run 在 FinalizeFailingClient 中会 raise AssertionError，
        # 若被调用则此处失败）。

    def asyncio_run(self, awaitable) -> None:
        import asyncio

        asyncio.run(awaitable)


if __name__ == "__main__":
    unittest.main()
