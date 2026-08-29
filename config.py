import json
import logging
import os
import sys
import winreg
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("tuneshine-windows.config")

APP_NAME = "TuneshineWindows"
APP_VERSION = "0.3.2"
DEFAULT_CONFIG = {
    "hub_url": "http://localhost:8585",
    "mode": "hub",  # "hub" or "direct"
    "enabled": True,
    "start_in_tray": True,
    "clear_delay": 2.0,
    "service_name": "Spotify",
    "autostart": False,
    "filter_mode": "off",  # "off", "blacklist", "whitelist"
    "blacklist": [],
    "whitelist": [],
    "detected_apps": {},
}

KNOWN_APP_NAMES = {
    "spotify.exe": "Spotify",
    "spotify": "Spotify",
    "chrome.exe": "Google Chrome",
    "msedge.exe": "Microsoft Edge",
    "firefox.exe": "Mozilla Firefox",
    "brave.exe": "Brave Browser",
    "opera.exe": "Opera",
    "opera_gx.exe": "Opera GX",
    "vivaldi.exe": "Vivaldi",
    "vlc.exe": "VLC Media Player",
    "foobar2000.exe": "foobar2000",
    "tidal.exe": "TIDAL",
    "deezer.exe": "Deezer",
    "musicbee.exe": "MusicBee",
    "plezy.exe": "Plezy",
    "plex.exe": "Plex",
    "plex": "Plex",
    "mpv.exe": "MPV",
    "mpv": "MPV",
    "fladder.exe": "Fladder",
    "fladder": "Fladder",
    "cider.exe": "Cider (Apple Music)",
    "aimp.exe": "AIMP",
    "winamp.exe": "Winamp",
    "wmplayer.exe": "Windows Media Player",
    "itunes.exe": "iTunes",
    "discord.exe": "Discord",
    "audacity.exe": "Audacity",
    "telegram.exe": "Telegram",
    "plexamp.exe": "Plexamp",
    "dopamine.exe": "Dopamine",
}


def get_friendly_app_name(app_id: str) -> str:
    """Translates a Windows App ID / exe name into a clean user-friendly name."""
    if not app_id:
        return "Unknown App"

    clean_id = app_id.strip()
    lower_id = clean_id.lower()

    if lower_id in KNOWN_APP_NAMES:
        return KNOWN_APP_NAMES[lower_id]

    base_lower = Path(lower_id).name
    if base_lower in KNOWN_APP_NAMES:
        return KNOWN_APP_NAMES[base_lower]

    stem_lower = Path(base_lower).stem
    if stem_lower in KNOWN_APP_NAMES:
        return KNOWN_APP_NAMES[stem_lower]

    # UWP / Package Family Name heuristics
    if "applemusic" in lower_id:
        return "Apple Music"
    if "zunemusic" in lower_id or "microsoft.zunemusic" in lower_id:
        return "Windows Media Player"
    if "spotify" in lower_id:
        return "Spotify"
    if "amazonmusic" in lower_id:
        return "Amazon Music"
    if "tidal" in lower_id:
        return "TIDAL"

    if "!" in clean_id:
        part = clean_id.split("!")[0]
        if "_" in part:
            part = part.split("_")[0]
        if "." in part:
            part = part.split(".")[-1]
        if part:
            return part

    name = Path(clean_id).name
    if name.lower().endswith(".exe"):
        name = name[:-4]

    return name.replace("_", " ").replace("-", " ").strip().title()


def get_config_dir() -> Path:
    """Returns the configuration directory (%APPDATA%/tuneshine-windows or local)."""
    # Check if a local config.json exists next to script/exe or in cwd (portable mode)
    local_dir = Path(__file__).parent.resolve()
    if (local_dir / "config.json").exists():
        return local_dir

    cwd_dir = Path.cwd().resolve()
    if (cwd_dir / "config.json").exists():
        return cwd_dir

    appdata = os.environ.get("APPDATA")
    if appdata:
        config_dir = Path(appdata) / "tuneshine-windows"
    else:
        config_dir = local_dir
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_path() -> Path:
    return get_config_dir() / "config.json"


