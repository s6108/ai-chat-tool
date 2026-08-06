from services.date_service import get_search_query


def plan_search(prompt: str) -> list[str]:
    """
    生成搜索关键词。
    新闻任务增加日期和可靠来源限制。
    """

    prompt = (prompt or "").strip()

    if not prompt:
        return []

    dated_query = get_search_query(prompt)

    news_keywords = (
        "新闻",
        "国际新闻",
        "时事",
        "news",
        "breaking",
        "latest",
    )

    lowered = prompt.lower()

    if any(
        keyword in lowered
        for keyword in news_keywords
    ):
        return [
            f"{dated_query} Reuters BBC AP latest news",
            f"{dated_query} breaking news world",
            f"site:reuters.com {dated_query}",
            f"site:apnews.com {dated_query}",
        ]

    return [
        dated_query
    ]