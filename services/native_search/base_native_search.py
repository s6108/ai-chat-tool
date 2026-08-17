from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NativeSearchResult:
    """
    单条原生搜索结果。
    """

    title: str = ""
    url: str = ""
    content: str = ""
    source: str = ""
    published_date: str | None = None
    score: float | None = None
    raw: dict[str, Any] | None = None


@dataclass
class NativeSearchResponse:
    """
    某个模型一次原生搜索的统一返回格式。
    """

    success: bool

    model_name: str
    provider: str

    query: str

    results: list[NativeSearchResult] = field(
        default_factory=list
    )

    answer: str = ""

    error: str | None = None

    # True 表示：
    # 原生搜索失败后应该进入 Tavily 安全网
    should_fallback: bool = False
    # 原生搜索自身产生的 token / provider 实际成本。
    # 没有 usage 数据的 provider 保持 None。
    usage: dict[str, Any] | None = None


class BaseNativeSearch(ABC):
    """
    所有模型原生搜索 Adapter 的统一接口。

    Megor 不关心 Grok / Gemini / Claude / ChatGPT
    各自具体怎样执行搜索。

    Megor 只调用统一的 search() 接口。
    """

    model_name: str = ""
    provider: str = ""

    @abstractmethod
    def search(
        self,
        *,
        query: str,
        messages: list[dict[str, Any]] | None = None,
        max_results: int = 8,
    ) -> NativeSearchResponse:
        """
        执行该模型自己的原生搜索。

        成功：
            success=True
            should_fallback=False

        原生搜索失败 / 超时 / 不可用：
            success=False
            should_fallback=True

        注意：
        不允许在这里自动调用 Tavily。
        Tavily fallback 由 Megor 上层统一决定。
        """

        raise NotImplementedError