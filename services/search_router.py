from openai import OpenAI

from config import SEARCH_ROUTER_MODEL
from models import model_options


def should_search(prompt: str) -> bool:
    if not prompt or not prompt.strip():
        return False

    normalized_prompt = prompt.strip().lower()

    # 简繁体基础统一
    normalized_prompt = normalized_prompt.translate(
        str.maketrans(
            {
                "氣": "气",
                "溫": "温",
                "濕": "湿",
                "風": "风",
            }
        )
    )

    print(f"🔎 路由收到的问题：{normalized_prompt!r}")

    # 明确需要实时数据的问题，直接联网
    weather_keywords = (
        "天气",
        "气温",
        "温度",
        "降雨",
        "下雨",
        "雷雨",
        "暴雨",
        "下雪",
        "湿度",
        "风速",
        "weather",
        "temperature",
        "rain",
        "snow",
    )

    if any(keyword in normalized_prompt for keyword in weather_keywords):
        print("🌦️ 命中天气硬规则，直接联网")
        return True

    print("🤖 未命中天气硬规则，交给 AI 判断")

    try:
        cfg = model_options[SEARCH_ROUTER_MODEL]

        if not cfg.get("key"):
            print("⚠️ 搜索路由模型 API Key 未配置")
            return False

        client = OpenAI(
            api_key=cfg["key"],
            base_url=cfg["base_url"],
        )

        response = client.chat.completions.create(
            model=cfg["model"],
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是联网搜索路由器，只判断用户的问题是否需要"
                        "实时互联网信息。\n"
                        "只允许输出 YES 或 NO，不得输出其他内容。\n\n"
                        "以下问题必须输出 YES：\n"
                        "1. 天气、气温、降雨、空气质量；\n"
                        "2. 当前时间、今天日期；\n"
                        "3. 最新新闻、今日事件、近期发布；\n"
                        "4. 当前股价、汇率、比分、商品价格；\n"
                        "5. 当前职位、现任人物或近期政策。\n\n"
                        "普通历史、数学、写作和稳定常识输出 NO。\n"
                        "不确定时输出 YES。"
                    ),
                },
                {
                    "role": "user",
                    "content": normalized_prompt,
                },
            ],
            temperature=0,
            max_tokens=10,
        )

        raw_result = response.choices[0].message.content or ""
        decision = raw_result.strip().upper()

        print(f"🤖 AI 路由原始输出：{raw_result!r}")
        print(f"🤖 AI 路由标准化输出：{decision!r}")

        if decision.startswith("YES"):
            print("🌐 AI 判断：需要联网")
            return True

        if decision.startswith("NO"):
            print("📚 AI 判断：不需要联网")
            return False

        print("⚠️ AI 输出无法识别，保守选择联网")
        return True

    except Exception as error:
        print(f"⚠️ 联网判断失败：{error}")
        # 判断器出错时，对实时性不明确的问题保守联网
        return True