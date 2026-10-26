from __future__ import annotations

import re


class AppError(Exception):
    """An expected, user-facing application error with a stable exit status."""

    def __init__(self, message: str, exit_code: int = 10) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def sanitize_message(message: str) -> str:
    """Remove URL query strings and common credential-shaped values from errors."""
    message = re.sub(r"https?://[^\s'\"]+", lambda m: m.group(0).split("?", 1)[0], message)
    message = re.sub(r"(?i)(cookie|authorization|token|signature|sig)=([^\s&]+)", r"\1=[redacted]", message)
    return message.strip()


def classify_download_error(message: str) -> AppError:
    safe = sanitize_message(message)
    lowered = safe.casefold()
    if any(word in lowered for word in ("private video", "video unavailable", "has been removed", "not available in your country", "members-only")):
        return AppError(f"Media is unavailable to this session. Check the URL and access in your browser. Details: {safe}", 6)
    if any(word in lowered for word in ("sign in", "login required", "cookies", "age-restricted", "confirm you're not a bot", "authentication")):
        return AppError(f"YouTube requires an authorized session. Try --cookies-from-browser with a supported browser. Details: {safe}", 4)
    if any(word in lowered for word in ("http error 429", "429", "timed out", "timeout", "network", "connection", "temporary failure", "unable to download webpage")):
        return AppError(f"Network request failed or was rate limited. Wait a while and retry. Details: {safe}", 7)
    return AppError(f"yt-dlp could not complete the operation. Check the URL and yt-dlp version. Details: {safe}", 8)

