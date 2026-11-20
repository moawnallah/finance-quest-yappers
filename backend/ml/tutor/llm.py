"""The model adapter: roles -> models from config/llm.yaml, called through the LiteLLM SDK.

Code calls roles, never model names. A request that contains user data is refused for any role
not allowed user data (cloud roles), before any network call.
"""
from __future__ import annotations

import os
import re
import time
from pathlib import Path

import yaml

from .models import Completion

CONFIG = Path(__file__).resolve().parents[1] / "config" / "llm.yaml"
_ENV = re.compile(r"\$\{(\w+)\}")


def load_config(path: Path | str | None = None) -> dict:
    path = Path(path or os.environ.get("LLM_CONFIG") or CONFIG)
    raw = path.read_text(encoding="utf-8")
    return yaml.safe_load(_ENV.sub(lambda m: os.environ.get(m.group(1), ""), raw))


class RoleRefused(PermissionError):
    pass


class LiteLLMClient:
    def __init__(self, config: dict | None = None):
        self.config = config or load_config()

    def _role(self, role: str, contains_user_data: bool) -> dict:
        spec = self.config["roles"].get(role)
        if spec is None:
            raise RoleRefused(f"unknown role {role!r}")
        if contains_user_data and not spec.get("allowed_for_user_data", True):
            raise RoleRefused(f"role {role!r} may not receive user data")
        if spec.get("cloud") and os.environ.get("CLOUD_ROLES_ENABLED", "false").lower() != "true":
            raise RoleRefused(f"cloud role {role!r} is switched off (CLOUD_ROLES_ENABLED)")
        allow = [m.strip() for m in os.environ.get("MODEL_ALLOWLIST", "").split(",") if m.strip()]
        if allow and spec["primary"]["model"] not in allow:
            raise RoleRefused(f"model {spec['primary']['model']!r} is not in MODEL_ALLOWLIST")
        return spec

    def complete(self, role: str, messages: list[dict], json_schema: dict | None,
                 max_tokens: int, contains_user_data: bool) -> Completion:
        spec = self._role(role, contains_user_data)
        import litellm  # imported here so tests and the rule layer run without it

        params = dict(spec["primary"])
        model = params.pop("model")
        if json_schema is not None and spec.get("json_mode"):
            params["response_format"] = {"type": "json_object"}
        start = time.perf_counter()
        resp = litellm.completion(model=model, messages=messages, max_tokens=max_tokens,
                                  timeout=spec.get("timeout_s", 20), **params)
        usage = getattr(resp, "usage", None)
        return Completion(
            text=resp.choices[0].message.content or "",
            model=model,
            tokens_in=getattr(usage, "prompt_tokens", 0) or 0,
            tokens_out=getattr(usage, "completion_tokens", 0) or 0,
            latency_ms=int((time.perf_counter() - start) * 1000),
        )
