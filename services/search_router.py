import re

REALTIME_KEYWORDS = (
    "天气", "气温", "温度", "降雨", "下雨", "下雪", "湿度", "风速", "空气质量",
    "最新", "今天", "今日","明天","明日", "现在", "当前", "实时", "近期", "刚刚",
    "新闻", "股价", "股票价格", "汇率", "比分", "赛程", "价格", "现任", "政策",
    "weather", "temperature", "latest", "today","tomorrow", "current", "live", "news",
    "stock price", "exchange rate", "score", "schedule", "price",
)

STABLE_KEYWORDS = (
    "翻译", "改写", "润色", "总结", "写一", "代码", "数学", "解释", "怎么做",
    "translate", "rewrite", "summarize", "code", "math", "explain",
)


def should_search(prompt: str) -> bool:
    """纯本地路由，避免回答前额外调用一次模型。"""
    text = (prompt or "").strip().lower()
    if not text:
        return False
    if any(k in text for k in REALTIME_KEYWORDS):
        return True
    if re.search(r"\b(20\d{2}|19\d{2})\b", text) and any(k in text for k in ("发生", "发布", "价格", "数据", "新闻")):
        return True
    if any(k in text for k in STABLE_KEYWORDS):
        return False
    return False
