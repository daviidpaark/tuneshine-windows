import asyncio
import logging
import os
import sys
import threading
import time
from typing import Optional

import webview

from config import Config
from hub_client import HubClient
from media_listener import MediaListener, TrackInfo
from tray import TrayApp
from ui_webview import WebviewDashboard
import updater

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("tuneshine-windows")


class TuneshineWindowsApp:
    def __init__(self):
        self.config = Config()
        self.hub_client = HubClient(self.config.hub_url, mode=self.config.mode)
        self.listener = MediaListener(self.on_media_update)

        self.dashboard = WebviewDashboard(
            config=self.config,
            hub_client=self.hub_client,
            on_config_changed=self.on_config_changed,
        )

        self.tray = TrayApp(
            config=self.config,
            on_open_dashboard=self.show_dashboard,
            on_toggle_enabled=self.on_toggle_enabled,
            on_exit=self.stop,
        )

        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._clear_timer_task: Optional[asyncio.Task] = None

    def show_dashboard(self):
        self.dashboard.show()

    def on_config_changed(self):
        self.tray.update_state(
            is_playing=self.hub_client.is_currently_playing,
            is_paused=False,
            track_summary=self.listener.current_track.summary,
        )

    def on_toggle_enabled(self, enabled: bool):
        self.config.enabled = enabled
        if not enabled and self._loop:
            asyncio.run_coroutine_threadsafe(self.hub_client.send_stopped(), self._loop)
        self.on_config_changed()

    async def on_media_update(self, track: TrackInfo):
        """Called whenever Windows media session changes."""
        self.dashboard.update_media(track)

        if not self.config.enabled:
            return

        if track.is_playing and track.thumbnail_bytes:
            if self._clear_timer_task and not self._clear_timer_task.done():
                self._clear_timer_task.cancel()

            service_label = self.config.service_name
            if track.app_id:
                service_label = track.app_id.replace(".exe", "").capitalize()

            success = await self.hub_client.send_playing(
                image_bytes=track.thumbnail_bytes,
                title=track.title,
                artist=track.artist,
                album=track.album,
                service_name=service_label,
                item_id=f"{track.artist}-{track.title}",
            )

            self.tray.update_state(
                is_playing=True,
                is_paused=False,
                track_summary=track.summary,
                hub_error=self.hub_client.last_error if not success else None,
            )
        else:
            async def delayed_clear():
                try:
                    await asyncio.sleep(self.config.clear_delay)
                    await self.hub_client.send_stopped()
                except asyncio.CancelledError:
                    pass

            if self._clear_timer_task and not self._clear_timer_task.done():
                self._clear_timer_task.cancel()

            self._clear_timer_task = asyncio.create_task(delayed_clear())
            is_paused = bool(track.title)

            self.tray.update_state(
                is_playing=False,
                is_paused=is_paused,
                track_summary=track.summary,
                hub_error=None,
            )

    def _run_async_worker(self):
        """Background thread executing the asyncio event loop."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        async def _update_checker_loop():
            await asyncio.sleep(3.0)
            while self._running:
                try:
                    update_info = await updater.check_for_updates()
                    if update_info:
                        self.tray.set_available_update(update_info)
                except Exception as e:
                    logger.debug(f"Update check error: {e}")
                await asyncio.sleep(12 * 3600)

        async def _main():
            await self.listener.start()
            asyncio.create_task(_update_checker_loop())
            while self._running:
                await asyncio.sleep(1.0)
            await self.hub_client.close()

        try:
            self._loop.run_until_complete(_main())
        except Exception as e:
            logger.error(f"Error in async worker: {e}")
        finally:
            self._loop.close()

    def start(self):
        logger.info("Starting Tuneshine Windows Desktop Companion...")
        self._running = True

        # Start WinRT & networking background loop
        self._async_thread = threading.Thread(target=self._run_async_worker, daemon=True)
        self._async_thread.start()

        # Start system tray in background thread
        self._tray_thread = threading.Thread(target=self.tray.run, daemon=True)
        self._tray_thread.start()

        # Create WebView window
        self.dashboard.create_window()

        # Run WebView GUI loop on main thread
        webview.start(debug=False)

    def stop(self):
        logger.info("Stopping Tuneshine Windows Desktop Companion...")
        self._running = False
        self.listener.stop()
        if self.dashboard.window:
            self.dashboard.window.destroy()
        os._exit(0)


def main():
    app = TuneshineWindowsApp()
    try:
        app.start()
    except KeyboardInterrupt:
        app.stop()


if __name__ == "__main__":
    main()
