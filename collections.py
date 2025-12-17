from typing import List, Callable, Optional, Iterator
class NodeCollection:
    def __init__(self):
        self._list = []
    def Add(self, n): self._list.append(n)
    def Remove(self, n): self._list.remove(n)
    def Find(self, pred: Callable):
        for x in self._list:
            if pred(x): return x
        return None
    def FindIndex(self, pred: Callable):
        for i,x in enumerate(self._list):
            if pred(x): return i
        return -1
    def __len__(self): return len(self._list)
    def __getitem__(self, idx): return self._list[idx]
    def __iter__(self): return iter(self._list)
class LineCollection(NodeCollection): pass
class ConductorCollection(NodeCollection): pass
class ConfigurationCollection(NodeCollection): pass
class TrfCollection(NodeCollection): pass
