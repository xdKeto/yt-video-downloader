from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import DownloadProgress, DownloadResult, ProbeResult


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "unknown"
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def render_probe(probe: ProbeResult) -> str:
    metadata = probe.metadata
    selection = probe.selection
    heights = sorted({f.height for f in probe.formats if f.height}, reverse=True)
    lines = [
        f"Title:       {metadata.title}",
        f"ID:          {metadata.video_id}",
        f"Channel:     {metadata.channel or 'unknown'}",
        f"Duration:    {format_duration(metadata.duration)}",
        f"Live state:  {metadata.live_status or ('live' if metadata.is_live else 'unknown')}",
        f"Available:   {', '.join(f'{h}p' for h in heights[:8]) or 'no video formats'}",
        f"Selector:    {selection.selector}",
        f"Selected:    {_selected_text(selection)}",
        f"Container:   {selection.container}",
        f"Explanation: {selection.explanation}",
    ]
    return "\n".join(lines)


def render_download_summary(probe: ProbeResult, result: DownloadResult) -> str:
    return "\n".join([
        f"Title:       {probe.metadata.title}",
        f"Selected:    {_selected_text(probe.selection)}",
        f"Verified:    {result.height or 'unknown'}p {result.video_codec or 'unknown'} video + {result.audio_codec or 'unknown'} audio",
        f"Output:      {result.path}",
    ])


def render_progress(progress: DownloadProgress) -> str:
    if progress.percent is not None:
        text = f"{progress.phase}: {progress.percent:5.1f}%"
    else:
        text = progress.phase
    if progress.speed:
        text += f" at {progress.speed}"
    if progress.eta:
        text += f" ETA {progress.eta}"
    return text


def render_json_probe(probe: ProbeResult) -> dict[str, Any]:
    return {
        "metadata": asdict(probe.metadata),
        "formats": [asdict(item) for item in probe.formats],
        "selection": asdict(probe.selection),
    }


def write_manifest(path: Path, probe: ProbeResult, result: DownloadResult, yt_dlp_version: str | None = None) -> Path:
    manifest = path.with_suffix(path.suffix + ".json")
    payload = {
        "url": probe.metadata.webpage_url,
        "video_id": probe.metadata.video_id,
        "title": probe.metadata.title,
        "selected": asdict(probe.selection),
        "verified": asdict(result),
        "yt_dlp_version": yt_dlp_version,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return manifest


def _selected_text(selection) -> str:
    if selection.video and selection.audio:
        video = selection.video
        audio = selection.audio
        height = f"{video.height}p" if video.height else "unknown height"
        return f"video {video.format_id} ({height}, {video.vcodec or 'unknown'}) + audio {audio.format_id} ({audio.ext or 'unknown'}, {audio.acodec or 'unknown'})"
    if selection.combined:
        c = selection.combined
        return f"format {c.format_id} ({c.height or 'unknown'}p, {c.vcodec or 'unknown'} + {c.acodec or 'unknown'})"
    return "no format selected"

