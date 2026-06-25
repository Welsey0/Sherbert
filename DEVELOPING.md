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

## Step 5: STManager Quick Guide
Use `stmanager.py` from the repository root for the core pack workflow:

- `python stmanager.py setup-folders --yes` creates or resets each `src-<loader>` folder from `packinfo.toml` and `src/`.
- `python stmanager.py sync-loaders` refreshes existing loader folders from the current source files.
- `python stmanager.py sync-content --write-unsuccessful` syncs local exceptions, nonremotes, pinned remotes, and Packwiz remotes, then writes any failures to `unsuccessful.md`.
- `python stmanager.py update-updatables` replaces the version token in files listed under `updatables.version`.
- `python stmanager.py validate --report-file validation-report.json` checks the generated loader folders against `packinfo.toml` and each loader's `index.toml`, so resource packs, shader packs, and other non-mod files are covered too.
- `python stmanager.py build` refreshes and exports the final `.mrpack` artifacts into the repo root.

For a safe preview, add `--dry-run` to the command you want to inspect first.

## Notes
- `packinfo.toml` is source of truth.
- Release safety checks now fail publish when a version is reused (existing tag/release/Modrinth version) or when `src/pack.toml` and `packinfo.toml` versions do not match.
- Paths in `content.nonremote`, `content.remote_exception`, and `updatables.version` are relative to each `src-*` folder root.
- For exact Modrinth version pinning, use `[[content.pinned_remote]]` entries.
- Set `allow_different_mc = true` on a pinned remote when intentionally installing a different Minecraft-compatible version.
- Pushing `changelog.md` triggers the release workflow.
- Pushing `README.md` updates the Modrinth description.