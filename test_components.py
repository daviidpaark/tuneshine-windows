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


if __name__ == "__main__":
    unittest.main()
