"""ST Manager
Command line tool for managing ST Family modpacks.

This keeps only the user-facing workflow needed to bootstrap, sync,
and validate loader folders from packinfo.toml.
"""

from __future__ import annotations

import argparse
import importlib
import datetime as dt
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


try:
	_TOML = importlib.import_module("tomllib")
except ModuleNotFoundError:
	try:
		_TOML = importlib.import_module("tomli")
	except ModuleNotFoundError:
		_TOML = None


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
PACKINFO_PATH = ROOT / "packinfo.toml"
TEMPLATE_PACK_PATH = ROOT / "templates" / "pack.toml"
TEMPLATE_INDEX_PATH = ROOT / "templates" /  "index.toml"
UNSUCCESSFUL_PATH = ROOT / "unsuccessful.md"


@dataclass
class RunResult:
	command: list[str]
	cwd: Path
	returncode: int
	stdout: str
	stderr: str

	@property
	def ok(self) -> bool:
		return self.returncode == 0


@dataclass
class Issue:
	level: str
	code: str
	message: str
	hint: str


def load_packinfo() -> dict[str, Any]:
	if not PACKINFO_PATH.exists():
		raise FileNotFoundError(f"Missing {PACKINFO_PATH}")
	if _TOML is None:
		raise RuntimeError("No TOML parser found. Use Python 3.11+ or install tomli.")
	with PACKINFO_PATH.open("rb") as handle:
		return _TOML.load(handle)


def content_section(packinfo: dict[str, Any], section: str) -> dict[str, Any]:
	nested = packinfo.get("content", {}).get(section, {})
	top_level = packinfo.get(section, {})
	merged: dict[str, Any] = {}
	if isinstance(top_level, dict):
		merged.update(top_level)
	if isinstance(nested, dict):
		merged.update(nested)
	return merged


def active_loaders(packinfo: dict[str, Any]) -> list[str]:
	loaders: list[str] = []
	for key, value in packinfo.get("targets", {}).items():
		if key != "mc" and str(value).lower() != "none":
			loaders.append(key)
	return loaders


def loader_dirs(packinfo: dict[str, Any]) -> dict[str, Path]:
	return {loader: ROOT / f"src-{loader}" for loader in active_loaders(packinfo)}


def loader_entries(packinfo: dict[str, Any], loader: str) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
	shared_section = packinfo.get("content", {}) if isinstance(packinfo.get("content", {}), dict) else {}
	loader_section = content_section(packinfo, loader)
	remotes = [item for item in list(packinfo.get("all", {}).get("remotes", [])) + list(loader_section.get("remotes", [])) if item]
	pinned = [item for item in list(shared_section.get("pinned_remote", [])) + list(loader_section.get("pinned_remote", [])) if isinstance(item, dict)]
	exceptions = [item for item in list(shared_section.get("remote_exception", [])) + list(loader_section.get("remote_exception", [])) if isinstance(item, dict)]
	nonremotes = [item for item in list(shared_section.get("nonremote", [])) + list(loader_section.get("nonremote", [])) if isinstance(item, dict)]
	return remotes, pinned, exceptions, nonremotes


def expected_files_for_loader(packinfo: dict[str, Any], loader: str) -> list[str]:
	remotes, pinned, exceptions, nonremotes = loader_entries(packinfo, loader)
	files = [f"mods/{item}.pw.toml" for item in remotes]
	files.extend(f"mods/{str(item.get('id', '')).strip()}.pw.toml" for item in pinned if str(item.get("id", "")).strip())
	files.extend(str(item.get("file", "")).strip() for item in nonremotes if str(item.get("file", "")).strip())
	files.extend(str(item.get("file", "")).strip() for item in exceptions if str(item.get("file", "")).strip())
	return sorted(set(files))


def resolve_packwiz_executable() -> str | None:
	names = ["packwiz"]
	if os.name == "nt":
		names = ["packwiz.exe", "packwiz.cmd", "packwiz.bat", "packwiz"]
	for base in (ROOT.parent, ROOT):
		for name in names:
			candidate = base / name
			if candidate.is_file():
				return str(candidate)
	return shutil.which("packwiz")


