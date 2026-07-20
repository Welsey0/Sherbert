## Developing with ST Family Modpacks
This guide explains how to set up a development environment for Sherbert and other packs using ST Family tooling.

### Step 1: Install Packwiz
Download the latest Packwiz executable for your platform from the [Packwiz repository](https://github.com/packwiz/packwiz).

### Step 2: Clone This Repository
Choose a working folder, place your Packwiz executable there, then clone Sherbert.

```bash
git clone https://github.com/Welsey0/Sherbert.git
```

### Step 3: Match the Expected Layout
STManager expects you project to follow this layout:

```text
Root Folder (example: Modpacks)
├── packwiz executable
└── Modpack Name (Sherbert repo root)
    ├── .github
    ├── src
    ├── templates
    ├── packinfo.toml
    └── stmanager.py
```

STManager also checks the repo root and PATH, but the parent-folder layout above is the default recommendation.

### Finished!
You are now fully set up to develop with the Sherbert modpack.

## STManager
STManager is a Python CLI tool that acts as a layer on top of the excellent packwiz tool, allowing a modpack to be defined with one file, `packinfo.toml`. It also provides various bespoke utilies to help with this workflow. STManager is equipped with a help flag that explains all of it's functions. The output of that is below:
```text
ST Manager

positional arguments:
  {setup-folders,sync-loaders,sync-content,update-variable-values,validate,build,quick-build,qb,cleanup,c,cu,setup-workspace}
    setup-folders       Create src-<loader> folders from packinfo ground truth
    sync-loaders        Sync existing src-* folders from packinfo/src changes
    sync-content        Sync local files, remote exceptions, pinned remotes, and Packwiz remotes into each src-* folder
    update-variable-values
                        Replace version tokens in files listed under [variablevalues].version
    validate            Validate src-* loader structure against packinfo ground truth
    build               Run packwiz refresh/export and move the final .mrpack files to root
    quick-build (qb)    Runs all the commands to build the modpack in sequence
    cleanup (c, cu)     Cleans up generated files from builds
    setup-workspace     Sets up files and folders for a new modpack

options:
  -h, --help            show this help message and exit
  --dry-run             Print actions without running packwiz or writing changes
```

## Notes
- Releases will fail to publish when a version is reused. In the case that this happens accidentally, update the number and dispatch the workflow manually.
- Check `templates/packinfo.toml` for a commented template version of the file to better understand what can be done with it.
- Set `allow_different_mc = true` on a pinned remote when intentionally installing a different Minecraft-compatible version.
- Pushing `changelog.md` triggers the release workflow.
- Pushing `README.md` updates the Modrinth description.