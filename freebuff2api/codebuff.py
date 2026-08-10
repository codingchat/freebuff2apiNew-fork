from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, AsyncIterator
from urllib.parse import urlparse

import httpx

from .config import HAR_BROWSER_USER_AGENT, Settings, project_env_path
from .logging_config import redact_headers, render_debug
from .models import agent_validation_payload
from .token_rotation import (
    STATUS_ACTIVE,
    STATUS_BLOCKED,
    STATUS_CHECKING,
    STATUS_INVALID,
    RotationState,
    is_rate_limit_error,
    parse_429_info,
)


logger = logging.getLogger("freebuff2api.codebuff")

CODEBUFF_ACCEPT_ENCODING = "gzip, deflate"
# 桌面版协议伪装（2026-08-10，对齐 pingmike2/freebuff2api-wokers 1.7.0 / issue #13）：
# 旧版 CLI 指纹（Bun/1.3.11、Freebuff-CLI/0.0.105、旧 ai-sdk 版本号）已被上游
# detectForeignFreebuffClient / foreign-client-signals.ts 标记，命中后强制降级到
# 免费层模型（表现为空响应/429），并做账号级统计（终态封禁）。
# - JSON 请求不再手动设置 User-Agent（httpx 默认），消除 CLI 运行时特征
# - chat 请求使用官方 SDK 版本号签名（桌面版同款）
CHAT_COMPLETIONS_USER_AGENT = "ai-sdk/openai-compatible/3.0.20/codebuff"


class CodebuffError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class FreebuffSession:
    instance_id: str
    model: str
    expires_at: str | None = None
    remaining_ms: int | None = None

    @property
    def is_fresh(self) -> bool:
        return self.remaining_ms is None or self.remaining_ms > 60_000


@dataclass
class FreebuffRun:
    run_id: str
    agent_id: str
    started_at: str
    child_run_id: str | None = None
    chat_run_id: str | None = None
    chat_started_at: str | None = None

    @property
    def payload_run_id(self) -> str:
        return self.chat_run_id or self.run_id


@dataclass
class FreebuffSessionLease:
    session: FreebuffSession
    _lock: asyncio.Lock
    _closed: bool = False

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._lock.release()


class CodebuffClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        # httpx client is created lazily on first use. With a proxy configured,
        # constructing an AsyncClient is slow (~1.4s on Windows); deferring it
        # keeps account-pool startup fast even with many accounts.
        self._client: httpx.AsyncClient | None = None
        self._client_lock = asyncio.Lock()
        self._agents_validated = False
        self._validate_lock = asyncio.Lock()

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            async with self._client_lock:
                if self._client is None:
                    self._client = httpx.AsyncClient(
                        timeout=httpx.Timeout(self.settings.request_timeout, read=None),
                        follow_redirects=True,
                        proxy=self.settings.upstream_proxy_url,
                        trust_env=False,
                    )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _headers(
        self,
        *,
        json_body: bool = False,
        user_agent: str | None = None,
        require_auth: bool = True,
        extra: dict[str, str] | None = None,
    ) -> dict[str, str]:
        if require_auth and not self.settings.codebuff_token:
            raise CodebuffError("FREEBUFF_TOKEN or CODEBUFF_TOKEN is required", 500)

        headers = {
            "Accept": "*/*",
            "Accept-Encoding": CODEBUFF_ACCEPT_ENCODING,
            "Connection": "keep-alive",
            "Host": _host_header(self.settings.codebuff_api_url),
        }
        # 桌面版协议：默认不手动设置 User-Agent（httpx 默认），避免 CLI 运行时指纹
        if user_agent:
            headers["User-Agent"] = user_agent
        if require_auth:
            headers["Authorization"] = f"Bearer {self.settings.codebuff_token}"
        if json_body:
            headers["Content-Type"] = "application/json"
        if extra:
            headers.update(extra)
        return headers

    async def _json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.settings.codebuff_api_url}{path}"
        request_headers = headers or self._headers(json_body=body is not None)
        try:
            response = await (await self._ensure_client()).request(
                method,
                url,
                json=body,
                headers=request_headers,
            )
        except httpx.RequestError as error:
            raise _network_error(method, url, error) from error
        if self.settings.debug:
            logger.debug(
                "upstream json request method=%s url=%s headers=%s body=%s",
                method,
                url,
                redact_headers(request_headers),
                render_debug(body, self.settings.log_body_chars),
            )
            logger.debug(
                "upstream json response status=%s body=%s",
                response.status_code,
                render_debug(response.text, self.settings.log_body_chars),
            )
        if response.status_code >= 400:
            raise _upstream_error(response)
        if not response.content:
            return {}
        return response.json()

    async def validate_agents(self) -> None:
        if self._agents_validated:
            return
        async with self._validate_lock:
            if self._agents_validated:
                return
            try:
                data = await self._json(
                    "POST",
                    "/api/agents/validate",
                    body=agent_validation_payload(),
                    headers=self._headers(json_body=True, require_auth=False),
                )
            except CodebuffError:
                logger.warning(
                    "agent validation failed; continuing with server configs",
                    exc_info=self.settings.debug,
                )
                self._agents_validated = True
                return
            error_count = int(data.get("errorCount") or 0)
            if error_count:
                logger.warning(
                    "agent validation returned errors count=%s body=%s",
                    error_count,
                    render_debug(data, self.settings.log_body_chars),
                )
            else:
                logger.info(
                    "agent validation completed configs=%s",
                    len(data.get("configs") or []),
                )
            self._agents_validated = True

    async def health(self) -> dict[str, Any]:
        return await self._json(
            "GET",
            "/api/healthz",
            headers=self._headers(require_auth=False),
        )

    async def get_session(self, instance_id: str | None = None) -> dict[str, Any]:
        headers_extra = {}
        if instance_id:
            headers_extra["x-freebuff-instance-id"] = instance_id
        return await self._json(
            "GET",
            "/api/v1/freebuff/session",
            headers=self._headers(extra=headers_extra),
        )

    async def create_session(self, model: str) -> FreebuffSession:
        logger.info("create freebuff session requested model=%s", model)
        # 桌面版签名（对齐 Worker 1.7.0）：客户端预生成 instance-id，服务端据此绑定会话，
        # 避免旧版"服务端分配实例"特征被 detectForeignFreebuffClient 标记。
        instance_id = str(uuid.uuid4())
        data = await self._json(
            "POST",
            "/api/v1/freebuff/session",
            headers=self._headers(
                extra={
                    "x-freebuff-model": model,
                    "x-freebuff-instance-id": instance_id,
                }
            ),
        )
        if data.get("status") == "queued":
            return await self._wait_for_active_session(data, model)
        return self._session_from_data(data, model)

    def _session_from_data(
        self,
        data: dict[str, Any],
        model: str,
        instance_id: str | None = None,
    ) -> FreebuffSession:
        resolved_instance_id = data.get("instanceId") or instance_id
        if data.get("status") != "active" or not resolved_instance_id:
            raise CodebuffError(f"Freebuff session is not active: {data}", 502)
        return FreebuffSession(
            instance_id=resolved_instance_id,
            model=data.get("model") or model,
            expires_at=data.get("expiresAt"),
            remaining_ms=data.get("remainingMs"),
        )

    async def _wait_for_active_session(
        self,
        data: dict[str, Any],
        model: str,
    ) -> FreebuffSession:
        instance_id = data.get("instanceId")
        if not instance_id:
            raise CodebuffError(f"Freebuff queued session id missing: {data}", 502)

        deadline = time.monotonic() + self.settings.request_timeout
        attempts = 0
        while data.get("status") == "queued":
            logger.info(
                "freebuff session queued model=%s instance_id=%s position=%s estimated_wait_ms=%s",
                model,
                instance_id,
                data.get("position"),
                data.get("estimatedWaitMs"),
            )
            if time.monotonic() >= deadline:
                raise CodebuffError(
                    f"Freebuff session did not become active before timeout: {data}",
                    502,
                )
            if attempts:
                await asyncio.sleep(_queue_poll_delay(data.get("estimatedWaitMs")))
            data = await self.get_session(instance_id)
            attempts += 1

        return self._session_from_data(data, model, instance_id=instance_id)

    async def delete_session(self) -> None:
        await self._json(
            "DELETE",
            "/api/v1/freebuff/session",
            headers=self._headers(),
        )
        logger.info("deleted active freebuff session")

    async def get_streak(self) -> dict[str, Any]:
        data = await self._json(
            "GET",
            "/api/v1/freebuff/streak",
            headers=self._headers(),
        )
        logger.info(
            "freebuff streak streak=%s today_used=%s",
            data.get("streak"),
            data.get("todayUsed"),
        )
        return data

    async def request_ads(
        self,
        provider: str,
        messages: list[dict[str, Any]] | None = None,
        surface: str | None = None,
    ) -> dict[str, Any]:
        body = {
            "provider": provider,
            "messages": _ad_messages(messages),
            "sessionId": self.settings.session_id,
            "device": {
                "os": self.settings.os_name,
                "timezone": self.settings.timezone,
                "locale": self.settings.locale,
            },
            "userAgent": HAR_BROWSER_USER_AGENT,
        }
        if surface:
            body["surface"] = surface
        return await self._json(
            "POST",
            "/api/v1/ads",
            body=body,
            headers=self._headers(json_body=True),
        )

    async def request_ad_chain(
        self,
        messages: list[dict[str, Any]] | None = None,
        *,
        surface: str | None = None,
    ) -> None:
        for provider in self.settings.ad_providers:
            try:
                ads_data = await self.request_ads(
                    provider,
                    messages=messages,
                    surface=surface,
                )
                ads = ads_data.get("ads") or []
                ad = ads[0] if ads else None
                logger.info(
                    "ads provider=%s messages=%s count=%s selected=%s",
                    provider,
                    len(messages or []),
                    len(ads),
                    bool(ad),
                )
                if not ad:
                    continue
                await self.report_zeroclick_impressions(
                    list(ad.get("impressionIds") or [])
                )
                await self.report_codebuff_impression(ad.get("impUrl") or "")
                return
            except CodebuffError as error:
                logger.warning(
                    "ads provider=%s failed; continuing without blocking chat: %s",
                    provider,
                    error,
                    exc_info=self.settings.debug,
                )

    async def report_zeroclick_impressions(self, ids: list[str]) -> None:
        if not ids:
            return
        url = f"{self.settings.zeroclick_api_url}/api/v2/impressions"
        try:
            response = await (await self._ensure_client()).post(
                url,
                json={"ids": ids},
                headers={
                    "Content-Type": "application/json",
                    "Accept": "*/*",
                },
            )
        except httpx.RequestError as error:
            raise _network_error("POST", url, error) from error
        if self.settings.debug:
            logger.debug(
                "zeroclick impression ids=%s status=%s body=%s",
                ids,
                response.status_code,
                render_debug(response.text, self.settings.log_body_chars),
            )
        if response.status_code >= 400:
            raise CodebuffError(
                f"Zeroclick impression failed: {response.status_code} {response.text[:500]}",
                502,
            )

    async def report_codebuff_impression(self, imp_url: str) -> None:
        if not imp_url:
            return
        await self._json(
            "POST",
            "/api/v1/ads/impression",
            body={"impUrl": imp_url, "mode": "LITE"},
            headers=self._headers(json_body=True),
        )

    async def start_run(
        self,
        agent_id: str,
        ancestor_run_ids: list[str] | None = None,
    ) -> str:
        data = await self._json(
            "POST",
            "/api/v1/agent-runs",
            body={
                "action": "START",
                "agentId": agent_id,
                "ancestorRunIds": ancestor_run_ids or [],
            },
        )
        run_id = data.get("runId")
        if not run_id:
            raise CodebuffError(f"Codebuff run id missing: {data}", 502)
        logger.info(
            "agent run started agent_id=%s run_id=%s ancestors=%s",
            agent_id,
            run_id,
            ancestor_run_ids or [],
        )
        return run_id

    async def record_run_step(
        self,
        run_id: str,
        *,
        step_number: int,
        message_id: str | None,
        start_time: str,
        child_run_ids: list[str] | None = None,
    ) -> None:
        await self._json(
            "POST",
            f"/api/v1/agent-runs/{run_id}/steps",
            body={
                "stepNumber": step_number,
                "credits": 0,
                "childRunIds": child_run_ids or [],
                "messageId": message_id,
                "status": "completed",
                "startTime": start_time,
            },
        )
        logger.info(
            "agent run step recorded run_id=%s step=%s message_id=%s children=%s",
            run_id,
            step_number,
            message_id,
            child_run_ids or [],
        )

    async def finish_run(self, run_id: str, *, total_steps: int) -> None:
        await self._json(
            "POST",
            "/api/v1/agent-runs",
            body={
                "action": "FINISH",
                "runId": run_id,
                "status": "completed",
                "totalSteps": total_steps,
                "directCredits": 0,
                "totalCredits": 0,
            },
        )
        logger.info("agent run finished run_id=%s total_steps=%s", run_id, total_steps)

    async def chat_events(self, payload: dict[str, Any]) -> AsyncIterator[str]:
        url = f"{self.settings.codebuff_api_url}/api/v1/chat/completions"
        extra: dict[str, str] = {}
        # 桌面版签名（对齐 Worker 1.7.0）：chat 请求头带 x-freebuff-instance-id，
        # 上游据此识别桌面端实例；缺省会落入旧 CLI 会话特征。
        instance_id = (payload.get("codebuff_metadata") or {}).get(
            "freebuff_instance_id"
        )
        if instance_id:
            extra["x-freebuff-instance-id"] = str(instance_id)
        request_headers = self._headers(
            json_body=True,
            user_agent=CHAT_COMPLETIONS_USER_AGENT,
            extra=extra,
        )
        try:
            async with (await self._ensure_client()).stream(
                "POST",
                url,
                json=payload,
                headers=request_headers,
            ) as response:
                if self.settings.debug:
                    logger.debug(
                        "chat stream request url=%s headers=%s payload=%s",
                        url,
                        redact_headers(request_headers),
                        render_debug(payload, self.settings.log_body_chars),
                    )
                    logger.debug(
                        "chat stream response status=%s headers=%s",
                        response.status_code,
                        redact_headers(dict(response.headers)),
                    )
                if response.status_code >= 400:
                    text = await response.aread()
                    raise _upstream_error(
                        response,
                        body=text,
                        prefix="Codebuff chat failed",
                    )
                async for line in response.aiter_lines():
                    if self.settings.debug:
                        logger.debug(
                            "chat stream line=%s",
                            render_debug(line, self.settings.log_body_chars),
                        )
                    yield line
        except httpx.RequestError as error:
            raise _network_error("POST", url, error) from error


