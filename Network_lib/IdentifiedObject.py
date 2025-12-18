from dataclasses import dataclass
@dataclass
class IdentifyObject:
    uid: str
    name: str
    description: str = ""