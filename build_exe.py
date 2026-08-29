import os
import subprocess
import sys
from pathlib import Path

import generate_icon


def build():
    root = Path(__file__).parent
    generate_icon.export_app_icons(str(root))

    icon_path = root / "icon.ico"
    main_py = root / "main.py"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconsole",
        "--onefile",
        "--name", "TuneshineWindows",
        f"--icon={icon_path}",
        "--hidden-import", "webview",
        "--hidden-import", "pystray",
        "--hidden-import", "winrt.windows.media.control",
        "--hidden-import", "winrt.windows.storage.streams",
        "--hidden-import", "winrt.windows.foundation",
        "--hidden-import", "winrt.runtime",
        "--hidden-import", "PIL",
        "--hidden-import", "httpx",
        "--hidden-import", "pythonnet",
        "--hidden-import", "clr_loader",
        "--collect-all", "webview",
        "--clean",
        "--noconfirm",
        str(main_py),
    ]

    print("Building standalone TuneshineWindows.exe...")
    print(" ".join(cmd))
    res = subprocess.run(cmd, cwd=str(root))
    if res.returncode == 0:
        print("\nSUCCESS! Executable built at: dist/TuneshineWindows.exe")
    else:
        print("\nBuild failed with code", res.returncode)


if __name__ == "__main__":
    build()
