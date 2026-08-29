import asyncio
import logging
from dataclasses import dataclass
from typing import Optional, Callable, Awaitable
import winrt.windows.media.control as wmc
import winrt.windows.storage.streams as wss

logger = logging.getLogger("tuneshine-windows.listener")

# WinRT Playback Status
STATUS_PLAYING = wmc.GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING


@dataclass
class TrackInfo:
    is_playing: bool
    title: str = ""
    artist: str = ""
    album: str = ""
    app_id: str = ""
    thumbnail_bytes: Optional[bytes] = None

    @property
    def summary(self) -> str:
        if not self.is_playing:
            return "Idle / Paused"
        if self.artist and self.title:
            return f"{self.title} - {self.artist}"
        return self.title or "Playing"


class MediaListener:
    def __init__(self, on_update: Callable[[TrackInfo], Awaitable[None]]):
        self.on_update = on_update
        self.manager: Optional[wmc.GlobalSystemMediaTransportControlsSessionManager] = None
        self.current_session: Optional[wmc.GlobalSystemMediaTransportControlsSession] = None
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._last_state_key: Optional[str] = None
        self.current_track: TrackInfo = TrackInfo(is_playing=False)

    async def start(self):
        """Initializes WinRT session manager and begins listening."""
        self._running = True
        self._loop = asyncio.get_running_loop()
        try:
            self.manager = await wmc.GlobalSystemMediaTransportControlsSessionManager.request_async()
            self.manager.add_current_session_changed(self._on_current_session_changed)
            logger.info("WinRT Media Session Manager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize WinRT Session Manager: {e}")

        # Start the background sync loop (handles active polling & event fallbacks)
        asyncio.create_task(self._sync_loop())

    def stop(self):
        self._running = False
        self.current_session = None

    def _on_current_session_changed(self, sender, args):
        """WinRT event handler for active media session change."""
        if self._loop and self._running:
            self._loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self.check_current_media(trigger="session_changed"))
            )

    def _on_media_properties_changed(self, sender, args):
        """WinRT event handler for title/artist/album/art changes."""
        if self._loop and self._running:
            self._loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self.check_current_media(trigger="props_changed"))
            )

    def _on_playback_info_changed(self, sender, args):
        """WinRT event handler for play/pause/stop changes."""
        if self._loop and self._running:
            self._loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self.check_current_media(trigger="playback_changed"))
            )

    def _attach_session_events(self, session: wmc.GlobalSystemMediaTransportControlsSession):
        try:
            session.add_media_properties_changed(self._on_media_properties_changed)
            session.add_playback_info_changed(self._on_playback_info_changed)
        except Exception as e:
            logger.debug(f"Could not attach session event listeners: {e}")

    async def _read_thumbnail(self, thumbnail_ref) -> Optional[bytes]:
        """Reads the IRandomAccessStreamReference into bytes."""
        if not thumbnail_ref:
            return None
        try:
            stream = await thumbnail_ref.open_read_async()
            if not stream or stream.size == 0:
                return None
            reader = wss.DataReader(stream)
            await reader.load_async(stream.size)
            buf = bytearray(stream.size)
            reader.read_bytes(buf)
            return bytes(buf)
        except Exception as e:
            logger.debug(f"Error reading thumbnail stream: {e}")
            return None

    async def check_current_media(self, trigger: str = "poll"):
        """Inspects the current media session and notifies callback on state change."""
        if not self._running:
            return

        if not self.manager:
            try:
                self.manager = await wmc.GlobalSystemMediaTransportControlsSessionManager.request_async()
            except Exception:
                return

        try:
            session = self.manager.get_current_session()
            if session != self.current_session:
                self.current_session = session
                if session:
                    self._attach_session_events(session)

            if not session:
                track = TrackInfo(is_playing=False)
                state_key = "idle"
                if state_key != self._last_state_key:
                    self._last_state_key = state_key
                    self.current_track = track
                    await self.on_update(track)
                return

            # Check playback status
            playback_info = session.get_playback_info()
            is_playing = bool(playback_info and playback_info.playback_status == STATUS_PLAYING)

            if not is_playing:
                track = TrackInfo(is_playing=False, app_id=session.source_app_user_model_id or "")
                state_key = f"paused:{track.app_id}"
                if state_key != self._last_state_key:
                    self._last_state_key = state_key
                    self.current_track = track
                    await self.on_update(track)
                return

            # Active playback - retrieve media properties
            props = await session.try_get_media_properties_async()
            if not props:
                return

            app_id = session.source_app_user_model_id or "Unknown"
            title = props.title or ""
            artist = props.artist or ""
            album = props.album_title or ""

            state_key = f"playing:{app_id}:{artist}:{title}:{album}"

            # Only fetch thumbnail if track changed or thumbnail was missing
            thumbnail_bytes = None
            if state_key != self._last_state_key or not self.current_track.thumbnail_bytes:
                thumbnail_bytes = await self._read_thumbnail(props.thumbnail)

            track = TrackInfo(
                is_playing=True,
                title=title,
                artist=artist,
                album=album,
                app_id=app_id,
                thumbnail_bytes=thumbnail_bytes if thumbnail_bytes is not None else self.current_track.thumbnail_bytes,
            )

            if state_key != self._last_state_key or thumbnail_bytes is not None:
                self._last_state_key = state_key
                self.current_track = track
                await self.on_update(track)

        except Exception as e:
            logger.debug(f"Exception checking media ({trigger}): {e}")

    async def _sync_loop(self):
        """Adaptive periodic sync loop to ensure display stays in sync."""
        while self._running:
            try:
                await self.check_current_media(trigger="loop")
            except Exception as e:
                logger.error(f"Error in sync loop: {e}")

            # Sleep 1.5s when playing, 4.0s when idle
            delay = 1.5 if self.current_track.is_playing else 4.0
            await asyncio.sleep(delay)
