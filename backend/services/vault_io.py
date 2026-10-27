"""Read-only, noncreating handles that cooperate with Windows Drive sync."""
from contextlib import contextmanager
import os

if os.name == "nt":
    import ctypes
    from ctypes import wintypes
    import msvcrt

    _kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    _create_file = _kernel.CreateFileW
    _create_file.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                            wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    _create_file.restype = wintypes.HANDLE
    _close_handle = _kernel.CloseHandle
    _close_handle.argtypes = [wintypes.HANDLE]
    _close_handle.restype = wintypes.BOOL
    _INVALID = wintypes.HANDLE(-1).value


@contextmanager
def read_binary(path):
    if os.name != "nt":
        with path.open("rb") as stream:
            yield stream
        return
    # GENERIC_READ, SHARE_READ|WRITE|DELETE, OPEN_EXISTING, OPEN_REPARSE_POINT.
    # Share modes grant us no write rights. The caller checks all ancestor links
    # and pathname/handle identities; the final component is never followed.
    handle = _create_file(str(path), 0x80000000, 7, None, 3, 0x00200000, None)
    if handle == _INVALID:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        _close_handle(handle)
        raise
    try:
        # BufferedReader initialization queries the stream position. On Drive
        # that introduces a costly provider seek even for a readability probe.
        stream = os.fdopen(descriptor, "rb", buffering=0)
    except BaseException:
        os.close(descriptor)
        raise
    with stream:
        yield stream
