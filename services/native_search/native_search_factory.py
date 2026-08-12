from __future__ import annotations

from services.native_search.base_native_search import BaseNativeSearch
from services.native_search.grok_native_search import GrokNativeSearch
from services.native_search.gemini_native_search import GeminiNativeSearch
from services.native_search.claude_native_search import ClaudeNativeSearch
from services.native_search.openai_native_search import OpenAINativeSearch
from services.native_search.qwen_native_search import QwenNativeSearch
from services.native_search.kimi_native_search import KimiNativeSearch
from services.native_search.doubao_native_search import DoubaoNativeSearch
from services.native_search.glm_native_search import GLMNativeSearch


class NativeSearchFactory:
    """
    Megor 原生搜索 Adapter 工厂。

    职责：
    根据当前实际回答模型，返回对应的原生搜索 Adapter。

    注意：
    - 不执行搜索
    - 不调用 Tavily
    - 不判断是否需要联网
    - 不负责 fallback
    """

    @staticmethod
    def create(
        model_name: str,
    ) -> BaseNativeSearch | None:

        normalized_name = (
            model_name
            .strip()
            .casefold()
        )

        if normalized_name == "grok":
            return GrokNativeSearch()

        if normalized_name == "gemini":
            return GeminiNativeSearch()

        if normalized_name == "claude":
            return ClaudeNativeSearch()

        if normalized_name == "chatgpt":
            return OpenAINativeSearch()

        if normalized_name == "qwen":
            return QwenNativeSearch()
        if normalized_name == "kimi":
            return KimiNativeSearch()
        if normalized_name == "doubao-pro":
            return DoubaoNativeSearch()
        if normalized_name == "glm":
            return GLMNativeSearch()

        return None

    @staticmethod
    def supports(
        model_name: str,
    ) -> bool:
        """
        判断当前模型是否已经接入 Megor 原生搜索。
        """

        normalized_name = (
            model_name
            .strip()
            .casefold()
        )

        return normalized_name in {
            "grok",
            "gemini",
            "claude",
            "chatgpt",
            "qwen",
            "kimi",
            "doubao-pro",
            "glm",
        }