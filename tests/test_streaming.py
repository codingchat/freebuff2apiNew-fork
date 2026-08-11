import asyncio
import json
import unittest
from types import SimpleNamespace

from freebuff2api.app import _start_freebuff_run_chain, _stream_openai_chunks
from freebuff2api.codebuff import CodebuffError, FreebuffRun
from freebuff2api.config import Settings
from freebuff2api.models import resolve_model


class FakeClient:
    def __init__(self) -> None:
        self.recorded = False
        self.finished = False
        self.calls = []

    async def chat_events(self, payload):
        yield (
            'data: {"id":"chunk-1","object":"chat.completion.chunk",'
            '"created":1,"model":"deepseek/deepseek-v4-flash",'
            '"choices":[{"index":0,"delta":{"content":null,'
            '"reasoning_content":"hello"},"finish_reason":null}]}'
        )
        yield "data: [DONE]"

    async def record_run_step(self, *args, **kwargs) -> None:
        self.recorded = True
        self.calls.append(("step", args, kwargs))
        await asyncio.sleep(0)

    async def finish_run(self, *args, **kwargs) -> None:
        self.finished = True
        self.calls.append(("finish", args, kwargs))
        await asyncio.sleep(0)

    async def start_run(self, agent_id, ancestor_run_ids=None):
        run_id = f"run-{len([call for call in self.calls if call[0] == 'start']) + 1}"
        self.calls.append(("start", agent_id, ancestor_run_ids or [], run_id))
        await asyncio.sleep(0)
        return run_id


class FailingStreamClient(FakeClient):
    async def chat_events(self, payload):
        raise CodebuffError("Codebuff chat failed: 403 hierarchy", 502)
        yield


class NoDoneStreamClient(FakeClient):
    """上游 EOF 但从不发 [DONE]（免费通道长对话常见行为）。"""

    async def chat_events(self, payload):
        yield (
            'data: {"id":"chunk-1","object":"chat.completion.chunk",'
            '"created":1,"model":"deepseek/deepseek-v4-flash",'
            '"choices":[{"index":0,"delta":{"content":"answer",'
            '"reasoning_content":null},"finish_reason":"stop"}]}'
        )
        # 不 yield "[DONE]",直接 EOF


class UnexpectedErrorStreamClient(FakeClient):
    """上游流中途抛未预期异常（非 CodebuffError）。"""

    async def chat_events(self, payload):
        yield 'data: {"id":"chunk-1","object":"chat.completion.chunk","created":1,"model":"m","choices":[{"index":0,"delta":{"content":"hi"},"finish_reason":null}]}'
        raise RuntimeError("stream broke mid-way")


class StreamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_forwards_content_before_finalize(self) -> None:
        client = FakeClient()
        request = SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(
                    codebuff=client,
                    settings=Settings(
                        codebuff_token="token",
                        local_api_key=None,
                        debug=False,
                    ),
                )
            )
        )

        chunks = []
        run = FreebuffRun(
            run_id="run-1",
            agent_id="base2-free-deepseek-flash",
            started_at="2026-05-23T00:00:00.000Z",
        )
        async for chunk in _stream_openai_chunks(request, {}, run):
            chunks.append(chunk.decode("utf-8"))

        first_payload = json.loads(chunks[0].removeprefix("data: ").strip())

        delta = first_payload["choices"][0]["delta"]
        self.assertNotIn("content", delta)
        self.assertEqual(delta["reasoning_content"], "hello")
        self.assertEqual(chunks[1], "data: [DONE]\n\n")

        await asyncio.sleep(0.05)
        # 精简版（对齐 Worker 1.7.0）：finalize 不再调用 record_step/finish_run，
        # 只 START 两个 run。断言不再产生管理端调用。
        self.assertFalse(client.recorded)
        self.assertFalse(client.finished)

    async def test_run_chain_matches_freebuff_parent_child_shape(self) -> None:
        client = FakeClient()

        run = await _start_freebuff_run_chain(client, "base2-free-kimi")

        self.assertEqual(run.run_id, "run-1")
        self.assertEqual(run.child_run_id, "run-2")
        self.assertEqual(client.calls[0], ("start", "base2-free-kimi", [], "run-1"))
        self.assertEqual(
            client.calls[1],
            ("start", "context-pruner", ["run-1"], "run-2"),
        )
        # 精简版：只 START 两个 run，不再打 record_step / finish_run 管理请求。
        self.assertEqual(len(client.calls), 2)

    async def test_gemini_thinker_run_chain_uses_child_as_payload_run(self) -> None:
        client = FakeClient()

        run = await _start_freebuff_run_chain(
            client,
            resolve_model("google/gemini-3.1-pro-preview"),
        )

        self.assertEqual(run.run_id, "run-1")
        self.assertEqual(run.chat_run_id, "run-2")
        self.assertEqual(run.payload_run_id, "run-2")
        self.assertEqual(client.calls[0], ("start", "base2-free-kimi", [], "run-1"))
        self.assertEqual(
            client.calls[1],
            ("start", "thinker-with-files-gemini", ["run-1"], "run-2"),
        )

    async def test_gemini_flash_lite_run_chain_uses_session_root_parent(self) -> None:
        client = FakeClient()

        run = await _start_freebuff_run_chain(
            client,
            resolve_model("google/gemini-2.5-flash-lite"),
        )

        self.assertEqual(run.run_id, "run-1")
        self.assertEqual(run.chat_run_id, "run-2")
        self.assertEqual(run.payload_run_id, "run-2")
        self.assertEqual(
            client.calls[0],
            ("start", "base2-free-deepseek-flash", [], "run-1"),
        )
        self.assertEqual(
            client.calls[1],
            ("start", "file-picker", ["run-1"], "run-2"),
        )

    async def test_streaming_codebuff_error_is_returned_as_sse_error(self) -> None:
        client = FailingStreamClient()
        request = SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(
                    codebuff=client,
                    settings=Settings(
                        codebuff_token="token",
                        local_api_key=None,
                        debug=False,
                    ),
                )
            )
        )

        chunks = []
        run = FreebuffRun(
            run_id="run-1",
            agent_id="base2-free-deepseek-flash",
            started_at="2026-05-23T00:00:00.000Z",
        )
        with self.assertLogs("freebuff2api.app", level="WARNING"):
            async for chunk in _stream_openai_chunks(request, {}, run):
                chunks.append(chunk.decode("utf-8"))

        error_payload = json.loads(chunks[0].removeprefix("data: ").strip())
        self.assertEqual(error_payload["error"]["code"], "codebuff_error")
        self.assertEqual(chunks[1], "data: [DONE]\n\n")

    async def test_stream_appends_done_when_upstream_eof_without_done(self) -> None:
        client = NoDoneStreamClient()
        request = SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(
                    codebuff=client,
                    settings=Settings(
                        codebuff_token="token",
                        local_api_key=None,
                        debug=False,
                    ),
                )
            )
        )
        run = FreebuffRun(
            run_id="run-1",
            agent_id="base2-free-deepseek-flash",
            started_at="2026-05-23T00:00:00.000Z",
        )

        chunks = [
            chunk.decode("utf-8")
            async for chunk in _stream_openai_chunks(request, {}, run)
        ]

        # 上游 EOF 无 [DONE] → 末尾补发 [DONE]，客户端不会报 "terminated"
        self.assertEqual(chunks[-1], "data: [DONE]\n\n")
        self.assertEqual(chunks[0].count("[DONE]"), 0)  # 内容块正常透传

    async def test_stream_unexpected_error_still_emits_done(self) -> None:
        client = UnexpectedErrorStreamClient()
        request = SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(
                    codebuff=client,
                    settings=Settings(
                        codebuff_token="token",
                        local_api_key=None,
                        debug=False,
                    ),
                )
            )
        )
        run = FreebuffRun(
            run_id="run-1",
            agent_id="base2-free-deepseek-flash",
            started_at="2026-05-23T00:00:00.000Z",
        )

        chunks = [
            chunk.decode("utf-8")
            async for chunk in _stream_openai_chunks(request, {}, run)
        ]

        # 未预期异常也要发 error + [DONE]，不允许连接裸断
        error_payload = json.loads(chunks[-2].removeprefix("data: ").strip())
        self.assertEqual(error_payload["error"]["code"], "codebuff_error")
        self.assertEqual(chunks[-1], "data: [DONE]\n\n")


if __name__ == "__main__":
    unittest.main()
