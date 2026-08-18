"""Port of freebuff-proxy's tool JSON-schema normalization.

The upstream Codebuff/Freebuff desktop client sends a small, clean toolset.
Clients like Trae/ZCode send hundreds of MCP tools with ``$defs``/``$ref``,
``nullable``, ``type: ["string","null"]`` and other JSON-schema features that
the official toolset never contains.  This module rewrites each function
tool's ``parameters`` into the same normalized shape the official client
would send, reducing the foreign-toolset fingerprint.

Algorithm ported from freebuff-proxy ``internal/convert/convert.go``:
- resolve ``$ref`` against ``definitions``/``$defs`` and the schema root
- drop ``definitions``/``$defs``/``nullable``
- simplify nullable ``anyOf``/``oneOf``
- reduce ``type`` arrays to the first non-null entry
- strip nulls/duplicates from ``enum``, drop ``const: null``
- depth cap 12 and per-request node budget 100_000
"""
from __future__ import annotations

from typing import Any

MAX_SCHEMA_NODES = 100_000
MAX_SCHEMA_DEPTH = 12


def normalize_tool_schemas(payload: dict[str, Any]) -> None:
    """Normalize every function tool's parameters schema in-place."""
    tools = payload.get("tools")
    if not isinstance(tools, list):
        return
    budget = [MAX_SCHEMA_NODES]
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        fn = tool.get("function")
        if not isinstance(fn, dict):
            continue
        params = fn.get("parameters")
        if not isinstance(params, dict):
            continue
        fn["parameters"] = _normalize_schema(
            params,
            _extract_definitions(params),
            params,
            None,
            MAX_SCHEMA_DEPTH,
            budget,
        )


