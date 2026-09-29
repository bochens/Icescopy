import os
import sys


if sys.platform == "win32":
    candidate_dirs = []
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        candidate_dirs.append(meipass)
        candidate_dirs.append(os.path.join(meipass, "_internal"))
    executable_dir = os.path.dirname(sys.executable)
    if executable_dir:
        candidate_dirs.append(executable_dir)
        candidate_dirs.append(os.path.join(executable_dir, "_internal"))

    seen = set()
    for path in candidate_dirs:
        normalized = os.path.normpath(path)
        if not os.path.isdir(normalized) or normalized in seen:
            continue
        seen.add(normalized)
        try:
            os.add_dll_directory(normalized)
        except (AttributeError, FileNotFoundError, OSError):
            pass
