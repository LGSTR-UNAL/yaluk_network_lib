from typing import List, Callable, Optional, Iterator
class NodeCollection:
    def __init__(self):
        self._list = []
        self._by_idx = {}

    def Add(self, n):
        if n.idx in self._by_idx:
            raise ValueError(f"Duplicate node idx {n.idx}")
        self._list.append(n)
        self._by_idx[n.idx] = n

    def Remove(self, n):
        self._list.remove(n)
        del self._by_idx[n.idx]

    def Find(self, pred):
        return next((x for x in self._list if pred(x)), None)

    def GetByIdx(self, idx):
        return self._by_idx.get(idx)

    def __len__(self):
        return len(self._list)

    def __getitem__(self, i):
        return self._list[i]

    def __iter__(self):
        return iter(self._list)
class LineCollection(NodeCollection): pass
class ConductorCollection(NodeCollection): pass
class ConfigurationCollection(NodeCollection): pass
class TrfCollection(NodeCollection): pass
