import requests
from config import TAVILY_API_KEY


def search_web(query: str, max_results: int = 5):
    if not query.strip():
        return []

    response = requests.post(
        "https://api.tavily.com/search",
        json={
            "api_key": TAVILY_API_KEY,
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
        },
        timeout=20,
    )

    response.raise_for_status()

    return response.json().get("results", [])

def format_search_results(results: list) -> str:
    if not results:
        return ""

    search_text_parts = []

    for index, result in enumerate(results, start=1):
        title = result.get("title", "无标题")
        content = result.get("content", "")
        url = result.get("url", "")

        search_text_parts.append(
            f"{index}. 标题：{title}\n"
            f"内容：{content}\n"
            f"来源：{url}"
        )

    return "\n\n".join(search_text_parts)