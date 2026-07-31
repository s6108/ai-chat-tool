from __future__ import annotations

from services.providers.openai_compatible_provider import (
    OpenAICompatibleProvider,
)


class KimiProvider(OpenAICompatibleProvider):
    """Moonshot Kimi adapter using its OpenAI-compatible chat API."""