def require_packwiz(dry_run: bool) -> str:
	executable = resolve_packwiz_executable()
	if executable:
		return executable
	if dry_run:
		return "packwiz"
	raise RuntimeError("packwiz executable not found. Place it in the parent folder above this repo, in the repo root, or add it to PATH.")


def run_cmd(command: list[str], cwd: Path, *, dry_run: bool) -> RunResult:
	if dry_run:
		message = f"[dry-run] ({cwd.name}) {' '.join(command)}"
		print(message)
		return RunResult(command=command, cwd=cwd, returncode=0, stdout=message, stderr="")

	completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
	if completed.stdout:
		print(completed.stdout.strip())
	if completed.stderr:
		print(completed.stderr.strip(), file=sys.stderr)
	return RunResult(command=command, cwd=cwd, returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)


def run_packwiz(args: list[str], cwd: Path, *, dry_run: bool) -> RunResult:
	return run_cmd([require_packwiz(dry_run), *args], cwd, dry_run=dry_run)


def ensure_parent(path: Path) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)


def copy_file(src: Path, dst: Path) -> None:
	ensure_parent(dst)
	shutil.copy2(src, dst)


def make_tree_writable(path: Path) -> None:
	for root, dirs, files in os.walk(path, topdown=False):
		for name in [*files, *dirs]:
			entry = Path(root) / name
			try:
				entry.chmod(entry.stat().st_mode | stat.S_IWRITE)
			except OSError:
				pass
	try:
		path.chmod(path.stat().st_mode | stat.S_IWRITE)
	except OSError:
		pass


def _rmtree_onerror(func: Any, path: str, _exc: Any) -> None:
	entry = Path(path)
	try:
		entry.chmod(entry.stat().st_mode | stat.S_IWRITE)
	except OSError:
		pass
	func(path)


def remove_tree(path: Path) -> None:
	if not path.exists():
		return

	last_error: OSError | None = None
	for attempt in range(3):
		make_tree_writable(path)
		try:
			shutil.rmtree(path, onerror=_rmtree_onerror)
			return
		except OSError as exc:
			last_error = exc
			if attempt < 2:
				time.sleep(0.2 * (attempt + 1))

	hint = "Close apps that may be using files there, then re-run the command." if os.name == "nt" else "Close processes using this path and re-run."
	if isinstance(last_error, PermissionError):
		raise RuntimeError(f"Could not remove '{path}'. Access denied. {hint}") from last_error
	raise RuntimeError(f"Could not remove '{path}': {last_error}. {hint}") from last_error


def copy_tree(src: Path, dst: Path) -> None:
	if dst.exists():
		remove_tree(dst)
	shutil.copytree(src, dst)


def render_pack_toml(packinfo: dict[str, Any], loader: str, target_dir: Path) -> None:
	template = TEMPLATE_PACK_PATH.read_text(encoding="utf-8")
	(target_dir / "pack.toml").write_text(
		template.replace("<!NAME!>", str(packinfo.get("name", "")))
		.replace("<!AUTHOR!>", str(packinfo.get("author", "")))
		.replace("<!VERSION!>", str(packinfo.get("version", "")))
		.replace("<!MODLOADER!>", loader)
		.replace("<!LOADERVERSION!>", str(packinfo.get("targets", {}).get(loader, "")))
		.replace("<!MCVERSION!>", str(packinfo.get("targets", {}).get("mc", ""))),
		encoding="utf-8",
	)


