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


def search_web(query: str, max_results: int = 10):
    if not query.strip():
        return []
    response = _SESSION.post(
        "https://api.tavily.com/search",
        json={
            "api_key": TAVILY_API_KEY,
            "query": query,
            "search_depth": "advanced",
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
            "topic": "news",
            "days": 3,
        },
        timeout=(5, 15),
    )
    response.raise_for_status()
    results = response.json().get(
        "results",
        []
    )


    filtered_results = []

    for result in results:

        if is_valid_news_result(result):
            filtered_results.append(result)

    return filtered_results


def format_search_results(results: list) -> str:
    parts = []
    for index, result in enumerate(results[:6], start=1):
        content = (result.get("content") or "")[:700]
        parts.append(
            f"{index}. 标题：{result.get('title', '无标题')}\n"
            f"内容：{content}\n"
            f"来源：{result.get('url', '')}"
        )
    return "\n\n".join(parts)
