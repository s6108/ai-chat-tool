from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "America/Calgary"


def get_now(timezone_name=DEFAULT_TIMEZONE):
    """获取当前时间"""

    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = ZoneInfo("UTC")

    return datetime.now(tz)


def build_date_prompt(timezone_name=DEFAULT_TIMEZONE):
    """
    返回给大模型的日期规则
    """

    now = get_now(timezone_name)

    today = now.strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    week = (now - timedelta(days=7)).strftime("%Y-%m-%d")

    return f"""
【日期校验规则】

当前日期：
{today}

当前时区：
{timezone_name}

昨天：
{yesterday}

最近一周：
{week} ~ {today}

回答要求：

1、涉及新闻、天气、比赛、人物职位、股价、政策等时效信息时，
必须以当前日期为基准。

2、不要把去年新闻回答成今天新闻。

3、页面更新时间 ≠ 新闻发生日期。

4、如果搜索结果日期不明确，请说明。

5、如果多个搜索结果时间冲突，请说明存在冲突。

6、回答最后尽量注明：

（信息截至 {today}）
"""


def get_search_query(
    prompt: str,
    timezone_name=DEFAULT_TIMEZONE,
):
    """
    给搜索增加当前日期信息
    """

    now = get_now(timezone_name)

    today = now.strftime("%Y-%m-%d")

    return (
        f"{prompt}\n\n"
        f"Current Date: {today}\n"
        f"Timezone: {timezone_name}"
    )