def materialize_loader(packinfo: dict[str, Any], loader: str, target_dir: Path, *, dry_run: bool, rebuild: bool) -> None:
	if rebuild and target_dir.exists():
		if dry_run:
			print(f"[dry-run] remove {target_dir}")
		else:
			remove_tree(target_dir)

	if dry_run:
		print(f"[dry-run] create {target_dir}")
	else:
		target_dir.mkdir(parents=True, exist_ok=True)

	for folder in ("mods", "resourcepacks", "shaderpacks"):
		path = target_dir / folder
		if dry_run:
			print(f"[dry-run] mkdir {path}")
		else:
			path.mkdir(parents=True, exist_ok=True)

	config_src = SRC / "config"
	if not config_src.exists():
		raise FileNotFoundError("src/config folder not found; cannot copy base config.")
	if dry_run:
		print(f"[dry-run] copytree {config_src} -> {target_dir / 'config'}")
	else:
		copy_tree(config_src, target_dir / "config")

	index_src = SRC / "index.toml"
	index_dst = target_dir / "index.toml"
	if index_src.exists():
		if dry_run:
			print(f"[dry-run] copy {index_src} -> {index_dst}")
		else:
			copy_file(index_src, index_dst)

	_, _, exceptions, nonremotes = loader_entries(packinfo, loader)
	for entry in [*nonremotes, *exceptions]:
		rel = str(entry.get("file", "")).strip()
		if not rel:
			continue
		src = SRC / rel
		dst = target_dir / rel
		if not src.exists():
			print(f"Warning: source file missing: {src}", file=sys.stderr)
			continue
		if dry_run:
			print(f"[dry-run] copy {src} -> {dst}")
		else:
			copy_file(src, dst)

	if dry_run:
		print(f"[dry-run] render pack.toml for {loader} in {target_dir}")
	else:
		render_pack_toml(packinfo, loader, target_dir)


def copy_local_content(packinfo: dict[str, Any], loader: str, target_dir: Path, *, dry_run: bool) -> None:
	_, _, exceptions, nonremotes = loader_entries(packinfo, loader)
	for entry in [*nonremotes, *exceptions]:
		rel = str(entry.get("file", "")).strip()
		if not rel:
			continue
		src = SRC / rel
		dst = target_dir / rel
		if not src.exists():
			print(f"Warning: source file missing: {src}", file=sys.stderr)
			continue
		if dry_run:
			print(f"[dry-run] copy {src} -> {dst}")
		else:
			copy_file(src, dst)


def setup_folders(*, yes: bool, dry_run: bool) -> int:
	packinfo = load_packinfo()
	loaders = loader_dirs(packinfo)
	if not loaders:
		print("No active loaders found in packinfo targets.", file=sys.stderr)
		return 1

	existing = [path for path in loaders.values() if path.exists()]
	if existing and not yes:
		print("setup-folders would delete existing loader folders. Re-run with --yes to confirm.", file=sys.stderr)
		for path in existing:
			print(f"- {path.name}", file=sys.stderr)
		return 1

	if not SRC.exists():
		print("src folder not found; cannot create modloader folders.", file=sys.stderr)
		return 1

	for loader, path in loaders.items():
		materialize_loader(packinfo, loader, path, dry_run=dry_run, rebuild=True)
		print(f"Prepared {path.name}")
	return 0


def sync_loaders(*, dry_run: bool) -> int:
	packinfo = load_packinfo()
	loaders = loader_dirs(packinfo)
	if not loaders:
		print("No active loaders found in packinfo targets.", file=sys.stderr)
		return 1
	if not SRC.exists():
		print("src folder not found; cannot sync modloader folders.", file=sys.stderr)
		return 1

	for loader, path in loaders.items():
		materialize_loader(packinfo, loader, path, dry_run=dry_run, rebuild=False)
		print(f"Synchronized {path.name}")
	return 0


def pinned_add_commands(entry: dict[str, Any]) -> list[list[str]]:
	base = ["mr", "add", str(entry.get("id", "")).strip(), "--version-id", str(entry.get("version", "")).strip()]
	if bool(entry.get("allow_different_mc", False)):
		return [base + ["--ignore-game-version"], base]
	return [base]


