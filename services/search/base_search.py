from abc import ABC, abstractmethod


class BaseSearchProvider(ABC):

    @abstractmethod
    def search(
        self,
        query: str,
    ) -> str:
        pass