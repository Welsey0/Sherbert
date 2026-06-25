# Forking for Your Own Use
You are welcome to fork ST Family tooling for your own modpack projects. If you reuse this tooling, please credit this repository.

## Step 1: Set Up Development Environment
Follow [DEVELOPING.md](../DEVELOPING.md) first.

## Step 2: Understand the New Flow
This repo uses:
- `packinfo.toml` as source of truth.
- `src/` as base content.
- `src-*` loader folders generated and maintained by STManager.

Avoid editing generated loader folders manually unless you know exactly why.

## Step 3: Forking Paths
### Keep Sherbert content as a base
1. Fork the repository.
2. Update metadata in `packinfo.toml`.
3. Run:

```bash
python stmanager.py setup-folders --yes
python stmanager.py sync-loaders
python stmanager.py sync-content --write-unsuccessful
python stmanager.py update-updatables
python stmanager.py validate
```

### Start a new pack from tooling only
1. Keep tooling files and workflow files.
2. Replace `src/` content with your own base files and config.
3. Update `packinfo.toml` (`targets`, remotes, nonremotes, updatables, and optional pinned remotes).
4. Run the same STManager commands as above.

## Step 4: Modrinth Setup
The workflows in this repo are designed for publishing on [Modrinth](https://modrinth.com).

Helpful support links:
- [Modpacks on Modrinth](https://support.modrinth.com/en/articles/8802250-modpacks-on-modrinth)
- [Sharing Modpacks](https://support.modrinth.com/en/articles/8797522-sharing-modpacks)

## Step 5: GitHub Secrets and Permissions
Create these repository secrets:
- `MODRINTH_TOKEN`
- `MODRINTH_PID`

Recommended PAT scopes:
- Create versions
- Write projects
- Write versions

Also set repository workflow permissions to `Read and write permissions`.
## Notes
- `[[content.pinned_remote]]` lets you pin exact Modrinth version IDs.
- Set `allow_different_mc = true` for a pinned remote when you intentionally want a version from a different Minecraft line.
- Refer to [Packwiz documentation](https://packwiz.infra.link/) for deeper Packwiz usage.