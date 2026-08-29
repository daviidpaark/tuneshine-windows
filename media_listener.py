import asyncio
import logging
from dataclasses import dataclass
from typing import Optional, Callable, Awaitable, List
import winrt.windows.media.control as wmc
import winrt.windows.storage.streams as wss

try:
    import winrt.windows.foundation.collections  # Required for IVectorView enumeration
except ImportError:
    pass

from config import Config

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
    is_blocked: bool = False

    @property
    def summary(self) -> str:
        if self.is_blocked:
            return f"Blocked: {self.app_id}" if self.app_id else "Blocked by filter"
        if not self.is_playing:
            return "Idle / Paused"
        if self.artist and self.title:
            return f"{self.title} - {self.artist}"
        return self.title or "Playing"


class MediaListener:
    def __init__(
        self,
        on_update: Callable[[TrackInfo], Awaitable[None]],
        config: Optional[Config] = None,
        on_detected_apps_changed: Optional[Callable[[], None]] = None,
    ):
        self.on_update = on_update
        self.config = config
        self.on_detected_apps_changed = on_detected_apps_changed
        self.manager: Optional[wmc.GlobalSystemMediaTransportControlsSessionManager] = None
        self.current_session: Optional[wmc.GlobalSystemMediaTransportControlsSession] = None
        self._attached_sessions: set = set()
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
            try:
                self.manager.add_sessions_changed(self._on_sessions_changed)
            except Exception:
                pass
            logger.info("WinRT Media Session Manager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize WinRT Session Manager: {e}")

        # Start the background sync loop (handles active polling & event fallbacks)
        asyncio.create_task(self._sync_loop())

    def stop(self):
        self._running = False
        self.current_session = None
        self._attached_sessions.clear()

    def _is_allowed(self, app_id: str) -> bool:
        if not self.config:
            return True
        return self.config.is_app_allowed(app_id)

    def _register_app_if_new(self, app_id: str):
        if not app_id or not self.config:
            return
        is_new = self.config.register_detected_app(app_id)
        if is_new and self.on_detected_apps_changed:
            try:
                self.on_detected_apps_changed()
            except Exception as e:
                logger.debug(f"Error in on_detected_apps_changed: {e}")

    def _scan_all_sessions(self) -> List[wmc.GlobalSystemMediaTransportControlsSession]:
        """Discovers all active media sessions and registers their app IDs dynamically."""
        sessions = []
        if not self.manager:
            return sessions
        try:
            raw_sessions = self.manager.get_sessions()
            if raw_sessions:
                for s in raw_sessions:
                    sessions.append(s)
                    app_id = s.source_app_user_model_id or ""
                    if app_id:
                        self._register_app_if_new(app_id)
                    self._attach_session_events(s)
        except Exception as e:
            logger.debug(f"Could not enumerate all sessions: {e}")
        return sessions

    def _on_sessions_changed(self, sender, args):
        """WinRT event handler for session list changed."""
        if self._loop and self._running:
            self._loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self.check_current_media(trigger="sessions_changed"))
            )

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
        if not session:
            return
        # Avoid duplicate attachments
        session_id = getattr(session, "source_app_user_model_id", None)
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
        """Inspects media sessions with filter awareness and smart fallback."""
        if not self._running:
            return

        if not self.manager:
            try:
                self.manager = await wmc.GlobalSystemMediaTransportControlsSessionManager.request_async()
            except Exception:
                return

        try:
            # 1. Scan and register all currently active sessions on Windows
            all_sessions = self._scan_all_sessions()

            current_session = self.manager.get_current_session()
            if current_session:
                curr_id = current_session.source_app_user_model_id or ""
                if curr_id:
                    self._register_app_if_new(curr_id)
                self._attach_session_events(current_session)

            # 2. Select the optimal allowed session
            chosen_session = None

            # Check if current_session is allowed and playing
            if current_session and self._is_allowed(current_session.source_app_user_model_id or ""):
                try:
                    pb = current_session.get_playback_info()
                    if pb and pb.playback_status == STATUS_PLAYING:
                        chosen_session = current_session
                except Exception:
                    pass

            # If current_session is not playing or is filtered out, scan for an allowed playing session
            if not chosen_session:
                for s in all_sessions:
                    app_id = s.source_app_user_model_id or ""
                    if self._is_allowed(app_id):
                        try:
                            pb = s.get_playback_info()
                            if pb and pb.playback_status == STATUS_PLAYING:
                                chosen_session = s
                                break
                        except Exception:
                            pass

            # If no playing allowed session found, fallback to current_session if it is allowed (e.g. paused)
            if not chosen_session and current_session and self._is_allowed(current_session.source_app_user_model_id or ""):
                chosen_session = current_session

            # 3. Handle chosen session state
            if chosen_session != self.current_session:
                self.current_session = chosen_session

            if not chosen_session:
                # Check if current_session is playing (but was filtered/blocked)
                blocked_track = None
                if current_session:
                    try:
                        pb = current_session.get_playback_info()
                        if pb and pb.playback_status == STATUS_PLAYING:
                            props = await current_session.try_get_media_properties_async()
                            curr_app = current_session.source_app_user_model_id or "Unknown"
                            blocked_track = TrackInfo(
                                is_playing=False,
                                is_blocked=True,
                                title=props.title if props else "Blocked Playback",
                                artist=props.artist if props else "",
                                album=props.album_title if props else "",
                                app_id=curr_app,
                            )
                    except Exception:
                        pass

                if blocked_track:
                    state_key = f"blocked:{blocked_track.app_id}:{blocked_track.artist}:{blocked_track.title}"
                    if state_key != self._last_state_key:
                        self._last_state_key = state_key
                        self.current_track = blocked_track
                        await self.on_update(blocked_track)
                    return

                track = TrackInfo(is_playing=False, is_blocked=False)
                state_key = "idle"
                if state_key != self._last_state_key:
                    self._last_state_key = state_key
                    self.current_track = track
                    await self.on_update(track)
                return

            # Check playback status of chosen session
            playback_info = chosen_session.get_playback_info()
            is_playing = bool(playback_info and playback_info.playback_status == STATUS_PLAYING)

            if not is_playing:
                track = TrackInfo(is_playing=False, app_id=chosen_session.source_app_user_model_id or "")
                state_key = f"paused:{track.app_id}"
                if state_key != self._last_state_key:
                    self._last_state_key = state_key
                    self.current_track = track
                    await self.on_update(track)
                return

            # Active playback - retrieve media properties
            props = await chosen_session.try_get_media_properties_async()
            if not props:
                return

            app_id = chosen_session.source_app_user_model_id or "Unknown"
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

            # Sleep 1.5s when playing, 3.5s when idle
            delay = 1.5 if self.current_track.is_playing else 3.5
            await asyncio.sleep(delay)
