"""
hybx_timer-v1.0.0.py
Hybrid RobotiX — HybX Development System
Dale Weber <hybotix@hybridrobotix.io>

HybX timing utility. Measures elapsed time for any operation and
reports it clearly. Usable as a context manager, a decorator, or
a simple start/stop pair.

Usage examples
--------------
# Context manager (recommended):
from hybx_timer import HybXTimer

with HybXTimer("sensor init"):
    status = Bridge.call("get_sensor_status", timeout=120)
# prints: [timer] sensor init: 8.342s

# Decorator:
@HybXTimer.timed("build")
def run_build():
    ...
# prints: [timer] build: 12.105s

# Manual start/stop:
t = HybXTimer("flash")
t.start()
do_something()
elapsed = t.stop()   # prints and returns elapsed seconds

# Nested timers:
with HybXTimer("total init"):
    with HybXTimer("firmware upload"):
        ...
    with HybXTimer("sensor boot"):
        ...
# prints each individually plus total

# Inline measurement:
elapsed, result = HybXTimer.measure("bridge call", Bridge.call, "get_data")

License: MIT
"""

import time
import functools


class HybXTimer:
    """Timing utility for HybX operations.

    Measures elapsed wall-clock time and prints results in a consistent
    format: [timer] <label>: <elapsed>s

    All times are in seconds with millisecond precision (3 decimal places).
    Nested timers are indented for readability.
    """

    # Class-level depth tracking for nested timers
    _depth: int = 0

    def __init__(self, label: str, print_start: bool = False):
        """
        label       : Human-readable name for this operation.
        print_start : If True, print a line when the timer starts.
                      Useful for long operations where you want immediate
                      feedback that timing has begun.
        """
        self.label       = label
        self.print_start = print_start
        self._start: float | None = None
        self._elapsed: float | None = None

    # ------------------------------------------------------------------
    # Context manager interface
    # ------------------------------------------------------------------

    def __enter__(self) -> "HybXTimer":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.stop()
        return False   # never suppress exceptions

    # ------------------------------------------------------------------
    # Manual start / stop
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the timer."""
        self._start = time.monotonic()
        HybXTimer._depth += 1
        if self.print_start:
            indent = "  " * (HybXTimer._depth - 1)
            print(f"{indent}[timer] {self.label}: starting...")

    def stop(self) -> float:
        """Stop the timer, print elapsed time, and return elapsed seconds."""
        if self._start is None:
            raise RuntimeError(
                f"HybXTimer '{self.label}': stop() called before start()"
            )
        self._elapsed = time.monotonic() - self._start
        HybXTimer._depth = max(0, HybXTimer._depth - 1)
        indent = "  " * HybXTimer._depth
        print(f"{indent}[timer] {self.label}: {self._elapsed:.3f}s")
        return self._elapsed

    @property
    def elapsed(self) -> float | None:
        """Elapsed seconds, or None if the timer has not been stopped."""
        return self._elapsed

    # ------------------------------------------------------------------
    # Decorator interface
    # ------------------------------------------------------------------

    @staticmethod
    def timed(label: str, print_start: bool = False):
        """Decorator that times a function call.

        @HybXTimer.timed("my operation")
        def do_something():
            ...
        """
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                with HybXTimer(label, print_start=print_start):
                    return func(*args, **kwargs)
            return wrapper
        return decorator

    # ------------------------------------------------------------------
    # Convenience: time a single callable inline
    # ------------------------------------------------------------------

    @staticmethod
    def measure(label: str, fn, *args, **kwargs):
        """Time a single callable and return (elapsed_seconds, result).

        elapsed, result = HybXTimer.measure("bridge call", Bridge.call, "get_data")
        """
        t = HybXTimer(label)
        t.start()
        result = fn(*args, **kwargs)
        elapsed = t.stop()
        return elapsed, result
