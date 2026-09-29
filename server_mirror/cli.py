"""Command-line entry point for Server Mirror."""

import argparse
import asyncio
import getpass
import os
import warnings

import discord

from server_mirror.core.clone import Clone, CloneCancelled, CloneError
from server_mirror.core.discord_errors import http_error_message
from server_mirror.core.recovery import CopyIssue
from server_mirror.ui.terminal import CopySummary, TerminalUI, demo


def guild_id(value: str) -> int:
    """Parse a positive Discord snowflake."""
    if not value.isascii() or not value.isdecimal() or not 0 < int(value) < 2**64:
        raise argparse.ArgumentTypeError("Server IDs must be positive decimal integers.")
    return int(value)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m server_mirror",
        description="Preview or copy a Discord server's structure using your account token.",
    )
    parser.add_argument("--source", type=guild_id, help="Source server ID")
    parser.add_argument("--target", type=guild_id, help="Destination server ID")
    parser.add_argument(
        "--apply", action="store_true", help="Apply the copy after an interactive confirmation"
    )
    parser.add_argument(
        "--demo", action="store_true", help="Preview the interface offline with sample data"
    )
    args = parser.parse_args(argv)
    if args.source is not None and args.source == args.target:
        parser.error("Source and destination must be different servers.")
    return args


def read_token(ui: TerminalUI | None = None) -> str:
    token = os.environ.get("DISCORD_USER_TOKEN", "").strip()
    if not token:
        if ui is not None:
            ui.console.print()
            ui.console.print("[brand]Account token[/brand]")
            ui.note("Hidden input. Your token is never displayed or saved.")
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            try:
                token = getpass.getpass("  > " if ui else "Account token (hidden): ").strip()
            except getpass.GetPassWarning as error:
                raise ValueError(
                    "Hidden input is unavailable. Set DISCORD_USER_TOKEN in your environment."
                ) from error
    if not token or any(character.isspace() for character in token):
        raise ValueError("Provide your account token without whitespace or a 'Bot ' prefix.")
    return token


class MirrorClient(discord.Client):
    def __init__(
        self, source_id: int, target_id: int, *, apply: bool = False, ui: TerminalUI | None = None
    ):
        super().__init__(chunk_guilds_at_startup=False, guild_subscriptions=False)
        self.source_id = source_id
        self.target_id = target_id
        self.apply = apply
        self.started = False
        self.exit_code = 1
        self.ui = ui or TerminalUI()

    async def recover(self, issue: CopyIssue) -> bool:
        if not self.apply:
            return True
        return await asyncio.to_thread(self.ui.confirm_recovery, issue)

    async def on_ready(self) -> None:
        if self.started:
            return
        self.started = True
        copy_started = False
        clone = None
        try:
            source = self.get_guild(self.source_id)
            target = self.get_guild(self.target_id)
            if source is None or target is None:
                raise CloneError("Your account must be a member of both selected servers.")
            clone = Clone(
                source,
                target,
                report=self.ui.report,
                recover=self.recover,
                report_skip=self.ui.report_skip,
            )
            with self.ui.busy("Checking server access, permissions, and copy settings..."):
                await clone.prepare()
            summary = CopySummary.from_clone(clone)
            self.ui.preview(summary)
            if not self.apply:
                self.ui.preview_complete()
                self.exit_code = 0
                return
            confirmation = await asyncio.to_thread(self.ui.confirm, target.id)
            if confirmation.strip() != str(target.id):
                self.ui.cancelled()
                self.exit_code = 2
                return
            with self.ui.copying(clone.operation_count):
                copy_started = True
                await clone.execute()
            result = CopySummary.from_clone(clone)
            self.ui.completed(result)
            self.exit_code = 3 if result.has_omissions else 0
        except CloneCancelled as error:
            state = (
                "Earlier changes remain; the destination is partially modified."
                if copy_started
                else "No destination changes were made."
            )
            self.ui.cancelled(f"{error} {state}")
            self.exit_code = 2
        except CloneError as error:
            self.ui.error(str(error))
        except discord.HTTPException as error:
            self.ui.error(http_error_message(error, copy_started=copy_started))
        except EOFError:
            self.ui.cancelled(
                "Confirmation input ended; the destination may be partially modified."
                if copy_started
                else "Confirmation input ended; no changes made."
            )
            self.exit_code = 130
        except OSError:
            self.ui.error("Input or connection failed. Inspect the destination before retrying.")
        except Exception as error:
            self.ui.error(
                f"Unexpected {type(error).__name__}. Copy stopped; "
                "inspect the destination before retrying."
            )
        finally:
            try:
                if clone is not None and self.exit_code not in {0, 3}:
                    self.ui.recovery_notes(tuple(clone.issues))
            finally:
                await self.close()


async def connect(
    token: str, source_id: int, target_id: int, *, apply: bool, ui: TerminalUI | None = None
) -> int:
    async with MirrorClient(source_id, target_id, apply=apply, ui=ui) as client:
        await client.start(token, reconnect=False)
        return client.exit_code


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ui = TerminalUI()
    try:
        if args.demo:
            demo(ui)
            return 0
        ui.banner(apply=args.apply)
        source_id = args.source or guild_id(
            ui.prompt("Source server ID", hint="The server to read from.").strip()
        )
        target_id = args.target or guild_id(
            ui.prompt("Destination server ID", hint="The server to replace.").strip()
        )
        if source_id == target_id:
            raise ValueError("Source and destination must be different servers.")
        token = read_token(ui)
        ui.console.print()
        ui.note("Connecting to Discord...")
        return asyncio.run(connect(token, source_id, target_id, apply=args.apply, ui=ui))
    except discord.LoginFailure:
        ui.error("Login failed. Use a valid token for your own Discord account.")
    except (ValueError, argparse.ArgumentTypeError) as error:
        ui.error(str(error))
    except (EOFError, KeyboardInterrupt):
        ui.cancelled("If copying had started, inspect the destination before retrying.")
        return 130
    except (discord.DiscordException, OSError) as error:
        ui.error(
            f"Connection failed ({type(error).__name__}). Check account access and connectivity."
        )
    return 1