import logging
import threading
from typing import Optional, Callable
from PIL import Image
import pystray
from pystray import MenuItem as item

from config import Config
from generate_icon import generate_square_icon

logger = logging.getLogger("tuneshine-windows.tray")


def create_default_icon(is_playing: bool = False, is_paused: bool = False) -> Image.Image:
    return generate_square_icon(is_playing=is_playing, is_paused=is_paused, size=64)


class TrayApp:
    def __init__(
        self,
        config: Config,
        on_open_dashboard: Callable[[], None],
        on_toggle_enabled: Callable[[bool], None],
        on_exit: Callable[[], None],
    ):
        self.config = config
        self.on_open_dashboard = on_open_dashboard
        self.on_toggle_enabled = on_toggle_enabled
        self.on_exit_callback = on_exit

        self.current_status_text = "Idle"
        self.current_track_text = "No track playing"

        self.icon = pystray.Icon(
            name="TuneshineWindows",
            icon=create_default_icon(is_playing=False),
            title="Tuneshine Windows (Idle)",
            menu=self._build_menu(),
        )

    def _build_menu(self) -> pystray.Menu:
        mode_label = "Hub" if self.config.mode == "hub" else "Direct"

        items = [
            item("Open Dashboard", lambda *args: self.on_open_dashboard(), default=True),
            item(lambda text: f"Status: {self.current_status_text} ({mode_label})", lambda: None, enabled=False),
            item(lambda text: f"Track: {self.current_track_text[:35]}", lambda: None, enabled=False),
            pystray.Menu.SEPARATOR,
            item(
                "Sync Enabled",
                lambda icon, it: self._toggle_sync(not it.checked),
                checked=lambda it: self.config.enabled,
            ),
            pystray.Menu.SEPARATOR,
            item("Exit", self._exit),
        ]

        return pystray.Menu(*items)

    def _toggle_sync(self, enabled: bool):
        self.config.enabled = enabled
        self.on_toggle_enabled(enabled)
        self.icon.menu = self._build_menu()

    def update_state(
        self,
        is_playing: bool,
        is_paused: bool,
        track_summary: str,
        hub_error: Optional[str] = None,
    ):
        """Updates the tray icon color, tooltip, and menu state."""
        if not self.config.enabled:
            self.current_status_text = "Sync Disabled"
            self.current_track_text = "Paused by user"
            tooltip = "Tuneshine Sync: Disabled"
        elif hub_error:
            self.current_status_text = "Hub Error"
            self.current_track_text = track_summary[:35]
            tooltip = f"Tuneshine: {hub_error[:40]}"
        elif is_playing:
            self.current_status_text = "Syncing"
            self.current_track_text = track_summary[:35]
            tooltip = f"Tuneshine: {track_summary}"
        elif is_paused:
            self.current_status_text = "Paused"
            self.current_track_text = track_summary[:35]
            tooltip = "Tuneshine: Paused"
        else:
            self.current_status_text = "Idle"
            self.current_track_text = "No active playback"
            tooltip = "Tuneshine: Idle"

        self.icon.icon = create_default_icon(is_playing=is_playing, is_paused=is_paused)
        self.icon.title = tooltip[:64]
        self.icon.menu = self._build_menu()

    def run(self):
        self.icon.run()

    def _exit(self, icon, item):
        self.icon.stop()
        if self.on_exit_callback:
            self.on_exit_callback()
