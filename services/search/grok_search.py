from __future__ import annotations

from openai import OpenAI

from config import XAI_API_KEY
from services.search.base_search import BaseSearchProvider


class GrokSearchProvider(BaseSearchProvider):

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "grok-4.5",
    ):
        resolved_api_key = api_key or XAI_API_KEY

        if not resolved_api_key:
            raise ValueError("XAI_API_KEY 未配置")

        self.model = model

        self.client = OpenAI(
            api_key=resolved_api_key,
            base_url="https://api.x.ai/v1",
            timeout=60.0,
        )

    def search(
        self,
        query: str,
    ) -> str:

        if not query.strip():
            return ""

        print("🚀 Grok API request start")

        try:
            response = self.client.responses.create(
                model=self.model,
                input=query,
                tools=[
                    {
                        "type": "web_search",
                    }
                ],
                store=False,
                timeout=60,
            )

        except Exception as e:
            print(
                "Grok Search failed:",
                e,
            )
            return ""

        print("✅ Grok API response received")

        # =========================
        # 提取最终回答文本
        # 合并所有 output_text
        # =========================

        final_text = ""

        try:

            for item in response.output:

                if getattr(item, "type", None) != "message":
                    continue

                for content in item.content:

                    if getattr(content, "type", None) == "output_text":

                        text = (
                            getattr(content, "text", "")
                            or ""
                        ).strip()

                        if text:
                            final_text += (
                                text
                                + "\n\n"
                            )

            # Responses API 备用字段
            if not final_text:

                output_text = getattr(
                    response,
                    "output_text",
                    None,
                )

                if output_text:
                    final_text = output_text.strip()


        except Exception as e:

            print(
                "Grok parse failed:",
                e,
            )

            return ""


        if final_text.strip():

            print(
                "DEBUG GROK TEXT LENGTH:",
                len(final_text),
            )

            return final_text.strip()


        print(
            "DEBUG GROK EMPTY RESPONSE"
        )

        return ""