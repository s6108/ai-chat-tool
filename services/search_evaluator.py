from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


MIN_RESULT_SCORE = 0.35


def _get_domain(url: str) -> str:
    """
    从 URL 中提取域名，并统一去掉 www.
    """
    if not url:
        return ""

    try:
        domain = urlparse(url).netloc.lower().strip()

        if domain.startswith("www."):
            domain = domain[4:]

        return domain

    except Exception:
        return ""


def _is_domain_match(
    domain: str,
    preferred_domains: list[str],
) -> bool:
    """
    判断结果域名是否属于 preferred_domains。

    例如：
    preferred_domains = ["canada.ca"]

    以下都算匹配：
    canada.ca
    www.canada.ca
    pm.gc.ca（如果明确加入列表）
    subdomain.canada.ca
    """
    if not domain:
        return False

    for preferred in preferred_domains:
        preferred = (
            preferred
            .lower()
            .strip()
            .removeprefix("www.")
        )

        if not preferred:
            continue

        if (
            domain == preferred
            or domain.endswith("." + preferred)
        ):
            return True

    return False


def _filter_useful_results(
    results: list[dict],
) -> list[dict]:
    """
    根据 Tavily score 做基础相关性过滤。
    """
    useful: list[dict] = []

    for result in results:
        score = result.get("score")

        try:
            if (
                score is None
                or float(score) >= MIN_RESULT_SCORE
            ):
                useful.append(result)

        except (TypeError, ValueError):
            # score 无法解析时暂时保留，
            # 避免误删可能有价值的结果。
            useful.append(result)

    return useful


def evaluate_search_results(
    user_prompt: str,
    results: list[dict],
    *,
    search_type: str = "general_web",
    preferred_domains: list[str] | None = None,
) -> dict[str, Any]:
    """
    本地快速评估搜索结果。

    不额外调用模型。

    根据 search_type 使用不同标准：

    - general_web:
        普通联网查询，有足够相关结果即可。

    - current_fact:
        当前职位、当前领导人、当前版本、
        当前政策状态等容易过期的事实。
        必须采用更严格的来源验证。

    - realtime_data:
        当前天气、市场、汇率、比赛、
        时间表等实时或近实时信息。

    - recent_event:
        最近新闻和事件由 evaluate_news_results()
        进一步评估。
    """

    del user_prompt  # 暂时保留接口，当前本地评估不分析文本语义

    preferred_domains = preferred_domains or []

    useful = _filter_useful_results(results)

    # ==================================================
    # CURRENT FACT
    # ==================================================
    if search_type == "current_fact":

        if not useful:
            return {
                "enough": False,
                "reason": "没有获得可用于确认当前事实的搜索资料",
                "missing": "需要当前、直接且可信的来源",
            }

        official_results: list[dict] = []

        if preferred_domains:
            for result in useful:
                domain = _get_domain(
                    result.get("url", "")
                )

                if _is_domain_match(
                    domain,
                    preferred_domains,
                ):
                    official_results.append(result)

        # --------------------------------------------------
        # 如果 planner 已经提供 preferred_domains，
        # current_fact 必须至少命中 1 个优先权威域名。
        # --------------------------------------------------
        if preferred_domains and not official_results:
            return {
                "enough": False,
                "reason": "尚未获得优先权威来源确认当前事实",
                "missing": (
                    "需要从官方或第一方权威来源确认当前状态"
                ),
            }

        # --------------------------------------------------
        # 有官方来源时：
        # 1 个官方来源本身就有较高价值；
        # 如果还能有第二个结果，则更理想。
        # --------------------------------------------------
        if official_results:
            if len(useful) >= 2:
                return {
                    "enough": True,
                    "reason": (
                        "已获得权威来源，并有额外搜索结果可用于交叉验证"
                    ),
                    "missing": "",
                }

            official_content = (
                official_results[0].get("content")
                or ""
            ).strip()

            if official_content:
                return {
                    "enough": True,
                    "reason": "已获得直接的权威来源确认当前事实",
                    "missing": "",
                }

        # --------------------------------------------------
        # 没有 preferred_domains 的情况：
        # 暂时要求至少两个独立域名，
        # 避免只靠一个普通网页回答当前事实。
        # --------------------------------------------------
        domains = {
            _get_domain(
                result.get("url", "")
            )
            for result in useful
            if result.get("url")
        }

        domains.discard("")

        if len(useful) < 2:
            return {
                "enough": False,
                "reason": "当前事实的搜索结果数量不足",
                "missing": "需要至少两个可交叉验证的结果",
            }

        if len(domains) < 2:
            return {
                "enough": False,
                "reason": "当前事实缺少独立来源交叉验证",
                "missing": "需要来自至少两个独立来源的资料",
            }

        return {
            "enough": True,
            "reason": "已获得多个独立来源用于确认当前事实",
            "missing": "",
        }

    # ==================================================
    # REALTIME DATA
    # ==================================================
    if search_type == "realtime_data":

        if not useful:
            return {
                "enough": False,
                "reason": "没有获得可用的实时数据",
                "missing": "需要当前或近实时数据来源",
            }

        # 实时数据至少要有正文内容，
        # 不能只有标题和 URL。
        content_results = [
            result
            for result in useful
            if bool(
                (
                    result.get("content")
                    or ""
                ).strip()
            )
        ]

        if not content_results:
            return {
                "enough": False,
                "reason": "实时搜索结果缺少有效数据内容",
                "missing": "需要包含实际数据的搜索结果",
            }

        return {
            "enough": True,
            "reason": "已获得可用的当前数据资料",
            "missing": "",
        }

    # ==================================================
    # RECENT EVENT
    # ==================================================
    if search_type == "recent_event":
        return evaluate_news_results(
            useful
        )

    # ==================================================
    # GENERAL WEB
    # ==================================================
    enough = (
        len(useful) >= 2
        or (
            len(useful) == 1
            and bool(
                (
                    useful[0].get("content")
                    or ""
                ).strip()
            )
        )
    )

    return {
        "enough": enough,
        "reason": (
            "已获得可用搜索资料"
            if enough
            else "可用搜索结果不足"
        ),
        "missing": (
            ""
            if enough
            else "需要更直接的来源"
        ),
    }


def evaluate_news_results(
    results: list[dict],
) -> dict[str, Any]:
    """
    新闻类搜索结果评估。

    要求：
    - 至少 3 条结果
    - 至少 2 个独立域名
    """

    if len(results) < 3:
        return {
            "enough": False,
            "reason": "新闻结果数量不足",
            "missing": "需要至少3条新闻来源",
        }

    domains: set[str] = set()

    for result in results:
        domain = _get_domain(
            result.get("url", "")
        )

        if domain:
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