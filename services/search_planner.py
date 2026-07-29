from services.date_service import get_search_query


def plan_search(prompt: str) -> list[str]:
    """默认只执行一次高质量搜索，减少串行网络等待。"""
    prompt = (prompt or "").strip()
    if not prompt:
        return []
    return [get_search_query(prompt)]
