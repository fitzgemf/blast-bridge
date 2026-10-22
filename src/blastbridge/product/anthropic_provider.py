"""Anthropic transport only; training-record decisions live in the intake gate."""

import importlib.util
import os
from typing import Any

from .agent import ProviderError, ProviderTurn


class AnthropicProvider:
    name = "live"

    def __init__(self, model: str = "claude-sonnet-5-5") -> None:
        import anthropic

        self.model = model
        self._sdk: Any = anthropic
        self._client: Any = anthropic.Anthropic(max_retries=0, timeout=45.0)

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        output_schema: dict[str, Any] | None,
        allow_tools: bool,
    ) -> ProviderTurn:
        output_config: dict[str, Any] = {"effort": "low"}
        if output_schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": output_schema}
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=4000,
                system=system,
                tools=tools,
                tool_choice={"type": "auto"} if allow_tools else {"type": "none"},
                messages=messages,
                output_config=output_config,
            )
        except self._sdk.AuthenticationError:
            raise ProviderError("API key rejected") from None
        except self._sdk.RateLimitError:
            raise ProviderError("rate limited") from None
        except self._sdk.APIStatusError as exc:
            raise ProviderError(f"API error {exc.status_code}") from None
        except self._sdk.APIConnectionError:
            raise ProviderError("network unavailable") from None
        except self._sdk.AnthropicError:
            raise ProviderError("AI request failed") from None
        if response.stop_reason == "refusal":
            raise ProviderError("The model declined this request.")
        if response.stop_reason == "max_tokens":
            raise ProviderError("The model reached its response limit. Please use manual entry.")
        blocks = []
        for block in response.content:
            if block.type == "text":
                blocks.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                blocks.append(
                    {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
                )
        return ProviderTurn(
            stop_reason=response.stop_reason or "",
            blocks=blocks,
            raw_content=response.content,
            model=response.model,
        )


def live_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY")) and (
        importlib.util.find_spec("anthropic") is not None
    )