class Config:
    def __init__(self, custom_path: Path = None):
        self.config_path = custom_path or get_config_path()
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
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
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
        return str(self.data.get("mode", DEFAULT_CONFIG["mode"])).lower()

    @mode.setter
    def mode(self, value: str):
        self.data["mode"] = value.strip().lower()
        self.save()

    @property
    def enabled(self) -> bool:
        return bool(self.data.get("enabled", DEFAULT_CONFIG["enabled"]))

    @enabled.setter
    def enabled(self, value: bool):
        self.data["enabled"] = bool(value)
        self.save()

    @property
    def start_in_tray(self) -> bool:
        return bool(self.data.get("start_in_tray", DEFAULT_CONFIG["start_in_tray"]))

    @start_in_tray.setter
    def start_in_tray(self, value: bool):
        self.data["start_in_tray"] = bool(value)
        self.save()

    @property
    def clear_delay(self) -> float:
        return float(self.data.get("clear_delay", DEFAULT_CONFIG["clear_delay"]))

    @clear_delay.setter
    def clear_delay(self, value: float):
        self.data["clear_delay"] = float(value)
        self.save()

    @property
    def service_name(self) -> str:
        return str(self.data.get("service_name", DEFAULT_CONFIG["service_name"]))

    @service_name.setter
    def service_name(self, value: str):
        self.data["service_name"] = str(value)
        self.save()

    @property
    def autostart(self) -> bool:
        return bool(self.data.get("autostart", DEFAULT_CONFIG["autostart"]))

    @autostart.setter
    def autostart(self, value: bool):
        self.data["autostart"] = bool(value)
        self.save()
        self.sync_autostart_registry(value)

    def sync_autostart_registry(self, enable: bool):
        """Adds or removes the startup registry key in HKCU."""
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                if enable:
                    if getattr(sys, "frozen", False):
                        cmd = f'"{sys.executable}"'
                    else:
                        python_exe = sys.executable
                        pythonw_exe = Path(python_exe).parent / "pythonw.exe"
                        main_script = (Path(__file__).parent / "main.py").resolve()
                        
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

    @property
    def filter_mode(self) -> str:
        mode = str(self.data.get("filter_mode", DEFAULT_CONFIG["filter_mode"])).lower()
        if mode == "blacklist":
            return "block"
        if mode == "whitelist":
            return "allow"
        return mode

    @filter_mode.setter
    def filter_mode(self, value: str):
        val = str(value).strip().lower()
        if val in ("blacklist", "block"):
            val = "block"
        elif val in ("whitelist", "allow"):
            val = "allow"
        else:
            val = "off"
        self.data["filter_mode"] = val
        self.save()

    @property
    def blacklist(self) -> list:
        return list(self.data.get("blacklist", DEFAULT_CONFIG["blacklist"]))

    @blacklist.setter
    def blacklist(self, value: list):
        self.data["blacklist"] = list(value)
        self.save()

    @property
    def blocked_apps(self) -> list:
        return self.blacklist

    @blocked_apps.setter
    def blocked_apps(self, value: list):
        self.blacklist = value

    @property
    def whitelist(self) -> list:
        return list(self.data.get("whitelist", DEFAULT_CONFIG["whitelist"]))

    @whitelist.setter
    def whitelist(self, value: list):
        self.data["whitelist"] = list(value)
        self.save()

    @property
    def allowed_apps(self) -> list:
        return self.whitelist

    @allowed_apps.setter
    def allowed_apps(self, value: list):
        self.whitelist = value

    @property
    def detected_apps(self) -> dict:
        return dict(self.data.get("detected_apps", DEFAULT_CONFIG["detected_apps"]))

    @detected_apps.setter
    def detected_apps(self, value: dict):
        self.data["detected_apps"] = dict(value)
        self.save()

    def is_app_allowed(self, app_id: str) -> bool:
        """Determines whether a media session from app_id is permitted based on current filter settings."""
        if not app_id:
            return True

        mode = self.filter_mode
        if mode in ("off", "none", "all"):
            return True

        def _normalize_app(name: str) -> set:
            if not name:
                return set()
            s = name.strip().lower()
            base = Path(s).name.lower()
            if base.endswith(".exe"):
                base = base[:-4]

            tokens = {s, base, base.replace(" ", "")}
            if "!" in base:
                for p in base.split("!"):
                    if p and p not in ("exe", "app", "win"):
                        tokens.add(p)
                        tokens.add(p.replace(" ", ""))
            if "_" in base:
                for p in base.split("_"):
                    if p and p not in ("exe", "app", "win"):
                        tokens.add(p)
                        tokens.add(p.replace(" ", ""))
            if "." in base:
                for p in base.split("."):
                    if p and p not in ("exe", "app", "win"):
                        tokens.add(p)
                        tokens.add(p.replace(" ", ""))
            return {t for t in tokens if t and t not in ("exe", "app", "win")}

        def _match(rule: str, target: str) -> bool:
            if not rule or not target:
                return False
            r_set = _normalize_app(rule)
            t_set = _normalize_app(target)
            if r_set.intersection(t_set):
                return True
            for r in r_set:
                if len(r) >= 4:
                    for t in t_set:
                        if len(t) >= 4 and (r in t or t in r):
                            return True
            return False

        if mode in ("block", "blacklist"):
            for blocked in self.blocked_apps:
                if _match(blocked, app_id):
                    return False
            return True

        if mode in ("allow", "whitelist"):
            for allowed in self.allowed_apps:
                if _match(allowed, app_id):
                    return True
            return False

        return True

    def register_detected_app(self, app_id: str, display_name: str = None) -> bool:
        """Registers or updates an app in the detected_apps registry. Returns True if new/updated."""
        if not app_id:
            return False

        clean_id = app_id.strip()
        detected = dict(self.data.get("detected_apps", {}))

        # Check if already present under same or normalized key
        existing_key = None
        for k in detected.keys():
            if k.lower() == clean_id.lower():
                existing_key = k
                break

        key = existing_key or clean_id
        is_new = key not in detected

        # If already registered and no custom display name change, do not rewrite disk
        if not is_new and not display_name:
            return False

        resolved_display = display_name or detected.get(key, {}).get("display_name") or get_friendly_app_name(clean_id)

        from datetime import datetime
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        detected[key] = {
            "app_id": key,
            "display_name": resolved_display,
            "last_seen": now_str,
        }
        self.data["detected_apps"] = detected
        self.save()
        return is_new

    def remove_detected_app(self, app_id: str):
        """Removes an app from detected_apps and any blacklist/whitelist."""
        if not app_id:
            return
        clean_id = app_id.strip().lower()

        detected = {k: v for k, v in self.detected_apps.items() if k.strip().lower() != clean_id}
        self.data["detected_apps"] = detected

        self.data["whitelist"] = [x for x in self.whitelist if x.strip().lower() != clean_id]
        self.data["blacklist"] = [x for x in self.blacklist if x.strip().lower() != clean_id]
        self.save()

    def set_app_filter_state(self, app_id: str, state: str):
        """Sets an app's filter status: 'allow'/'whitelist', 'block'/'blacklist', or 'neutral'/'default'."""
        if not app_id:
            return
        clean_id = app_id.strip()
        lower_id = clean_id.lower()

        self.register_detected_app(clean_id)

        w_list = [x for x in self.whitelist if x.strip().lower() != lower_id]
        b_list = [x for x in self.blacklist if x.strip().lower() != lower_id]

        state_val = str(state).strip().lower()
        if state_val in ("allow", "whitelist"):
            w_list.append(clean_id)
        elif state_val in ("block", "blacklist"):
            b_list.append(clean_id)

        self.data["whitelist"] = w_list
        self.data["blacklist"] = b_list
        self.save()

    def open_config_folder(self):
        """Opens the folder containing config.json in Windows Explorer."""
        folder = str(self.config_path.parent)
        try:
            if sys.platform == "win32":
                os.startfile(folder)
            else:
                import subprocess
                subprocess.Popen(["explorer", folder])
        except Exception as e:
            logger.error(f"Failed to open config folder: {e}")

