# Disclaimer

worksforme is an open-source developer tool provided "AS IS" and "AS AVAILABLE",
without warranties or conditions of any kind, subject to the terms of the
[Apache License 2.0](LICENSE) and applicable law. There is no guarantee that the
software is error-free, continuously available, or correct in every environment.
Diagnostic results can contain false positives or false negatives and should be
reviewed alongside your own understanding of the project.

`worksforme fix` can modify dependencies and the Python environment. Depending on
package installation behavior and future supported repair operations, project files
or configuration may also be affected. Automated fixes may produce unexpected
results, dependency conflicts, unwanted file or configuration changes, or a broken
project or environment. Package installation can execute third-party build code.
The current version does not provide transactional rollback; failed installations
may leave partial changes. Read-only diagnosis and dry-run do not eliminate the
risks of a subsequent installation.

You are responsible for backing up important data, using version control, reviewing
proposed changes before applying them, and deciding whether a repair is appropriate.
Before changing an important project, commit current changes and create a suitable
backup. You are strongly encouraged to run `worksforme fix --dry-run` first and use
an isolated, disposable environment when evaluating unfamiliar dependencies.

To the maximum extent permitted by applicable law, maintainers and contributors
are not liable for direct, indirect, incidental, special or consequential losses
arising from use of, or inability to use, this software, including data loss,
environment damage, interruption of work or lost profits. You use the software at
your own risk. Nothing here excludes liability that cannot lawfully be excluded.

This document explains operational risks and does not amend, replace or impose
additional restrictions on the Apache License 2.0. If there is any inconsistency,
the license and applicable law govern.
