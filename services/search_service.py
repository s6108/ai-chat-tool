import requests
from config import TAVILY_API_KEY

_SESSION = requests.Session()


def search_web(query: str, max_results: int = 6):
    if not query.strip():
        return []
    response = _SESSION.post(
        "https://api.tavily.com/search",
        json={
            "api_key": TAVILY_API_KEY,
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
        },
        timeout=(3.5, 8),
    )
    response.raise_for_status()
    return response.json().get("results", [])


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
