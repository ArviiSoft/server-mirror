"""Discord error formatting without printing response bodies or submitted values."""

import re

import discord

_FIELDS = frozenset(
    {
        "name",
        "permissions",
        "color",
        "colors",
        "primary_color",
        "secondary_color",
        "tertiary_color",
        "hoist",
        "mentionable",
        "icon",
        "position",
        "id",
        "type",
        "parent_id",
        "permission_overwrites",
        "allow",
        "deny",
        "topic",
        "nsfw",
        "rate_limit_per_user",
        "default_auto_archive_duration",
        "default_thread_rate_limit_per_user",
        "bitrate",
        "user_limit",
        "rtc_region",
        "video_quality_mode",
        "lock_permissions",
    }
)
_CODE = re.compile(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\Z")


def is_name_length_error(error: discord.HTTPException) -> bool:
    """Retry only a 400 that explicitly rejects the name's length and no other field."""
    if error.status != 400 or error.code != 50035:
        return False
    payload = getattr(error, "json", None)
    errors = payload.get("errors") if isinstance(payload, dict) else None
    if not isinstance(errors, dict) or set(errors) != {"name"}:
        return False
    name = errors["name"]
    if not isinstance(name, dict) or set(name) != {"_errors"}:
        return False
    entries = name["_errors"]
    return (
        isinstance(entries, list)
        and bool(entries)
        and all(
            isinstance(entry, dict) and entry.get("code") == "BASE_TYPE_BAD_LENGTH"
            for entry in entries
        )
    )


def validation_details(error: discord.HTTPException) -> list[str]:
    """Extract bounded field paths and machine codes, never human-readable API text."""
    payload = getattr(error, "json", None)
    if not isinstance(payload, dict):
        return []
    details = []

    def visit(node, path: str, depth: int) -> None:
        if not isinstance(node, dict) or depth > 8 or len(details) >= 12:
            return
        entries = node.get("_errors", [])
        if isinstance(entries, list):
            for entry in entries[:12]:
                if len(details) >= 12:
                    return
                code = entry.get("code") if isinstance(entry, dict) else None
                if not isinstance(code, str) or len(code) > 64 or not _CODE.fullmatch(code):
                    code = "VALIDATION_ERROR"
                detail = f"{path or 'request'}: {code}"
                if detail not in details:
                    details.append(detail)
        for key, child in node.items():
            if key == "_errors":
                continue
            if isinstance(key, str) and key.isascii() and key.isdecimal() and len(key) <= 4:
                child_path = f"{path}[{key}]"
            else:
                field = key if isinstance(key, str) and key in _FIELDS else "<unknown field>"
                child_path = f"{path}.{field}" if path else field
            visit(child, child_path, depth + 1)
            if len(details) >= 12:
                break

    visit(payload.get("errors"), "", 0)
    return details


def http_error_details(error: discord.HTTPException) -> str:
    description = (
        "Discord rejected request data" if error.code == 50035 else "Discord request failed"
    )
    lines = [f"{description} (HTTP {error.status}, code {error.code})."]
    details = validation_details(error)
    if details:
        lines.append("Rejected fields:")
        lines.extend(f"  {detail}" for detail in details)
    elif error.code == 50035:
        lines.append("No structured field details are available for this response.")
    return "\n".join(lines)


def http_error_message(error: discord.HTTPException, *, copy_started: bool) -> str:
    context = (
        "The destination may be partially modified; inspect it before retrying."
        if copy_started
        else "No destination changes were made."
    )
    return f"{http_error_details(error)}\n{context}"