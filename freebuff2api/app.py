from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import datetime
import logging
import time
from typing import Any, AsyncIterator
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import ClientDisconnect

from .admin import router as admin_router
from .codebuff import (
    CodebuffAccountLease,
    CodebuffAccountPool,
    CodebuffClient,
    CodebuffError,
    FreebuffRun,
    SessionManager,
    utc_now_iso,
)
from .config import Settings, load_settings
from .logging_config import configure_logging, redact_headers, render_debug
from .token_rotation import parse_429_info
from .openai_compat import (
    CompletionAccumulator,
    build_upstream_payload,
    normalize_chat_messages,
    sanitize_stream_chunk,
)
from .anthropic_compat import (
    AnthropicCompletionAccumulator,
    AnthropicStreamState,
    anthropic_error_payload,
    anthropic_sse_encode,
    anthropic_sse_ping,
    build_anthropic_upstream_payload,
)
from .models import (
    CONTEXT_PRUNER_AGENT_ID,
    FreebuffModel,
    model_response,
    models_response,
    resolve_model,
)
from .sse import decode_sse_data, encode_sse
from .usage import RequestRecord
from .usage_store import RequestStore, ApiKeyStore, create_stores


logger = logging.getLogger("freebuff2api.app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = load_settings()
    configure_logging(settings)
    accounts = CodebuffAccountPool(settings)
    request_store, api_key_store = create_stores(settings.max_request_records)
    api_key_store.load_from_settings(settings.api_keys_json, settings.local_api_key)
    app.state.settings = settings
    app.state.accounts = accounts
    app.state.rotation = accounts.rotation
    app.state.codebuff = accounts.default_client
    app.state.sessions = accounts.default_sessions
    app.state.request_store = request_store
    app.state.api_key_store = api_key_store
    validation_task = asyncio.create_task(accounts.validate_accounts())
    logger.info("configured freebuff accounts count=%s api_keys=%s", accounts.account_count, api_key_store.total_count)
    try:
        yield
    finally:
        validation_task.cancel()
        await accounts.aclose()


app = FastAPI(title="freebuff2api", version="0.1.0", lifespan=lifespan)
app.include_router(admin_router)


@app.exception_handler(ClientDisconnect)
async def _handle_client_disconnect(request: Request, exc: ClientDisconnect) -> JSONResponse:
    """客户端在请求体读完前断开（用户停止/网络中断）→ 静默结束，不打 ERROR 堆栈。

    这是常态而非故障：request.json() 读到一半客户端断开会抛 ClientDisconnect，
    若不加 handler 会在 uvicorn 层打出整段 traceback 干扰监控。客户端已断开，
    响应实际送不出去，这里返回 499（Nginx 语义）仅作记录。
    """
    logger.info(
        "client disconnected before request body complete path=%s",
        request.url.path,
    )
    return JSONResponse(status_code=499, content={"error": {"message": "client closed connection", "type": "client_disconnect"}})


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _client(request: Request) -> CodebuffClient:
    return request.app.state.codebuff


def _sessions(request: Request) -> SessionManager:
    return request.app.state.sessions


def _accounts(request: Request) -> CodebuffAccountPool:
    return request.app.state.accounts


def _check_local_auth(request: Request, *, require_configured: bool = False):
    store: ApiKeyStore = request.app.state.api_key_store
    if store.total_count == 0:
        if require_configured:
            raise HTTPException(
                status_code=503,
                detail="Set FREEBUFF_API_KEY in the admin panel before using /v1 APIs",
            )
        return None
    key = store.authenticate(
        request.headers.get("authorization"),
        request.headers.get("x-api-key"),
    )
    if not key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return key


def _check_freebuff_token(request: Request) -> None:
    if not _settings(request).codebuff_tokens:
        raise HTTPException(
            status_code=503,
            detail="Set FREEBUFF_TOKEN in the admin panel before using chat completions",
        )


def _check_anthropic_auth(request: Request, *, require_configured: bool = False):
    store: ApiKeyStore = request.app.state.api_key_store
    if store.total_count == 0:
        if require_configured:
            raise HTTPException(
                status_code=503,
                detail="Set FREEBUFF_API_KEY in the admin panel before using /v1 APIs",
            )
        return None
    key = store.authenticate(
        request.headers.get("authorization"),
        request.headers.get("x-api-key"),
    )
    if not key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return key


def _error_response(error: Exception) -> JSONResponse:
    if isinstance(error, CodebuffError):
        headers: dict[str, str] = {}
        if error.status_code == 429:
            retry_ms = parse_429_info(str(error)).get("retry_after_ms", 0)
            if retry_ms:
                headers["Retry-After"] = str(max(1, round(retry_ms / 1000)))
        return JSONResponse(
            status_code=error.status_code,
            content={
                "error": {
                    "message": str(error),
                    "type": "upstream_error",
                    "code": "codebuff_error",
                }
            },
            headers=headers or None,
        )
    raise error


def _handle_upstream_error(request: Request, account_index: int | None, error: Exception, model: str = "") -> None:
    """Feed an upstream failure into the account rotation/health tracker."""
    if not isinstance(error, CodebuffError) or account_index is None:
        return
    accounts: CodebuffAccountPool = request.app.state.accounts
    # 428 waiting_room_required：缓存 session 已失效（僵尸实例，上游 chat gate 不识别）。
    # 清除该账号/模型的 session 缓存让下次请求重建，且不记入 failure/rotation，
    # 避免账号被误判失效（对齐 Worker 1.7.0 stale-session 处理）。
    if error.status_code == 428:
        try:
            account = accounts._accounts[account_index]
            account.sessions._sessions.pop(model, None)
        except Exception:
            pass
        logger.warning(
            "session stale (428 waiting_room_required) account=%s model=%s; cache cleared",
            account_index + 1,
            model,
        )
        return
    accounts.handle_error(account_index, str(error), error.status_code, model)


def _record_request(
    request: Request,
    api_key,
    model: str,
    duration_ms: int,
    status: str,
    *,
    error: str | None = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
) -> None:
    store: RequestStore = request.app.state.request_store
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    record = RequestRecord(
        id=0,
        timestamp=ts,
        api_key_name=api_key.name if api_key else "anonymous",
        api_key_prefix=api_key.prefix if api_key else "---",
        model=model,
        duration_ms=duration_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        status=status,
        error=error,
        client_ip=request.client.host if request.client else None,
    )
    store.add(record)


@app.get("/api/keep-warm")
async def keep_warm() -> dict[str, Any]:
    return {"status": "ok", "warm": True}

@app.get("/healthz")
async def healthz(request: Request) -> dict[str, Any]:
    _check_local_auth(request)
    return {"status": "ok"}


@app.get("/v1/models")
async def list_models(request: Request) -> dict[str, Any]:
    _check_local_auth(request, require_configured=True)
    return models_response()


@app.get("/v1/models/{model_id:path}")
async def get_model(request: Request, model_id: str) -> dict[str, Any]:
    _check_local_auth(request, require_configured=True)
    result = model_response(model_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Model not found: {model_id}")
    return result


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> Any:
    api_key = _check_local_auth(request, require_configured=True)
    _check_freebuff_token(request)
    body = await request.json()
    settings = _settings(request)
    try:
        model_config = resolve_model(body.get("model"))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    model = model_config.id
    if api_key and not api_key.allows_model(model):
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "message": f"API key '{api_key.name}' not allowed to use model '{model}'",
                    "type": "invalid_request_error",
                    "code": "model_not_allowed",
                }
            },
        )
    logger.info(
        "chat completion request model=%s stream=%s messages=%s",
        model,
        body.get("stream") is True,
        len(body.get("messages") or []),
    )
    if settings.debug:
        logger.debug(
            "incoming request headers=%s",
            redact_headers(dict(request.headers)),
        )
        logger.debug(
            "chat completion request body=%s",
            render_debug(body, settings.log_body_chars),
        )

    messages = normalize_chat_messages(body.get("messages"))
    lease: CodebuffAccountLease | None = None
    try:
        lease = await _accounts(request).acquire_session(
            model_config.session_id,
            messages=messages,
        )
        client = lease.client
        await client.request_ad_chain(messages=messages)
        # 不再调用 validate_agents()：/api/agents/validate 是旧 CLI 的额外管理请求，
        # Worker 1.7.0 桌面版协议不发送，去掉以缩小暴露面。
        run = await _start_freebuff_run_chain(client, model_config)
        trace_session_id = str(uuid.uuid4())
        payload = build_upstream_payload(
            {**body, "messages": messages},
            session=lease.session,
            run_id=run.payload_run_id,
            client_id=settings.client_id,
            trace_session_id=trace_session_id,
            upstream_model_id=model_config.upstream_id,
            system_prompt=settings.system_prompt_override,
        )
        if settings.debug:
            logger.debug(
                "prepared upstream chat trace=%s run=%s payload=%s",
                trace_session_id,
                run,
                render_debug(payload, settings.log_body_chars),
            )
    except CodebuffError as error:
        if lease is not None:
            _handle_upstream_error(request, lease._account_index, error, model)
            await lease.aclose()
        logger.warning(
            "failed to prepare chat completion: %s",
            error,
            exc_info=settings.debug,
        )
        return _error_response(error)
    except Exception as error:
        if lease is not None:
            await lease.aclose()
        logger.exception("failed to prepare chat completion")
        return _error_response(error)

    if body.get("stream") is True:
        return StreamingResponse(
            _stream_openai_chunks(request, payload, run, api_key=api_key, account_lease=lease),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    started = time.time()
    try:
        response = await _collect_completion(
            request,
            payload,
            run,
            model,
            client=lease.client,
        )
        duration_ms = int((time.time() - started) * 1000)
        usage = response.get("usage") or {}
        _record_request(request, api_key, model, duration_ms, "success",
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0))
        return JSONResponse(response)
    except Exception as error:
        duration_ms = int((time.time() - started) * 1000)
        _record_request(request, api_key, model, duration_ms, "error", error=str(error))
        _handle_upstream_error(request, lease._account_index, error, model)
        return _error_response(error)
    finally:
        await lease.aclose()


