from typing import Any

MIN_RESULT_SCORE = 0.35


def evaluate_search_results(user_prompt: str, results: list[dict]) -> dict[str, Any]:
    """本地快速评估，不再额外调用模型。"""
    useful = []
    for result in results:
        score = result.get("score")
        try:
            if score is None or float(score) >= MIN_RESULT_SCORE:
                useful.append(result)
        except (TypeError, ValueError):
            useful.append(result)

    enough = len(useful) >= 2 or (len(useful) == 1 and bool(useful[0].get("content")))
    return {
        "enough": enough,
        "reason": "已获得可用搜索资料" if enough else "可用搜索结果不足",
        "missing": "" if enough else "需要更直接的来源",
    }

def evaluate_news_results(
    results: list[dict],
) -> dict:

    if len(results) < 3:
        return {
            "enough": False,
            "reason": "新闻结果数量不足",
            "missing": "需要至少3条新闻来源",
        }


    domains = set()

    for result in results:

        url = result.get("url", "")

        if url:
            domain = (
                url.split("/")[2]
                if "//" in url
                else ""
            )

            domains.add(domain)


    if len(domains) < 2:
        return {
            "enough": False,
            "reason": "新闻来源不足",
            "missing": "需要多个独立来源",
        }


    return {
        "enough": True,
        "reason": "新闻来源数量满足要求",
        "missing": "",
    }
