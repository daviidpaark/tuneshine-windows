import asyncio
import os
import unittest
from unittest.mock import AsyncMock, patch, MagicMock

from config import Config, DEFAULT_CONFIG
from hub_client import HubClient
from media_listener import TrackInfo
from generate_icon import generate_square_icon


class TestTuneshineWindows(unittest.TestCase):
    def test_config_defaults_and_properties(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_config_path = Path(tmpdir) / "config_props.json"
            config = Config(custom_path=tmp_config_path)
            self.assertTrue(config.hub_url.startswith("http"))
            self.assertTrue(config.enabled)
            self.assertTrue(config.start_in_tray)
            self.assertIn(config.mode, ["hub", "direct"])
            self.assertIsInstance(config.clear_delay, float)
            self.assertEqual(config.service_name, "Spotify")

            # Test hub_url setter stripping trailing slash
            config.hub_url = "http://192.168.1.50:8585/"
            self.assertEqual(config.hub_url, "http://192.168.1.50:8585")

            config.mode = "direct"
            self.assertEqual(config.mode, "direct")

            config.start_in_tray = False
            self.assertFalse(config.start_in_tray)
            config.start_in_tray = True
            self.assertTrue(config.start_in_tray)

            config.clear_delay = 3.5
            self.assertEqual(config.clear_delay, 3.5)

            config.service_name = "Spotify"
            self.assertEqual(config.service_name, "Spotify")

    def test_config_file_persistence(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_config_path = Path(tmpdir) / "test_config.json"
            cfg1 = Config(custom_path=tmp_config_path)
            cfg1.hub_url = "http://10.0.0.99:9000"
            cfg1.mode = "direct"
            cfg1.enabled = False
            cfg1.start_in_tray = False
            cfg1.clear_delay = 4.0
            cfg1.service_name = "TestPlayer"

            self.assertTrue(tmp_config_path.exists())

            # Load new instance from same file
            cfg2 = Config(custom_path=tmp_config_path)
            self.assertEqual(cfg2.hub_url, "http://10.0.0.99:9000")
            self.assertEqual(cfg2.mode, "direct")
            self.assertFalse(cfg2.enabled)
            self.assertFalse(cfg2.start_in_tray)
            self.assertEqual(cfg2.clear_delay, 4.0)
            self.assertEqual(cfg2.service_name, "TestPlayer")

    def test_webview_api_save_settings(self):
        import tempfile
        from pathlib import Path
        from ui_webview import WebViewApi
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_config_path = Path(tmpdir) / "webview_config.json"
            cfg = Config(custom_path=tmp_config_path)
            client = HubClient(cfg.hub_url, mode=cfg.mode)
            callback_called = False

            def on_changed():
                nonlocal callback_called
                callback_called = True

            api = WebViewApi(cfg, client, on_changed)
            res = api.save_settings({
                "hub_url": "http://192.168.1.200:8585/",
                "mode": "hub",
                "enabled": True,
                "start_in_tray": True,
                "autostart": False,
                "clear_delay": 1.5,
            })
            self.assertTrue(res.get("success"))
            self.assertTrue(callback_called)
            self.assertEqual(cfg.hub_url, "http://192.168.1.200:8585")
            self.assertEqual(cfg.clear_delay, 1.5)
            self.assertTrue(cfg.start_in_tray)

    def test_direct_mode_webp_conversion(self):
        from hub_client import convert_to_tuneshine_webp
        # Create a small dummy 100x100 PNG
        from PIL import Image
        import io
        img = Image.new("RGB", (100, 100), (255, 0, 0))
        png_buf = io.BytesIO()
        img.save(png_buf, format="PNG")
        png_bytes = png_buf.getvalue()

        webp_bytes = convert_to_tuneshine_webp(png_bytes)
        self.assertTrue(len(webp_bytes) > 0)
        self.assertTrue(webp_bytes.startswith(b"RIFF"))

        # Verify output size is 64x64
        with Image.open(io.BytesIO(webp_bytes)) as out_img:
            self.assertEqual(out_img.size, (64, 64))
            self.assertEqual(out_img.format, "WEBP")

    def test_track_info_summary(self):
        idle_track = TrackInfo(is_playing=False)
        self.assertEqual(idle_track.summary, "Idle / Paused")

        playing_track = TrackInfo(
            is_playing=True,
            title="Song Title",
            artist="Artist Name",
            album="Album Name",
        )
        self.assertEqual(playing_track.summary, "Song Title - Artist Name")

    def test_tray_icon_generation(self):
        img_idle = generate_square_icon(is_playing=False, is_paused=False)
        self.assertEqual(img_idle.size, (64, 64))

        img_playing = generate_square_icon(is_playing=True, is_paused=False)
        self.assertEqual(img_playing.size, (64, 64))

        img_paused = generate_square_icon(is_playing=False, is_paused=True)
        self.assertEqual(img_paused.size, (64, 64))

    def test_hub_client_hash_deduplication(self):
        async def run_test():
            client = HubClient("http://fake-hub:8585")
            dummy_img = b"fake-png-bytes"

            # Mock post method
            mock_response = MagicMock()
            mock_response.status_code = 200
            client.client.post = AsyncMock(return_value=mock_response)

            # First send -> should call client.post
            res1 = await client.send_playing(dummy_img, "Title", "Artist", "Album")
            self.assertTrue(res1)
            self.assertEqual(client.client.post.call_count, 1)

            # Second identical send -> should deduplicate without network call
            res2 = await client.send_playing(dummy_img, "Title", "Artist", "Album")
            self.assertTrue(res2)
            self.assertEqual(client.client.post.call_count, 1)

            # Send stopped
            client.client.delete = AsyncMock(return_value=mock_response)
            res_stop = await client.send_stopped()
            self.assertTrue(res_stop)
            self.assertEqual(client.client.delete.call_count, 1)
            self.assertFalse(client.is_currently_playing)

            await client.close()

        asyncio.run(run_test())

    def test_friendly_app_names(self):
        from config import get_friendly_app_name
        self.assertEqual(get_friendly_app_name("Spotify.exe"), "Spotify")
        self.assertEqual(get_friendly_app_name("spotify"), "Spotify")
        self.assertEqual(get_friendly_app_name("chrome.exe"), "Google Chrome")
        self.assertEqual(get_friendly_app_name("msedge.exe"), "Microsoft Edge")
        self.assertEqual(get_friendly_app_name("AppleInc.AppleMusicWin_8wekyb3d8bbwe!App"), "Apple Music")
        self.assertEqual(get_friendly_app_name("vlc.exe"), "VLC Media Player")
        self.assertEqual(get_friendly_app_name("foobar2000.exe"), "foobar2000")
        self.assertEqual(get_friendly_app_name("cider.exe"), "Cider (Apple Music)")
        self.assertEqual(get_friendly_app_name("my_custom_player.exe"), "My Custom Player")

    def test_config_filter_logic(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_config_path = Path(tmpdir) / "filter_config.json"
            cfg = Config(custom_path=tmp_config_path)

            self.assertEqual(cfg.filter_mode, "off")
            self.assertEqual(cfg.blacklist, [])
            self.assertEqual(cfg.whitelist, [])
            self.assertEqual(cfg.blocked_apps, [])
            self.assertEqual(cfg.allowed_apps, [])
            self.assertEqual(cfg.detected_apps, {})

            # In 'off' mode, all apps are allowed
            self.assertTrue(cfg.is_app_allowed("Spotify.exe"))
            self.assertTrue(cfg.is_app_allowed("chrome.exe"))

            # Test Block Mode (alias Blacklist)
            cfg.filter_mode = "block"
            cfg.blocked_apps = ["chrome.exe", "msedge.exe"]
            self.assertTrue(cfg.is_app_allowed("Spotify.exe"))
            self.assertTrue(cfg.is_app_allowed("foobar2000.exe"))
            self.assertFalse(cfg.is_app_allowed("chrome.exe"))
            self.assertFalse(cfg.is_app_allowed("CHROME.EXE"))
            self.assertFalse(cfg.is_app_allowed("chrome"))
            self.assertFalse(cfg.is_app_allowed("msedge.exe"))

            # Test Allow Mode (alias Whitelist)
            cfg.filter_mode = "allow"
            cfg.allowed_apps = ["Spotify.exe", "AppleInc.AppleMusicWin_8wekyb3d8bbwe!App"]
            self.assertTrue(cfg.is_app_allowed("Spotify.exe"))
            self.assertTrue(cfg.is_app_allowed("spotify"))
            self.assertTrue(cfg.is_app_allowed("AppleInc.AppleMusicWin_8wekyb3d8bbwe!App"))
            self.assertFalse(cfg.is_app_allowed("chrome.exe"))
            self.assertFalse(cfg.is_app_allowed("vlc.exe"))

    def test_app_registration_and_state_management(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_config_path = Path(tmpdir) / "reg_config.json"
            cfg = Config(custom_path=tmp_config_path)

            # Register apps
            is_new = cfg.register_detected_app("Spotify.exe")
            self.assertTrue(is_new)
            self.assertIn("Spotify.exe", cfg.detected_apps)
            self.assertEqual(cfg.detected_apps["Spotify.exe"]["display_name"], "Spotify")

            # Duplicate registration should not be marked as new
            is_new2 = cfg.register_detected_app("Spotify.exe")
            self.assertFalse(is_new2)

            # Set filter state: allow
            cfg.set_app_filter_state("Spotify.exe", "allow")
            self.assertIn("Spotify.exe", cfg.allowed_apps)
            self.assertNotIn("Spotify.exe", cfg.blocked_apps)

            # Set filter state: block
            cfg.set_app_filter_state("chrome.exe", "block")
            self.assertIn("chrome.exe", cfg.blocked_apps)
            self.assertNotIn("chrome.exe", cfg.allowed_apps)
            self.assertIn("chrome.exe", cfg.detected_apps)

            # Change to neutral
            cfg.set_app_filter_state("chrome.exe", "neutral")
            self.assertNotIn("chrome.exe", cfg.blocked_apps)
            self.assertNotIn("chrome.exe", cfg.allowed_apps)

            # Remove app
            cfg.remove_detected_app("Spotify.exe")
            self.assertNotIn("Spotify.exe", cfg.detected_apps)
            self.assertNotIn("Spotify.exe", cfg.allowed_apps)

    def test_webview_filter_api(self):
        import tempfile
        from pathlib import Path
        from ui_webview import WebViewApi
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_config_path = Path(tmpdir) / "wv_filter_config.json"
            cfg = Config(custom_path=tmp_config_path)
            client = HubClient(cfg.hub_url, mode=cfg.mode)
            changed_count = 0

            def on_changed():
                nonlocal changed_count
                changed_count += 1

            api = WebViewApi(cfg, client, on_changed)

            # Set filter mode
            res = api.set_filter_mode("block")
            self.assertTrue(res["success"])
            self.assertEqual(cfg.filter_mode, "block")
            self.assertEqual(changed_count, 1)

            # Add custom app
            res_add = api.add_custom_app("cider.exe")
            self.assertTrue(res_add["success"])
            self.assertIn("cider.exe", cfg.detected_apps)
            self.assertEqual(changed_count, 2)

            # Set filter state via API
            res_state = api.set_app_filter_state("cider.exe", "allow")
            self.assertTrue(res_state["success"])
            self.assertIn("cider.exe", cfg.allowed_apps)
            self.assertEqual(changed_count, 3)

            # Remove app via API
            res_rem = api.remove_app("cider.exe")
            self.assertTrue(res_rem["success"])
            self.assertNotIn("cider.exe", cfg.detected_apps)
            self.assertEqual(changed_count, 4)

            # Initial state should include filter keys
            init_state = api.get_initial_state()
            self.assertIn("filter_mode", init_state["config"])
            self.assertIn("whitelist", init_state["config"])
            self.assertIn("blacklist", init_state["config"])
            self.assertIn("allowed_apps", init_state["config"])
            self.assertIn("blocked_apps", init_state["config"])
            self.assertIn("detected_apps", init_state["config"])

    def test_media_listener_filter_callbacks(self):
        import tempfile
        from pathlib import Path
        from media_listener import MediaListener
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_config_path = Path(tmpdir) / "ml_filter_config.json"
            cfg = Config(custom_path=tmp_config_path)
            apps_changed_called = False

            def on_apps_changed():
                nonlocal apps_changed_called
                apps_changed_called = True

            async def dummy_update(track):
                pass

            listener = MediaListener(
                on_update=dummy_update,
                config=cfg,
                on_detected_apps_changed=on_apps_changed,
            )

            # Registering app through listener
            listener._register_app_if_new("plezy.exe")
            self.assertTrue(apps_changed_called)
            self.assertIn("plezy.exe", cfg.detected_apps)

    def test_uwp_and_app_matching(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_config_path = Path(tmpdir) / "uwp_config.json"
            cfg = Config(custom_path=tmp_config_path)

            # Block mode test
            cfg.filter_mode = "block"
            cfg.blocked_apps = ["plezy.exe", "Plex.exe"]
            self.assertFalse(cfg.is_app_allowed("plezy.exe"))
            self.assertFalse(cfg.is_app_allowed("Plezy"))
            self.assertFalse(cfg.is_app_allowed("plex.exe"))
            self.assertTrue(cfg.is_app_allowed("Spotify.exe"))
            self.assertTrue(cfg.is_app_allowed("SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify"))

            # Allow mode test with UWP app ID matching exe rule
            cfg.filter_mode = "allow"
            cfg.allowed_apps = ["Spotify.exe", "AppleInc.AppleMusicWin_8wekyb3d8bbwe!App"]
            self.assertTrue(cfg.is_app_allowed("Spotify.exe"))
            self.assertTrue(cfg.is_app_allowed("SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify"))
            self.assertTrue(cfg.is_app_allowed("AppleInc.AppleMusicWin_8wekyb3d8bbwe!App"))
            self.assertFalse(cfg.is_app_allowed("plezy.exe"))
            self.assertFalse(cfg.is_app_allowed("chrome.exe"))

    def test_listener_session_priority_and_selection(self):
        import tempfile
        from pathlib import Path
        from media_listener import MediaListener, STATUS_PLAYING
        import winrt.windows.media.control as wmc

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_config_path = Path(tmpdir) / "priority_config.json"
            cfg = Config(custom_path=tmp_config_path)
            cfg.filter_mode = "block"
            cfg.blocked_apps = ["plezy.exe"]

            updates = []
            async def on_update(track):
                updates.append(track)

            listener = MediaListener(on_update=on_update, config=cfg)
            listener._running = True

            # Create mock session factory
            def make_mock_session(app_id, is_playing, title, artist):
                mock_s = MagicMock()
                mock_s.source_app_user_model_id = app_id
                mock_pb = MagicMock()
                mock_pb.playback_status = STATUS_PLAYING if is_playing else wmc.GlobalSystemMediaTransportControlsSessionPlaybackStatus.PAUSED
                mock_s.get_playback_info.return_value = mock_pb

                mock_props = MagicMock()
                mock_props.title = title
                mock_props.artist = artist
                mock_props.album_title = "Test Album"
                mock_props.thumbnail = None
                mock_s.try_get_media_properties_async = AsyncMock(return_value=mock_props)
                return mock_s

            plezy_session = make_mock_session("plezy.exe", is_playing=True, title="Co-Pilot", artist="The Shield")
            spotify_session = make_mock_session("Spotify.exe", is_playing=True, title="Song A", artist="Artist A")

            # Mock session manager
            mock_mgr = MagicMock()
            listener.manager = mock_mgr

            # Scenario 1: Both Plezy (blocked, playing) and Spotify (allowed, playing) active
            mock_mgr.get_current_session.return_value = plezy_session
            mock_mgr.get_sessions.return_value = [plezy_session, spotify_session]

            asyncio.run(listener.check_current_media(trigger="test1"))
            self.assertEqual(len(updates), 1)
            self.assertEqual(updates[-1].app_id, "Spotify.exe")
            self.assertTrue(updates[-1].is_playing)
            self.assertEqual(updates[-1].title, "Song A")
            self.assertFalse(updates[-1].is_blocked)

            # Scenario 2: Spotify is PAUSED, Plezy is PLAYING (blocked)
            # Spotify (allowed paused) should take precedence over showing blocked Plezy
            spotify_paused = make_mock_session("Spotify.exe", is_playing=False, title="Song B", artist="Artist B")
            mock_mgr.get_sessions.return_value = [plezy_session, spotify_paused]
            listener.invalidate_state()

            asyncio.run(listener.check_current_media(trigger="test2"))
            self.assertEqual(updates[-1].app_id, "Spotify.exe")
            self.assertFalse(updates[-1].is_playing)
            self.assertEqual(updates[-1].title, "Song B")
            self.assertFalse(updates[-1].is_blocked)

            # Scenario 3: Only Plezy (blocked, playing) is active
            mock_mgr.get_current_session.return_value = plezy_session
            mock_mgr.get_sessions.return_value = [plezy_session]
            listener.invalidate_state()

            asyncio.run(listener.check_current_media(trigger="test3"))
            self.assertEqual(updates[-1].app_id, "plezy.exe")
            self.assertFalse(updates[-1].is_playing)
            self.assertTrue(updates[-1].is_blocked)
            # Scenario 5: Closed sessions should be ignored
            chrome_closed = make_mock_session("chrome.exe", is_playing=False, title="YouTube", artist="")
            chrome_closed.get_playback_info.return_value.playback_status = wmc.GlobalSystemMediaTransportControlsSessionPlaybackStatus.CLOSED
            mock_mgr.get_sessions.return_value = [chrome_closed, spotify_paused]
            listener.invalidate_state()

            asyncio.run(listener.check_current_media(trigger="test5"))
            self.assertEqual(updates[-1].app_id, "Spotify.exe")
            self.assertEqual(updates[-1].title, "Song B")

    def test_delayed_artwork_arrival(self):
        import tempfile
        from pathlib import Path
        from media_listener import MediaListener, STATUS_PLAYING
        import winrt.windows.media.control as wmc

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_config_path = Path(tmpdir) / "art_config.json"
            cfg = Config(custom_path=tmp_config_path)

            updates = []
            async def on_update(track):
                updates.append(track)

            listener = MediaListener(on_update=on_update, config=cfg)
            listener._running = True

            mock_s = MagicMock()
            mock_s.source_app_user_model_id = "Spotify.exe"
            mock_pb = MagicMock()
            mock_pb.playback_status = STATUS_PLAYING
            mock_s.get_playback_info.return_value = mock_pb

            # Stage 1: Song starts with title and artist, but thumbnail is None
            mock_props = MagicMock()
            mock_props.title = "Song With Delayed Art"
            mock_props.artist = "Artist Name"
            mock_props.album_title = "Album"
            mock_props.thumbnail = None
            mock_s.try_get_media_properties_async = AsyncMock(return_value=mock_props)

            mock_mgr = MagicMock()
            mock_mgr.get_current_session.return_value = mock_s
            mock_mgr.get_sessions.return_value = [mock_s]
            listener.manager = mock_mgr

            asyncio.run(listener.check_current_media(trigger="art_stage1"))
            self.assertEqual(len(updates), 1)
            self.assertIsNone(updates[-1].thumbnail_bytes)

            # Stage 2: 100ms later, thumbnail becomes available
            mock_thumb_ref = MagicMock()
            mock_props.thumbnail = mock_thumb_ref
            listener._read_thumbnail = AsyncMock(return_value=b"fake_jpeg_bytes")

            # Even though state_key is identical, it must emit update because art arrived!
            asyncio.run(listener.check_current_media(trigger="art_stage2"))
            self.assertEqual(len(updates), 2)
            self.assertEqual(updates[-1].thumbnail_bytes, b"fake_jpeg_bytes")


if __name__ == "__main__":
    unittest.main()


