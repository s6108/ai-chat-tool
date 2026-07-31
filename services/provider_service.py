from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from services.model_config import get_model_config
from services.providers.provider_factory import ProviderFactory


class MissingModelApiKeyError(RuntimeError):
    """Raised when the selected model has no configured API key."""


def _build_identity_prompt(model_name: str) -> dict[str, str]:
    return {
        "role": "system",
        "content": (
            f"你是 {model_name}。你正在参与由用户主导的 Mango AI 多模型讨论。\n"
            "请始终遵守以下规则：\n"
            f"1. 你必须明确知道自己的身份是 {model_name}，不得冒充其他模型。\n"
            "2.  不要在回答开头写“【某某的发言】”，\n"
            "3.  页面已经显示你的身份，请直接开始发表观点。\n"
            "4.  你可以阅读当前主题中此前各模型的发言。\n"
            "5.  引用或回应其他模型时，必须明确写出模型名称。\n"
            "6.  不要使用“上面说的”“他们认为”“之前的模型”等模糊表达。\n"
            "7.  如果不同意，应明确说明：‘我不同意 Gemini 关于……的观点，因为……’。\n"
            "8.  如果同意，应明确说明：‘我同意 Claude 关于……的判断，并补充……’。\n"
            "9.  不要为了制造分歧而刻意反驳；有不同意见时应清楚说明依据。\n"
            "10. 优先回答用户本次提出的问题，不要擅自替所有模型作最终总结。\n"
            "11. 使用与用户最新问题相同的语言回答。"
        ),
    }


def _label_assistant_message(message: dict[str, Any]) -> dict[str, Any] | None:
    content = message.get("content", "")

    if not isinstance(content, str) or not content.strip():
        return None

    speaker = (
        message.get("model_name")
        or message.get("model")
        or "Mango AI"
    )

    return {
        "role": "assistant",
        "content": f"【{speaker} 的发言】\n{content}",
    }


def _prepare_text_only_user_message(
    message: dict[str, Any],
) -> dict[str, str] | None:
    content = message.get("content", "")

    if isinstance(content, str):
        if not content.strip():
            return None
        return {
            "role": "user",
            "content": content,
        }

    if not isinstance(content, list):
        return None

    text_parts: list[str] = []

    for item in content:
        if not isinstance(item, dict):
            continue

        if item.get("type") == "text":
            text = item.get("text", "")
            if isinstance(text, str) and text.strip():
                text_parts.append(text.strip())

    if not text_parts:
        return None

    return {
        "role": "user",
        "content": "\n\n".join(text_parts),
    }


def prepare_messages(
    model_name: str,
    messages: list[dict[str, Any]],
    *,
    history_limit: int = 12,
) -> list[dict[str, Any]]:
    """Build model-ready history with explicit speaker identity labels."""
    config = get_model_config(model_name)
    recent_messages = messages[-history_limit:]
    prepared_messages: list[dict[str, Any]] = [
        _build_identity_prompt(model_name)
    ]

    for message in recent_messages:
        role = message.get("role")

        if role == "assistant":
            labeled_message = _label_assistant_message(message)
            if labeled_message:
                prepared_messages.append(labeled_message)
            continue

        if role != "user":
            continue

        if config.supports_vision:
            content = message.get("content")
            if isinstance(content, (str, list)):
                prepared_messages.append(
                    {
                        "role": "user",
                        "content": content,
                    }
                )
            continue

        text_message = _prepare_text_only_user_message(message)
        if text_message:
            prepared_messages.append(text_message)

    return prepared_messages


def stream_model_response(
    *,
    model_name: str,
    messages: list[dict[str, Any]],
    max_tokens: int = 1200,
    temperature: float = 0.7,
) -> Iterator[str]:
    """Stream text through the provider adapter selected for the model."""
    config = get_model_config(model_name)

    if not config.api_key:
        raise MissingModelApiKeyError(model_name)

    provider = ProviderFactory.create(config)

    yield from provider.stream_chat(
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