def sync_content_for_loader(packinfo: dict[str, Any], loader: str, loader_dir: Path, *, dry_run: bool) -> tuple[int, int, int, list[tuple[str, str]]]:
	remotes, pinned, exceptions, _ = loader_entries(packinfo, loader)
	exception_notes = {
		str(entry.get("id", "")).strip(): str(entry.get("reason", "")).strip()
		for entry in exceptions
		if str(entry.get("id", "")).strip()
	}
	success = failed = 0
	skipped = 0
	failures: list[tuple[str, str]] = []

	copy_local_content(packinfo, loader, loader_dir, dry_run=dry_run)

	for index, remote_id in enumerate(remotes, start=1):
		if remote_id in exception_notes:
			reason = exception_notes.get(remote_id) or "declared as a local remote exception"
			print(f"[{loader}] skipping local exception {remote_id}: {reason}")
			skipped += 1
			continue
		print(f"[{loader}] adding remote {index}/{len(remotes)}: {remote_id}")
		result = run_packwiz(["-y", "mr", "add", remote_id], loader_dir, dry_run=dry_run)
		if result.ok:
			success += 1
		else:
			failed += 1
			reason = (result.stderr or result.stdout).strip() or "packwiz failed"
			print(f"[{loader}] warning: could not add {remote_id}: {reason}; continuing")
			failures.append((remote_id, reason))

	for index, entry in enumerate(pinned, start=1):
		mod_id = str(entry.get("id", "")).strip()
		version_id = str(entry.get("version", "")).strip()
		if not mod_id or not version_id:
			failed += 1
			failures.append((mod_id or "<missing-id>", "Invalid pinned_remote entry: requires id and version"))
			continue

		print(f"[{loader}] adding pinned remote {index}/{len(pinned)}: {mod_id}@{version_id}")
		command = ["-y", *pinned_add_commands(entry)[0]]
		result = run_packwiz(command, loader_dir, dry_run=dry_run)
		if result.ok:
			success += 1
		else:
			failed += 1
			reason = (result.stderr or result.stdout).strip() or "packwiz failed"
			print(f"[{loader}] warning: could not add {mod_id}@{version_id}: {reason}; continuing")
			failures.append((f"{mod_id}@{version_id}", reason))

	if skipped:
		print(f"[{loader}] skipped {skipped} local exception(s)")

	return success, failed, skipped, failures


def sync_content_option(*, write_unsuccessful: bool, dry_run: bool) -> int:
	require_packwiz(dry_run)
	packinfo = load_packinfo()
	loaders = loader_dirs(packinfo)
	if not loaders:
		print("No active loader folders to process.", file=sys.stderr)
		return 1

	total_success = total_failed = 0
	total_skipped = 0
	all_failures: list[tuple[str, str, str]] = []
	for loader, loader_dir in loaders.items():
		if not loader_dir.exists():
			print(f"Warning: skipping missing folder {loader_dir}", file=sys.stderr)
			continue
		success, failed, skipped, failures = sync_content_for_loader(packinfo, loader, loader_dir, dry_run=dry_run)
		total_success += success
		total_failed += failed
		total_skipped += skipped
		all_failures.extend((loader, remote_id, reason) for remote_id, reason in failures)

	attempted = total_success + total_failed
	percent = (total_success / attempted * 100.0) if attempted else 100.0
	print(f"Sync content summary: {total_success} succeeded, {total_failed} failed, {total_skipped} skipped, {percent:.1f}% success")
	if write_unsuccessful and all_failures:
		lines = ["# Unsuccessful remotes", ""]
		lines.extend(f"- loader={loader} id={remote_id}: {reason}" for loader, remote_id, reason in all_failures)
		UNSUCCESSFUL_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
		print(f"Wrote failure report to {UNSUCCESSFUL_PATH.name}")
	return 0 if total_failed == 0 else 1


def update_updatables(*, dry_run: bool) -> int:
	packinfo = load_packinfo()
	loaders = loader_dirs(packinfo)
	paths = list(packinfo.get("updatables", {}).get("version", []))
	if not paths:
		print("No [updatables].version entries found.")
		return 0
	if not loaders:
		print("No active loaders found in packinfo targets.", file=sys.stderr)
		return 1

	version = str(packinfo.get("version", ""))
	updated = 0
	current = 0
	missing = 0

	for loader, loader_dir in loaders.items():
		if not loader_dir.exists():
			print(f"Warning: skipping missing folder {loader_dir}", file=sys.stderr)
			continue
		for rel in paths:
			target = loader_dir / rel
			if not target.exists():
				missing += 1
				print(f"Warning: updatable path not found for {loader}: {target}", file=sys.stderr)
				continue
			text = target.read_text(encoding="utf-8")
			if "<!VERSION!>" in text:
				if dry_run:
					print(f"[dry-run] replace <!VERSION!> in {target}")
				else:
					target.write_text(text.replace("<!VERSION!>", version), encoding="utf-8")
				updated += 1
			elif version in text:
				current += 1
			else:
				missing += 1
				print(f"Warning: cannot safely update {target}; expected <!VERSION!> token or current version string.", file=sys.stderr)

	print(f"Updatables summary: updated={updated}, current={current}, missing={missing}")
	return 0 if missing == 0 else 1


