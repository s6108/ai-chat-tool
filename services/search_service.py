import requests
from datetime import datetime, timedelta, date
from config import TAVILY_API_KEY

_SESSION = requests.Session()

def is_valid_news_result(result: dict) -> bool:
    """
    新闻日期过滤。
    """

    raw_date = (
        result.get("published_date")
        or result.get("published_at")
        or result.get("date")
        or ""
    )

    if not raw_date:
        return True

    try:
        news_date = datetime.fromisoformat(
            raw_date.replace("Z", "+00:00")
        ).date()

    except Exception:
        return True


    today = date.today()

    # 禁止未来新闻
    if news_date > today:
        return False

    # 新闻最多接受过去3天
    if news_date < today - timedelta(days=3):
        return False

    return True


def search_web(
    query: str,
    max_results: int = 10,
    *,
    search_type: str = "general_web",
    include_domains: list[str] | None = None,
    search_depth: str = "advanced",
):
    if not query.strip():
        return []

    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": search_depth,
        "max_results": max_results,
        "include_answer": False,
        "include_raw_content": False,
        "topic": "general",
    }

    if include_domains:
        payload["include_domains"] = include_domains

    if search_type == "recent_event":
        payload["topic"] = "news"
        payload["days"] = 7

    response = _SESSION.post(
        "https://api.tavily.com/search",
        json=payload,
        timeout=(5, 15),
    )

    response.raise_for_status()

    results = response.json().get(
        "results",
        [],
    )

    if search_type == "recent_event":
        return [
            result
            for result in results
            if is_valid_news_result(result)
        ]

    return results

def format_search_results(
    results: list,
    *,
    max_items: int = 5,
    max_chars_per_item: int = 450,
) -> str:
    parts = []
    for index, result in enumerate(
        results[:max_items],
        start=1,
    ):
        content = (
            result.get("content") or ""
        )[:max_chars_per_item]
        parts.append(
            f"{index}. 标题：{result.get('title', '无标题')}\n"
            f"内容：{content}\n"
            f"来源：{result.get('url', '')}"
        )
    return "\n\n".join(parts)
