"""Switches used to prove failure handling (Probes 4 and 5). Only reachable when DEV_TOOLS=1."""
import threading

_lock = threading.Lock()
_DEFAULT = {"geo_a_down": False, "geo_b_down": False, "email_fail": False}
_state = dict(_DEFAULT)


def get():
    with _lock:
        return dict(_state)


def update(changes):
    with _lock:
        _state.update({k: bool(v) for k, v in changes.items() if k in _DEFAULT and v is not None})
        return dict(_state)


def reset():
    with _lock:
        _state.update(_DEFAULT)
