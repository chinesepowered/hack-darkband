"""One OpenAI-compatible LLM client for the whole factory.

Default: Qwen 3.8 27B on W&B Inference. Any OpenAI-compatible endpoint works:
  ONSEN_LLM_BASE_URL   (default https://api.inference.wandb.ai/v1)
  ONSEN_LLM_API_KEY    (falls back to WANDB_API_KEY)
  ONSEN_LLM_MODEL      (default Qwen/Qwen3.8-27B)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

logger = logging.getLogger("onsen.llm")

T = TypeVar("T", bound=BaseModel)

DEFAULT_BASE_URL = "https://api.inference.wandb.ai/v1"
DEFAULT_MODEL = "Qwen/Qwen3.8-27B"


def llm_api_key() -> str | None:
    return os.environ.get("ONSEN_LLM_API_KEY") or os.environ.get("WANDB_API_KEY")


def llm_model(override_env: str | None = None) -> str:
    return (override_env and os.environ.get(override_env)) or os.environ.get("ONSEN_LLM_MODEL", DEFAULT_MODEL)


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Pydantic JSON schema tightened for guided decoding: no extra keys, every key required."""
    schema = model.model_json_schema()

    def tighten(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"])
            node.pop("title", None)
            for value in node.values():
                tighten(value)
        elif isinstance(node, list):
            for item in node:
                tighten(item)

    tighten(schema)
    return schema


class LLM:
    def __init__(self, *, model: str | None = None, base_url: str | None = None, api_key: str | None = None):
        self.model = model or llm_model()
        self.client = AsyncOpenAI(
            base_url=base_url or os.environ.get("ONSEN_LLM_BASE_URL", DEFAULT_BASE_URL),
            api_key=api_key or llm_api_key() or "missing-key",
            timeout=float(os.environ.get("ONSEN_LLM_TIMEOUT_S", "300")),
            max_retries=2,
        )

    async def structured(self, *, system: str, prompt: str, output: type[T], max_tokens: int = 24000,
                         attempts: int = 3, reasoning: str | None = None) -> T:
        """Chat completion constrained to `output`'s JSON schema, validated with Pydantic, retried on errors.

        Qwen 3.x thinks before answering, and thinking tokens count against max_tokens, so reasoning effort
        is capped (ONSEN_LLM_REASONING: none | low | medium | high; default low) to leave room for the JSON.
        """
        messages: list[dict[str, str]] = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        schema = strict_schema(output)
        effort = reasoning or os.environ.get("ONSEN_LLM_REASONING", "low")
        thinking: dict[str, Any] = (
            {"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}} if effort == "none"
            else {"reasoning_effort": effort}
        )
        last_error = ""
        for attempt in range(1, attempts + 1):
            # Constrained decoding first; if it fails (Qwen can loop on "]}]}" under a grammar), the last attempt
            # uses plain JSON mode with the schema in the prompt, and Pydantic still validates the result.
            constrained = attempt < attempts or attempts == 1
            fmt: dict[str, Any] = (
                {"type": "json_schema", "json_schema": {"name": output.__name__, "schema": schema, "strict": True}}
                if constrained else {"type": "json_object"}
            )
            if not constrained:
                messages = [*messages, {"role": "user", "content": "Return one JSON object that validates against "
                                        f"this JSON schema, and nothing else:\n{json.dumps(schema)}"}]
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                response_format=fmt,
                **thinking,
            )
            choice = resp.choices[0]
            content = (choice.message.content or "").strip()
            try:
                return output.model_validate_json(content)
            except ValidationError as exc:
                last_error = str(exc)[:1500]
            except json.JSONDecodeError as exc:
                last_error = f"invalid JSON: {exc}"
            logger.warning("LLM output failed validation (attempt %d/%d, finish=%s): %s",
                           attempt, attempts, choice.finish_reason, last_error[:300])
            if choice.finish_reason == "length":
                # A runaway (usually repeated brackets): retrying from a clean slate works better than repairing it.
                messages = messages[:2]
            else:
                messages += [{"role": "assistant", "content": content[:20000]},
                             {"role": "user", "content": f"That didn't validate against the schema: {last_error}\n"
                                                         "Return the corrected JSON only."}]
        raise RuntimeError(f"{self.model} never produced valid {output.__name__}: {last_error[:300]}")
