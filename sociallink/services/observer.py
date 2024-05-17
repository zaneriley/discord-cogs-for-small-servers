from abc import ABC, abstractmethod


class Observer(ABC):
    @abstractmethod
    async def update(self, event_data):
        pass
