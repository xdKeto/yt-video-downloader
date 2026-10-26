from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


class _FakeYoutubeDL:
    options: dict = {}

    def __init__(self, options):
        type(self).options = options

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def download(self, _urls):
        output_dir = Path(self.options["paths"]["home"])
        final_path = output_dir / "downloads" / "result.mkv"
        final_path.parent.mkdir(parents=True)
        final_path.write_bytes(b"merged media")
        for hook in self.options["postprocessor_hooks"]:
            hook({"status": "finished", "filename": str(final_path)})
        return 0


class YtDlpAdapterDownloadTests(unittest.TestCase):
    def test_returns_nested_output_reported_by_postprocessor(self):
        fake_yt_dlp = types.SimpleNamespace(YoutubeDL=_FakeYoutubeDL)
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(sys.modules, {"yt_dlp": fake_yt_dlp}):
            from stream_downloader.yt_dlp_adapter import YtDlpAdapter

            output_dir = Path(temp_dir) / "downloads"
            adapter = YtDlpAdapter(SimpleNamespace(retries=1, fragment_retries=1, ffmpeg_location=None, js_runtime=None))
            result = adapter.download("https://example.test/video", "maximum", output_dir, Path(temp_dir) / "temp")

            self.assertEqual(result, output_dir / "downloads" / "result.mkv")
            self.assertTrue(Path(_FakeYoutubeDL.options["outtmpl"]).is_absolute())


if __name__ == "__main__":
    unittest.main()
