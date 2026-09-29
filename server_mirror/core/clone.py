"""Validated, one-shot copying of Discord server structure."""

from collections.abc import Awaitable, Callable
from typing import TypeVar
from unicodedata import category

import discord

from server_mirror.core.discord_errors import http_error_details, is_name_length_error
from server_mirror.core.recovery import CopyIssue, can_skip_request

REASON = "Server Mirror: user-confirmed structure copy"
MAX_ROLES = 250
MAX_ROLE_NAME = 100
TEXT_CHANNEL_TYPES = (discord.ChannelType.text, discord.ChannelType.news)
COPYABLE_CHANNEL_TYPES = (
    discord.ChannelType.category,
    discord.ChannelType.voice,
    *TEXT_CHANNEL_TYPES,
)
_BLANK_GLYPHS = frozenset("\u115f\u1160\u2800\u3164\uffa0")
T = TypeVar("T")
SKIPPED = object()


def copy_role_name(name: str, source_id: int) -> str:
    """Preserve visible names; make empty, invisible, or overlong names usable."""
    cleaned = "".join(char for char in name if category(char) not in {"Cc", "Cs"})
    cleaned = cleaned.strip()[:MAX_ROLE_NAME].rstrip()
    if any(
        not char.isspace() and category(char)[0] not in "CMZ" and char not in _BLANK_GLYPHS
        for char in cleaned
    ):
        return cleaned
    return f"Role {source_id}"


class CloneError(Exception):
    """A precondition failed; the copy must not continue."""


class CloneCancelled(CloneError):
    """The user declined a proposed recovery."""


