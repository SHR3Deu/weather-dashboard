from abc import ABC, abstractmethod


class Layer(ABC):

    name = "Layer"
    enabled = True

    @abstractmethod
    def draw(self, canvas, basemap):
        pass