async def _stream_openai_chunks(
    request: Request,
    payload: dict[str, Any],
    run: FreebuffRun,
    *,
    api_key = None,
    account_lease: CodebuffAccountLease | None = None,
    client: CodebuffClient | None = None,
) -> AsyncIterator[bytes]:
    started = time.time()
    message_id: str | None = None
    client = client or (account_lease.client if account_lease else _client(request))
    settings = _settings(request)
    done_sent = False
    try:
        async for line in client.chat_events(payload):
            data = decode_sse_data(line)
            if data is None:
                continue
            if data == "[DONE]":
                if settings.debug:
                    logger.debug(
                        "chat stream done run_id=%s message_id=%s",
                        run.run_id,
                        message_id,
                    )
                yield encode_sse("[DONE]")
                done_sent = True
                break

            message_id = data.get("id") or message_id
            chunk = sanitize_stream_chunk(data)
            if chunk is not None:
                if settings.debug:
                    logger.debug(
                        "chat stream chunk=%s",
                        render_debug(chunk, settings.log_body_chars),
                    )
                yield encode_sse(chunk)
            elif settings.debug:
                logger.debug(
                    "chat stream ignored data=%s",
                    render_debug(data, settings.log_body_chars),
                )
    except CodebuffError as error:
        if account_lease is not None:
            _handle_upstream_error(request, account_lease._account_index, error, payload.get("model", ""))
        logger.warning(
            "chat stream failed run_id=%s: %s",
            run.run_id,
            error,
            exc_info=settings.debug,
        )
        if api_key:
            duration_ms = int((time.time() - started) * 1000)
            _record_request(request, api_key, payload.get("model", ""), duration_ms, "error", error=str(error))
        yield encode_sse(
            {
                "error": {
                    "message": str(error),
                    "type": "upstream_error",
                    "code": "codebuff_error",
                }
            }
        )
        yield encode_sse("[DONE]")
        done_sent = True
    except Exception as error:
        # 兜底：任何未预期异常（上游断流/解析异常等）也发 error + [DONE]，
        # 避免生成器裸抛导致连接直接关闭（客户端报 "terminated / other side closed"）。
        if account_lease is not None:
            _handle_upstream_error(request, account_lease._account_index, error, payload.get("model", ""))
        logger.exception(
            "chat stream unexpected error run_id=%s",
            run.run_id,
        )
        if api_key:
            duration_ms = int((time.time() - started) * 1000)
            _record_request(request, api_key, payload.get("model", ""), duration_ms, "error", error=str(error))
        yield encode_sse(
            {
                "error": {
                    "message": str(error),
                    "type": "upstream_error",
                    "code": "codebuff_error",
                }
            }
        )
        yield encode_sse("[DONE]")
        done_sent = True
    finally:
        # 上游 EOF 但未发 [DONE]（免费通道长对话常见）→ 补发终止符，
        # 否则客户端等 [DONE] 等到连接关闭报 "terminated"。
        if not done_sent:
            yield encode_sse("[DONE]")
        if api_key:
            duration_ms = int((time.time() - started) * 1000)
            _record_request(request, api_key, payload.get("model", ""), duration_ms, "success")
        _schedule_finalize_run(client, run, message_id)
        if account_lease is not None:
            await account_lease.aclose()


