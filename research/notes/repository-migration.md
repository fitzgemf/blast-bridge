# Repository migration record

The working repository was migrated from the former OneDrive project tree to
the user's local workspace on September 16, 2026 (U.S. Eastern time). All work
after verification uses the local workspace repository. Machine-specific paths
are deliberately excluded from tracked documentation.

- Copied and SHA-256 compared 46 nondisposable files, including all 18 files in
  the original `.git` directory. Python environments and tool caches were excluded.
- The original repository was on an unborn `main` branch with no commits. The
  full existing Git state was preserved; no history was rewritten or discarded.
- Rebuilt the Python 3.12 virtual environment, installed the pinned development
  dependencies and reinstalled the editable package against the new directory.
- Confirmed the new Git working tree, local `.git` object storage, `main` branch,
  installed package path and all 121 premigration tests.
- Attempted removal only of the old BlastBridge directory after verification.
  Windows denied removal of `.git`. Inspection found an explicit Everyone deny
  rule for `DeleteSubdirectoriesAndFiles`. The old directory remains. Permissions
  were not changed and deletion was not forced. This is not evidence that
  OneDrive itself locked the files.

The old directory is retired and must not be used for further development.
Its eventual removal requires resolving the Windows deletion permission outside
this migration. The local repository is independent of it. The storage boundary
is documented in [data-governance.md](data-governance.md).
