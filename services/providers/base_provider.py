from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any

from services.model_config import ModelConfig


class BaseProvider(ABC):
    """Common interface implemented by every model provider."""

    def __init__(self, config: ModelConfig) -> None:
        self.config = config

    @abstractmethod
    def stream_chat(
        self,
        *,
        messages: list[dict[str, Any]],
        max_tokens: int = 1200,
        temperature: float = 0.7,
    ) -> Iterator[str]:
        """Yield response text chunks from the provider."""
        raise NotImplementedError
