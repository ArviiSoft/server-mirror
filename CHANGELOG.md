# Changelog

Notable changes to Server Mirror are documented here, following [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Changes remain unreleased until a release is tagged.

## [v1.0.0] - 29.09.2026

### Added

- Per-issue continuation prompts for noncritical preparation and copy failures, showing the affected item and the effect of accepting each omission.
- Warning completion reports with actual creation counts, separate skipped-step progress, and exit code `3` for copies finished with omissions.
- A styled terminal interface with server cards, copy totals, and distinct confirmation and result panels.
- Live copy progress with completed steps, elapsed time, and recent role/channel names.
- An offline `--demo` mode for previewing the interface without an account token.
- A preview-only default mode, explicit `--apply` option, and destination-ID confirmation.
- Preflight checks for server access, permissions, role hierarchy, unsupported channel types, and overwrite mappings.
- Account tokens from hidden terminal input or the `DISCORD_USER_TOKEN` environment variable.

### Changed

- Organized application code into the `server_mirror` package with separate core and terminal UI modules; launch it with `python -m server_mirror` or `start.bat`.
- Moved dependency lists to `requirements/runtime.txt` and `requirements/dev.txt`.
- Added Rich for adaptive terminal colors and narrow-window layouts.
- Enabled Python UTF-8 output in the Windows launcher.
- Restored personal account-token authentication using `discord.py-self` 2.1 or newer.
- Removed bot applications, bot invitations, and bot-only permission checks from setup.
- Replaced the looping Windows launcher with `start.bat`, which uses the local virtual environment and preserves the exit code.
- Made copying a one-shot operation that stops and reports a failure instead of reporting false success.

### Fixed

- Removed the unsupported `bot=False` argument and obsolete `icon_url` API.
- Mapped roles and categories by source ID, preventing collisions between identical names.
- Copied `@everyone` permissions and preserved role and channel ordering.
- Preserved uncategorized channels without leaking the previous channel's category.
- Resolved member overwrites before deletion instead of treating every overwrite as a role.
- Protected managed roles and checked destination role hierarchy before modifying the server.
- Limited voice bitrate to the destination's supported maximum.
- Checked role capacity and missing category references before deleting destination data.
- Used a static icon fallback when the destination cannot accept an animated icon.
- Guarded against repeated READY events replaying destructive operations.
- Updated channel and icon calls for current Discord APIs.
- Made managed/missing role overwrites recoverable, with one decision per source role and remaining permission mappings preserved.
- Continued independent work after accepted role/channel creation, deletion, permission, ordering, member-lookup, and identity failures; missing categories can fall back to uncategorized child channels.
- Kept failed roles out of ordering and overwrite mappings and omitted ordering for failed channels/categories, preventing follow-on mapping errors.
- Preserved the destination icon when its source download is omitted; allowed role-capacity omissions during preparation with explicit disclosure.
- Kept authentication, lost access, uncertain writes, and unexpected errors fatal; decline/EOF after copying now correctly reports a partially modified destination.
- Converted announcement (`news`) channels to standard text channels, preserving their names, categories, order, topics, permission overwrites, and compatible text settings.
- Skipped forum, media, stage, and unrecognized channel types during preparation instead of aborting the copy; skipped channels no longer trigger overwrite lookups or count toward copy progress.
- Reported channel conversions and omissions in the preview and completion summary, with creation totals reflecting the actual destination channel types.
- Normalized empty, invisible-only, control-containing, and overlong role names before copying, with adjusted destination names shown in the preview and completion summary.
- Retried role creation once with an ID-based fallback name when Discord specifically rejects only the name's length, preserving role permissions and overwrite mappings.
- Kept the failed operation and item visible after the live progress panel closes.
- Added field paths and validation codes to Discord request errors, without displaying raw API messages or submitted values; failures during preparation now correctly report that no destination changes were made.
- Allowed copying to continue when a member referenced by a channel/category overwrite is absent from the destination; only that member's overwrite is skipped and reported before confirmation and on completion.
- Cached missing-member lookups during preparation while preserving overwrites for existing members and errors unrelated to missing members.
- Removed the unnecessary source-server Administrator requirement; membership is sufficient.
- Kept the full channel/category metadata list supplied by Discord, without filtering on the account's View Channel permission, and retained copying of ordinary roles the account does not hold.
- Kept destination Administrator and role-hierarchy checks before any destructive operations.

### Removed

- Unused `psutil` and `colorama` dependencies and the ambiguous `discord` package.
- The obsolete dependency-downgrade troubleshooting note.
- Unused emoji-copy methods that were never invoked by the application.

### Security

- Hid interactive token input and refused terminals that would echo it.
- Blocked copying a server onto itself.
- Stopped on unsupported permission mappings instead of silently making channels less restrictive.
- Preserved the account's highest Administrator role when the account does not own the destination.
- Avoided printing raw API response bodies and credentials in error messages.

[v1.0.0](https://github.com/ArviiSoft/server-mirror/releases/tag/v1.0.0)