async def _collect_completion(
    request: Request,
    payload: dict[str, Any],
    run: FreebuffRun,
    model: str,
    *,
    client: CodebuffClient | None = None,
) -> dict[str, Any]:
    message_id: str | None = None
    accumulator = CompletionAccumulator(model)
    client = client or _client(request)
    try:
        async for line in client.chat_events(payload):
            data = decode_sse_data(line)
            if data is None:
                continue
            if data == "[DONE]":
                break
            message_id = data.get("id") or message_id
            accumulator.add(data)
        response = accumulator.final_response()
        logger.info(
            "chat completion response run_id=%s message_id=%s content_chars=%s finish_reason=%s",
            run.run_id,
            message_id,
            len(response["choices"][0]["message"].get("content") or ""),
            response["choices"][0].get("finish_reason"),
        )
        if _settings(request).debug:
            logger.debug(
                "chat completion response body=%s",
                render_debug(response, _settings(request).log_body_chars),
            )
        return response
    finally:
        await _finalize_run(request, run, message_id, client=client)


async def _start_freebuff_run_chain(
    client: CodebuffClient,
    model: FreebuffModel | str,
) -> FreebuffRun:
    if isinstance(model, str):
        model = FreebuffModel(model, model)
    if model.parent_agent_id:
        return await _start_child_chat_run_chain(client, model)

    # 精简版（对齐 Worker 1.7.0 startRunChain）：只 START 主 run + context-pruner
    # 子 run。chat 只校验 run_id 存在，recordRunStep/finishRun 可跳过——去掉这些
    # 额外管理请求可缩小请求特征暴露面（旧 CLI 行为已被上游统计）。
    agent_id = model.agent_id
    started_at = utc_now_iso()
    run_id = await client.start_run(agent_id)
    child_run_id = await client.start_run(
        CONTEXT_PRUNER_AGENT_ID,
        ancestor_run_ids=[run_id],
    )
    return FreebuffRun(
        run_id=run_id,
        agent_id=agent_id,
        started_at=started_at,
        child_run_id=child_run_id,
    )


