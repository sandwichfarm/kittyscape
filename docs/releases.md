# Release notes

## 0.1.0.dev1 · local development build

The local archive and website are being qualified against the product requirements. No package or website
has been published, and macOS arm64 qualification remains open.

This build provides shared directory rules, native Bash/Zsh/Fish reporting, per-OS-window image ownership,
restoration, explicit lifecycle controls, and reversible user-local setup. The landing page and documentation
are one VitePress site.

See the [compatibility matrix](./reference/compatibility.md) for tested versions, configuration profiles,
and unresolved target gates. See [installation](./guide/installation.md) for the local artifact workflow.
Artifact identity and completed validation rows are recorded in the [release record](/evidence/release.json).
The [release checklist](./development/release-checklist.md) describes the remaining delivery gates.

## Before a public release

Release preparation must bind the artifact checksum, runtime matrix, installation roundtrip, and documentation
to the same version. A release must identify support changes and restoration limitations explicitly.

Repository, release channel, project license, and hosting remain unselected.
