"""Explicit, item-scoped recovery decisions shared by the core and terminal UI."""

from dataclasses import dataclass

import discord


@dataclass(frozen=True)
class CopyIssue:
    phase: str
    item: str
    reason: str
    consequence: str


def can_skip_request(error: discord.HTTPException) -> bool:
    """Only definite item rejections; never replay an uncertain write or bypass login."""
    return (
        error.status in {400, 403, 404, 413}
        and error.code
        not in {
            10001,
            10004,
            10012,
            10020,
            20026,
            40001,
            40002,
            40003,
            50001,
            50014,
            50025,
            60003,
        }
        and not isinstance(error, discord.CaptchaRequired)
    )
