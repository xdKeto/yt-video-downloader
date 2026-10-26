from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .errors import AppError, classify_download_error
from .models import DownloadProgress, ProbeResult, VideoMetadata
from .quality import choose_selector, normalize_format, selection_from_info


ProgressCallback = Callable[[DownloadProgress], None]


class YtDlpAdapter:
    """The only module that imports and configures yt-dlp."""

    def __init__(self, config, progress: ProgressCallback | None = None) -> None:
        self.config = config
        self.progress = progress or (lambda _: None)
        self._output_candidates: list[Path] = []
        try:
            import yt_dlp
        except ImportError as exc:
            raise AppError("yt-dlp is not installed. Install dependencies with: python -m pip install -e .", 3) from exc
        self.yt_dlp = yt_dlp

    def probe(self, url: str, profile: str = "maximum") -> ProbeResult:
        options = self._base_options(profile)
        options.update({"quiet": True, "skip_download": True, "noplaylist": True})
        try:
            with self.yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as exc:
            raise classify_download_error(str(exc)) from exc
        if not isinstance(info, dict):
            raise AppError("yt-dlp returned no metadata for this URL.", 6)
        formats = tuple(normalize_format(item) for item in info.get("formats", []) if isinstance(item, dict))
        selector, explanation = choose_selector(profile, formats)
        metadata = VideoMetadata(
            video_id=str(info.get("id") or "unknown"),
            title=str(info.get("title") or "Untitled"),
            channel=info.get("channel") or info.get("uploader"),
            upload_date=info.get("upload_date"),
            duration=info.get("duration"),
            live_status=info.get("live_status"),
            is_live=bool(info.get("is_live")),
            was_live=bool(info.get("was_live") or info.get("live_status") == "was_live"),
            webpage_url=str(info.get("webpage_url") or url),
        )
        selection = selection_from_info(info, selector, explanation, profile)
        return ProbeResult(metadata, formats, selection, info)

    def download(self, url: str, profile: str, output_dir: Path, temp_dir: Path, output_template: str = "%(upload_date)s - %(title)s [%(id)s].%(ext)s", selector: str | None = None, merge_output_format: str | None = None) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        temp_dir.mkdir(parents=True, exist_ok=True)
        output_dir = output_dir.resolve()
        temp_dir = temp_dir.resolve()
        output_template_path = Path(output_template)
        outtmpl = output_template_path if output_template_path.is_absolute() else output_dir / output_template_path
        before = self._file_snapshot(output_dir)
        self._output_candidates = []
        options = self._base_options(profile)
        options.update({
            "format": selector or (MAXIMUM_SELECTOR if profile == "maximum" else MP4_SELECTOR),
            "outtmpl": str(outtmpl),
            "paths": {"home": str(output_dir), "temp": str(temp_dir)},
            "continuedl": True,
            "retries": self.config.retries,
            "fragment_retries": self.config.fragment_retries,
            "keepvideo": False,
            "noplaylist": True,
            "merge_output_format": merge_output_format or ("mkv" if profile == "maximum" else "mp4"),
            "progress_hooks": [self._progress_hook],
            "postprocessor_hooks": [self._postprocessor_hook],
            "quiet": True,
            "no_warnings": True,
        })
        try:
            with self.yt_dlp.YoutubeDL(options) as ydl:
                code = ydl.download([url])
                if code not in (None, 0):
                    raise AppError(f"yt-dlp exited with status {code}.", 8)
        except AppError:
            raise
        except Exception as exc:
            raise classify_download_error(str(exc)) from exc
        for candidate in reversed(self._output_candidates):
            resolved = self._within_directory(candidate, output_dir)
            if resolved and resolved.is_file() and self._is_media_file(resolved):
                return resolved
        matches = sorted(
            (path for path in self._file_snapshot(output_dir)
             if self._is_media_file(path) and self._file_changed(path, before)),
            key=lambda p: p.stat().st_mtime_ns,
            reverse=True,
        )
        if matches:
            return matches[0]
        raise AppError("yt-dlp reported success but the output file could not be found.", 9)

    def ffprobe(self, path: Path) -> dict[str, Any]:
        executable = self._executable("ffprobe", self.config.ffmpeg_location)
        if not executable:
            raise AppError("ffprobe is required to verify downloads. Install ffmpeg and ensure ffprobe.exe is on PATH.", 3)
        command = [executable, "-v", "error", "-show_entries", "format=duration:stream=index,codec_type,codec_name,height", "-of", "json", str(path)]
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            import json
            return json.loads(result.stdout)
        except (OSError, subprocess.CalledProcessError, ValueError) as exc:
            raise AppError(f"ffprobe could not read {path}: {exc}", 8) from exc

    def _base_options(self, profile: str) -> dict[str, Any]:
        options: dict[str, Any] = {
            "noplaylist": True,
            "retries": self.config.retries,
            "fragment_retries": self.config.fragment_retries,
            "concurrent_fragment_downloads": 1,
        }
        if self.config.ffmpeg_location:
            options["ffmpeg_location"] = self.config.ffmpeg_location
        if getattr(self.config, "cookies_from_browser", None):
            options["cookiesfrombrowser"] = self.config.cookies_from_browser
        if getattr(self.config, "js_runtime", None):
            options["js_runtimes"] = {self.config.js_runtime: {}}
        return options

    def _progress_hook(self, data: dict[str, Any]) -> None:
        self._remember_output_paths(data)
        status = data.get("status", "")
        phase = "downloading" if status in {"downloading", "finished"} else status
        total = data.get("total_bytes") or data.get("total_bytes_estimate")
        done = data.get("downloaded_bytes")
        percent = (done / total * 100) if total and done is not None else None
        self.progress(DownloadProgress(phase, status, percent, data.get("speed"), data.get("eta"), data.get("format_id")))

    def _postprocessor_hook(self, data: dict[str, Any]) -> None:
        self._remember_output_paths(data)
        self.progress(DownloadProgress("merging", data.get("status", ""), None, None, None, None))

    def _remember_output_paths(self, data: dict[str, Any]) -> None:
        """Capture filenames yt-dlp exposes while downloading and post-processing."""
        values: list[Any] = [data.get("filename"), data.get("filepath")]
        info = data.get("info_dict")
        if isinstance(info, dict):
            values.extend((info.get("filepath"), info.get("_filename"), info.get("filename")))
            requested = info.get("requested_downloads")
            if isinstance(requested, list):
                values.extend(item.get("filepath") for item in requested if isinstance(item, dict))
        for value in values:
            if isinstance(value, (str, Path)):
                path = Path(value).expanduser()
                if path not in self._output_candidates:
                    self._output_candidates.append(path)

    @staticmethod
    def _file_snapshot(directory: Path) -> dict[Path, tuple[int, int]]:
        snapshot: dict[Path, tuple[int, int]] = {}
        for path in directory.rglob("*"):
            if path.is_file():
                try:
                    stat = path.stat()
                except OSError:
                    continue
                snapshot[path] = (stat.st_size, stat.st_mtime_ns)
        return snapshot

    @staticmethod
    def _file_changed(path: Path, before: dict[Path, tuple[int, int]]) -> bool:
        if path not in before:
            return True
        try:
            stat = path.stat()
            return (stat.st_size, stat.st_mtime_ns) != before[path] and stat.st_size > 0
        except OSError:
            return False

    @staticmethod
    def _is_media_file(path: Path) -> bool:
        return path.suffix.lower() in {".mkv", ".mp4", ".webm", ".mov", ".m4v", ".avi", ".flv", ".ts", ".3gp"}

    @staticmethod
    def _within_directory(path: Path, directory: Path) -> Path | None:
        candidates = [path] if path.is_absolute() else [Path.cwd() / path, directory / path]
        safe_candidates: list[Path] = []
        for candidate in candidates:
            try:
                resolved = candidate.resolve()
                resolved.relative_to(directory.resolve())
            except (OSError, ValueError):
                continue
            if resolved.is_file():
                return resolved
            safe_candidates.append(resolved)
        return safe_candidates[0] if safe_candidates else None

    @staticmethod
    def _executable(name: str, location: str | None = None) -> str | None:
        if location:
            configured = Path(location)
            candidates = [configured / f"{name}.exe", configured / name] if configured.is_dir() else [configured]
            for candidate in candidates:
                if candidate.exists():
                    return str(candidate)
        return shutil.which(name) or shutil.which(f"{name}.exe")


MAXIMUM_SELECTOR = "bv+ba/b"
MP4_SELECTOR = "bv[ext=mp4]+ba[ext=m4a]/b[ext=mp4]"