def index_files_for_loader(loader_dir: Path) -> list[str]:
	index_path = loader_dir / "index.toml"
	if not index_path.exists():
		return []
	if _TOML is None:
		raise RuntimeError("No TOML parser found. Use Python 3.11+ or install tomli.")
	with index_path.open("rb") as handle:
		data = _TOML.load(handle)
	files: list[str] = []
	for entry in data.get("files", []):
		if not isinstance(entry, dict):
			continue
		rel = str(entry.get("file", "")).strip()
		if rel and rel not in {"pack.toml", "index.toml"}:
			files.append(rel)
	return files


def validate(*, strict: bool, report_file: str | None) -> int:
	packinfo = load_packinfo()
	loaders = active_loaders(packinfo)
	loader_map = loader_dirs(packinfo)
	issues: list[Issue] = []

	if not loaders:
		issues.append(Issue("error", "NO_LOADERS", "No active loaders found in packinfo [targets].", "Set at least one non-'none' modloader target."))

	for loader in loaders:
		loader_dir = loader_map[loader]
		if not loader_dir.exists():
			issues.append(Issue("error", "LOADER_DIR_MISSING", f"Missing loader folder: {loader_dir.name}", "Run: python stmanager.py setup-folders --yes"))
			continue

		for required in ("mods", "resourcepacks", "shaderpacks", "config"):
			if not (loader_dir / required).exists():
				issues.append(Issue("error", "REQUIRED_DIR_MISSING", f"Missing required folder for {loader}: {loader_dir.name}/{required}", "Re-run setup-folders to recreate missing structure."))

		if not (loader_dir / "pack.toml").exists():
			issues.append(Issue("error", "PACK_TOML_MISSING", f"Missing {loader_dir.name}/pack.toml", "Run setup-folders so pack.toml is rendered from templates/pack.toml."))
		if not (loader_dir / "index.toml").exists():
			issues.append(Issue("error", "INDEX_TOML_MISSING", f"Missing {loader_dir.name}/index.toml", "Run sync-content so Packwiz can manage all files in the loader folder."))

		_, pinned, _, _ = loader_entries(packinfo, loader)
		for entry in pinned:
			mod_id = str(entry.get("id", "")).strip()
			version_id = str(entry.get("version", "")).strip()
			if not mod_id or not version_id:
				issues.append(Issue("error", "PINNED_REMOTE_INVALID", f"Invalid pinned_remote entry for {loader}: id='{mod_id}', version='{version_id}'", "Each pinned_remote must include non-empty id and version fields."))
			if not isinstance(entry.get("allow_different_mc", False), bool):
				issues.append(Issue("error", "PINNED_REMOTE_INVALID", f"Invalid allow_different_mc for pinned_remote {mod_id}@{version_id} in {loader}", "allow_different_mc must be true or false."))

		expected_files = set(index_files_for_loader(loader_dir))
		for rel in sorted(expected_files):
			if not (loader_dir / rel).exists():
				issues.append(Issue("error", "EXPECTED_FILE_MISSING", f"Missing expected file for {loader}: {loader_dir.name}/{rel}", "Run sync-content so Packwiz can keep all tracked files in sync."))

	errors = [item for item in issues if item.level == "error"]
	warnings = [item for item in issues if item.level == "warning"]

	print("Validation Report")
	print(f"- Loaders: {', '.join(loaders) if loaders else 'none'}")
	print(f"- Errors: {len(errors)}")
	print(f"- Warnings: {len(warnings)}")
	if errors:
		print("\nErrors:")
		for item in errors:
			print(f"- [{item.code}] {item.message}")
			print(f"  hint: {item.hint}")
	if warnings:
		print("\nWarnings:")
		for item in warnings:
			print(f"- [{item.code}] {item.message}")
			print(f"  hint: {item.hint}")
	if report_file:
		payload = {
			"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
			"loaders": loaders,
			"errors": [item.__dict__ for item in errors],
			"warnings": [item.__dict__ for item in warnings],
		}
		(ROOT / report_file).write_text(json.dumps(payload, indent=2), encoding="utf-8")
		print(f"\nSaved report: {Path(report_file).name}")
	if errors:
		return 1
	if strict and warnings:
		print("Strict mode enabled: warnings are treated as failures.", file=sys.stderr)
		return 1
	return 0


