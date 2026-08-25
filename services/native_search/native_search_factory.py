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

    性能：
    - Adapter 按模型名做进程级缓存。
    - 同一 Python 进程中，每个模型只创建一次 Adapter。
    - 后续请求直接复用实例，避免重复初始化 API Client。

    注意：
    - 不执行搜索
    - 不调用 Tavily
    - 不判断是否需要联网
    - 不负责 fallback
    """

    _instances: dict[
        str,
        BaseNativeSearch,
    ] = {}

    _adapter_classes = {
        "grok": GrokNativeSearch,
        "gemini": GeminiNativeSearch,
        "claude": ClaudeNativeSearch,
        "chatgpt": OpenAINativeSearch,
        "qwen": QwenNativeSearch,
        "kimi": KimiNativeSearch,
        "doubao-pro": DoubaoNativeSearch,
        "glm": GLMNativeSearch,
    }

    @classmethod
    def create(
        cls,
        model_name: str,
    ) -> BaseNativeSearch | None:

        normalized_name = (
            model_name
            .strip()
            .casefold()
        )

        adapter_class = (
            cls._adapter_classes.get(
                normalized_name
            )
        )

        if adapter_class is None:
            return None

        cached_instance = (
            cls._instances.get(
                normalized_name
            )
        )

        if cached_instance is not None:
            print(
                "⚡ NativeSearchFactory cache hit:",
                normalized_name,
            )
            return cached_instance

        instance = adapter_class()

        cls._instances[
            normalized_name
        ] = instance

        print(
            "🔧 NativeSearchFactory created:",
            normalized_name,
        )

        return instance

    @classmethod
    def clear_cache(
        cls,
    ) -> None:
        """
        仅供调试 / 测试使用。
        正常请求流程不需要调用。
        """
        cls._instances.clear()

    @classmethod
    def supports(
        cls,
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

        return (
            normalized_name
            in cls._adapter_classes
        )