class SessionManager:
    def __init__(self, client: CodebuffClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings
        self._sessions: dict[str, FreebuffSession] = {}
        self._lock = asyncio.Lock()

    async def ensure_session(
        self,
        model: str,
        messages: list[dict[str, Any]] | None = None,
    ) -> FreebuffSession:
        async with self._lock:
            return await self._ensure_session_locked(model, messages)

    async def acquire_session(
        self,
        model: str,
        messages: list[dict[str, Any]] | None = None,
    ) -> FreebuffSessionLease:
        await self._lock.acquire()
        try:
            session = await self._ensure_session_locked(model, messages)
        except Exception:
            self._lock.release()
            raise
        return FreebuffSessionLease(session=session, _lock=self._lock)

    async def _ensure_session_locked(
        self,
        model: str,
        messages: list[dict[str, Any]] | None = None,
    ) -> FreebuffSession:
        cached = self._sessions.get(model)
        if cached and cached.is_fresh:
            try:
                data = await self.client.get_session(cached.instance_id)
                if data.get("status") == "active" and data.get("model") in {
                    None,
                    model,
                }:
                    cached.remaining_ms = data.get("remainingMs")
                    logger.debug(
                        "reuse freebuff session model=%s instance_id=%s remaining_ms=%s",
                        model,
                        cached.instance_id,
                        cached.remaining_ms,
                    )
                    return cached
                if data.get("status") == "active":
                    logger.info(
                        "cached freebuff session model mismatch cached=%s upstream=%s",
                        model,
                        data.get("model"),
                    )
                    self._sessions.pop(model, None)
            except CodebuffError:
                logger.debug(
                    "cached freebuff session invalid model=%s instance_id=%s",
                    model,
                    cached.instance_id,
                    exc_info=self.settings.debug,
                )
                self._sessions.pop(model, None)

        active_session = await self._delete_locked_session(model)
        if active_session:
            return active_session
        await self._request_ads_and_streak(surface="waiting_room")

        try:
            session = await self.client.create_session(model)
        except CodebuffError as error:
            if "model_locked" not in str(error):
                raise
            logger.info(
                "freebuff session locked during create; delete and retry model=%s",
                model,
            )
            await self.client.delete_session()
            self._sessions.clear()
            await self._request_ads_and_streak(surface="waiting_room")
            session = await self.client.create_session(model)
        self._sessions[model] = session
        logger.debug(
            "created freebuff session model=%s instance_id=%s remaining_ms=%s",
            model,
            session.instance_id,
            session.remaining_ms,
        )
        return session

    async def _request_ads_and_streak(
        self,
        messages: list[dict[str, Any]] | None = None,
        *,
        surface: str | None = None,
    ) -> None:
        for provider in self.settings.ad_providers:
            try:
                ads_data = await self.client.request_ads(
                    provider,
                    messages=messages,
                    surface=surface,
                )
                ads = ads_data.get("ads") or []
                ad = ads[0] if ads else None
                logger.info(
                    "ads provider=%s messages=%s count=%s selected=%s",
                    provider,
                    len(messages or []),
                    len(ads),
                    bool(ad),
                )
                if not ad:
                    continue
                await self.client.get_streak()
                await self.client.report_zeroclick_impressions(
                    list(ad.get("impressionIds") or [])
                )
                await self.client.report_codebuff_impression(ad.get("impUrl") or "")
                return
            except CodebuffError as error:
                logger.warning(
                    "ads provider=%s failed; continuing without blocking chat: %s",
                    provider,
                    error,
                    exc_info=self.settings.debug,
                )

    async def _delete_locked_session(
        self,
        requested_model: str,
    ) -> FreebuffSession | None:
        try:
            data = await self.client.get_session()
        except CodebuffError:
            logger.debug(
                "could not inspect active freebuff session before create",
                exc_info=self.settings.debug,
            )
            return None

        if data.get("status") != "active":
            return None

        current_model = data.get("model")
        instance_id = data.get("instanceId")
        if current_model == requested_model and instance_id:
            session = FreebuffSession(
                instance_id=instance_id,
                model=current_model,
                expires_at=data.get("expiresAt"),
                remaining_ms=data.get("remainingMs"),
            )
            self._sessions[requested_model] = session
            logger.info(
                "discovered active freebuff session model=%s instance_id=%s remaining_ms=%s",
                requested_model,
                session.instance_id,
                session.remaining_ms,
            )
            return session

        if not current_model or current_model == requested_model:
            return None

        logger.info(
            "switch freebuff session current_model=%s requested_model=%s instance_id=%s",
            current_model,
            requested_model,
            instance_id,
        )
        await self.client.delete_session()
        self._sessions.clear()
        return None


@dataclass
class CodebuffAccount:
    client: CodebuffClient
    sessions: SessionManager
    busy: bool = False
    active_requests: int = 0

    @property
    def is_busy(self) -> bool:
        return self.active_requests > 0


@dataclass
class CodebuffAccountLease:
    client: CodebuffClient
    session: FreebuffSession
    _session_lease: FreebuffSessionLease
    _pool: CodebuffAccountPool
    _account_index: int
    _closed: bool = False

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._session_lease.aclose()
        await self._pool.release(self._account_index)


class CodebuffAccountPool:
    def __init__(self, settings: Settings, rotation: RotationState | None = None) -> None:
        tokens = settings.codebuff_tokens or (None,)
        self._accounts: list[CodebuffAccount] = []
        for token in tokens:
            account_settings = replace(settings, codebuff_token=token)
            client = CodebuffClient(account_settings)
            self._accounts.append(
                CodebuffAccount(
                    client=client,
                    sessions=SessionManager(client, account_settings),
                )
            )
        self._next_index = 0
        self._condition = asyncio.Condition()
        self._rotation = rotation or RotationState(len(self._accounts), project_env_path())
        self._max_concurrency = max(1, getattr(settings, "max_concurrency_per_account", 1))
        self._last_used: dict[int, float] = {}
        self._probe_tasks: set[asyncio.Task] = set()

    @property
    def account_count(self) -> int:
        return len(self._accounts)

    @property
    def active_request_count(self) -> int:
        """Number of in-flight requests across all accounts (for deferred close)."""
        return sum(account.active_requests for account in self._accounts)

    @property
    def default_client(self) -> CodebuffClient:
        return self._accounts[0].client

    @property
    def default_sessions(self) -> SessionManager:
        return self._accounts[0].sessions

    async def aclose(self) -> None:
        for task in list(self._probe_tasks):
            task.cancel()
        if self._probe_tasks:
            await asyncio.gather(*self._probe_tasks, return_exceptions=True)
        await asyncio.gather(
            *(account.client.aclose() for account in self._accounts),
            return_exceptions=True,
        )

    async def acquire_session(
        self,
        model: str,
        messages: list[dict[str, Any]] | None = None,
    ) -> CodebuffAccountLease:
        last_error: Exception | None = None
        for _ in range(2):
            account_index = await self._reserve_account(model)
            account = self._accounts[account_index]
            logger.info(
                "account reserved index=%s session_model=%s messages=%s",
                account_index + 1,
                model,
                len(messages or []),
            )
            try:
                session_lease = await account.sessions.acquire_session(model, messages)
            except CodebuffError as error:
                await self.release(account_index)
                if error.status_code == 429 or is_rate_limit_error(str(error)):
                    raise
                last_error = error
                self.handle_error(account_index, str(error), error.status_code, model)
                logger.warning(
                    "account session acquire transient failure index=%s session_model=%s: %s",
                    account_index + 1,
                    model,
                    error,
                )
                continue
            except Exception:
                logger.exception(
                    "account session acquire failed index=%s session_model=%s",
                    account_index + 1,
                    model,
                )
                await self.release(account_index)
                raise
            # Success: reset the transient-failure counter (optimization ②)
            if self._rotation is not None:
                self._rotation.mark_success(account_index)
            self._last_used[account_index] = time.monotonic()
            logger.info(
                "account session acquired index=%s session_model=%s instance_id=%s remaining_ms=%s",
                account_index + 1,
                session_lease.session.model,
                session_lease.session.instance_id,
                session_lease.session.remaining_ms,
            )
            return CodebuffAccountLease(
                client=account.client,
                session=session_lease.session,
                _session_lease=session_lease,
                _pool=self,
                _account_index=account_index,
            )
        raise last_error if last_error else CodebuffError("no account available")

    async def release(self, account_index: int) -> None:
        async with self._condition:
            account = self._accounts[account_index]
            account.active_requests = max(0, account.active_requests - 1)
            account.busy = account.active_requests > 0
            self._condition.notify(1)

    async def _reserve_account(self, model: str = "") -> int:
        async with self._condition:
            while True:
                account_index = self._next_available_index(model)
                if account_index is not None:
                    account = self._accounts[account_index]
                    account.active_requests += 1
                    account.busy = True
                    self._next_index = (account_index + 1) % len(self._accounts)
                    return account_index
                # No usable account right now. Trigger half-open probes for any
                # account whose cooldown just expired, then wait until the earliest
                # unblock (or a release).
                self._maybe_trigger_half_open_probes()
                wait_secs: float | None = None
                if self._rotation:
                    remaining = [
                        self._rotation.block_remaining(i, model)
                        for i in range(len(self._accounts))
                        if self._rotation.is_blocked(i, model)
                    ]
                    if remaining:
                        wait_secs = min(remaining)
                if wait_secs is None or wait_secs <= 0:
                    wait_secs = 5.0
                try:
                    await asyncio.wait_for(self._condition.wait(), timeout=wait_secs)
                except asyncio.TimeoutError:
                    pass

    def _next_available_index(self, model: str = "") -> int | None:
        """Round-robin: scan from _next_index (true rotation), skipping busy/
        over-concurrency / blocked(for model) / invalid accounts."""
        account_count = len(self._accounts)
        if account_count == 0:
            return None
        start = self._next_index % account_count
        for offset in range(account_count):
            account_index = (start + offset) % account_count
            account = self._accounts[account_index]
            if account.active_requests >= self._max_concurrency:
                continue
            if self._rotation and (
                self._rotation.is_blocked(account_index, model)
                or self._rotation.status_of(account_index) == STATUS_INVALID
            ):
                continue
            return account_index
        return None

    # ── Half-open probes (optimization ③) ───────

    def _maybe_trigger_half_open_probes(self) -> None:
        """Accounts whose cooldown expired but are still marked blocked get a
        background probe; success → active (notifies waiters), failure → re-block."""
        if self._rotation is None:
            return
        now = time.monotonic()
        for index in range(len(self._accounts)):
            if self._rotation.status_of(index) != STATUS_BLOCKED:
                continue
            if not self._rotation.is_blocked(index):
                # cooldown expired → probe in the background
                self._rotation.mark_checking(index)
                task = asyncio.create_task(self._half_open_probe(index))
                self._probe_tasks.add(task)
                task.add_done_callback(self._probe_tasks.discard)
                logger.info("half-open probe scheduled account=%s", index + 1)

    async def _half_open_probe(self, index: int) -> None:
        """Probe one account after cooldown expiry. True → active + notify;
        False → re-block briefly; inconclusive → active (keep usable)."""
        try:
            result = await self._validate_account_token(index)
            async with self._condition:
                if result is False:
                    # Still failing: short cooldown so it isn't retried immediately
                    self._rotation.block(index, retry_after_ms=30_000)
                    logger.warning(
                        "half-open probe failed account=%s re-blocked 30s", index + 1
                    )
                else:
                    self._rotation.mark_active(index)
                    logger.info(
                        "half-open probe ok account=%s", index + 1
                    )
                self._condition.notify_all()
        except Exception:
            logger.exception("half-open probe error account=%s", index + 1)
            async with self._condition:
                self._rotation.mark_active(index)
                self._condition.notify_all()

    # ── Health / rotation helpers ────────────────

    @property
    def rotation(self) -> RotationState:
        return self._rotation

    def account_statuses(self) -> list[dict[str, Any]]:
        """Per-account status for the admin panel."""
        rows: list[dict[str, Any]] = []
        for index, account in enumerate(self._accounts):
            rows.append(
                {
                    "index": index + 1,
                    "token_prefix": (account.client.settings.codebuff_token or "")[:8],
                    "status": (
                        self._rotation.status_of(index) if self._rotation else STATUS_ACTIVE
                    ),
                    "blocked": self._rotation.is_blocked(index) if self._rotation else False,
                    "block_remaining": (
                        round(self._rotation.block_remaining(index), 1)
                        if self._rotation
                        else 0
                    ),
                    "failure_count": (
                        self._rotation.failure_count_of(index) if self._rotation else 0
                    ),
                    "is_current": bool(
                        self._rotation and index == self._rotation.current_index
                    ),
                    "last_429": (
                        self._rotation.last_429_info
                        if self._rotation
                        and self._rotation.last_429_account == index
                        else {}
                    ),
                }
            )
        return rows

    def handle_error(self, index: int, message: str, status_code: int = 502, model: str = "") -> None:
        """Record an upstream error against an account. 429 → cooldown (per model)
        + rotate; transient (5xx/network) → failure counter; 409 etc. → untouched."""
        if self._rotation is None:
            return
        if status_code == 429 or is_rate_limit_error(message):
            self._rotation.rotate(
                reason="429",
                error_message=message,
                is_429=True,
                failed_index=index,
                model=model,
            )
        elif status_code in (502, 500):
            self._rotation.record_failure(index)

    def manual_rotate(self) -> int:
        if self._rotation is None:
            return 0
        index, _ = self._rotation.rotate(reason="manual")
        if self._accounts:
            self._next_index = index
        return index

    def set_active(self, index: int) -> None:
        """index is 1-based (admin UI). Sets the preferred rotation pointer."""
        if self._rotation is None:
            return
        if index < 1 or index > len(self._accounts):
            raise IndexError(f"account index out of range: {index}")
        self._rotation.set_active(index - 1)
        self._next_index = index - 1

    async def validate_accounts(self) -> None:
        """Startup/background health check. Marks invalid accounts so selection skips them."""
        if self._rotation is None:
            return
        if not any(account.client.settings.codebuff_token for account in self._accounts):
            return
        # Cap concurrency: creating an httpx client with a proxy is slow (~1.4s
        # each on Windows), so validating many accounts at once would flood the
        # event loop and delay the server from binding its socket.
        semaphore = asyncio.Semaphore(5)

        async def _run(index: int):
            async with semaphore:
                return await self._validate_account_token(index)

        results = await asyncio.gather(
            *(_run(index) for index in range(len(self._accounts))),
            return_exceptions=True,
        )
        valid = 0
        inconclusive = 0
        for index, ok in enumerate(results):
            if ok is True:
                self._rotation.mark_active(index)
                self._rotation.reset_failures(index)
                valid += 1
            elif ok is False:
                self._rotation.mark_invalid(index)
                logger.warning(
                    "account validation marked invalid index=%s", index + 1
                )
            else:
                # Could not verify (timeout/network) → keep the account usable
                self._rotation.mark_active(index)
                inconclusive += 1
        logger.info(
            "account validation done valid=%s inconclusive=%s total=%s",
            valid,
            inconclusive,
            len(self._accounts),
        )

    async def _validate_account_token(self, index: int) -> bool | None:
        self._rotation.mark_checking(index)
        account = self._accounts[index]
        try:
            await account.client.get_session()
        except CodebuffError as error:
            message = str(error)
            if error.status_code == 401 or "Invalid" in message or "invalid" in message:
                logger.warning(
                    "account validation failed index=%s: %s", index + 1, error
                )
                return False
            logger.warning(
                "account validation could not verify index=%s; keeping: %s",
                index + 1,
                error,
            )
            return None
        except Exception:
            logger.exception(
                "account validation unexpected error index=%s", index + 1
            )
            return None
        return True


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00",
        "Z",
    )


