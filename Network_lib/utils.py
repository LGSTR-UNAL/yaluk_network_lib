
def get_short_path(path):
    import platform
    import ctypes
    from pathlib import Path
    p = Path(path).resolve()

    # If NOT Windows → return normal full path
    if platform.system() != "Windows":
        return str(p)

    # Windows → try to get 8.3 short path
    buffer = ctypes.create_unicode_buffer(260)
    result = ctypes.windll.kernel32.GetShortPathNameW(
        str(p),
        buffer,
        260
    )

    if result == 0:
        print(f"Warning: Could not get short path for {p}. Error code: {ctypes.GetLastError()}")
        # 8.3 name not available → return normal path
        return str(p)

    return buffer.value

