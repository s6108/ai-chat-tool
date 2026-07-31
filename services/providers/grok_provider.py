from __future__ import annotations

from services.providers.openai_compatible_provider import (
    OpenAICompatibleProvider,
)


class GrokProvider(OpenAICompatibleProvider):
    """Grok adapter using xAI OpenAI-compatible API."""