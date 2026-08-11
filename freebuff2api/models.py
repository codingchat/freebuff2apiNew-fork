from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FreebuffModel:
    id: str
    agent_id: str
    owned_by: str = "freebuff"
    upstream_model_id: str | None = None
    session_model_id: str | None = None
    parent_agent_id: str | None = None
    # 模型参数（供 /v1/models 下发，客户端据此自适应钳制输出/上下文）。
    # 实测来源：yuzu-octopus/freebuff2api router/config.ts MODEL_CATALOG
    # （"contextWindow values are measured from real provider rejections"）。
    context_window: int = 131_072  # 保守默认（未实测模型）
    max_output_tokens: int = 32_768  # 统一保守输出上限（上游实测）
    input_modalities: tuple[str, ...] = ("text",)
    output_modalities: tuple[str, ...] = ("text",)

    @property
    def upstream_id(self) -> str:
        return self.upstream_model_id or self.id

    @property
    def session_id(self) -> str:
        return self.session_model_id or self.upstream_id


FREEBUFF_MODELS: tuple[FreebuffModel, ...] = (
    FreebuffModel(
        "deepseek/deepseek-v4-flash",
        "base2-free-deepseek-flash",
        context_window=1_048_576,
    ),
    FreebuffModel(
        "deepseek/deepseek-v4-pro",
        "base2-free-deepseek",
        context_window=131_072,
    ),
    FreebuffModel("moonshotai/kimi-k2.6", "base2-free-kimi"),
    FreebuffModel("minimax/minimax-m2.7", "base2-free"),
    FreebuffModel(
        "minimax/minimax-m3",
        "base2-free-minimax-m3",
        context_window=524_288,
        input_modalities=("text", "image"),
        output_modalities=("text",),
    ),
    FreebuffModel("mimo/mimo-v2.5", "base2-free-mimo", context_window=131_072),
    FreebuffModel("mimo/mimo-v2.5-pro", "base2-free-mimo-pro"),
    # 以下 8 个模型对齐 pingmike2/freebuff2api-wokers v1.7.2 MODELS 表
    # （来源：Freebuff Desktop orchestrator.js FREEBUFF_ROOT_AGENT_ID_BY_MODEL，2026-08-07 实测同步）
    FreebuffModel(
        "openai/gpt-5.6-luna",
        "base2-free-luna",
        context_window=1_000_000,
    ),
    FreebuffModel(
        "z-ai/glm-5.2",
        "base2-free-glm",
        context_window=131_072,
    ),
    FreebuffModel("poolside/laguna-s-2.1", "base2-free-laguna-s-2-1"),
    FreebuffModel("openrouter/poolside/laguna-s-2.1", "base2-free-laguna-s-2-1-openrouter"),
    FreebuffModel("inclusionai/ling-3.0-flash:free", "base2-free-ling-3-flash"),
    FreebuffModel("crof/greg-2-ultra", "base2-free-greg-2-ultra"),
    FreebuffModel("crof/greg-2-super", "base2-free-greg-2-super"),
    FreebuffModel("anthropic/claude-fable-5", "base2-free-fable"),
    FreebuffModel("meta/muse-spark-1.2-contributor", "base2-free-muse-spark"),
)

DEFAULT_MODEL = FREEBUFF_MODELS[0]
CONTEXT_PRUNER_AGENT_ID = "context-pruner"
GEMINI_THINKER_AGENT_ID = "thinker-with-files-gemini"
GEMINI_THINKER_PARENT_AGENT_ID = "base2-free-kimi"
GEMINI_THINKER_PARENT_MODEL_ID = "moonshotai/kimi-k2.6"
GEMINI_FLASH_LITE_SESSION_MODEL_ID = DEFAULT_MODEL.id