async def _start_child_chat_run_chain(
    client: CodebuffClient,
    model: FreebuffModel,
) -> FreebuffRun:
    assert model.parent_agent_id is not None

    started_at = utc_now_iso()
    parent_run_id = await client.start_run(model.parent_agent_id)
    chat_started_at = utc_now_iso()
    chat_run_id = await client.start_run(
        model.agent_id,
        ancestor_run_ids=[parent_run_id],
    )
    return FreebuffRun(
        run_id=parent_run_id,
        agent_id=model.parent_agent_id,
        started_at=started_at,
        child_run_id=chat_run_id,
        chat_run_id=chat_run_id,
        chat_started_at=chat_started_at,
    )


async def _finalize_run(
    request: Request,
    run: FreebuffRun,
    message_id: str | None,
    *,
    client: CodebuffClient | None = None,
) -> None:
    await _finalize_run_with_client(client or _client(request), run, message_id)


def _schedule_finalize_run(
    client: CodebuffClient,
    run: FreebuffRun,
    message_id: str | None,
) -> None:
    task = asyncio.create_task(_finalize_run_with_client(client, run, message_id))

    def _log_background_error(done: asyncio.Task[None]) -> None:
        try:
            done.result()
        except asyncio.CancelledError:
            logger.debug("background finalize task cancelled run_id=%s", run.run_id)
        except Exception:
            logger.exception("background finalize task failed run_id=%s", run.run_id)

    task.add_done_callback(_log_background_error)


async def _finalize_run_with_client(
    client: CodebuffClient,
    run: FreebuffRun,
    message_id: str | None,
) -> None:
    # 精简版（对齐 Worker 1.7.0）：chat 只校验 run_id 存在，finalize 无需再打
    # record_step / finish_run 管理请求。保留函数为向后兼容，函数体为空。
    logger.debug(
        "finalize run skipped (streamlined) run_id=%s message_id=%s",
        run.run_id,
        message_id,
    )


# ── Anthropic Messages API (/v1/messages) ─────────────────────────────


