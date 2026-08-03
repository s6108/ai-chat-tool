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
        
        

        response = self.client.responses.create(
            model=self.model,
            input=query,
            tools=[
                {
                    "type": "web_search",
                }
            ],
            store=False,
        )

        
        # 提取最终回答文本
        final_text = None

        for item in response.output:
            if getattr(item, "type", None) == "message":

                for content in item.content:

                    if getattr(content, "type", None) == "output_text":

                        final_text = content.text

        if final_text:
            return final_text.strip()

        return "未获取到有效回答。"

        

        # 备用方案
        output_text = getattr(
            response,
            "output_text",
            None,
        )

        if output_text:
            return output_text.strip()

        return "未获取到有效回答。"