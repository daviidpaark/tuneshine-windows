import asyncio
import base64
import json
import logging
import os
import sys
import threading
from typing import Optional, Callable
import webview

from config import Config, APP_VERSION
from hub_client import HubClient
from media_listener import TrackInfo

logger = logging.getLogger("tuneshine-windows.ui")

_SCRIPT_DIR = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))


def _load_html_template() -> str:
    html_path = os.path.join(_SCRIPT_DIR, "dashboard.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


HTML_TEMPLATE = _load_html_template()


class WebViewApi:
    """Exposed Python API callable from JavaScript."""

    def __init__(self, config: Config, hub_client: HubClient, on_config_changed: Callable[[], None]):
        self.config = config
        self.hub_client = hub_client
        self.on_config_changed = on_config_changed
        self.latest_track_dict = {}

    def get_initial_state(self):
        return {
            "config": {
                "hub_url": self.config.hub_url,
                "mode": self.config.mode,
                "enabled": self.config.enabled,
                "start_in_tray": self.config.start_in_tray,
                "autostart": self.config.autostart,
                "clear_delay": self.config.clear_delay,
                "filter_mode": self.config.filter_mode,
                "blacklist": self.config.blacklist,
                "whitelist": self.config.whitelist,
                "blocked_apps": self.config.blocked_apps,
                "allowed_apps": self.config.allowed_apps,
                "detected_apps": self.config.detected_apps,
                "ignored_apps": self.config.ignored_apps,
            },
            "config_path": str(self.config.config_path),
            "config_filename": self.config.config_path.name,
            "version": APP_VERSION,
            "current_track": self.latest_track_dict,
        }

    def save_settings(self, data: dict):
        if not data:
            return {"success": False}
        if "hub_url" in data:
            self.config.hub_url = data.get("hub_url", self.config.hub_url).rstrip("/")
        if "mode" in data:
            self.config.mode = data.get("mode", self.config.mode)
        if "enabled" in data:
            self.config.enabled = bool(data.get("enabled", self.config.enabled))
        if "start_in_tray" in data:
            self.config.start_in_tray = bool(data.get("start_in_tray", self.config.start_in_tray))
        if "autostart" in data:
            self.config.autostart = bool(data.get("autostart", self.config.autostart))
        if "clear_delay" in data:
            self.config.clear_delay = float(data.get("clear_delay", self.config.clear_delay))
        if "filter_mode" in data:
            self.config.filter_mode = str(data.get("filter_mode", self.config.filter_mode))

        self.config.save()

        self.hub_client.update_url(self.config.hub_url, mode=self.config.mode)
        self.on_config_changed()
        return {"success": True, "path": str(self.config.config_path)}

    def set_filter_mode(self, mode: str):
        self.config.filter_mode = mode
        self.on_config_changed()
        return {"success": True, "filter_mode": self.config.filter_mode}

    def set_app_filter_state(self, app_id: str, state: str):
        self.config.set_app_filter_state(app_id, state)
        self.on_config_changed()
        return {
            "success": True,
            "whitelist": self.config.whitelist,
            "blacklist": self.config.blacklist,
            "allowed_apps": self.config.allowed_apps,
            "blocked_apps": self.config.blocked_apps,
            "detected_apps": self.config.detected_apps,
            "ignored_apps": self.config.ignored_apps,
        }

    def add_custom_app(self, app_id: str):
        clean_id = app_id.strip()
        if clean_id:
            self.config.unignore_app(clean_id)
            self.config.register_detected_app(clean_id)
            self.on_config_changed()
        return {
            "success": True,
            "detected_apps": self.config.detected_apps,
            "whitelist": self.config.whitelist,
            "blacklist": self.config.blacklist,
            "allowed_apps": self.config.allowed_apps,
            "blocked_apps": self.config.blocked_apps,
            "ignored_apps": self.config.ignored_apps,
        }

    def remove_app(self, app_id: str):
        self.config.remove_detected_app(app_id)
        self.on_config_changed()
        return {
            "success": True,
            "detected_apps": self.config.detected_apps,
            "whitelist": self.config.whitelist,
            "blacklist": self.config.blacklist,
            "allowed_apps": self.config.allowed_apps,
            "blocked_apps": self.config.blocked_apps,
            "ignored_apps": self.config.ignored_apps,
        }

    def restore_app(self, app_id: str):
        clean_id = app_id.strip()
        if clean_id:
            self.config.unignore_app(clean_id)
            self.config.register_detected_app(clean_id)
            self.on_config_changed()
        return {
            "success": True,
            "detected_apps": self.config.detected_apps,
            "whitelist": self.config.whitelist,
            "blacklist": self.config.blacklist,
            "allowed_apps": self.config.allowed_apps,
            "blocked_apps": self.config.blocked_apps,
            "ignored_apps": self.config.ignored_apps,
        }

    def open_config_folder(self):
        self.config.open_config_folder()
        return {"success": True}

    def test_connection(self, url: str):
        target = (url or self.config.hub_url).strip().rstrip("/")
        loop = asyncio.new_event_loop()
        try:
            client = HubClient(target, mode="hub")
            res = loop.run_until_complete(client.check_health())
            loop.run_until_complete(client.close())
            return res
        except Exception as e:
            return {"online": False, "error": str(e)}
        finally:
            loop.close()


class WebviewDashboard:
    def __init__(self, config: Config, hub_client: HubClient, on_config_changed: Callable[[], None]):
        self.config = config
        self.hub_client = hub_client
        self.on_config_changed = on_config_changed
        self.api = WebViewApi(config, hub_client, on_config_changed)
        self.window: Optional[webview.Window] = None

    def create_window(self, hidden: bool = False):
        self.window = webview.create_window(
            title="Tuneshine Windows",
            html=HTML_TEMPLATE,
            js_api=self.api,
            width=420,
            height=820,
            resizable=True,
            hidden=hidden,
            background_color="#0c0d12",
        )
        self.window.events.closing += self._on_closing

    def _on_closing(self):
        # Hide window instead of terminating application
        if self.window:
            self.window.hide()
            return False

    def show(self):
        if self.window:
            self.window.show()
            self.window.restore()

    def update_detected_apps(self):
        if self.window:
            try:
                data = {
                    "detected_apps": self.config.detected_apps,
                    "filter_mode": self.config.filter_mode,
                    "whitelist": self.config.whitelist,
                    "blacklist": self.config.blacklist,
                    "allowed_apps": self.config.allowed_apps,
                    "blocked_apps": self.config.blocked_apps,
                    "ignored_apps": self.config.ignored_apps,
                }
                js_code = f"if (window.updateDetectedApps) {{ window.updateDetectedApps({json.dumps(data)}); }}"
                self.window.evaluate_js(js_code)
            except Exception as e:
                logger.debug(f"Could not push detected apps to webview: {e}")

    def update_media(self, track: TrackInfo):
        art_b64 = ""
        if track.thumbnail_bytes:
            art_b64 = base64.b64encode(track.thumbnail_bytes).decode("utf-8")

        track_dict = {
            "is_playing": track.is_playing,
            "is_blocked": getattr(track, "is_blocked", False),
            "title": track.title,
            "artist": track.artist,
            "album": track.album,
            "app_id": track.app_id,
            "app_name": getattr(track, "app_name", "") or track.app_id,
            "art_b64": art_b64,
        }
        self.api.latest_track_dict = track_dict

        if self.window:
            try:
                js_code = f"if (window.updateTrackInfo) {{ window.updateTrackInfo({json.dumps(track_dict)}); }}"
                self.window.evaluate_js(js_code)
            except Exception as e:
                logger.debug(f"Could not push to webview: {e}")