GEMINI_FREE_MODELS: tuple[FreebuffModel, ...] = (
    FreebuffModel(
        "google/gemini-2.5-flash-lite",
        "file-picker",
        owned_by="google",
        session_model_id=GEMINI_FLASH_LITE_SESSION_MODEL_ID,
        parent_agent_id=DEFAULT_MODEL.agent_id,
    ),
    FreebuffModel(
        "google/gemini-3.1-flash-lite-preview",
        "file-picker-max",
        owned_by="google",
        session_model_id=GEMINI_FLASH_LITE_SESSION_MODEL_ID,
        parent_agent_id=DEFAULT_MODEL.agent_id,
    ),
    FreebuffModel(
        "google/gemini-3.1-pro-preview",
        GEMINI_THINKER_AGENT_ID,
        owned_by="google",
        session_model_id=GEMINI_THINKER_PARENT_MODEL_ID,
        parent_agent_id=GEMINI_THINKER_PARENT_AGENT_ID,
    ),
)

ALL_MODELS = FREEBUFF_MODELS + GEMINI_FREE_MODELS

def resolve_model(requested: str | None) -> FreebuffModel:
    if not requested:
        return DEFAULT_MODEL

    # Direct match.
    for model in ALL_MODELS:
        if model.id == requested:
            return model

    raise ValueError(f"Unsupported Freebuff model: {requested}")


def _model_entry(model: FreebuffModel) -> dict[str, object]:
    """模型条目：OpenAI 标准字段 + Anthropic Models API 字段（附加，客户端自适应）。"""
    return {
        "id": model.id,
        "object": "model",
        "created": 0,
        "owned_by": model.owned_by,
        # Anthropic Models API 字段（Claude Code / anthropic-sdk 读取，
        # 用于 context sizing 与输出上限自适应）。
        "type": "model",
        "display_name": model.id,
        "context_window": model.context_window,
        "max_output_tokens": model.max_output_tokens,
        "input_modalities": list(model.input_modalities),
        "output_modalities": list(model.output_modalities),
    }


def models_response() -> dict[str, object]:
    return {
        "object": "list",
        "data": [_model_entry(model) for model in ALL_MODELS],
    }


def model_response(model_id: str) -> dict[str, object] | None:
    for model in ALL_MODELS:
        if model.id == model_id:
            return _model_entry(model)
    return None


def agent_validation_payload() -> dict[str, object]:
    models_by_agent: dict[str, FreebuffModel] = {}
    spawnable_by_agent: dict[str, set[str]] = {}
    for model in ALL_MODELS:
        models_by_agent.setdefault(model.agent_id, model)
        spawnable_by_agent.setdefault(model.agent_id, set()).add(CONTEXT_PRUNER_AGENT_ID)
        if model.parent_agent_id:
            spawnable_by_agent.setdefault(model.parent_agent_id, set()).add(model.agent_id)

    definitions = [
        _agent_definition(
            agent_id=model.agent_id,
            model_id=model.upstream_id,
            display_name=f"Freebuff {model.upstream_id}",
            spawnable_agents=sorted(spawnable_by_agent.get(model.agent_id, set())),
        )
        for model in models_by_agent.values()
    ]
    definitions.append(
        _agent_definition(
            agent_id=CONTEXT_PRUNER_AGENT_ID,
            model_id=DEFAULT_MODEL.id,
            display_name="Context Pruner",
            spawnable_agents=[],
        )
    )

    return {"agentDefinitions": definitions}


def _agent_definition(
    *,
    agent_id: str,
    model_id: str,
    display_name: str,
    spawnable_agents: list[str],
) -> dict[str, object]:
    return {
        "id": agent_id,
        "publisher": "codebuff",
        "model": model_id,
        "displayName": display_name,
        "spawnerPrompt": "Freebuff OpenAI-compatible orchestrator",
        "inputSchema": {
            "prompt": {
                "type": "string",
                "description": "A coding task to complete",
            },
            "params": {"type": "object", "properties": {}, "required": []},
        },
        "outputMode": "last_message",
        "includeMessageHistory": True,
        "toolNames": ["spawn_agents"] if spawnable_agents else [],
        "spawnableAgents": spawnable_agents,
        "systemPrompt": "Act as a helpful coding assistant.",
    }
