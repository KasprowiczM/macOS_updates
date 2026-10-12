# Dev Sync System — File Index

This directory (`dev_sync/`) contains the complete private-overlay sync system. Root `dev-sync-*.sh` wrappers call these scripts for backward compatibility.

## Quick Navigation

### For First-Time Users
1. Start here: [QUICK_START.md](QUICK_START.md) — 5-minute setup guide
2. Run the wizard: `bash provider_setup.sh`
3. Then see [README.md](README.md) for full documentation

### For Developers
1. Architecture: See [README.md](README.md#what-gets-synced)
2. Core code: [dev_sync_core.py](dev_sync_core.py)
3. Import safety: [overlay_import.py](overlay_import.py) — overlay import planner (directory manifests, Git-tracked and excluded paths skipped, symlink escapes refused)

### Reference Materials
- Configuration details: [README.md](README.md#configuration)
- Logs and recovery: [README.md](README.md#logs)
- Command reference: [README.md](README.md#commands)

## Files in This Directory

### Documentation

| File | Purpose | Audience |
|------|---------|----------|
| [QUICK_START.md](QUICK_START.md) | 5-minute quick start guide | Users - start here! |
| [README.md](README.md) | Complete documentation | Everyone |
| [INDEX.md](INDEX.md) | This file - navigation guide | Everyone |

### Core Implementation

| File | Purpose |
|------|---------|
| [dev_sync_core.py](dev_sync_core.py) | Main logic: providers, config, classification, transfer, manifest and verification |
| [overlay_import.py](overlay_import.py) | Import planner: expands directory manifests, skips Git-tracked and excluded paths, refuses symlink escapes |
| [dev_sync_export.py](dev_sync_export.py) | CLI for exporting files to cloud |
| [dev_sync_import.py](dev_sync_import.py) | CLI for importing files from cloud |
| [dev_sync_verify_full.py](dev_sync_verify_full.py) | CLI for full verification |
| [dev_sync_verify_git.py](dev_sync_verify_git.py) | CLI for git state verification |
| [dev_sync_prune_excluded.py](dev_sync_prune_excluded.py) | Plan/quarantine stale or generated provider files |
| [dev_sync_purge_quarantine.py](dev_sync_purge_quarantine.py) | Permanently delete reviewed quarantine |
| [dev_sync_proton_status.py](dev_sync_proton_status.py) | Check Proton File Provider upload/offload readiness |
| [provider_setup.sh](provider_setup.sh) | Interactive setup wizard (Bash 3.2+) |
| `dev-sync-*.sh` | Thin shell wrappers around the Python CLIs (root-level copies call these) |
| [__init__.py](__init__.py) | Python package marker |

## Usage Commands

### First Setup
```bash
bash provider_setup.sh
```

### Export Private Files
```bash
bash dev_sync/dev-sync-export.sh                # Export to cloud
bash dev_sync/dev-sync-export.sh --dry-run      # Preview
bash dev_sync/dev-sync-export.sh --verbose      # Show files
```

### Import Private Files
```bash
bash dev_sync/dev-sync-import.sh                # Import from cloud
bash dev_sync/dev-sync-import.sh --dry-run      # Preview
bash dev_sync/dev-sync-import.sh --verbose      # Show files
```

### Verification
```bash
bash dev_sync/dev-sync-verify-git.sh            # Check git state
bash dev_sync/dev-sync-verify-full.sh           # Check git + cloud
bash dev_sync/dev-sync-verify-full.sh --verbose # Detailed report
bash dev_sync/dev-sync-prune-excluded.sh        # Dry-run cleanup candidate report
bash dev_sync/dev-sync-proton-status.sh --full  # Proton upload/offload readiness
```

## Supported Cloud Providers

- **iCloud Drive** — Mac native cloud storage
- **Google Drive** — Google's cloud storage (via Google Drive app)
- **OneDrive** — Microsoft's cloud storage
- **Proton Drive** — Privacy-focused cloud storage
- **Mega.nz** — MEGAsync app or rclone
- **rclone** — Network remotes (S3, B2, Dropbox, etc.)
- **Local** — Any local folder

## Configuration

Configuration file: `.dev_sync_config.json` in project root

```json
{
  "project_name": "macOS_updates",
  "provider": "protondrive",
  "provider_path": "/path/to/cloud/mount",
  "exclude_patterns": [...],
  "include_always": [...]
}
```

Edit with setup wizard: `bash provider_setup.sh`

## Logs

All operations create timestamped logs:
- Location: `dev_sync_logs/`
- Files: `export_*.log`, `import_*.log`, `verify_full_*.log`
- Contains: file lists, operation details, transport method

Example:
```bash
cat dev_sync_logs/export_<timestamp>.log
```

## Architecture Overview

```
CloudProvider (abstract base)
├── LocalFileSystemProvider
│   ├── iCloud
│   ├── Google Drive
│   ├── OneDrive
│   ├── Proton Drive
│   ├── Mega.nz
│   └── Local/Custom
└── RCloneProvider
    ├── S3
    ├── B2
    ├── Dropbox
    └── Any rclone remote
```

Transport methods:
1. **rsync** (if available) — Fast incremental
2. **Python shutil** (fallback) — Universal
3. **rclone copy** (for rclone provider) — Network-aware

Exports to local filesystem providers also write `.dev_sync_manifest.json` into the provider mirror. Imports prefer that manifest so stale files from older exports are not restored.

## Common Tasks

### Switch Cloud Provider
```bash
bash provider_setup.sh
```

### New Mac: Restore Private Files
```bash
bash provider_setup.sh        # Configure provider
bash dev_sync/dev-sync-import.sh       # Import files
```

### After Changing .env
```bash
bash dev_sync/dev-sync-export.sh
```

### Check Sync Status
```bash
bash dev_sync/dev-sync-verify-full.sh --verbose
```

### Clean stale/generated provider files
```bash
bash dev_sync/dev-sync-prune-excluded.sh --plan-out dev_sync_cleanup_plan.json
bash dev_sync/dev-sync-prune-excluded.sh --apply-plan dev_sync_cleanup_plan.json
bash dev_sync/dev-sync-purge-quarantine.sh --apply
```

### Debug Issues
```bash
bash dev_sync/dev-sync-verify-git.sh         # Check git state first
bash dev_sync/dev-sync-verify-full.sh        # Full verification
cat dev_sync_logs/verify_full_*.log # Check logs
```

## Key Concepts

### Export
Copies untracked/ignored files (`.env`, config) to cloud storage.
- Source: Local repository (untracked + ignored files)
- Destination: Cloud provider's `project_name` folder
- Filters: Applies `exclude_patterns` and `include_always`

### Import
Copies private files from cloud back to local repository.
- Source: Cloud provider's `project_name` folder
- Destination: Local repository
- Use on new machines to restore private files

### Verification
Checks that all files are properly synced.
- Git verification: Clean working tree, upstream set
- Full verification: Git state + cloud overlay files
- Report: Lists orphan files, missing files, stale files

## Backward Compatibility

Old `.dev_sync_config.json` files with only `proton_project_root` still work.
The system automatically migrates to the new schema.

```bash
# Old format still works
{
  "project_name": "macOS_updates",
  "proton_project_root": "/path/to/folder"
}

# Gets converted to new format on-the-fly
{
  "provider": "protondrive",
  "provider_path": "/path/to/folder"
}
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Provider not detected | Run `bash provider_setup.sh` and enter path manually |
| Permission denied | Check System Preferences > Cloud app access |
| Git verification fails | Run `git status` and resolve any changes |
| Files not syncing | Check logs: `cat dev_sync_logs/export_*.log` |
| Provider mirror contains generated files | Use `bash dev_sync/dev-sync-prune-excluded.sh --plan-out dev_sync_cleanup_plan.json` |
| rsync not found | Install: `brew install rsync` |
| rclone not found | Install: `brew install rclone` |

See [README.md](README.md#logs) and [README.md](README.md#cleanup-and-quarantine) for more details.

## Adding Custom Providers

The provider classes live in [dev_sync_core.py](dev_sync_core.py). To add a provider:
1. Subclass `CloudProvider`
2. Implement required methods
3. Register in factory function
4. Add to setup wizard

## Getting Help

1. **Quick start**: [QUICK_START.md](QUICK_START.md)
2. **Full guide**: [README.md](README.md)
3. **Command reference**: [README.md](README.md#commands)
4. **Command help**: `bash dev_sync/dev-sync-export.sh --help`

## Dependencies

- No external Python dependencies (standard library only); transfers use `rsync` or `rclone` depending on the provider
- Bash 3.2+ compatible shell scripts

## Release Notes

### v2.0 (Multi-Provider)
- Support for 7 cloud providers
- Plugin architecture with CloudProvider classes
- Interactive setup wizard with auto-detection
- Backward compatible with v1 configurations
- Enhanced error handling and logging
- Comprehensive documentation
- Tested and validated
