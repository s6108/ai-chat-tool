from __future__ import annotations

from services.providers.openai_compatible_provider import (
    OpenAICompatibleProvider,
)


class GeminiProvider(OpenAICompatibleProvider):
    """Gemini adapter using Google OpenAI Compatible API."""