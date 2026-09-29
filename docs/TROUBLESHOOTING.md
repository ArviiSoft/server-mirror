# Troubleshooting

## Discord rejects request data (HTTP 400, code 50035)

Discord rejected a request field. The code alone does not identify the field: check `Rejected fields`, `Failed step`, and `Item` in the error panel. For example, `permissions: NUMBER_TYPE_MAX` identifies a permission value outside an accepted range; `colors.primary_color` identifies a role color. These are examples, not a diagnosis of every 50035 response.

The panel preserves the completed step count after the live display closes. It shows only field paths and validation codes from Discord's structured response, never the raw response or submitted values. If no structured details are available from the library, the panel says so.

An item-specific rejection now shows **RECOVERABLE ISSUE** with the affected step/item and the exact consequence of continuing. Answer `y`/`yes` (or `e`/`evet`) to accept that omission and continue the current run. Answer `n`/`no` or Enter to stop. Invalid input prompts again. A rejected creation skips the entire role/channel rather than silently dropping its permissions. A skipped role's overwrites and a skipped channel's later ordering step are also handled.

If the error occurred during copying, some destination changes may already have happened. Restarting the program starts a new replacement, not a resume. When reporting the failure, include the failed step, item, rejected fields, and completed step count; never include your account token.

## Role creation fails with `name: BASE_TYPE_BAD_LENGTH`

Discord rejected the role name's length. A blank `Item` often means the source name is empty or contains only spaces or invisible characters.

Server Mirror now checks role names during preparation. Empty or invisible-only names become `Role <source ID>`, control characters and surrounding whitespace are removed, and long names are limited to [Discord's 100-character maximum](https://docs.discord.com/developers/resources/guild#create-guild-role). The preview lists adjusted destination names before confirmation. The source role is unchanged, and its permissions and channel overwrites still map to the copied role by ID.

If Discord rejects another name specifically with `BASE_TYPE_BAD_LENGTH`, the tool retries that role once with the ID-based name. The completion summary includes these additional adjustments. If that fallback is also rejected, or other role fields are rejected, you can accept skipping the role and its overwrites. Authentication, lost server access, and uncertain connection/write failures remain fatal.

## `Client.run() got an unexpected keyword argument 'bot'`

That argument belongs to the legacy application. The current `discord.py-self` client accepts your account token directly. Do not add `bot=False` or install discord.py 1.7.3. Follow the migration commands in the README to remove conflicting packages before installing requirements.

## Login failed

Use a valid token for your own Discord account. Do not include the `Bot ` prefix, quotes, or spaces. Check that `DISCORD_USER_TOKEN` does not contain an old token; unset it to use the hidden prompt instead. Bot tokens are not supported by this version.

## The account cannot find a server

Verify the copied server IDs and ensure the account associated with the token belongs to both servers. You do not need to create or invite a bot.

## Administrator or role hierarchy check failed

Administrator is required only in the destination. In the source, membership is sufficient: the tool does not require Administrator, Manage Server, or View Channel to copy channel metadata Discord has supplied. Ordinary roles are copied even if your account does not hold them.

If you do not own the destination, your highest role must directly grant Administrator and sit above every other ordinary role. That role is preserved so deleting other roles cannot remove your access. A destination owner does not need this retained role and can replace all ordinary roles.

## Hidden source channels

The copy uses the entire channel/category list supplied by Discord, without filtering by your channel permissions. Hidden channels are copied when their metadata is present. Messages are never copied. If Discord omits a channel or redacts its name or settings, the original metadata cannot be recovered by the copier. See the [Discord announcement](https://docs.discord.com/developers/change-log#channel-obfuscation-for-users-and-bots).

## Unsupported channel types

Announcement (`news`) channels are copied as standard text channels. Their name, category, order, topic, permission overwrites, and compatible text settings are preserved. Announcement publishing and following are not copied, and the destination does not need Community enabled for these converted channels.

Forum, media, stage, and unrecognized channel types are skipped instead of stopping the copy. The `CHANNEL TYPE ADJUSTMENTS` panel lists converted and skipped channels before confirmation and again on completion. Creation totals and progress count only channels included in the copy. Categories can remain empty if all of their child channels were skipped.

If you see the old `unsupported type 'news'` error, restart the program from the updated project directory. Channel type handling is decided during preparation, before any destination changes.

## Unsupported role overwrite

A role overwrite for another bot or integration cannot be mapped to an ordinary copied role. It no longer forces the entire run to stop. Preview lists the omission. In `--apply` mode, the tool asks whether to skip that role's overwrites across the affected channels/categories. Accepting continues with all remaining permissions. It does not match managed roles by name or give another role their permissions. Review channel access afterward because missing allow/deny rules can change visibility. Overwrites on unsupported channels are not processed.

## A permission overwrite refers to an absent member

The source has a person-specific channel/category permission for someone who is not in the destination. Current versions skip only that person's overwrite and continue copying the channel and its remaining permissions. A yellow copy note reports the skipped count before confirmation, and the completion summary repeats it. You do not need to invite every source member into the destination.

Overwrites for members who are present are preserved. If a skipped member joins later, review their permissions because their original individual rules were not copied. A definite item-specific lookup rejection offers a separate recovery decision and is reported as an unresolved lookup, not as proof the member is absent. Network failures, authentication, and lost server access still stop the operation.

## Community destination

Use a destination with Community disabled. Community servers require system channels that may not be deletable. A fresh ordinary server is the easiest starting point.

## Lower voice bitrate

The preview reports how many voice channels exceed the destination bitrate limit. Those channels use the destination maximum; higher source boost limits do not transfer.

## Hidden token input is unavailable

Use a normal interactive terminal or inject `DISCORD_USER_TOKEN` into the process environment through your secret manager. The application refuses a prompt that would display your token. It does not load `.env` files.

## Copy stopped partway through

Recoverable failures pause at `Continue? [y/N]`. The live display is suspended while answering, and the Discord event loop remains available. Choosing to continue resumes the same run without repeating completed deletions or creations. A failed category can be omitted with its children created uncategorized; a failed role is removed from subsequent ordering and overwrite mappings. Failed deletions leave the old items in place, so review their permissions and possible duplicates.

If you decline or input ends, copying stops and the panel states whether destination changes may already exist. Critical failures still stop immediately: authentication/verification, lost guild access, missing Administrator access, invalid destination prerequisites, exhausted rate limiting, server failures, uncertain writes/network failures, and unexpected internal errors. These distinctions use [Discord's status and error codes](https://docs.discord.com/developers/topics/opcodes-and-status-codes). Inspect the destination before restarting; completed API requests are not rolled back.

`SKIP` entries count toward processed progress but are not successful operations. The final **COPY FINISHED WITH WARNINGS** panel shows actual created role/channel totals and all accepted recovery details. Exit code `3` means the run reached the end with omissions, `2` means a recovery was declined, and `130` means input ended or the operation was interrupted. Preview continues to return `0` when the read-only plan completes.

HTTP status and Discord error codes are reported without raw response bodies. Include these codes in a sanitized bug report. A fresh destination is usually easier to validate than a partially modified one.

## Windows launcher exits immediately

Create `.venv` and install dependencies as shown in the README. Run `start.bat` from PowerShell or Command Prompt to keep its output visible. The launcher intentionally runs once and returns the Python exit code.

## Python cannot find `server_mirror`

Run `python -m server_mirror` from the repository root, beside `README.md` and
`start.bat`. On Windows, `start.bat` selects the correct working directory and the
project's virtual environment automatically. Do not run individual files inside
`server_mirror` directly. Install dependencies using
`python -m pip install -r requirements/runtime.txt`.