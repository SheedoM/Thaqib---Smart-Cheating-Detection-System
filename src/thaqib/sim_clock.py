import time

class SimClock:
    def __init__(self):
        self._start = time.monotonic()
        
    def now(self) -> float:
        return time.monotonic() - self._start
        
    def reset(self):
        self._start = time.monotonic()
