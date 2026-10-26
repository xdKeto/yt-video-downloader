from __future__ import annotations

from collections.abc import Iterable

from .errors import AppError
from .models import FormatCandidate, SelectionResult


MAXIMUM_SELECTOR = "bv+ba/b"
MP4_SELECTOR = "bv[ext=mp4]+ba[ext=m4a]/b[ext=mp4]"


def normalize_format(item: dict) -> FormatCandidate:
    return FormatCandidate(
        format_id=str(item.get("format_id", "unknown")),
        ext=item.get("ext"),
        height=_number(item.get("height"), int),
        fps=_number(item.get("fps"), float),
        vcodec=item.get("vcodec"),
        acodec=item.get("acodec"),
        tbr=_number(item.get("tbr"), float),
        format_note=item.get("format_note"),
    )


def choose_selector(profile: str, formats: Iterable[FormatCandidate]) -> tuple[str, str]:
    formats = tuple(formats)
    best_height = max((f.height or 0 for f in formats if f.vcodec not in (None, "none")), default=0)
    mp4_at_best_height = any(
        f.ext == "mp4" and f.vcodec not in (None, "none") and (f.height or 0) >= best_height
        for f in formats
    ) and any(f.ext == "m4a" and f.acodec not in (None, "none") for f in formats)
    if profile == "mp4" and mp4_at_best_height:
        return MP4_SELECTOR, "MP4-compatible streams are available at the highest exposed video height."
    if profile == "mp4":
        return MAXIMUM_SELECTOR, "The MP4-compatible choice would reduce quality; using the maximum-quality streams and MKV."
    return MAXIMUM_SELECTOR, "Using the best exposed video stream plus the best audio stream, with a combined-format fallback."


def selection_from_info(info: dict, selector: str, explanation: str, profile: str) -> SelectionResult:
    requested = info.get("requested_formats") or []
    video_info = next((f for f in requested if f.get("vcodec") not in (None, "none")), None)
    audio_info = next((f for f in requested if f.get("acodec") not in (None, "none") and f.get("vcodec") in (None, "none")), None)
    if video_info and audio_info:
        video, audio = normalize_format(video_info), normalize_format(audio_info)
        container = "mp4" if profile == "mp4" and video.ext == "mp4" and audio.ext == "m4a" else "mkv"
        return SelectionResult(selector, video, audio, None, container, explanation)
    # Probes do not request a format, so choose representative streams from the
    # normalized table for display and minimum-height validation.
    all_formats = [normalize_format(item) for item in info.get("formats", []) if isinstance(item, dict)]
    videos = [f for f in all_formats if f.video_only]
    audios = [f for f in all_formats if f.audio_only]
    if videos and audios:
        video = max(videos, key=lambda f: ((f.height or 0), (f.fps or 0), (f.tbr or 0)))
        audio = max(audios, key=lambda f: (f.tbr or 0))
        container = "mp4" if profile == "mp4" and video.ext == "mp4" and audio.ext == "m4a" else "mkv"
        return SelectionResult(selector, video, audio, None, container, explanation)
    combined_candidates = [f for f in all_formats if not f.video_only and not f.audio_only and f.vcodec not in (None, "none")]
    if combined_candidates:
        combined = max(combined_candidates, key=lambda f: ((f.height or 0), (f.fps or 0), (f.tbr or 0)))
        container = "mp4" if profile == "mp4" and combined.ext == "mp4" else "mkv"
        return SelectionResult(selector, None, None, combined, container, explanation)
    chosen = info.get("requested_downloads") or []
    combined_info = next((f for f in chosen if f.get("vcodec") not in (None, "none")), None)
    if combined_info is None and info.get("vcodec") not in (None, "none"):
        combined_info = info
    combined = normalize_format(combined_info) if combined_info else None
    container = "mp4" if profile == "mp4" and combined and combined.ext == "mp4" else "mkv"
    return SelectionResult(selector, None, None, combined, container, explanation)


def validate_minimum(selection: SelectionResult, minimum: int | None, allow_lower: bool = False) -> None:
    if minimum is None:
        return
    height = selection.height or 0
    if height < minimum and not allow_lower:
        shown = f"{height}p" if height else "no video height"
        raise AppError(
            f"Requested at least {minimum}p, but the highest selected format is {shown}. Use --wait-for-height {minimum} for an archive still processing, or --allow-lower-quality to accept the available quality.",
            5,
        )


def max_video_height(formats: Iterable[FormatCandidate]) -> int | None:
    heights = [f.height for f in formats if f.height and f.vcodec not in (None, "none")]
    return max(heights) if heights else None


def _number(value, converter):
    try:
        return converter(value) if value is not None else None
    except (TypeError, ValueError):
        return None