def _host_header(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc or "www.codebuff.com"


def _queue_poll_delay(estimated_wait_ms: Any) -> float:
    if isinstance(estimated_wait_ms, int | float) and estimated_wait_ms > 0:
        return min(max(float(estimated_wait_ms) / 1000.0, 0.25), 2.0)
    return 0.25


def _network_error(method: str, url: str, error: httpx.RequestError) -> CodebuffError:
    detail = str(error).strip()
    suffix = f": {detail}" if detail else ""
    return CodebuffError(
        f"Codebuff request failed: {method} {url} network error "
        f"({type(error).__name__}){suffix}",
        502,
    )


def _upstream_error(
    response: httpx.Response,
    *,
    body: bytes | None = None,
    prefix: str = "Codebuff request failed",
) -> CodebuffError:
    raw_text = (
        body.decode("utf-8", errors="replace")
        if body is not None
        else response.text
    )
    text = raw_text[:500]
    if response.status_code == 429:
        return CodebuffError(
            f"{prefix}: {response.status_code} {text}",
            429,
        )
    if response.status_code == 409:
        try:
            data = (
                response.json()
                if body is None
                else httpx.Response(
                    response.status_code,
                    content=body,
                    headers=response.headers,
                ).json()
            )
        except ValueError:
            data = {}
        if data.get("error") == "session_model_mismatch":
            upstream_message = data.get("message") or text
            return CodebuffError(
                "Codebuff 409 session_model_mismatch: "
                f"{upstream_message} 上游判定当前账号或服务器出口只允许 DeepSeek V4 Flash；"
                "即使公网定位显示 US，也可能因出口 IP 段、账号状态或上游限免策略无法使用 Pro。",
                409,
            )

    return CodebuffError(
        f"{prefix}: {response.status_code} {text}",
        502,
    )


def _ad_messages(messages: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    return [
        {
            "role": _ad_message_role(message.get("role")),
            "content": _ad_message_content(message.get("content")),
        }
        for message in messages or []
    ]


def _ad_message_role(role: Any) -> str:
    if role == "developer":
        return "system"
    return str(role or "user")


def _ad_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    if isinstance(content, list):
        parts = [
            str(part.get("text"))
            for part in content
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        ]
        return "\n".join(parts)
    if isinstance(content, dict) and isinstance(content.get("text"), str):
        return content["text"]
    return str(content)