class Clone:
    def __init__(
        self,
        source: discord.Guild,
        target: discord.Guild,
        *,
        report: Callable[[str, str, bool], None] | None = None,
        recover: Callable[[CopyIssue], Awaitable[bool]] | None = None,
        report_skip: Callable[[str, str], None] | None = None,
    ):
        self.source = source
        self.target = target
        self.role_map: dict[int, discord.Role] = {}
        self.role_names: dict[int, str] = {}
        self.renamed_roles: dict[int, str] = {}
        self.member_map: dict[int, discord.Member] = {}
        self.skipped_member_overwrites: set[tuple[int, int]] = set()
        self.category_map: dict[int, discord.CategoryChannel] = {}
        self.converted_channels: list[discord.abc.GuildChannel] = []
        self.skipped_channels: list[discord.abc.GuildChannel] = []
        self.created_channels: list[tuple[discord.abc.GuildChannel, discord.abc.GuildChannel]] = []
        self.prepared = False
        self.executed = False
        self.report = report
        self.recover = recover
        self.report_skip = report_skip
        self.issues: list[CopyIssue] = []
        self.skipped_role_ids: set[int] = set()
        self.skipped_lookup_ids: set[int] = set()
        self.uncategorized_ids: set[int] = set()
        self.preserve_icon = False
        self.skipped_steps = 0
        self.created_role_count = 0

    @property
    def operation_count(self) -> int:
        if not self.prepared:
            raise CloneError("Prepare the copy before requesting its operation count.")
        return (
            len(self.channels_to_delete)
            + len(self.roles_to_delete)
            + len(self.roles)
            + bool(self.roles)
            + 2 * len(self.channels)
            + 2
        )

    async def _step(self, operation: Awaitable[T], phase: str, item: str) -> T:
        if self.report is not None:
            self.report(phase, item, False)
        result = await operation
        if self.report is not None:
            self.report(phase, item, True)
        return result

    async def _accept_issue(self, issue: CopyIssue) -> None:
        if self.recover is None:
            raise CloneError(f"{issue.item}: {issue.reason} {issue.consequence}")
        if not await self.recover(issue):
            raise CloneCancelled(f"Stopped at {issue.phase}: {issue.item}.")
        self.issues.append(issue)

    def _skip_step(self, phase: str, item: str) -> None:
        self.skipped_steps += 1
        if self.report_skip is not None:
            self.report_skip(phase, item)

    async def _recover_step(self, operation: Awaitable[T], phase: str, item: str, consequence: str):
        try:
            return await operation
        except discord.HTTPException as error:
            if self.recover is None or not can_skip_request(error):
                raise
            self.validate()
            await self._accept_issue(CopyIssue(phase, item, http_error_details(error), consequence))
            self._skip_step(phase, item)
            return SKIPPED

    async def _run_step(self, operation: Awaitable[T], phase: str, item: str, consequence: str):
        return await self._recover_step(
            self._step(operation, phase, item), phase, item, consequence
        )

    def _role_omission(self, role_id: int) -> str:
        affected = sum(
            any(subject.id == role_id for subject in channel.overwrites)
            for channel in self.channels
        )
        return (
            f"Skip this role and its permission overwrites on {affected} channels/categories. "
            "Other roles and channels will still be copied. Missing allow/deny rules can change "
            "who can view or use these channels; review destination permissions."
        )

    def retained_role_id(self) -> int | None:
        if self.target.me is None or self.target.owner_id == self.target.me.id:
            return None
        return self.target.me.top_role.id

    def validate(self) -> None:
        if self.source.id == self.target.id:
            raise CloneError("Source and destination must be different servers.")
        for guild in (self.source, self.target):
            if guild.unavailable or guild.me is None:
                raise CloneError(
                    f"Server {guild.id} is unavailable or your account is not a member."
                )
        if not self.target.me.guild_permissions.administrator:
            raise CloneError(
                f"Your account needs Administrator permission in destination server {self.target.id}."
            )
        if self.retained_role_id() is not None:
            if not self.target.me.top_role.permissions.administrator:
                raise CloneError(
                    "Your highest destination role must grant Administrator so it can be retained."
                )
            protected = [
                role
                for role in self.target.roles
                if not role.is_default()
                and not role.managed
                and role.id != self.retained_role_id()
                and role >= self.target.me.top_role
            ]
            if protected:
                raise CloneError(
                    "Move your destination Administrator role above every other ordinary role."
                )
        if "COMMUNITY" in self.target.features:
            raise CloneError(
                "Use a destination with Community disabled; required Community channels cannot be deleted."
            )

    async def prepare(self) -> None:
        """Resolve prerequisites without writing to either server."""
        self.prepared = False
        self.skipped_member_overwrites.clear()
        self.issues.clear()
        self.skipped_role_ids.clear()
        self.skipped_lookup_ids.clear()
        self.uncategorized_ids.clear()
        self.category_map.clear()
        self.created_channels.clear()
        self.preserve_icon = False
        self.validate()
        self.roles = [
            role for role in self.source.roles if not role.is_default() and not role.managed
        ]
        self.role_names = {role.id: copy_role_name(role.name, role.id) for role in self.roles}
        self.renamed_roles = {
            role.id: self.role_names[role.id]
            for role in self.roles
            if self.role_names[role.id] != role.name
        }
        self.roles_to_delete = [
            role
            for role in self.target.roles
            if not role.is_default() and not role.managed and role.id != self.retained_role_id()
        ]
        source_channels = list(self.source.channels)
        self.channels = [
            channel for channel in source_channels if channel.type in COPYABLE_CHANNEL_TYPES
        ]
        self.converted_channels = [
            channel for channel in self.channels if channel.type is discord.ChannelType.news
        ]
        self.skipped_channels = [
            channel for channel in source_channels if channel.type not in COPYABLE_CHANNEL_TYPES
        ]
        self.channels_to_delete = list(self.target.channels)
        retained_roles = len(self.target.roles) - len(self.roles_to_delete)
        if retained_roles + len(self.roles) > MAX_ROLES:
            capacity = max(0, MAX_ROLES - retained_roles)
            omitted = self.roles[capacity:]
            await self._accept_issue(
                CopyIssue(
                    "Checking role capacity",
                    ", ".join(f"{role.name} (ID {role.id})" for role in omitted),
                    "Copied roles plus retained destination roles exceed Discord's role limit.",
                    f"Copy the first {capacity} source roles in hierarchy order; skip these "
                    f"{len(omitted)} roles and their channel overwrites. "
                    "Missing allow/deny rules can change channel access.",
                )
            )
            self.skipped_role_ids.update(role.id for role in omitted)
            self.roles = self.roles[:capacity]
            self.renamed_roles = {
                key: name
                for key, name in self.renamed_roles.items()
                if key not in self.skipped_role_ids
            }
        category_ids = {
            channel.id for channel in self.channels if channel.type is discord.ChannelType.category
        }
        self.role_map = {self.source.default_role.id: self.target.default_role}
        self.member_map = {}
        missing_member_ids: set[int] = set()
        source_role_ids = {role.id for role in self.roles} | self.role_map.keys()
        for channel in self.channels:
            if (
                channel.category_id is not None
                and channel.category_id not in category_ids
                and channel.category_id not in self.uncategorized_ids
            ):
                await self._accept_issue(
                    CopyIssue(
                        "Checking categories",
                        f"Category ID {channel.category_id}",
                        f"Source channel {channel.id} references a missing category.",
                        "Create its channels without a category, preserving each channel's available "
                        "permission overwrites. Review their access and organization.",
                    )
                )
                self.uncategorized_ids.add(channel.category_id)
            for subject in channel.overwrites:
                is_role = isinstance(subject, discord.Role) or (
                    isinstance(subject, discord.Object) and subject.type is discord.Role
                )
                if is_role:
                    if (
                        subject.id not in source_role_ids
                        and subject.id not in self.skipped_role_ids
                    ):
                        await self._accept_issue(
                            CopyIssue(
                                "Checking role overwrites",
                                f"Role ID {subject.id} / channel {channel.name} (ID {channel.id})",
                                "This managed or missing source role cannot be copied.",
                                self._role_omission(subject.id),
                            )
                        )
                        self.skipped_role_ids.add(subject.id)
                else:
                    if subject.id in self.skipped_lookup_ids:
                        continue
                    if subject.id not in self.member_map and subject.id not in missing_member_ids:
                        member = self.target.get_member(subject.id)
                        if member is None:
                            try:
                                member = await self.target.fetch_member(subject.id)
                            except discord.HTTPException as error:
                                if isinstance(error, discord.NotFound) and error.code == 10007:
                                    missing_member_ids.add(subject.id)
                                else:
                                    if self.recover is None or not can_skip_request(error):
                                        raise
                                    await self._accept_issue(
                                        CopyIssue(
                                            "Resolving member overwrites",
                                            f"Member ID {subject.id}",
                                            http_error_details(error),
                                            "Skip this member's overwrites on all copied channels and "
                                            "categories. Their destination access may differ.",
                                        )
                                    )
                                    self.skipped_lookup_ids.add(subject.id)
                        if member is not None:
                            self.member_map[subject.id] = member
                    if subject.id in missing_member_ids:
                        self.skipped_member_overwrites.add((channel.id, subject.id))
        icon = self.source.icon
        self.static_icon = bool(
            icon is not None and icon.is_animated() and "ANIMATED_ICON" not in self.target.features
        )
        if self.static_icon:
            icon = icon.with_format("png")
        self.icon = None
        if icon is not None:
            try:
                self.icon = await icon.read()
            except (discord.HTTPException, OSError) as error:
                if self.recover is None:
                    raise
                if isinstance(error, discord.HTTPException) and not can_skip_request(error):
                    raise
                reason = (
                    http_error_details(error)
                    if isinstance(error, discord.HTTPException)
                    else "The source icon could not be downloaded."
                )
                await self._accept_issue(
                    CopyIssue(
                        "Reading server icon",
                        self.source.name,
                        reason,
                        "Keep the current destination icon; continue copying the server name and structure.",
                    )
                )
                self.preserve_icon = True
        self.prepared = True

    def preview(self) -> str:
        if not self.prepared:
            raise CloneError("Prepare the copy before requesting a preview.")
        categories = sum(channel.type is discord.ChannelType.category for channel in self.channels)
        texts = sum(channel.type in TEXT_CHANNEL_TYPES for channel in self.channels)
        voices = sum(channel.type is discord.ChannelType.voice for channel in self.channels)
        clamped = sum(
            channel.type is discord.ChannelType.voice
            and channel.bitrate > self.target.bitrate_limit
            for channel in self.channels
        )
        return "\n".join(
            [
                "Server Mirror | Copy preview",
                f"Source: {self.source.name} ({self.source.id})",
                f"Destination: {self.target.name} ({self.target.id})",
                f"Delete: {len(self.channels_to_delete)} channels/categories and {len(self.roles_to_delete)} roles",
                f"Create: {len(self.roles)} roles, {categories} categories, {texts} text channels, {voices} voice channels",
                "Replace: server name, icon, and @everyone permissions",
                "Preserve: destination managed roles; copy no messages or member role assignments",
                f"Retain your destination access role: {self.retained_role_id() or 'not needed (owner)'}",
                f"Voice channels limited to destination bitrate: {clamped}",
                f"Animated icon converted to a static PNG: {'yes' if self.static_icon else 'no'}",
                f"Skipped member-specific overwrites (member absent from destination): {len(self.skipped_member_overwrites)}",
                f"Adjusted role names: {len(self.renamed_roles)}",
                f"Announcement channels converted to standard text: {len(self.converted_channels)}",
                f"Skipped unsupported channels: {len(self.skipped_channels)}",
                f"Proposed omissions and adjustments: {len(self.issues)}",
            ]
        )

    async def overwrites(self, channel: discord.abc.GuildChannel) -> dict:
        mapped = {}
        for subject, permissions in channel.overwrites.items():
            if (channel.id, subject.id) in self.skipped_member_overwrites:
                continue
            if subject.id in self.skipped_role_ids or subject.id in self.skipped_lookup_ids:
                continue
            target = self.role_map.get(subject.id) or self.member_map.get(subject.id)
            if target is None:
                await self._accept_issue(
                    CopyIssue(
                        "Mapping channel permissions",
                        f"{channel.name} (ID {channel.id}) / overwrite ID {subject.id}",
                        "This permission subject has no destination mapping; source metadata may have changed.",
                        "Skip only this overwrite and copy the remaining channel settings. "
                        "Missing allow/deny rules can change who can use the channel.",
                    )
                )
                continue
            mapped[target] = permissions
        return mapped

    async def _create_role(self, role: discord.Role) -> discord.Role:
        options = {
            "name": self.role_names[role.id],
            "permissions": role.permissions,
            "colour": role.colour,
            "hoist": role.hoist,
            "mentionable": role.mentionable,
            "reason": REASON,
        }
        try:
            return await self._step(
                self.target.create_role(**options), "Creating roles", options["name"]
            )
        except discord.HTTPException as error:
            fallback = f"Role {role.id}"
            if not is_name_length_error(error) or options["name"] == fallback:
                raise
            options["name"] = fallback
            self.role_names[role.id] = fallback
            self.renamed_roles[role.id] = fallback
            return await self._step(self.target.create_role(**options), "Creating roles", fallback)

    async def execute(self) -> None:
        if not self.prepared or self.executed:
            raise CloneError("A copy must be prepared and can only be executed once.")
        self.validate()
        self.executed = True
        for channel in sorted(
            self.channels_to_delete,
            key=lambda channel: channel.type is discord.ChannelType.category,
        ):
            await self._run_step(
                channel.delete(reason=REASON),
                "Removing old channels",
                channel.name,
                "Leave this destination channel/category in place and continue. "
                "The result may contain old channels or duplicate names.",
            )
        for role in reversed(self.roles_to_delete):
            await self._run_step(
                role.delete(reason=REASON),
                "Removing old roles",
                role.name,
                "Leave this destination role and its member assignments in place. "
                "Its permissions remain active and it still uses a role slot.",
            )
        default_role = await self._run_step(
            self.target.default_role.edit(
                permissions=self.source.default_role.permissions, reason=REASON
            ),
            "Updating default permissions",
            "@everyone",
            "Keep the destination's existing @everyone permissions and continue. "
            "This can change access across the entire destination; review its permissions.",
        )
        if default_role is not SKIPPED:
            self.role_map[self.source.default_role.id] = default_role
        for role in self.roles:
            created_role = await self._recover_step(
                self._create_role(role),
                "Creating roles",
                f"{role.name} (ID {role.id})",
                self._role_omission(role.id),
            )
            if created_role is SKIPPED:
                self.skipped_role_ids.add(role.id)
            else:
                self.role_map[role.id] = created_role
                self.created_role_count += 1
        if self.roles:
            positions = {
                self.role_map[role.id]: index
                for index, role in enumerate(
                    (role for role in self.roles if role.id in self.role_map), 1
                )
            }
            if positions:
                await self._run_step(
                    self.target.edit_role_positions(positions=positions, reason=REASON),
                    "Restoring role order",
                    f"{len(positions)} roles",
                    "Keep the copied roles in their current order. Review the role hierarchy.",
                )
            else:
                self._skip_step("Restoring role order", "No roles were created")
        for channel in sorted(self.channels, key=lambda channel: channel.position):
            if channel.type is discord.ChannelType.category:
                created = await self._run_step(
                    self.target.create_category(
                        channel.name, overwrites=await self.overwrites(channel), reason=REASON
                    ),
                    "Creating categories",
                    channel.name,
                    "Skip this category and create its child channels without a category, "
                    "preserving each channel's available overwrites. Review channel access.",
                )
                if created is SKIPPED:
                    self.uncategorized_ids.add(channel.id)
                else:
                    self.category_map[channel.id] = created
        for channel in sorted(self.channels, key=lambda channel: channel.position):
            if channel.type is discord.ChannelType.category:
                continue
            category = self.category_map.get(channel.category_id)
            if (
                channel.category_id is not None
                and category is None
                and channel.category_id not in self.uncategorized_ids
            ):
                await self._accept_issue(
                    CopyIssue(
                        "Mapping categories",
                        f"{channel.name} (ID {channel.id})",
                        f"Category ID {channel.category_id} has no destination mapping.",
                        "Create channels belonging to this category without a category, "
                        "preserving each channel's available overwrites. Review channel access.",
                    )
                )
                self.uncategorized_ids.add(channel.category_id)
            options = {
                "name": channel.name,
                "category": category,
                "overwrites": await self.overwrites(channel),
                "reason": REASON,
                "nsfw": channel.nsfw,
            }
            if channel.type in TEXT_CHANNEL_TYPES:
                created = await self._run_step(
                    self.target.create_text_channel(
                        **options,
                        news=False,
                        slowmode_delay=channel.slowmode_delay,
                        topic=channel.topic,
                        default_auto_archive_duration=channel.default_auto_archive_duration,
                        default_thread_slowmode_delay=channel.default_thread_slowmode_delay,
                    ),
                    "Creating text channels",
                    channel.name,
                    "Skip this channel and its ordering step; continue with the remaining channels.",
                )
            else:
                created = await self._run_step(
                    self.target.create_voice_channel(
                        **options,
                        bitrate=min(channel.bitrate, int(self.target.bitrate_limit)),
                        user_limit=channel.user_limit,
                        rtc_region=channel.rtc_region,
                        video_quality_mode=channel.video_quality_mode,
                    ),
                    "Creating voice channels",
                    channel.name,
                    "Skip this channel and its ordering step; continue with the remaining channels.",
                )
            if created is SKIPPED:
                self._skip_step("Restoring channel order", channel.name)
            else:
                self.created_channels.append((channel, created))
        for source in sorted(self.channels, key=lambda channel: channel.position):
            if source.type is discord.ChannelType.category:
                if source.id not in self.category_map:
                    self._skip_step("Restoring category order", source.name)
                    continue
                await self._run_step(
                    self.category_map[source.id].edit(position=source.position, reason=REASON),
                    "Restoring category order",
                    source.name,
                    "Keep this category in its current position and continue.",
                )
        for source, created in self.created_channels:
            await self._run_step(
                created.edit(
                    position=source.position, slowmode_delay=source.slowmode_delay, reason=REASON
                ),
                "Restoring channel order",
                source.name,
                "Keep this channel's current position and slowmode settings and continue.",
            )
        identity = {"name": self.source.name, "reason": REASON}
        if not self.preserve_icon:
            identity["icon"] = self.icon
        await self._run_step(
            self.target.edit(**identity),
            "Updating server identity",
            self.source.name,
            "Skip the server name/icon update; keep the copied roles and channels.",
        )
