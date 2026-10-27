"""Import-safe relative path containment shared by HTTP and local adapters."""
import os
from urllib.parse import unquote


class VaultPathError(ValueError):
    pass


def resolve_relative_path(root, file_path):
    if not file_path or not str(file_path).strip():
        raise VaultPathError("Invalid Vault path: path cannot be empty")
    normalized = unquote(str(file_path)).strip().replace("\\", "/")
    if normalized.startswith("/") or ":" in normalized:
        raise VaultPathError("Invalid Vault path: absolute or drive-qualified paths not allowed")
    parts = [p for p in normalized.split("/") if p]
    if not parts or any(p in (".", "..") for p in parts):
        raise VaultPathError("Invalid Vault path: traversal or invalid segments not allowed")
    root_path = os.path.abspath(root)
    full_path = os.path.abspath(os.path.join(root_path, *parts))
    for base, target, message in (
        (root_path, full_path, "Invalid Vault path: path escapes Vault root"),
        (os.path.realpath(root_path), os.path.realpath(full_path),
         "Invalid Vault path: path escapes Vault root via symlink"),
    ):
        try:
            if os.path.commonpath([os.path.normcase(base), os.path.normcase(target)]) != os.path.normcase(base):
                raise VaultPathError(message)
        except ValueError as error:
            if isinstance(error, VaultPathError):
                raise
            raise VaultPathError("Invalid Vault path: path on different drive") from None
    if os.path.normcase(os.path.realpath(full_path)) == os.path.normcase(os.path.realpath(root_path)):
        raise VaultPathError("Invalid Vault path: Vault root is not a file path")
    return full_path
