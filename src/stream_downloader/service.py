from __future__ import annotations

import time
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

from .errors import AppError
from .models import DownloadResult, ProbeResult, VideoRequest
from .quality import max_video_height, validate_minimum


class DownloadService:
    def __init__(self, adapter, config, progress=None, sleeper: Callable[[float], None] = time.sleep) -> None:
        self.adapter = adapter
        self.config = config
        self.progress = progress or (lambda *_: None)
        self.sleeper = sleeper

    def inspect(self, request: VideoRequest) -> ProbeResult:
        if not request.url.startswith(("https://", "http://")):
            raise AppError("URL must start with http:// or https://.", 2)
        return self.adapter.probe(request.url, request.profile)

    def probe_until_ready(self, request: VideoRequest, wait_for_height: int | None = None, wait_timeout: float | None = None, wait_interval: float | None = None) -> ProbeResult:
        deadline = time.monotonic() + (wait_timeout if wait_timeout is not None else self.config.wait_timeout)
        interval = wait_interval if wait_interval is not None else self.config.wait_interval
        probe = self.inspect(request)
        target = wait_for_height or request.min_height
        if not target or (max_video_height(probe.formats) or 0) >= target:
            return probe
        while time.monotonic() < deadline:
            self.progress("waiting", max_video_height(probe.formats), target, deadline - time.monotonic())
            self.sleeper(min(interval, max(0, deadline - time.monotonic())))
            probe = self.inspect(request)
            if (max_video_height(probe.formats) or 0) >= target:
                return probe
        available = max_video_height(probe.formats)
        if request.allow_lower_quality:
            self.progress("fallback", available, target, 0)
            return probe
        duration = timedelta(seconds=max(0, int(wait_timeout or self.config.wait_timeout)))
        raise AppError(f"Requested {target}p was not exposed before the {duration} wait deadline. Highest available height is {available or 'unknown'}p. Retry later or use --allow-lower-quality.", 5)

    def download(self, request: VideoRequest, wait_for_height: int | None = None, wait_timeout: float | None = None, wait_interval: float | None = None) -> tuple[ProbeResult, DownloadResult]:
        probe = self.probe_until_ready(request, wait_for_height, wait_timeout, wait_interval)
        validate_minimum(probe.selection, request.min_height or wait_for_height, request.allow_lower_quality)
        self.progress("downloading", probe)
        path = self.adapter.download(
            request.url,
            request.profile,
            self.config.output_dir,
            self.config.temp_dir,
            selector=probe.selection.selector,
            merge_output_format=probe.selection.container,
        )
        facts = self.adapter.ffprobe(path)
        streams = facts.get("streams", [])
        video = next((s for s in streams if s.get("codec_type") == "video"), {})
        audio = next((s for s in streams if s.get("codec_type") == "audio"), {})
        height = video.get("height")
        requested_height = request.min_height or wait_for_height
        if requested_height and height and height < requested_height and not request.allow_lower_quality:
            raise AppError(f"The merged output is {height}p, below the requested {requested_height}p. The file was kept at {path}.", 5)
        duration = facts.get("format", {}).get("duration")
        return probe, DownloadResult(path, float(duration) if duration else None, height, video.get("codec_name"), audio.get("codec_name"), path.suffix.lstrip("."))

