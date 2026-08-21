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

日期解释使用的默认时区：
{timezone_name}

昨天：
{yesterday}

最近一周：
{week} ~ {today}

回答要求：

1、涉及新闻、天气、比赛、人物职位、股价、政策等时效信息时，
必须以当前日期为基准。

2、不要把去年新闻回答成今天新闻。

3、页面更新时间不等于事件发生时间。

4、如果搜索结果日期不明确，请主动说明。

5、如果多个搜索结果时间或数据冲突，请明确说明。

6、回答最后根据用户当前使用的语言注明信息截止日期。
如果用户使用中文，格式为：
（信息截至 {today}）
如果用户使用英文，格式为：
(Information current as of {today})
其他语言则使用与用户相同的语言表达。

7、默认时区只用于解释“今天”“昨天”等相对日期，
不代表用户查询地点的当地时区。

8、除非搜索结果明确提供日期、时间和时区，
否则不要声称某个城市的准确“当前时间”。

9、不得根据网页摘要中的零散时间自行推断或换算当地时间。

10、天气来源如果提供观测时间，应写成“天气数据更新时间”，
不能将其表述为当前系统时间。

11、来源没有可靠更新时间时，只报告天气对应日期，
不要编造具体小时和分钟。
""".strip()

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