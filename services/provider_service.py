from __future__ import annotations
import re
from collections.abc import Iterator
from typing import Any

from services.model_config import get_model_config
from services.providers.provider_factory import ProviderFactory


class MissingModelApiKeyError(RuntimeError):
    """Raised when the selected model has no configured API key."""

def _is_roundtable_context(
    model_name: str,
    messages: list[dict[str, Any]],
) -> bool:
    """历史中出现其他模型时，才进入多模型讨论模式。"""
    for message in messages:
        if message.get("role") != "assistant":
            continue

        speaker = (
            message.get("model_name")
            or message.get("model")
        )

        if speaker and speaker != model_name:
            return True

    return False


def _build_identity_prompt(
    model_name: str,
    *,
    roundtable_mode: bool,
) -> dict[str, str]:
    if not roundtable_mode:
        return {
            "role": "system",
            "content": (
                f"你是 {model_name}。"
                f"你必须始终明确自己的身份是 {model_name}，不得冒充其他模型。"
                "请直接、自然地回答用户当前问题。"
                "页面已经显示你的模型名称，"
                "不要在回答开头输出“某某的发言”“某某的观点”等身份标签。"
                "不要无故提及多模型讨论、圆桌会议或邀请其他模型参与。"
                "使用与用户最新问题相同的语言回答。"
                "历史记录中的“【某某的发言】”只是发言者标识。"
                "不要复制、复述或输出这些标签，请直接回答用户。"
            ),
        }

    return {
        "role": "system",
        "content": (
            f"你是 {model_name}，正在参与由用户主导的 Mango AI 多模型讨论。\n"
            "请遵守以下规则：\n"
            f"1. 明确自己的身份是 {model_name}，不得冒充其他模型。\n"
            "2. 页面已经显示你的名称，请直接发表观点，"
            "不要在回答开头写“某某的发言”或“某某的观点”。\n"
            "3. 你可以阅读当前主题中此前各模型的发言。\n"
            "4. 引用或回应其他模型时，必须明确写出模型名称。\n"
            "5. 不要使用“上面说的”“他们认为”“之前的模型”等模糊表达。\n"
            "6. 如果不同意，应明确指出不同意哪个模型的哪项观点及理由。\n"
            "7. 如果同意，应明确指出同意哪个模型，并补充自己的观点。\n"
            "8. 不要为了制造分歧而刻意反驳。\n"
            "9. 优先回答用户本次提出的问题，不要擅自替所有模型总结。\n"
            "10. 使用与用户最新问题相同的语言回答。"
            "11. 历史记录中的“【某某的发言】”仅用于帮助你识别发言者。"
            "12. 不得把任何历史模型的身份标签复制到自己回答的开头。"
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
    roundtable_mode = _is_roundtable_context(
        model_name,
        recent_messages,
    )

    prepared_messages: list[dict[str, Any]] = [
        _build_identity_prompt(
            model_name,
            roundtable_mode=roundtable_mode,
        )
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

def _clean_speaker_label_stream(
    stream: Iterator[str],
    model_name: str,
) -> Iterator[str]:
    """
    删除回答开头一个或多个模型身份标签。

    不管标签写的是当前模型还是其他模型，都会删除，例如：
    【Kimi 的发言】
    【Qwen 的发言】
    【Claude 的观点】
    Grok 的回答：
    """
    del model_name  # 保留参数接口，但清理时不限定模型名称

    pattern = re.compile(
        r"^\s*(?:"
        r"[【\[]\s*"
        r"[A-Za-z0-9_.+\-\u4e00-\u9fff]+"
        r"\s*的?\s*"
        r"(?:发言|發言|观点|觀點|回答)"
        r"\s*[】\]]\s*[:：\-—]?"
        r"|"
        r"[A-Za-z0-9_.+\-\u4e00-\u9fff]+"
        r"\s*的?\s*"
        r"(?:发言|發言|观点|觀點|回答)"
        r"\s*[:：\-—]?"
        r")\s*",
        flags=re.IGNORECASE,
    )

    buffer = ""
    checked = False

    for chunk in stream:
        if checked:
            yield chunk
            continue

        buffer += chunk

        # 防止流式输出把标签拆成多个 chunk
        if len(buffer) < 120 and "\n" not in buffer:
            continue

        previous = None

        # 连续清除多个开头标签
        while previous != buffer:
            previous = buffer
            buffer = pattern.sub("", buffer, count=1)

        checked = True

        if buffer:
            yield buffer

    if not checked and buffer:
        previous = None

        while previous != buffer:
            previous = buffer
            buffer = pattern.sub("", buffer, count=1)

        if buffer:
            yield buffer


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

    raw_stream = provider.stream_chat(
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )

    yield from _clean_speaker_label_stream(
        raw_stream,
        model_name,
    )