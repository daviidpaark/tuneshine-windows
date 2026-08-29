import json
import logging
import os
import sys
import winreg
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("tuneshine-windows.config")

APP_NAME = "TuneshineWindows"
DEFAULT_CONFIG = {
    "hub_url": "http://localhost:8585",
    "mode": "hub",  # "hub" or "direct"
    "enabled": True,
    "clear_delay": 2.0,
    "service_name": "Windows Media",
    "autostart": False,
}


def get_config_dir() -> Path:
    """Returns the configuration directory (%APPDATA%/tuneshine-windows or local)."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        config_dir = Path(appdata) / "tuneshine-windows"
    else:
        config_dir = Path(__file__).parent
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_path() -> Path:
    return get_config_dir() / "config.json"


class Config:
    def __init__(self):
        self.config_path = get_config_path()
        self.data: Dict[str, Any] = DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self.data.update(saved)
                logger.info(f"Loaded configuration from {self.config_path}")
            except Exception as e:
                logger.error(f"Error loading config file: {e}, using defaults")
        else:
            self.save()

    def save(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
            logger.info(f"Saved configuration to {self.config_path}")
        except Exception as e:
            logger.error(f"Error saving config file: {e}")

    @property
    def hub_url(self) -> str:
        url = self.data.get("hub_url", DEFAULT_CONFIG["hub_url"]).strip()
        return url.rstrip("/")

    @hub_url.setter
    def hub_url(self, value: str):
        self.data["hub_url"] = value.strip().rstrip("/")
        self.save()

    @property
    def mode(self) -> str:
        return str(self.data.get("mode", "hub")).lower()

    @mode.setter
    def mode(self, value: str):
        self.data["mode"] = value.strip().lower()
        self.save()

    @property
    def enabled(self) -> bool:
        return bool(self.data.get("enabled", True))

    @enabled.setter
    def enabled(self, value: bool):
        self.data["enabled"] = value
        self.save()

    @property
    def clear_delay(self) -> float:
        return float(self.data.get("clear_delay", 2.0))

    @property
    def service_name(self) -> str:
        return str(self.data.get("service_name", "Windows Media"))

    @property
    def autostart(self) -> bool:
        return bool(self.data.get("autostart", False))

    @autostart.setter
    def autostart(self, value: bool):
        self.data["autostart"] = value
        self.save()
        self.sync_autostart_registry(value)

    def sync_autostart_registry(self, enable: bool):
        """Adds or removes the startup registry key in HKCU."""
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                if enable:
                    # Point to pythonw.exe or the current script
                    python_exe = sys.executable
                    pythonw_exe = Path(python_exe).parent / "pythonw.exe"
                    main_script = Path(__file__).parent / "main.py"
                    
                    if pythonw_exe.exists():
                        cmd = f'"{pythonw_exe}" "{main_script}"'
                    else:
                        cmd = f'"{python_exe}" "{main_script}"'

                    winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
                    logger.info(f"Registered Windows autostart: {cmd}")
                else:
                    try:
                        winreg.DeleteValue(key, APP_NAME)
                        logger.info("Removed Windows autostart entry")
                    except FileNotFoundError:
                        pass
        except Exception as e:
            logger.error(f"Failed to update autostart registry: {e}")
