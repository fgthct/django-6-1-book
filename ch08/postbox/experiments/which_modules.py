import sys
from concurrent import interpreters

mods = sys.argv[1:]
for m in mods:
    interp = interpreters.create()
    try:
        interp.exec(f"import {m}")
        print(f"{m:14} ok")
    except interpreters.ExecutionFailed as e:
        msg = str(e.excinfo.msg) if hasattr(e, "excinfo") else str(e)
        key = [l for l in msg.splitlines() if "does not support" in l]
        short = key[-1].strip() if key else msg.strip().splitlines()[-1]
        print(f"{m:14} {e.excinfo.type.__name__}: {short}")
    finally:
        interp.close()
