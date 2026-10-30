"""Bounded active Portal review state; no filesystem or logging interface."""
from copy import deepcopy
from pathlib import Path
import re
import threading
import time
import uuid

_LOCK = threading.Lock()
_ITEMS = {}
_TIMERS = {}
_clock = time.monotonic
LIMIT = 32
TTL = 600

def _key(root, identity):
    if not isinstance(identity, str) or not re.fullmatch(r"portal-[a-f0-9]{32}", identity):
        raise ValueError("Invalid Portal preview.")
    return (str(Path(root).resolve()), identity)

def _drop_locked(key):
    _ITEMS.pop(key, None)
    timer = _TIMERS.pop(key, None)
    if timer is not None:
        timer.cancel()

def _timed_drop(key):
    with _LOCK:
        _drop_locked(key)

def _expire():
    now = _clock()
    for key in [k for k, value in _ITEMS.items() if value[0] <= now]:
        _drop_locked(key)

def reserve(root):
    with _LOCK:
        _expire()
        if len(_ITEMS) >= LIMIT:
            raise ValueError("Too many active Portal previews. Discard one first.")
        identity = "portal-" + uuid.uuid4().hex
        key = _key(root, identity)
        _ITEMS[key] = (_clock() + TTL, None)
        timer = threading.Timer(TTL, _timed_drop, args=(key,))
        timer.daemon = True
        _TIMERS[key] = timer
        timer.start()
        return identity

def fill(root, identity, record):
    with _LOCK:
        _expire()
        key = _key(root, identity)
        if key not in _ITEMS:
            raise ValueError("Portal preview expired. No retry was made.")
        _ITEMS[key] = (_ITEMS[key][0], deepcopy(record))

def read(root, identity):
    with _LOCK:
        _expire()
        value = _ITEMS.get(_key(root, identity))
        if value is None or value[1] is None:
            raise ValueError("Portal preview expired or unavailable in this session.")
        return deepcopy(value[1])

def discard(root, identity):
    with _LOCK:
        _expire()
        _drop_locked(_key(root, identity))
