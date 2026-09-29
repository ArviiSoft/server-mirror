# Security policy

## Supported versions

Security fixes target the latest code on the default branch. Historical revisions are not maintained separately.

## Reporting a vulnerability

Do not post tokens, private server data, or exploit details in public issues.

Use **Security > Report a vulnerability** if the repository has GitHub private vulnerability reporting enabled. If that option is unavailable, use a private contact method listed on the maintainer's GitHub profile. If no private route is listed, open an issue asking for a private reporting channel without including vulnerability details.

Include the affected revision, a description of the impact, and minimal reproduction steps using sanitized or synthetic data.

## Credential exposure

Treat an account token as a password. Secure your Discord account and revoke compromised sessions through account settings if the token is exposed. Removing it from the current files does not remove it from existing commits, forks, logs, or screenshots. Review account activity and server audit logs after exposure.

The repository ignores common local credential files. Ignore rules do not protect secrets already committed to Git.

## Operational safety

Server Mirror can delete destination channels, message history, and editable roles. Use a fresh destination and review the preview before confirming. Copying is not transactional, and failures may leave partial changes. Treat imported role and channel permissions as security-sensitive configuration.

The application uses your own account token through `discord.py-self`, asks for hidden input, and does not persist credentials. Dependencies should be installed into a virtual environment and checked with `python -m pip_audit -r requirements/runtime.txt`.

## Repository maintainer setup

Before publication, enable secret scanning and push protection where available in the repository's **Settings > Code security** area, and enable private vulnerability reporting. These are GitHub repository settings; adding this file does not enable them.