def build(*, dry_run: bool) -> int:
	require_packwiz(dry_run)
	packinfo = load_packinfo()
	loaders = loader_dirs(packinfo)
	failures = 0

	for loader, loader_dir in loaders.items():
		if not loader_dir.exists():
			print(f"Warning: missing folder {loader_dir}", file=sys.stderr)
			failures += 1
			continue

		before = {path.name for path in loader_dir.glob("*.mrpack")}
		refresh = run_packwiz(["refresh"], loader_dir, dry_run=dry_run)
		export = run_packwiz(["mr", "export"], loader_dir, dry_run=dry_run)
		if not refresh.ok or not export.ok:
			failures += 1
			continue

		if dry_run:
			print(f"[dry-run] would move the newest .mrpack from {loader_dir} to the repo root")
			continue

		after = list(loader_dir.glob("*.mrpack"))
		created = [path for path in after if path.name not in before]
		artifact = max(created or after, key=lambda path: path.stat().st_mtime, default=None)
		if artifact is None:
			print(f"No .mrpack found for loader {loader}", file=sys.stderr)
			failures += 1
			continue

		target = ROOT / f"{artifact.stem}-{loader}.mrpack"
		if target.exists():
			target.unlink()
		shutil.move(str(artifact), str(target))
		print(f"Built {target.name}")

	return 0 if failures == 0 else 1

def parser() -> argparse.ArgumentParser:
	p = argparse.ArgumentParser(description="ST Manager")
	p.add_argument("--dry-run", action="store_true", help="Print actions without running packwiz or writing changes")
	sp = p.add_subparsers(dest="command", required=True)

	setup = sp.add_parser("setup-folders", help="Create src-<loader> folders from packinfo ground truth")
	setup.add_argument("--yes", action="store_true", help="Confirm deletion of existing src-* folders")

	sp.add_parser("sync-loaders", help="Sync existing src-* folders from packinfo/src changes")

	add = sp.add_parser("sync-content", aliases=["add-remotes"], help="Sync local files, remote exceptions, pinned remotes, and Packwiz remotes into each src-* folder")
	add.add_argument("--write-unsuccessful", action="store_true", help="Write unsuccessful remotes to unsuccessful.md")

	updatables = sp.add_parser("update-updatables", help="Replace version tokens in files listed under [updatables].version")
	updatables.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS, help="Print actions without writing changes")

	validate_parser = sp.add_parser("validate", help="Validate src-* loader structure against packinfo ground truth")
	validate_parser.add_argument("--strict", action="store_true", help="Treat warnings as failures")
	validate_parser.add_argument("--report-file", help="Write a JSON validation report relative to repo root")

	sp.add_parser("build", help="Run packwiz refresh/export and move the final .mrpack files to root")

	return p


def main() -> int:
	args = parser().parse_args()
	try:
		if args.command == "setup-folders":
			return setup_folders(yes=args.yes, dry_run=args.dry_run)
		if args.command == "sync-loaders":
			return sync_loaders(dry_run=args.dry_run)
		if args.command in {"sync-content", "add-remotes"}:
			return sync_content_option(write_unsuccessful=args.write_unsuccessful, dry_run=args.dry_run)
		if args.command == "update-updatables":
			return update_updatables(dry_run=args.dry_run)
		if args.command == "validate":
			return validate(strict=args.strict, report_file=args.report_file)
		if args.command == "build":
			return build(dry_run=args.dry_run)
		print(f"Unknown command: {args.command}", file=sys.stderr)
		return 2
	except (FileNotFoundError, RuntimeError, ValueError) as exc:
		print(str(exc), file=sys.stderr)
		return 1


if __name__ == "__main__":
	raise SystemExit(main())
