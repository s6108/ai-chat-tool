from __future__ import annotations

from services.search.base_search import BaseSearchProvider
from services.search_service import (
    format_search_results,
    search_web,
)


class MangoSearchProvider(BaseSearchProvider):

    def search(
        self,
        query: str,
    ) -> str:
        results = search_web(query)

        if not results:
            return "未找到有效的联网搜索结果。"

        return format_search_results(results)