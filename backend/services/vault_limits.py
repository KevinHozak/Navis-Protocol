"""Explicit bounded budget for exhaustive Drive operations; no freshness cache."""
import os
from services.vault_access import VaultAccessError


def scan_timeout_seconds(env=None):
    value = (os.environ if env is None else env).get("NAVIS_MCP_SCAN_TIMEOUT_SECONDS", "10")
    if not isinstance(value, str) or not 1 <= len(value) <= 3 or not value.isascii() or not value.isdecimal():
        raise VaultAccessError("invalid_configuration")
    seconds = int(value)
    if not 1 <= seconds <= 120:
        raise VaultAccessError("invalid_configuration")
    return seconds