def _extract_definitions(node: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for key in ("definitions", "$defs"):
        table = node.get(key)
        if isinstance(table, dict):
            merged.update(table)
    return merged


def _merge_definitions(
    parent: dict[str, Any] | None,
    local: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if parent is None:
        return local
    if local is None:
        return parent
    return {**parent, **local}


def _normalize_schema(
    node: dict[str, Any],
    defs: dict[str, Any] | None,
    root: dict[str, Any],
    ref_stack: dict[str, bool] | None,
    depth: int,
    budget: list[int],
) -> dict[str, Any]:
    if depth <= 0 or budget[0] <= 0:
        return node
    budget[0] -= 1
    defs = _merge_definitions(defs, _extract_definitions(node))

    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/"):
        if ref_stack and ref_stack.get(ref):
            return {}
        next_stack = dict(ref_stack or {})
        next_stack[ref] = True

        # 1. bare #/definitions/<name> / #/$defs/<name>
        replaced = _try_resolve_ref(node, defs)
        if replaced is not None:
            if isinstance(replaced, dict):
                return _normalize_schema(replaced, defs, root, next_stack, depth - 1, budget)
            return node

        # 2. JSON pointer against the schema root, siblings win
        target = _lookup_json_pointer(root, ref)
        if target is not None:
            resolved = _normalize_value(target, defs, root, next_stack, depth - 1, budget)
            if not isinstance(resolved, dict):
                return node
            siblings = _without_ref(node)
            if siblings:
                merged = _merge_maps(resolved, siblings)
                return _normalize_schema(merged, defs, root, ref_stack, depth - 1, budget)
            return resolved

        # 3. unresolvable: keep as-is or normalize siblings
        siblings = _without_ref(node)
        if siblings:
            return _normalize_schema(siblings, defs, root, ref_stack, depth - 1, budget)
        return node

    normalized: dict[str, Any] = {}
    for key, value in node.items():
        normalized[key] = _normalize_value(value, defs, root, ref_stack, depth - 1, budget)
    normalized.pop("definitions", None)
    normalized.pop("$defs", None)
    normalized.pop("nullable", None)
    normalized = _simplify_nullable_combinator(normalized, "anyOf")
    normalized = _simplify_nullable_combinator(normalized, "oneOf")
    _normalize_type_field(normalized)
    _normalize_enum_field(normalized)
    _normalize_const_field(normalized)
    return normalized


def _normalize_value(
    value: Any,
    defs: dict[str, Any] | None,
    root: dict[str, Any],
    ref_stack: dict[str, bool] | None,
    depth: int,
    budget: list[int],
) -> Any:
    if isinstance(value, list):
        return [
            _normalize_value(v, defs, root, ref_stack, depth, budget)
            for v in value
        ]
    if isinstance(value, dict):
        return _normalize_schema(value, defs, root, ref_stack, depth, budget)
    return value


def _lookup_json_pointer(root: Any, pointer: str) -> Any:
    if not pointer.startswith("#/"):
        return None
    current = root
    for segment in pointer[2:].split("/"):
        segment = segment.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if segment not in current:
                return None
            current = current[segment]
        elif isinstance(current, list):
            try:
                idx = int(segment)
            except ValueError:
                return None
            if idx < 0 or idx >= len(current):
                return None
            current = current[idx]
        else:
            return None
    return current


def _without_ref(node: dict[str, Any]) -> dict[str, Any] | None:
    if "$ref" not in node:
        return None
    return {k: v for k, v in node.items() if k != "$ref"}


def _merge_maps(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    return {**base, **override}


def _try_resolve_ref(node: dict[str, Any], defs: dict[str, Any] | None) -> Any:
    ref = node.get("$ref")
    if not isinstance(ref, str) or len(node) != 1 or not defs:
        return None
    name = None
    if ref.startswith("#/definitions/"):
        name = ref[len("#/definitions/"):]
    elif ref.startswith("#/$defs/"):
        name = ref[len("#/$defs/"):]
    if not name or name not in defs:
        return None
    return _clone_json(defs[name], MAX_SCHEMA_DEPTH)


def _clone_json(value: Any, depth: int) -> Any:
    if depth <= 0:
        return value
    if isinstance(value, dict):
        return {k: _clone_json(v, depth - 1) for k, v in value.items()}
    if isinstance(value, list):
        return [_clone_json(v, depth - 1) for v in value]
    return value


def _is_null_schema(schema: dict[str, Any]) -> bool:
    if schema.get("type") == "null":
        return True
    if "const" in schema and schema["const"] is None:
        return True
    enum = schema.get("enum")
    return isinstance(enum, list) and len(enum) == 1 and enum[0] is None


def _simplify_nullable_combinator(
    schema: dict[str, Any],
    key: str,
) -> dict[str, Any]:
    raw = schema.get(key)
    if not isinstance(raw, list):
        return schema
    filtered = [
        o for o in raw
        if not (isinstance(o, dict) and _is_null_schema(o))
    ]
    if not filtered:
        schema.pop(key, None)
    elif len(filtered) == 1 and isinstance(filtered[0], dict):
        merged = {k: v for k, v in schema.items() if k != key}
        merged.update(filtered[0])
        return merged
    else:
        schema[key] = filtered
    return schema


def _normalize_type_field(schema: dict[str, Any]) -> None:
    raw = schema.get("type")
    if not isinstance(raw, list):
        return
    non_null = [
        t for t in raw
        if isinstance(t, str) and t.strip() and t != "null"
    ]
    if not non_null:
        schema.pop("type", None)
    else:
        schema["type"] = non_null[0]


def _normalize_enum_field(schema: dict[str, Any]) -> None:
    raw = schema.get("enum")
    if not isinstance(raw, list):
        return
    seen: set[str] = set()
    filtered: list[Any] = []
    for entry in raw:
        if entry is None:
            continue
        key = f"{type(entry).__name__}:{repr(entry)}"
        if key in seen:
            continue
        seen.add(key)
        filtered.append(entry)
    if not filtered:
        schema.pop("enum", None)
    else:
        schema["enum"] = filtered


def _normalize_const_field(schema: dict[str, Any]) -> None:
    if "const" in schema and schema["const"] is None:
        schema.pop("const", None)
