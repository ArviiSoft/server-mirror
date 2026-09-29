"""Terminal presentation for Server Mirror. No Discord requests are made here."""

from __future__ import annotations

import re
import time
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

from rich import box
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TaskProgressColumn,
    TimeElapsedColumn,
)
from rich.style import Style
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from server_mirror.core.recovery import CopyIssue

if TYPE_CHECKING:
    from server_mirror.core.clone import Clone


THEME = Theme(
    {
        "accent": "bright_cyan",
        "secondary": "bright_magenta",
        "muted": "bright_black",
        "good": "bright_green",
        "warning": "yellow",
        "danger": "bright_red",
        "heading": "bold white",
        "brand": "bold bright_cyan",
        "section": "bold bright_magenta",
    }
)


def literal(value: object, style: str = "") -> Text:
    """Keep server names literal and prevent control characters from altering the display."""
    value = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", str(value))
    return Text(re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", value), style=style)


@dataclass(frozen=True)
class CopySummary:
    source_name: str
    source_id: int
    target_name: str
    target_id: int
    roles: int
    categories: int
    text_channels: int
    voice_channels: int
    delete_channels: int
    delete_roles: int
    retained_role: str | None = None
    limited_bitrates: int = 0
    static_icon: bool = False
    skipped_member_overwrites: int = 0
    skipped_member_channels: int = 0
    renamed_roles: tuple[tuple[int, str], ...] = ()
    converted_channels: tuple[tuple[int, str, str], ...] = ()
    skipped_channels: tuple[tuple[int, str, str], ...] = ()
    issues: tuple[CopyIssue, ...] = ()
    skipped_steps: int = 0

    @property
    def has_omissions(self) -> bool:
        return bool(self.issues or self.skipped_channels or self.skipped_member_overwrites)

    @classmethod
    def from_clone(cls, clone: Clone) -> CopySummary:
        channels = (
            [source for source, _ in clone.created_channels] if clone.executed else clone.channels
        )
        counts = {
            name: sum(channel.type.name == name for channel in channels)
            for name in ("category", "text", "voice", "news")
        }
        created_ids = {channel.id for channel in channels}
        return cls(
            source_name=clone.source.name,
            source_id=clone.source.id,
            target_name=clone.target.name,
            target_id=clone.target.id,
            roles=clone.created_role_count if clone.executed else len(clone.roles),
            categories=len(clone.category_map) if clone.executed else counts["category"],
            text_channels=counts["text"] + counts["news"],
            voice_channels=counts["voice"],
            delete_channels=len(clone.channels_to_delete),
            delete_roles=len(clone.roles_to_delete),
            retained_role=(
                clone.target.me.top_role.name if clone.retained_role_id() is not None else None
            ),
            limited_bitrates=sum(
                channel.type.name == "voice" and channel.bitrate > clone.target.bitrate_limit
                for channel in clone.channels
            ),
            static_icon=clone.static_icon and not clone.preserve_icon,
            skipped_member_overwrites=len(clone.skipped_member_overwrites),
            skipped_member_channels=len(
                {channel_id for channel_id, _ in clone.skipped_member_overwrites}
            ),
            renamed_roles=tuple(
                (identifier, name)
                for identifier, name in clone.renamed_roles.items()
                if not clone.executed or identifier not in clone.skipped_role_ids
            ),
            converted_channels=tuple(
                (channel.id, channel.name, str(channel.type))
                for channel in clone.converted_channels
                if not clone.executed or channel.id in created_ids
            ),
            skipped_channels=tuple(
                (channel.id, channel.name, str(channel.type)) for channel in clone.skipped_channels
            ),
            issues=tuple(clone.issues),
            skipped_steps=clone.skipped_steps,
        )


class TerminalUI:
    def __init__(self, console: Console | None = None, error_console: Console | None = None):
        self.console = console or Console(theme=THEME, highlight=False)
        self.error_console = error_console or Console(theme=THEME, stderr=True, highlight=False)
        self.progress: Progress | None = None
        self.live: Live | None = None
        self.status = None
        self.task_id = None
        self.recent: deque[tuple[str, str]] = deque(maxlen=3)
        self.recent_skipped: deque[bool] = deque(maxlen=3)
        self.skipped_steps = 0
        self.phase = "Preparing copy"
        self.item = ""
        self.elapsed = 0.0

    @property
    def width(self) -> int:
        return min(self.console.width, 96)

    def panel(self, content, *, title: str = "", style: str = "accent") -> Panel:
        return Panel(
            content,
            title=Text(title, style=self.console.get_style(style) + Style(bold=True))
            if title
            else None,
            title_align="left",
            border_style=style,
            box=box.ROUNDED,
            padding=(1, 2),
            width=self.width,
        )

    def banner(self, *, apply: bool = False, demo: bool = False) -> None:
        mode = "OFFLINE DEMO" if demo else "COPY MODE" if apply else "PREVIEW MODE"
        heading = Table.grid(expand=True)
        heading.add_column(ratio=1)
        heading.add_column(justify="right")
        heading.add_row(Text("SERVER MIRROR", style="brand"), Text(mode, style="secondary"))
        self.console.print()
        self.console.print(
            self.panel(
                Group(
                    heading,
                    Text("Your server structure. A fresh destination.", style="muted"),
                    Text(),
                    Text("01  CONNECT    /    02  REVIEW    /    03  MIRROR", style="white"),
                )
            )
        )
        if demo:
            self.note("Sample data only. No account login or server changes.")
        else:
            self.note("Account session  |  Hidden token input  |  Confirm before copying")

    def note(self, message: str) -> None:
        self.console.print(literal(message, "muted"))

    def prompt(self, label: str, *, hint: str = "") -> str:
        self.console.print()
        self.console.print(literal(label, "brand"))
        if hint:
            self.note(hint)
        return self.console.input(Text("  > ", style="accent"))

    @contextmanager
    def busy(self, message: str) -> Iterator[None]:
        if self.console.is_interactive:
            self.status = self.console.status(literal(message, "accent"), spinner="line")
            try:
                with self.status:
                    yield
            finally:
                self.status = None
        else:
            self.note(message)
            yield

    def metrics(self, summary: CopySummary) -> Table:
        table = Table.grid(expand=True, padding=(0, 1))
        for _ in range(4):
            table.add_column(justify="center", ratio=1)
        table.add_row(
            *[
                Text(str(count), style="brand")
                for count in (
                    summary.roles,
                    summary.categories,
                    summary.text_channels,
                    summary.voice_channels,
                )
            ]
        )
        table.add_row(
            *[Text(name, style="muted") for name in ("ROLES", "CATEGORIES", "TEXT", "VOICE")]
        )
        return table

    def preview(self, summary: CopySummary) -> None:
        self.console.print()
        self.console.print(Text("02 / REVIEW THE COPY", style="section"))
        self.console.print()
        servers = Table.grid(expand=True, padding=(0, 2))
        for _ in range(2 if self.width >= 72 else 1):
            servers.add_column(ratio=1)
        cards = [
            self.panel(
                Group(literal(name, "heading"), literal(identifier, "muted")),
                title=label,
                style=style,
            )
            for name, identifier, label, style in (
                (summary.source_name, summary.source_id, "SOURCE / read only", "accent"),
                (summary.target_name, summary.target_id, "DESTINATION / replace", "secondary"),
            )
        ]
        if self.width >= 72:
            servers.add_row(*cards)
        else:
            for card in cards:
                servers.add_row(card)
        self.console.print(servers, width=self.width)
        self.console.print(self.panel(self.metrics(summary), title="TO CREATE", style="muted"))
        details = Table.grid(padding=(0, 2), expand=True)
        details.add_column(style="muted", no_wrap=True)
        details.add_column(ratio=1)
        details.add_row(
            "Remove", f"{summary.delete_channels} channels/categories, {summary.delete_roles} roles"
        )
        details.add_row("Replace", "Server name, icon, and @everyone permissions")
        details.add_row("Keep", "Managed roles; member role assignments are not copied")
        if summary.retained_role is not None:
            details.add_row("Access role", literal(summary.retained_role, "good"))
        if summary.limited_bitrates:
            details.add_row(
                "Voice limit", f"{summary.limited_bitrates} channels use destination bitrate"
            )
        if summary.static_icon:
            details.add_row("Icon", "Animated icon converted to a static PNG")
        self.console.print(self.panel(details, title="CHANGES", style="muted"))
        self.role_name_changes(summary)
        self.channel_type_changes(summary)
        self.recovery_notes(summary.issues)
        if summary.skipped_member_overwrites:
            self.console.print(
                self.panel(
                    Text(
                        f"{summary.skipped_member_overwrites} member-specific permission overwrites "
                        f"across {summary.skipped_member_channels} channels/categories will be skipped "
                        "because those members are not in the destination.\n"
                        "Channels, role permissions, and overwrites for existing members are still copied.",
                        style="warning",
                    ),
                    title="COPY NOTE",
                    style="warning",
                )
            )

    def channel_type_changes(self, summary: CopySummary) -> None:
        if not summary.converted_channels and not summary.skipped_channels:
            return
        channels = Table.grid(padding=(0, 2), expand=True)
        channels.add_column(style="warning")
        channels.add_column(ratio=1)
        changes = [
            ("Copy as text", identifier, name, kind)
            for identifier, name, kind in summary.converted_channels
        ] + [
            ("Skip", identifier, name, kind) for identifier, name, kind in summary.skipped_channels
        ]
        for action, identifier, name, kind in changes[:8]:
            channels.add_row(action, literal(f"{name} ({kind}, ID {identifier})"))
        if len(changes) > 8:
            channels.add_row("", f"...and {len(changes) - 8} more")
        self.console.print(
            self.panel(
                Group(
                    Text(
                        f"{len(summary.converted_channels)} announcement channels copied as text; "
                        f"{len(summary.skipped_channels)} unsupported channels skipped. "
                        "Announcement publishing and following are not copied.",
                        style="warning",
                    ),
                    Text(),
                    channels,
                ),
                title="CHANNEL TYPE ADJUSTMENTS",
                style="warning",
            )
        )

    def role_name_changes(self, summary: CopySummary) -> None:
        if not summary.renamed_roles:
            return
        names = Table.grid(padding=(0, 2))
        names.add_column(style="muted")
        names.add_column()
        for source_id, name in summary.renamed_roles[:8]:
            names.add_row(str(source_id), literal(name))
        if len(summary.renamed_roles) > 8:
            names.add_row("", f"...and {len(summary.renamed_roles) - 8} more")
        self.console.print(
            self.panel(
                Group(
                    Text(
                        f"{len(summary.renamed_roles)} role names adjusted for copying. "
                        "Permissions and role mappings are preserved.",
                        style="warning",
                    ),
                    Text(),
                    names,
                ),
                title="ROLE NAME ADJUSTMENTS / SOURCE ID TO NEW NAME",
                style="warning",
            )
        )

    def confirm(self, target_id: int) -> str:
        self.console.print(
            self.panel(
                Text(
                    "Destination channels, their messages, and editable roles will be deleted.\n"
                    "This cannot be undone. There is no automatic rollback.",
                    style="warning",
                ),
                title="CONFIRM REPLACEMENT",
                style="warning",
            )
        )
        return self.prompt(
            "Destination server ID", hint=f"Type {target_id} to begin; any other value cancels."
        )

    def confirm_recovery(self, issue: CopyIssue) -> bool:
        """Suspend animation while stdin is read in the client's worker thread."""
        activity = self.live or self.status
        if activity is not None:
            activity.stop()
        try:
            body = Text("\n").join(
                literal(line)
                for line in (
                    f"Step: {issue.phase}",
                    f"Item: {issue.item}",
                    *issue.reason.splitlines(),
                    "",
                    f"If you continue: {issue.consequence}",
                )
            )
            self.console.print(self.panel(body, title="RECOVERABLE ISSUE", style="warning"))
            while True:
                answer = (
                    self.prompt(
                        "Continue? [y/N]",
                        hint="y/yes (e/evet): accept this omission; n/no or Enter: stop.",
                    )
                    .strip()
                    .casefold()
                )
                if answer in {"y", "yes", "e", "evet"}:
                    return True
                if answer in {"", "n", "no", "h", "hayir", "hayır"}:
                    return False
                self.note("Please enter y or n.")
        finally:
            if activity is not None:
                activity.start()

    def recovery_notes(self, issues: tuple[CopyIssue, ...]) -> None:
        if not issues:
            return
        rows = []
        for index, issue in enumerate(issues, 1):
            rows.extend(
                [
                    literal(f"{index}. {issue.phase} / {issue.item}", "warning"),
                    *(literal(line) for line in issue.reason.splitlines()),
                    literal(issue.consequence),
                    Text(),
                ]
            )
        self.console.print(
            self.panel(
                Group(*rows),
                title=f"OMISSIONS AND ADJUSTMENTS ({len(issues)})",
                style="warning",
            )
        )

    def _progress_panel(self) -> Panel:
        activity = Table.grid(padding=(0, 2), expand=True)
        activity.add_column(style="good", no_wrap=True)
        activity.add_column(ratio=1)
        for (phase, name), skipped in zip(self.recent, self.recent_skipped, strict=True):
            activity.add_row(
                Text("SKIP" if skipped else "DONE", style="warning" if skipped else "good"),
                literal(f"{phase} / {name}", "muted"),
            )
        return self.panel(
            Group(
                literal(self.phase, "heading"),
                literal(self.item, "accent"),
                Text(),
                self.progress,
                Text(f"{self.skipped_steps} skipped steps", style="warning")
                if self.skipped_steps
                else Text(),
                Text(),
                activity,
            ),
            title="03 / MIRRORING",
        )

    @contextmanager
    def copying(self, total: int) -> Iterator[None]:
        self.recent.clear()
        self.recent_skipped.clear()
        self.skipped_steps = 0
        self.phase, self.item = "Preparing copy", "Waiting for the first operation"
        self.progress = Progress(
            BarColumn(
                bar_width=None, style="bright_black", complete_style="cyan", finished_style="green"
            ),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=self.console,
            auto_refresh=False,
            expand=True,
        )
        self.task_id = self.progress.add_task("Copying", total=total)
        started = time.monotonic()
        self.console.print()
        self.live = (
            Live(
                console=self.console,
                get_renderable=self._progress_panel,
                refresh_per_second=8,
                transient=True,
                redirect_stdout=False,
                redirect_stderr=False,
            )
            if self.console.is_interactive
            else None
        )
        if self.live is not None:
            self.live.start()
        try:
            yield
        finally:
            self.elapsed = time.monotonic() - started
            if self.live is not None:
                self.live.stop()
                self.live = None

    def report(self, phase: str, item: str, completed: bool) -> None:
        if self.progress is None or self.task_id is None:
            return
        if not self.console.is_interactive and phase != self.phase:
            self.console.print(literal(phase, "accent"))
        self.phase, self.item = phase, item
        if completed:
            self.progress.advance(self.task_id)
            self.recent.append((phase, item))
            self.recent_skipped.append(False)
        if self.live is not None:
            self.live.refresh()

    def report_skip(self, phase: str, item: str) -> None:
        if self.progress is None or self.task_id is None:
            return
        self.phase, self.item = phase, item
        self.skipped_steps += 1
        self.progress.advance(self.task_id)
        self.recent.append((phase, item))
        self.recent_skipped.append(True)
        if self.live is not None:
            self.live.refresh()
        else:
            self.console.print(literal(f"SKIP: {phase} / {item}", "warning"))

    def completed(self, summary: CopySummary) -> None:
        minutes, seconds = divmod(int(self.elapsed), 60)
        style = "warning" if summary.has_omissions else "good"
        self.console.print(
            self.panel(
                Group(
                    literal(summary.target_name, "heading"),
                    Text(f"Copy finished in {minutes:02d}:{seconds:02d}.", style=style),
                    Text(
                        f"{summary.skipped_steps} skipped steps. Counts show items created.",
                        style=style,
                    ),
                    Text(),
                    self.metrics(summary),
                    Text(),
                    Text("Review destination permissions before inviting members.", style="muted"),
                ),
                title="COPY FINISHED WITH WARNINGS" if summary.has_omissions else "COPY COMPLETE",
                style=style,
            )
        )
        self.role_name_changes(summary)
        self.channel_type_changes(summary)
        self.recovery_notes(summary.issues)
        if summary.skipped_member_overwrites:
            self.note(
                f"Skipped {summary.skipped_member_overwrites} overwrites for members absent from "
                "the destination. Review their permissions if they join later."
            )

    def preview_complete(self) -> None:
        self.console.print(
            self.panel(
                Text("No changes made. Run again with --apply when you are ready.", style="accent"),
                title="PREVIEW COMPLETE",
            )
        )

    def cancelled(self, message: str = "No changes made.") -> None:
        self.console.print(self.panel(literal(message), title="CANCELLED", style="warning"))

    def error(self, message: str) -> None:
        body = Text("\n").join(literal(line) for line in message.splitlines())
        if self.progress is not None and self.task_id is not None:
            task = self.progress.tasks[self.task_id]
            body.append("\n\nFailed step: ", style="muted")
            body.append(literal(self.phase, "heading"))
            body.append("\nItem: ", style="muted")
            body.append(literal(self.item))
            body.append(
                f"\n\nCompleted {int(task.completed)} of {int(task.total or 0)} steps.",
                style="muted",
            )
            if self.skipped_steps:
                body.append(f" Includes {self.skipped_steps} skipped steps.", style="warning")
        self.error_console.print(self.panel(body, title="OPERATION STOPPED", style="danger"))


def demo(ui: TerminalUI) -> None:
    """Show the actual interface with synthetic data and no network access."""
    summary = CopySummary(
        source_name="discord.gg/tkp",
        source_id=111111111111111111,
        target_name="discord.gg/tkp Mirror",
        target_id=222222222222222222,
        roles=9,
        categories=3,
        text_channels=12,
        voice_channels=2,
        delete_channels=4,
        delete_roles=0,
    )
    ui.banner(demo=True)
    ui.preview(summary)
    steps = [
        ("Removing old channels", "welcome"),
        ("Creating roles", "Community Lead"),
        ("Creating roles", "Moderator"),
        ("Creating categories", "INFORMATION"),
        ("Creating categories", "COMMUNITY"),
        ("Creating channels", "announcements"),
        ("Creating channels", "general"),
        ("Creating channels", "Lounge"),
        ("Restoring channel order", "general"),
        ("Updating server identity", "discord.gg/tkp"),
    ]
    with ui.copying(len(steps)):
        for phase, name in steps:
            ui.report(phase, name, False)
            if ui.console.is_interactive:
                time.sleep(0.25)
            ui.report(phase, name, True)
    ui.completed(summary)
    ui.note("Demo finished. All names and results above are simulated.")