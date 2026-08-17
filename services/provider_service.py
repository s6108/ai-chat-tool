from __future__ import annotations
import re
from collections.abc import Iterator
from typing import Any

from services.model_config import get_model_config
from services.providers.provider_factory import ProviderFactory
from services.usage_service import record_usage_event


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
    roundtable_mode: bool,
) -> dict[str, str]:

    if not roundtable_mode:
        return {
            "role": "system",
            "content": (
                f"你是 {model_name}。"
                f"你必须始终明确自己的身份是 {model_name}，不得冒充其他模型。\n"
                "请直接、自然地回答用户当前问题。\n"
                "页面已经显示你的模型名称，因此回答中不要重复自己的模型名称。\n"
                "不要在回答开头添加模型身份、署名、标题或发言标签。\n"
                "不要输出类似“XX 的发言”“XX 的观点”“XX 的回答”"
                "或“作为 XX”这样的开头。\n"
                "直接从正文内容开始回答。"
            ),
        }

    return {
        "role": "system",
        "content": (
            f"你是 {model_name}，正在参与由用户主导的 Megor 多模型讨论。\n"
            "请遵守以下规则：\n"
            f"1. 明确自己的身份是 {model_name}，不得冒充其他模型。\n"
            "2. 你可以阅读当前主题中其他模型此前提供的内容。\n"
            "3. 如需引用其他模型的观点，可以明确写出对方模型名称。\n"
            "4. 如果同意或不同意某个模型，可以自然地说明理由。\n"
            "5. 不要为了制造分歧而刻意反驳。\n"
            "6. 优先回答用户本次提出的问题，不要擅自替所有模型总结。\n"
            "7. 使用与用户最新问题相同的语言回答。\n"
            "8. 历史记录中的 [MODEL=模型名] 只是内部元数据，"
            "仅用于识别上一段内容由哪个模型生成。\n"
            "9. 绝对不要复制、复述或输出 [MODEL=...] 元数据。\n"
            "10. 页面已经显示当前模型名称，所以不要再次署名。\n"
            "11. 回答必须直接从正文开始，不要添加任何模型身份标题或前缀。\n"
            "12. 禁止输出类似“XX 的发言”“XX 的观点”“XX 的回答”、"
            "“作为 XX”或其他模型身份标签。"
        ),
    }

def _label_assistant_message(
    message: dict[str, Any],
) -> dict[str, Any] | None:
    content = message.get("content", "")

    if not isinstance(content, str) or not content.strip():
        return None

    speaker = (
        message.get("model_name")
        or message.get("model")
        or "Megor"
    )

    return {
        "role": "assistant",
        "content": (
            f"[MODEL={speaker}]\n"
            f"{content}"
        ),
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
            print(
                "DEBUG VISION:",
                model_name,
                config.supports_vision,
                type(message.get("content"))
            )
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
    Stream output directly.
    No buffering.
    """

    del model_name

    for chunk in stream:
        if chunk:
            yield chunk


def stream_model_response(
    *,
    model_name: str,
    messages: list[dict[str, Any]],
    max_tokens: int = 1200,
    temperature: float = 0.7,
    supabase_admin=None,
    user_id: str | None = None,
    request_type: str = "text",
    request_id: str | None = None,
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

    # ============================================================
    # Record actual provider token usage
    # ============================================================

    usage = getattr(
        provider,
        "last_usage",
        None,
    )

    if (
        usage
        and supabase_admin is not None
        and user_id
    ):
        try:
            input_tokens = int(
                usage.get(
                    "input_tokens",
                    0,
                )
                or 0
            )

            output_tokens = int(
                usage.get(
                    "output_tokens",
                    0,
                )
                or 0
            )

            # 目前先只记录真正拿到 usage 的 provider。
            # ChatGPT 已经支持，其他模型后续逐个接入。
            if input_tokens > 0 or output_tokens > 0:
                record_usage_event(
                    supabase_admin,
                    user_id=user_id,
                    model_key=model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    request_type=request_type,
                    request_id=request_id,
                    metadata={
                        "source": "provider_usage",
                    },
                )

                print(
                    "💳 Usage recorded:",
                    f"model={model_name},",
                    f"input={input_tokens},",
                    f"output={output_tokens}",
                )

        except Exception as usage_error:
            # 额度记录失败不能破坏已经完成的聊天回答。
            print(
                "⚠️ Usage recording failed:",
                repr(usage_error),
            )