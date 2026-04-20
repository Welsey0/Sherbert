# What Is the ST Family of Minecraft Modpacks?
The [ST Family](https://modrinth.com/collection/tBDkCBOo) is an opinionated set of Minecraft modpacks built for practical day-to-day play.

Sherbert is the tooling base for that family.

It combines:
- Packwiz for dependency management.
- STManager for architecture setup, synchronization, validation, and build routines.
- GitHub Actions for release automation.

Current architecture model:
- `packinfo.toml` is source of truth.
- `src/` stores base content.
- `src-*` folders are generated and synchronized per modloader.

This design keeps pack maintenance repeatable while allowing controlled exceptions like nonremote files and pinned Modrinth versions.