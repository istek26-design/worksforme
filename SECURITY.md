# Security policy

## Supported versions

Security fixes currently target the latest 0.1.x release. Older versions and
unreleased forks are not supported. No response-time or service-level guarantee is made.

## Report a vulnerability privately

Do not disclose exploitable security details, credentials or real `.env` contents
in public issues, discussions, pull requests or logs. Prefer GitHub **Private
Vulnerability Reporting**: open the repository's Security tab and choose **Report a
vulnerability** when enabled. If that option is unavailable, contact the maintainer
using a private contact method actually listed on their GitHub profile; do not
invent an address or post the exploit publicly. If no private channel is available,
wait for one or use GitHub Support for platform security concerns.

Include the affected version, platform, a sanitized minimal reproduction, impact
and proposed mitigation if known. Use fake credentials and generic paths. Never
include API keys, passwords, tokens, private index URLs or private keys.

## Security boundaries

- Diagnosis statically reads Python source and metadata; it never imports project
  code or executes setup.py. Third-party checks explicitly imported by Python users
  are trusted code and are outside this boundary.
- `.env` values are inspected for presence, never reported or persisted. Reports
  contain variable/package names and interpreter/project paths; redact private metadata.
- Repairs refuse global Python installation, require an active virtual environment
  and explicit default-No confirmation, and use argument arrays without a shell.
- Direct URLs, extras, ambiguous metadata and manager-specific changes require
  manual review. No telemetry, sudo, deletion or automatic secret edits are used.
- Package managers and installed dependencies remain trusted software. Downloads
  and builds may run third-party code. Resolver preflight is not a sandbox or rollback.
- A failed installation may partially change the environment. Back up, commit,
  review `fix --dry-run`, and rerun diagnosis after repairs.

If a credential is exposed, revoke or rotate it and remove it from Git history as
appropriate. Deleting a file alone does not invalidate a leaked credential.
