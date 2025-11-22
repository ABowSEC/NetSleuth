
from collections import deque
from dataclasses import dataclass, asdict
from typing import Deque, Dict, Any, List
from datetime import datetime


@dataclass
class AnomalyEvent:
    timestamp: str
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str
    score: float
    extra: Dict[str, Any]


class AnomalyStore:
    def __init__(self, maxlen: int = 500):
        self._events: Deque[AnomalyEvent] = deque(maxlen=maxlen)

    def add(self, event: AnomalyEvent) -> None:
        self._events.appendleft(event)

    def list(self) -> List[Dict[str, Any]]:
        return [asdict(e) for e in self._events]


# global singleton for now
anomaly_store = AnomalyStore()
