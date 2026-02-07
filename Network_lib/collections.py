from typing import List, Callable, Optional, Iterator
class SimpleCollection:
    def __init__(self):
        self._list = []

    def Add(self, obj):
        self._list.append(obj)

    def Remove(self, obj):
        self._list.remove(obj)

    def __len__(self):
        return len(self._list)

    def __iter__(self):
        return iter(self._list)

    def __getitem__(self, i):
        return self._list[i]

class NodeCollection(SimpleCollection):
    def __init__(self):
        super().__init__()
        self._by_idx = {}

    def Add(self, n):
        if n.idx in self._by_idx:
            raise ValueError(f"Duplicate node idx {n.idx}")
        self._by_idx[n.idx] = n
        self._list.append(n)

    def Remove(self, n):
        self._list.remove(n)
        del self._by_idx[n.idx]

    def Find(self, pred):
        return next((x for x in self._list if pred(x)), None)

    def GetByIdx(self, idx):
        return self._by_idx.get(idx)

class LineCollection(NodeCollection): pass
class ConductorCollection(SimpleCollection): pass
class ConfigurationCollection(SimpleCollection): pass
class TrfCollection(SimpleCollection): pass
