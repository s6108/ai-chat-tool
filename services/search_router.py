from openai import OpenAI

from config import SEARCH_ROUTER_MODEL
from models import model_options


def should_search(prompt: str) -> bool:
    if not prompt or not prompt.strip():
        return False

    try:
        cfg = model_options[SEARCH_ROUTER_MODEL]

        if not cfg.get("key"):
            print("搜索路由模型的 API Key 未配置")
            return False

        client = OpenAI(
            base_url=cfg["base_url"],
            api_key=cfg["key"],
        )

        response = client.chat.completions.create(
            model=cfg["model"],
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一个联网搜索判断器。"
                        "判断用户的问题是否需要获取互联网最新信息才能准确回答。"
                        "涉及最新新闻、实时价格、天气、比赛结果、当前人物职位、"
                        "近期发布、政策变化等内容时回答 YES。"
                        "普通知识、写作、翻译、数学、编程基础问题回答 NO。"
                        "只能回答 YES 或 NO，不要解释。"
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            stream=False,
            temperature=0,
            max_tokens=5,
        )

        answer = response.choices[0].message.content or ""
        answer = answer.strip().upper()

        return answer.startswith("YES")

    except Exception as error:
        print(f"联网判断失败：{error}")
        return False