@app.post("/v1/messages")
async def anthropic_messages(request: Request) -> Any:
    api_key = _check_anthropic_auth(request, require_configured=True)
    _check_freebuff_token(request)
    body = await request.json()
    settings = _settings(request)

    # Validate required fields — return Anthropic-compatible errors.
    if not isinstance(body.get("messages"), list):
        return JSONResponse(
            status_code=400,
            content=anthropic_error_payload(
                "messages: field required (must be a non-empty list)",
                error_type="invalid_request_error",
            ),
        )
    if not body.get("messages"):
        return JSONResponse(
            status_code=400,
            content=anthropic_error_payload(
                "messages: must be a non-empty list",
                error_type="invalid_request_error",
            ),
        )
    if body.get("max_tokens") is None:
        return JSONResponse(
            status_code=400,
            content=anthropic_error_payload(
                "max_tokens: field required",
                error_type="invalid_request_error",
            ),
        )

    # Model resolution — preserve original model name for the response.
    requested_model = body.get("model")
    try:
        model_config = resolve_model(requested_model)
    except ValueError as error:
        return JSONResponse(
            status_code=400,
            content=anthropic_error_payload(str(error), error_type="invalid_request_error"),
        )
    model = model_config.id
    if api_key and not api_key.allows_model(model):
        return JSONResponse(
            status_code=403,
            content=anthropic_error_payload(
                f"API key '{api_key.name}' not allowed to use model '{model}'",
                error_type="permission_error",
            ),
        )
    stream = body.get("stream") is True
    logger.info(
        "anthropic messages request model=%s stream=%s messages=%s max_tokens=%s",
        model,
        stream,
        len(body["messages"]),
        body["max_tokens"],
    )
    if settings.debug:
        logger.debug(
            "incoming anthropic request headers=%s",
            redact_headers(dict(request.headers)),
        )
        logger.debug(
            "anthropic messages request body=%s",
            render_debug(body, settings.log_body_chars),
        )

    # Session & run preparation (shared with OpenAI path).
    lease: CodebuffAccountLease | None = None
    try:
        lease = await _accounts(request).acquire_session(
            model_config.session_id,
        )
        client = lease.client
        await client.request_ad_chain()
        # 同 OpenAI 路径：不再调用 validate_agents()，缩小暴露面。
        run = await _start_freebuff_run_chain(client, model_config)
        trace_session_id = str(uuid.uuid4())
        payload = build_anthropic_upstream_payload(
            body,
            session=lease.session,
            run_id=run.payload_run_id,
            client_id=settings.client_id,
            trace_session_id=trace_session_id,
            upstream_model_id=model_config.upstream_id,
            system_prompt=settings.system_prompt_override,
        )
        if settings.debug:
            logger.debug(
                "prepared upstream anthropic trace=%s run=%s payload=%s",
                trace_session_id,
                run,
                render_debug(payload, settings.log_body_chars),
            )
    except CodebuffError as error:
        if lease is not None:
            _handle_upstream_error(request, lease._account_index, error, model)
            await lease.aclose()
        logger.warning(
            "failed to prepare anthropic messages: %s",
            error,
            exc_info=settings.debug,
        )
        status_code = getattr(error, "status_code", 502)
        return JSONResponse(
            status_code=status_code,
            content=anthropic_error_payload(str(error), status_code=status_code),
        )
    except Exception as error:
        if lease is not None:
            await lease.aclose()
        logger.exception("failed to prepare anthropic messages")
        return JSONResponse(
            status_code=500,
            content=anthropic_error_payload(str(error)),
        )

    if stream:
        return StreamingResponse(
            _stream_anthropic_events(request, payload, run, api_key=api_key, account_lease=lease, requested_model=requested_model),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    started = time.time()
    try:
        response = await _collect_anthropic_message(
            request,
            payload,
            run,
            requested_model,
            client=lease.client,
        )
        duration_ms = int((time.time() - started) * 1000)
        _record_request(request, api_key, model, duration_ms, "success",
            prompt_tokens=response.get("usage", {}).get("input_tokens", 0),
            completion_tokens=response.get("usage", {}).get("output_tokens", 0),
            total_tokens=(response.get("usage", {}).get("input_tokens", 0) + response.get("usage", {}).get("output_tokens", 0)))
        return JSONResponse(response)
    except Exception as error:
        duration_ms = int((time.time() - started) * 1000)
        _record_request(request, api_key, model, duration_ms, "error", error=str(error))
        _handle_upstream_error(request, lease._account_index, error, model)
        return JSONResponse(
            status_code=500,
            content=anthropic_error_payload(str(error)),
        )
    finally:
        await lease.aclose()


async def _stream_anthropic_events(
    request: Request,
    payload: dict[str, Any],
    run: FreebuffRun,
    *,
    api_key = None,
    account_lease: CodebuffAccountLease | None = None,
    client: CodebuffClient | None = None,
    requested_model: str | None = None,
) -> AsyncIterator[bytes]:
    started = time.time()
    client = client or (account_lease.client if account_lease else _client(request))
    settings = _settings(request)
    state = AnthropicStreamState(model=requested_model or payload.get("model", ""))
    _ping_active = True
    finalized = False

    async def _ping_loop() -> None:
        """Send ping every ~15 s to keep the connection alive across proxies."""
        try:
            while _ping_active:
                await asyncio.sleep(15)
                if _ping_active:
                    yield anthropic_sse_ping()
        except asyncio.CancelledError:
            pass

    def _emit_finalize():
        nonlocal finalized
        if finalized:
            return
        finalized = True
        for event_type, event_data in state.finalize_events():
            yield anthropic_sse_encode(event_type, event_data)

    try:
        async for line in client.chat_events(payload):
            data = decode_sse_data(line)
            if data is None:
                continue
            if data == "[DONE]":
                # Emit final events.
                for sse_line in _emit_finalize():
                    yield sse_line
                break

            for event_type, event_data in state.consume_chunk(data):
                if settings.debug:
                    logger.debug(
                        "anthropic stream event=%s data=%s",
                        event_type,
                        render_debug(event_data, settings.log_body_chars),
                    )
                yield anthropic_sse_encode(event_type, event_data)
    except CodebuffError as error:
        if account_lease is not None:
            _handle_upstream_error(request, account_lease._account_index, error, requested_model or payload.get("model", ""))
        logger.warning(
            "anthropic stream failed run_id=%s: %s",
            run.run_id,
            error,
            exc_info=settings.debug,
        )
        error_payload = anthropic_error_payload(str(error))
        yield anthropic_sse_encode("error", error_payload)
        # 错误后也补 finalize（message_stop），保证 Anthropic 客户端能收尾
        for sse_line in _emit_finalize():
            yield sse_line
    except Exception as error:
        if account_lease is not None:
            _handle_upstream_error(request, account_lease._account_index, error, requested_model or payload.get("model", ""))
        logger.exception(
            "anthropic stream unexpected error run_id=%s",
            run.run_id,
        )
        error_payload = anthropic_error_payload(str(error))
        yield anthropic_sse_encode("error", error_payload)
        for sse_line in _emit_finalize():
            yield sse_line
    finally:
        # 上游 EOF 但未发 [DONE]（免费通道长对话常见）→ 补 finalize（message_stop），
        # 否则 Anthropic 客户端悬挂/报 "terminated / other side closed"。
        for sse_line in _emit_finalize():
            yield sse_line
        if api_key:
            duration_ms = int((time.time() - started) * 1000)
            _record_request(request, api_key, payload.get("model", ""), duration_ms, "success")
        _ping_active = False
        _schedule_finalize_run(client, run, None)
        if account_lease is not None:
            await account_lease.aclose()


async def _collect_anthropic_message(
    request: Request,
    payload: dict[str, Any],
    run: FreebuffRun,
    model: str,
    *,
    client: CodebuffClient | None = None,
) -> dict[str, Any]:
    accumulator = AnthropicCompletionAccumulator(model)
    client = client or _client(request)
    try:
        async for line in client.chat_events(payload):
            data = decode_sse_data(line)
            if data is None:
                continue
            if data == "[DONE]":
                break
            accumulator.add(data)
        response = accumulator.final_response()
        content_blocks = len(response.get("content") or [])
        stop_reason = response.get("stop_reason")
        logger.info(
            "anthropic message response run_id=%s id=%s content_blocks=%s stop_reason=%s",
            run.run_id,
            response.get("id"),
            content_blocks,
            stop_reason,
        )
        if _settings(request).debug:
            logger.debug(
                "anthropic message response body=%s",
                render_debug(response, _settings(request).log_body_chars),
            )
        return response
    finally:
        await _finalize_run(request, run, None, client=client)
