from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class VideoRequest:
    url: str
    profile: str = "maximum"
    min_height: int | None = None
    allow_lower_quality: bool = False


@dataclass(frozen=True)
class VideoMetadata:
    video_id: str
    title: str
    channel: str | None
    upload_date: str | None
    duration: float | None
    live_status: str | None
    is_live: bool
    was_live: bool
    webpage_url: str


@dataclass(frozen=True)
class FormatCandidate:
    format_id: str
    ext: str | None
    height: int | None
    fps: float | None
    vcodec: str | None
    acodec: str | None
    tbr: float | None
    format_note: str | None

    @property
    def video_only(self) -> bool:
        return self.vcodec not in (None, "none") and self.acodec in (None, "none")

    @property
    def audio_only(self) -> bool:
        return self.acodec not in (None, "none") and self.vcodec in (None, "none")


@dataclass(frozen=True)
class SelectionResult:
    selector: str
    video: FormatCandidate | None
    audio: FormatCandidate | None
    combined: FormatCandidate | None
    container: str
    explanation: str

    @property
    def height(self) -> int | None:
        return self.video.height if self.video else (self.combined.height if self.combined else None)


@dataclass(frozen=True)
class ProbeResult:
    metadata: VideoMetadata
    formats: tuple[FormatCandidate, ...]
    selection: SelectionResult
    raw_info: dict[str, Any] = field(repr=False, compare=False)


@dataclass(frozen=True)
class DownloadProgress:
    phase: str
    status: str
    percent: float | None = None
    speed: str | None = None
    eta: str | None = None
    format_id: str | None = None


@dataclass(frozen=True)
class DownloadResult:
    path: Path
    duration: float | None
    height: int | None
    video_codec: str | None
    audio_codec: str | None
    container: str | None


@dataclass(frozen=True)
class DiagnosticResult:
    name: str
    status: str
    detail: str
    fix: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

