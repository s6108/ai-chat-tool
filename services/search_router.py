import re


UTILITY_REALTIME_KEYWORDS = (
    "天气", "气温", "温度", "降雨", "下雨", "下雪", "湿度", "风速", "空气质量",
    "台风", "天气预报", "股价", "股票价格", "股票", "行情", "指数",
    "收盘价", "开盘价", "最高价", "最低价", "涨停价", "跌停价", "涨跌幅",
    "成交价", "成交量", "市值", "市盈率", "分红", "财报", "上证", "深证",
    "港股", "美股", "A股", "基金净值", "汇率",
    "币价", "价格", "油价", "金价", "比分", "赛程", "排名", "航班", "火车",
    "时刻表", "weather", "temperature", "forecast", "stock", "stock price",
    "exchange rate", "price", "score", "schedule", "flight", "timetable",
)

NEWS_CURRENT_AFFAIRS_KEYWORDS = (
    "新闻", "时事", "国际局势", "国际新闻", "突发", "最新消息", "政治", "政府",
    "总统", "首相", "选举", "议会", "外交", "战争", "冲突", "军事", "制裁",
    "地缘政治", "社会事件", "白宫", "国会", "联合国", "欧盟", "北约",
    "news", "breaking news", "current affairs", "politics", "government",
    "president", "prime minister", "election", "parliament", "diplomacy",
    "war", "conflict", "military", "sanction", "geopolitics",
)

GENERAL_REALTIME_KEYWORDS = (
    "最新", "今天", "今日", "明天", "明日", "昨天", "昨日", "前天",
    "本周", "上周", "这周", "本月", "上月", "今年", "去年",
    "现在", "当前", "实时", "近期",
    "刚刚", "现任", "政策", "发布", "上市", "更新", "版本", "目前",
    "latest", "today", "tomorrow", "current", "live", "recent", "released",
    "updated", "version",
)

STABLE_TASK_KEYWORDS = (
    "翻译", "改写", "润色", "总结", "写一", "代码", "数学", "解释", "怎么做",
    "证明", "计算", "创作", "translate", "rewrite", "summarize", "code", "math",
    "explain", "prove", "calculate",
)


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def classify_search_intent(prompt: str) -> str:
    """返回 none / utility / news / general_realtime。"""
    text = (prompt or "").strip().lower()
    if not text:
        return "none"

    # 明确的天气、股票、汇率等优先归类为普通实时查询。
    if _contains_any(text, UTILITY_REALTIME_KEYWORDS):
        return "utility"

    # 新闻、政治、国际时事单独归类，供自动路由使用国际模型。
    if _contains_any(text, NEWS_CURRENT_AFFAIRS_KEYWORDS):
        return "news"

    if _contains_any(text, GENERAL_REALTIME_KEYWORDS):
        return "general_realtime"

    # 明确年份 + 发生/发布/价格/数据/新闻，通常需要搜索核实。
    if re.search(r"\b(20\d{2}|19\d{2})\b", text) and _contains_any(
        text,
        ("发生", "发布", "价格", "数据", "新闻", "政策", "选举", "上市"),
    ):
        return "general_realtime"

    if _contains_any(text, STABLE_TASK_KEYWORDS):
        return "none"

    return "none"


def should_search(prompt: str) -> bool:
    """保持原有调用接口不变。"""
    return classify_search_intent(prompt) != "none"
