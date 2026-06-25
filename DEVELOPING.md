# Developing for ST Family Modpacks
This guide explains how to set up a development environment for Sherbert and other packs using ST Family tooling.

## Step 1: Install Packwiz
Download the latest Packwiz executable for your platform from the [Packwiz repository](https://github.com/packwiz/packwiz).

## Step 2: Clone This Repository
Choose a working folder, place your Packwiz executable there, then clone Sherbert.

```bash
git clone https://github.com/Welsey0/Sherbert.git
```

## Step 3: Match the Expected Layout
STManager auto-resolves Packwiz from this layout:

```text
Root Folder (example: Modpacks)
├── packwiz executable
└── Sherbert
    ├── .github
    ├── src
    ├── templates
    ├── packinfo.toml
    └── stmanager.py
```

STManager also checks the repo root and PATH, but the parent-folder layout above is the default recommendation.

## Step 4: Bootstrap Loader Folders
From the repository root:

```bash
python stmanager.py --dry-run setup-folders --yes
python stmanager.py setup-folders --yes
```

This creates and prepares `src-<loader>` folders based on `packinfo.toml`.

## Step 5: Daily Workflow
Use these commands from the repository root:

```bash
python stmanager.py guide
python stmanager.py sync-loaders
python stmanager.py --dry-run add-remotes
python stmanager.py add-remotes --write-unsuccessful
python stmanager.py validate --report-file validation-report.json
python stmanager.py --dry-run build
```

## Notes
- `packinfo.toml` is source of truth.
- Release safety checks now fail publish when a version is reused (existing tag/release/Modrinth version) or when `src/pack.toml` and `packinfo.toml` versions do not match.
- Paths in `content.nonremote`, `content.remote_exception`, and `updatables.version` are relative to each `src-*` folder root.
- For exact Modrinth version pinning, use `[[content.pinned_remote]]` entries.
- Set `allow_different_mc = true` on a pinned remote when intentionally installing a different Minecraft-compatible version.
- Pushing `changelog.md` triggers the release workflow.
- Pushing `README.md` updates the Modrinth description.