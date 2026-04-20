"""ST Manager.

Command line tool for ST Family modpack automation.

Implemented functions/options:
- readInfo
- addRemotes (internal function)
- Individual Function Option via run-function <name>
- setupFolders
- updateUpdatables
- updateMods
- addRemotesOption
- completionHelper
- build

All functionality uses only Python standard library.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
SRC_LEGACY = ROOT / "src"
PACKINFO_PATH = ROOT / "packinfo.toml"
TEMPLATE_PACK_PATH = ROOT / "templates" / "pack.toml"
ADD_REMOTES_LOG = ROOT / "addremotes.log"
MOD_UPDATES_LOG = ROOT / "modupdates.log"
UNSUCCESSFUL_PATH = ROOT / "unsuccessful.md"
STATE_PATH = ROOT / ".stmanager-state.json"


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
class ValidationIssue:
	level: str
	code: str
	message: str
	hint: str


def load_packinfo() -> dict[str, Any]:
	if not PACKINFO_PATH.exists():
		raise FileNotFoundError(f"Missing {PACKINFO_PATH}")
	with PACKINFO_PATH.open("rb") as handle:
		return tomllib.load(handle)


def load_state() -> dict[str, Any]:
	if not STATE_PATH.exists():
		return {"updatables": {}}
	try:
		data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
		if isinstance(data, dict):
			data.setdefault("updatables", {})
			return data
	except (json.JSONDecodeError, OSError):
		pass
	return {"updatables": {}}


def save_state(state: dict[str, Any]) -> None:
	STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def active_loaders(packinfo: dict[str, Any]) -> list[str]:
	targets = packinfo.get("targets", {})
	loaders: list[str] = []
	for key, value in targets.items():
		if key == "mc":
			continue
		if str(value).lower() != "none":
			loaders.append(key)
	return loaders


def loader_dirs(packinfo: dict[str, Any]) -> dict[str, Path]:
	return {loader: ROOT / f"src-{loader}" for loader in active_loaders(packinfo)}


def content_section(packinfo: dict[str, Any], section: str) -> dict[str, Any]:
	"""Return section data from either [content.<section>] or top-level [<section>]."""
	nested = packinfo.get("content", {}).get(section, {})
	top_level = packinfo.get(section, {})
	merged: dict[str, Any] = {}
	if isinstance(top_level, dict):
		merged.update(top_level)
	if isinstance(nested, dict):
		merged.update(nested)
	return merged


def run_cmd(command: list[str], cwd: Path, *, dry_run: bool) -> RunResult:
	if dry_run:
		msg = f"[dry-run] ({cwd.name}) {' '.join(command)}"
		print(msg)
		return RunResult(command=command, cwd=cwd, returncode=0, stdout=msg, stderr="")

	completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
	if completed.stdout:
		print(completed.stdout.strip())
	if completed.stderr:
		print(completed.stderr.strip(), file=sys.stderr)

	return RunResult(
		command=command,
		cwd=cwd,
		returncode=completed.returncode,
		stdout=completed.stdout,
		stderr=completed.stderr,
	)


def require_packwiz(dry_run: bool) -> None:
	if dry_run:
		return
	if shutil.which("packwiz") is None:
		raise RuntimeError("packwiz is required for this command but was not found in PATH")


def ensure_parent(path: Path) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)


def copy_file(src: Path, dst: Path) -> None:
	ensure_parent(dst)
	shutil.copy2(src, dst)


def make_tree_writable(path: Path) -> None:
	for root, dirs, files in os.walk(path, topdown=False):
		for name in files + dirs:
			entry = Path(root) / name
			try:
				entry.chmod(entry.stat().st_mode | stat.S_IWRITE)
			except OSError:
				pass
	try:
		path.chmod(path.stat().st_mode | stat.S_IWRITE)
	except OSError:
		pass


def _rmtree_onexc(func: Any, path: str, _exc: Any) -> None:
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
			shutil.rmtree(path, onexc=_rmtree_onexc)
			return
		except OSError as exc:
			last_error = exc
			if attempt < 2:
				time.sleep(0.2 * (attempt + 1))

	hint = (
		"Close apps that may be using files there (Explorer windows, editors, game instances, antivirus scans), then re-run the command."
		if os.name == "nt"
		else "Close processes using this path and re-run (use lsof/fuser if needed)."
	)

	if isinstance(last_error, PermissionError):
		raise RuntimeError(f"Could not remove '{path}'. Access denied. {hint}") from last_error

	raise RuntimeError(f"Could not remove '{path}': {last_error}. {hint}") from last_error


def copy_tree(src: Path, dst: Path) -> None:
	if dst.exists():
		remove_tree(dst)
	shutil.copytree(src, dst)


def remotes_for_loader(packinfo: dict[str, Any], loader: str) -> list[str]:
	all_remote = list(content_section(packinfo, "all").get("remotes", []))
	loader_remote = list(content_section(packinfo, loader).get("remotes", []))
	return [item for item in all_remote + loader_remote if item]


def remote_exceptions_for_loader(packinfo: dict[str, Any], loader: str) -> list[dict[str, Any]]:
	exceptions = list(content_section(packinfo, "all").get("remote_exception", []))
	exceptions.extend(content_section(packinfo, loader).get("remote_exception", []))
	return [item for item in exceptions if isinstance(item, dict)]


def nonremotes_for_loader(packinfo: dict[str, Any], loader: str) -> list[dict[str, Any]]:
	entries = list(content_section(packinfo, "all").get("nonremote", []))
	entries.extend(content_section(packinfo, loader).get("nonremote", []))
	return [item for item in entries if isinstance(item, dict)]


def read_info(*, json_out: bool = False) -> int:
	packinfo = load_packinfo()
	loaders = active_loaders(packinfo)
	payload = {
		"name": packinfo.get("name"),
		"author": packinfo.get("author"),
		"version": packinfo.get("version"),
		"mc": packinfo.get("targets", {}).get("mc"),
		"loaders": {loader: packinfo.get("targets", {}).get(loader) for loader in loaders},
		"remotes": {
			loader: len(remotes_for_loader(packinfo, loader))
			for loader in loaders
		},
	}

	if json_out:
		print(json.dumps(payload, indent=2))
		return 0

	print("Pack Info")
	print(f"- Name: {payload['name']}")
	print(f"- Author: {payload['author']}")
	print(f"- Version: {payload['version']}")
	print(f"- Minecraft: {payload['mc']}")
	print("- Loaders:")
	for loader, version in payload["loaders"].items():
		print(f"  - {loader}: {version} ({payload['remotes'][loader]} remotes)")
	return 0


def guide(*, goal: str) -> int:
	workflows: dict[str, dict[str, Any]] = {
		"first-run": {
			"title": "First run (new architecture setup)",
			"steps": [
				"1. python stmanager.py --dry-run setup-folders --yes",
				"2. python stmanager.py setup-folders --yes",
				"3. python stmanager.py --dry-run add-remotes",
				"4. python stmanager.py add-remotes --write-unsuccessful",
				"5. python stmanager.py validate --report-file validation-report.json",
			],
			"notes": [
				"Use --dry-run first on destructive or network-dependent commands.",
				"If setup fails with access denied, close Explorer/editor/game windows using src-* paths and re-run.",
			],
		},
		"version-bump": {
			"title": "Version bump and metadata refresh",
			"steps": [
				"1. Update version in packinfo.toml",
				"2. python stmanager.py update-updatables",
				"3. python stmanager.py validate",
			],
			"notes": [
				"update-updatables is repeatable and tracks previously applied versions in .stmanager-state.json.",
				"If a file cannot be safely updated, stmanager prints a warning with next action.",
			],
		},
		"mod-maintenance": {
			"title": "Mod maintenance",
			"steps": [
				"1. python stmanager.py --dry-run update-mods",
				"2. python stmanager.py update-mods",
				"3. python stmanager.py validate",
			],
			"notes": [
				"Check modupdates.log for per-loader update counts and failures.",
			],
		},
		"release": {
			"title": "Pre-release checklist",
			"steps": [
				"1. python stmanager.py validate --strict --report-file validation-report.json",
				"2. python stmanager.py --dry-run build",
				"3. python stmanager.py build",
			],
			"notes": [
				"build requires packwiz and src-<loader> folders to be ready.",
			],
		},
		"troubleshoot": {
			"title": "Troubleshooting",
			"steps": [
				"1. python stmanager.py read-info",
				"2. python stmanager.py validate --report-file validation-report.json",
				"3. python stmanager.py completion-helper",
			],
			"notes": [
				"validation-report.json gives machine-readable error and warning details for CI or debugging.",
				"completion-helper shows exact expected files missing per loader.",
			],
		},
	}

	if goal == "all":
		print("ST Manager Guide")
		print("Pick one goal and run: python stmanager.py guide --goal <goal>")
		print("Goals: first-run, version-bump, mod-maintenance, release, troubleshoot")
		print("")
		for key in ("first-run", "version-bump", "mod-maintenance", "release", "troubleshoot"):
			item = workflows[key]
			print(f"[{key}] {item['title']}")
			for step in item["steps"]:
				print(step)
			for note in item["notes"]:
				print(f"Note: {note}")
			print("")
		return 0

	if goal not in workflows:
		print(f"Unknown guide goal: {goal}", file=sys.stderr)
		return 2

	item = workflows[goal]
	print(f"ST Manager Guide - {item['title']}")
	for step in item["steps"]:
		print(step)
	for note in item["notes"]:
		print(f"Note: {note}")
	return 0


def write_loader_pack_toml(packinfo: dict[str, Any], loader: str, target_dir: Path) -> None:
	template = TEMPLATE_PACK_PATH.read_text(encoding="utf-8")
	rendered = (
		template.replace("<!NAME!>", str(packinfo.get("name", "")))
		.replace("<!AUTHOR!>", str(packinfo.get("author", "")))
		.replace("<!VERSION!>", str(packinfo.get("version", "")))
		.replace("<!MODLOADER!>", loader)
		.replace("<!LOADERVERSION!>", str(packinfo.get("targets", {}).get(loader, "")))
		.replace("<!MCVERSION!>", str(packinfo.get("targets", {}).get("mc", "")))
	)
	(target_dir / "pack.toml").write_text(rendered, encoding="utf-8")


def setup_folders(*, yes: bool, dry_run: bool) -> int:
	packinfo = load_packinfo()
	ldirs = loader_dirs(packinfo)

	if not ldirs:
		print("No active loaders found in packinfo targets.", file=sys.stderr)
		return 1

	existing = [path for path in ldirs.values() if path.exists()]
	if existing and not yes:
		print(
			"setup-folders would delete existing loader folders. Re-run with --yes to confirm.",
			file=sys.stderr,
		)
		for path in existing:
			print(f"- {path.name}", file=sys.stderr)
		return 1

	if not SRC_LEGACY.exists():
		print("Legacy src folder not found; cannot seed new architecture.", file=sys.stderr)
		return 1

	config_src = SRC_LEGACY / "config"
	if not config_src.exists():
		print("Legacy src/config folder not found; cannot copy base config.", file=sys.stderr)
		return 1

	for loader, path in ldirs.items():
		if path.exists() and yes:
			if dry_run:
				print(f"[dry-run] remove {path}")
			else:
				remove_tree(path)

		if dry_run:
			print(f"[dry-run] create {path}")
		else:
			path.mkdir(parents=True, exist_ok=True)

		for folder in ("mods", "resourcepacks", "shaderpacks"):
			target = path / folder
			if dry_run:
				print(f"[dry-run] mkdir {target}")
			else:
				target.mkdir(parents=True, exist_ok=True)

		if dry_run:
			print(f"[dry-run] copytree {config_src} -> {path / 'config'}")
		else:
			copy_tree(config_src, path / "config")

		for entry in nonremotes_for_loader(packinfo, loader):
			rel = entry.get("file")
			if not rel:
				continue
			src = SRC_LEGACY / rel
			dst = path / rel
			if not src.exists():
				print(f"Warning: nonremote source file missing: {src}", file=sys.stderr)
				continue
			if dry_run:
				print(f"[dry-run] copy {src} -> {dst}")
			else:
				copy_file(src, dst)

		for entry in remote_exceptions_for_loader(packinfo, loader):
			rel = entry.get("file")
			if not rel:
				continue
			src = SRC_LEGACY / rel
			dst = path / rel
			if not src.exists():
				print(f"Warning: remote exception file missing: {src}", file=sys.stderr)
				continue
			if dry_run:
				print(f"[dry-run] copy {src} -> {dst}")
			else:
				copy_file(src, dst)

		if dry_run:
			print(f"[dry-run] render pack.toml for {loader} in {path}")
		else:
			write_loader_pack_toml(packinfo, loader, path)

		print(f"Prepared {path.name}")

	return 0


def update_updatables(*, dry_run: bool) -> int:
	packinfo = load_packinfo()
	state = load_state()
	state_updatables = state.setdefault("updatables", {})
	state_changed = False
	version = str(packinfo.get("version", ""))
	paths = list(packinfo.get("updatables", {}).get("version", []))
	ldirs = loader_dirs(packinfo)

	if not paths:
		print("No [updatables].version entries found.")
		return 0

	replaced = 0
	already_current = 0
	skipped_unsafe = 0
	for loader, ldir in ldirs.items():
		if not ldir.exists():
			print(
				f"Warning: loader folder missing for {loader}: {ldir} "
				"(updatable paths are relative to each src-* folder root)",
				file=sys.stderr,
			)
			continue
		for rel in paths:
			target = ldir / rel
			if not target.exists():
				print(
					f"Warning: updatable path not found for {loader}: {target} "
					"(defined relative to each src-* folder root)",
					file=sys.stderr,
				)
				continue
			text = target.read_text(encoding="utf-8")

			state_key = str(target.relative_to(ROOT)).replace("\\", "/")
			previous_version = state_updatables.get(state_key)

			if "<!VERSION!>" in text:
				updated = text.replace("<!VERSION!>", version)
				if dry_run:
					print(f"[dry-run] replaced <!VERSION!> token in {target}")
				else:
					target.write_text(updated, encoding="utf-8")
				state_updatables[state_key] = version
				state_changed = True
				replaced += 1
				continue

			if version in text:
				state_updatables[state_key] = version
				state_changed = True
				already_current += 1
				continue

			if isinstance(previous_version, str) and previous_version and previous_version in text:
				updated = text.replace(previous_version, version)
				if dry_run:
					print(f"[dry-run] replaced previous version ({previous_version} -> {version}) in {target}")
				else:
					target.write_text(updated, encoding="utf-8")
				state_updatables[state_key] = version
				state_changed = True
				replaced += 1
				continue

			skipped_unsafe += 1
			print(
				f"Warning: cannot safely update {target}. "
				"No <!VERSION!> token and no known prior applied version found.",
				file=sys.stderr,
			)

	if not dry_run and state_changed:
		save_state(state)

	print(
		f"Updatables summary: replaced={replaced}, already_current={already_current}, "
		f"skipped_unsafe={skipped_unsafe}"
	)
	return 0


def parse_packwiz_fail(stdout: str, stderr: str) -> str:
	combined = "\n".join(part for part in (stdout.strip(), stderr.strip()) if part)
	if not combined:
		return "unknown error"
	lines = [line for line in combined.splitlines() if line.strip()]
	return " | ".join(lines[-3:])


def add_remotes_for_loader(
	packinfo: dict[str, Any],
	loader: str,
	ldir: Path,
	*,
	dry_run: bool,
) -> tuple[int, int, list[tuple[str, str]]]:
	remotes = remotes_for_loader(packinfo, loader)
	if not remotes:
		return 0, 0, []

	success = 0
	failed = 0
	failures: list[tuple[str, str]] = []

	with ADD_REMOTES_LOG.open("a", encoding="utf-8") as log:
		stamp = dt.datetime.now().isoformat(timespec="seconds")
		log.write(f"\n[{stamp}] loader={loader} folder={ldir}\n")
		for remote_id in remotes:
			command = ["packwiz", "mr", "add", remote_id]
			result = run_cmd(command, ldir, dry_run=dry_run)
			log.write(f"$ {' '.join(command)}\n")
			log.write(result.stdout)
			if result.stderr:
				log.write("\n[stderr]\n")
				log.write(result.stderr)
			log.write("\n")

			if result.ok:
				success += 1
			else:
				failed += 1
				failures.append((remote_id, parse_packwiz_fail(result.stdout, result.stderr)))

	return success, failed, failures


def add_remotes_option(*, write_unsuccessful: bool, dry_run: bool) -> int:
	require_packwiz(dry_run)
	packinfo = load_packinfo()
	ldirs = loader_dirs(packinfo)
	if not ldirs:
		print("No active loader folders to process.", file=sys.stderr)
		return 1

	total_success = 0
	total_failed = 0
	all_failures: list[tuple[str, str, str]] = []

	for loader, ldir in ldirs.items():
		if not ldir.exists():
			print(f"Warning: skipping missing folder {ldir}", file=sys.stderr)
			continue

		success, failed, failures = add_remotes_for_loader(packinfo, loader, ldir, dry_run=dry_run)
		total_success += success
		total_failed += failed
		for remote_id, reason in failures:
			all_failures.append((loader, remote_id, reason))

	attempted = total_success + total_failed
	percent = (total_success / attempted * 100.0) if attempted else 100.0
	print(f"Add remotes summary: {total_success} succeeded, {total_failed} failed, {percent:.1f}% success")

	if write_unsuccessful and all_failures:
		lines = ["# Unsuccessful remotes", ""]
		for loader, remote_id, reason in all_failures:
			lines.append(f"- loader={loader} id={remote_id}: {reason}")
		UNSUCCESSFUL_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
		print(f"Wrote failure report to {UNSUCCESSFUL_PATH.name}")

	return 0 if total_failed == 0 else 1


def extract_update_count(text: str) -> int:
	for line in text.splitlines():
		match = re.search(r"(\d+)\s+mods?\s+updated", line, flags=re.IGNORECASE)
		if match:
			return int(match.group(1))
	return 0


def update_mods(*, dry_run: bool) -> int:
	require_packwiz(dry_run)
	packinfo = load_packinfo()
	ldirs = loader_dirs(packinfo)

	total = 0
	failures = 0
	logs: list[str] = []

	for loader, ldir in ldirs.items():
		if not ldir.exists():
			print(f"Warning: missing folder {ldir}", file=sys.stderr)
			failures += 1
			continue
		result = run_cmd(["packwiz", "update"], ldir, dry_run=dry_run)
		if not result.ok:
			failures += 1
		count = extract_update_count(result.stdout)
		total += count
		logs.append(f"loader={loader} updated={count} rc={result.returncode}")

	stamp = dt.datetime.now().isoformat(timespec="seconds")
	with MOD_UPDATES_LOG.open("a", encoding="utf-8") as handle:
		handle.write(f"[{stamp}] total={total} failures={failures}\n")
		for line in logs:
			handle.write(f"{line}\n")

	print(f"Mods updated: {total} (failures: {failures})")
	return 0 if failures == 0 else 1


def completion_helper() -> int:
	packinfo = load_packinfo()
	ldirs = loader_dirs(packinfo)

	any_missing = False
	for loader, ldir in ldirs.items():
		expected_remotes = remotes_for_loader(packinfo, loader)
		expected_files = [f"mods/{item}.pw.toml" for item in expected_remotes]

		for entry in nonremotes_for_loader(packinfo, loader):
			rel = entry.get("file")
			if rel:
				expected_files.append(rel)

		for entry in remote_exceptions_for_loader(packinfo, loader):
			rel = entry.get("file")
			if rel:
				expected_files.append(rel)

		normalized = sorted(set(expected_files))
		present = [rel for rel in normalized if (ldir / rel).exists()]
		missing = [rel for rel in normalized if not (ldir / rel).exists()]

		pct = (len(present) / len(normalized) * 100.0) if normalized else 100.0
		print(f"{loader}: {len(present)}/{len(normalized)} present ({pct:.1f}%)")
		if missing:
			any_missing = True
			for rel in missing:
				print(f"  MISSING: {rel}")

	return 1 if any_missing else 0


def expected_files_for_loader(packinfo: dict[str, Any], loader: str) -> list[str]:
	entries = [f"mods/{item}.pw.toml" for item in remotes_for_loader(packinfo, loader)]
	for item in nonremotes_for_loader(packinfo, loader):
		rel = item.get("file")
		if rel:
			entries.append(rel)
	for item in remote_exceptions_for_loader(packinfo, loader):
		rel = item.get("file")
		if rel:
			entries.append(rel)
	return sorted(set(entries))


def validate(*, strict: bool, report_file: str | None) -> int:
	packinfo = load_packinfo()
	loaders = active_loaders(packinfo)
	ldirs = loader_dirs(packinfo)
	issues: list[ValidationIssue] = []

	if not loaders:
		issues.append(
			ValidationIssue(
				level="error",
				code="NO_LOADERS",
				message="No active loaders found in packinfo [targets].",
				hint="Set at least one non-'none' modloader target (e.g. fabric).",
			)
		)

	for loader in loaders:
		ldir = ldirs[loader]
		if not ldir.exists():
			issues.append(
				ValidationIssue(
					level="error",
					code="LOADER_DIR_MISSING",
					message=f"Missing loader folder: {ldir.name}",
					hint="Run: python stmanager.py setup-folders --yes",
				)
			)
			continue

		for required in ("mods", "resourcepacks", "shaderpacks", "config"):
			path = ldir / required
			if not path.exists():
				issues.append(
					ValidationIssue(
						level="error",
						code="REQUIRED_DIR_MISSING",
						message=f"Missing required folder for {loader}: {ldir.name}/{required}",
						hint="Re-run setup-folders to recreate missing structure.",
					)
				)

		pack_toml = ldir / "pack.toml"
		if not pack_toml.exists():
			issues.append(
				ValidationIssue(
					level="error",
					code="PACK_TOML_MISSING",
					message=f"Missing {ldir.name}/pack.toml",
					hint="Run setup-folders so pack.toml is rendered from templates/pack.toml.",
				)
			)

		expected = expected_files_for_loader(packinfo, loader)
		for rel in expected:
			if not (ldir / rel).exists():
				issues.append(
					ValidationIssue(
						level="error",
						code="EXPECTED_FILE_MISSING",
						message=f"Missing expected file for {loader}: {ldir.name}/{rel}",
						hint="Run add-remotes and ensure nonremote/remote_exception files are copied.",
					)
				)

	for rel in packinfo.get("updatables", {}).get("version", []):
		for loader, ldir in ldirs.items():
			if not ldir.exists():
				# LOADER_DIR_MISSING already explains root cause for this loader.
				continue
			candidate = ldir / rel
			if not candidate.exists():
				issues.append(
					ValidationIssue(
						level="warning",
						code="UPDATABLE_PATH_MISSING",
						message=(
							f"Updatable path missing for {loader}: {ldir.name}/{rel} "
							"(path is relative to each src-* folder root)"
						),
						hint="Create file in that loader folder or remove it from [updatables].version.",
					)
				)

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
		report_path = ROOT / report_file
		payload = {
			"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
			"loaders": loaders,
			"errors": [item.__dict__ for item in errors],
			"warnings": [item.__dict__ for item in warnings],
		}
		report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
		print(f"\nSaved report: {report_path.name}")

	if errors:
		return 1
	if strict and warnings:
		print("Strict mode enabled: warnings are treated as failures.", file=sys.stderr)
		return 1
	return 0


def build(*, dry_run: bool) -> int:
	require_packwiz(dry_run)
	packinfo = load_packinfo()
	ldirs = loader_dirs(packinfo)
	failures = 0

	for loader, ldir in ldirs.items():
		if not ldir.exists():
			print(f"Warning: missing folder {ldir}", file=sys.stderr)
			failures += 1
			continue

		before = {path.name for path in ldir.glob("*.mrpack")}
		refresh = run_cmd(["packwiz", "refresh"], ldir, dry_run=dry_run)
		export = run_cmd(["packwiz", "mr", "export"], ldir, dry_run=dry_run)
		if not refresh.ok or not export.ok:
			failures += 1
			continue

		if dry_run:
			print(f"[dry-run] would locate .mrpack in {ldir} and move to repo root with loader suffix")
			continue

		after = list(ldir.glob("*.mrpack"))
		created = [path for path in after if path.name not in before]
		artifact = max(created or after, key=lambda p: p.stat().st_mtime, default=None)
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


def run_function(name: str, *, dry_run: bool) -> int:
	canonical = name.strip().lower()
	mapping: dict[str, Any] = {
		"readinfo": lambda: read_info(json_out=False),
		"guide": lambda: guide(goal="all"),
		"validate": lambda: validate(strict=False, report_file=None),
		"setupfolders": lambda: setup_folders(yes=False, dry_run=dry_run),
		"updateupdatables": lambda: update_updatables(dry_run=dry_run),
		"updatemods": lambda: update_mods(dry_run=dry_run),
		"addremotesoption": lambda: add_remotes_option(write_unsuccessful=False, dry_run=dry_run),
		"completionhelper": completion_helper,
		"build": lambda: build(dry_run=dry_run),
		"addremotes": lambda: add_remotes_option(write_unsuccessful=False, dry_run=dry_run),
	}
	if canonical not in mapping:
		print(f"Unknown function: {name}", file=sys.stderr)
		return 2
	return mapping[canonical]()


def parser() -> argparse.ArgumentParser:
	p = argparse.ArgumentParser(description="ST Manager")
	p.add_argument("--dry-run", action="store_true", help="Print actions without running packwiz or writing changes")

	sp = p.add_subparsers(dest="command", required=True)

	info = sp.add_parser("read-info", help="Read packinfo.toml and print summary")
	info.add_argument("--json", action="store_true", help="Output as JSON")

	guide_parser = sp.add_parser("guide", help="Show guided command flows based on user goal")
	guide_parser.add_argument(
		"--goal",
		default="all",
		choices=["all", "first-run", "version-bump", "mod-maintenance", "release", "troubleshoot"],
		help="Which workflow guide to show",
	)

	validate_parser = sp.add_parser("validate", help="Validate src-* loader structure against packinfo ground truth")
	validate_parser.add_argument("--strict", action="store_true", help="Treat warnings as failures")
	validate_parser.add_argument("--report-file", help="Write a JSON validation report relative to repo root")
	validate_parser.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS, help="Accepted for CLI consistency")

	setup = sp.add_parser("setup-folders", help="Create src-<loader> folders from packinfo ground truth")
	setup.add_argument("--yes", action="store_true", help="Confirm deletion of existing src-* folders")
	setup.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS, help="Print actions without writing changes")

	update_updatables_parser = sp.add_parser("update-updatables", help="Replace <!VERSION!> in updatable paths")
	update_updatables_parser.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS, help="Print actions without writing changes")

	update_mods_parser = sp.add_parser("update-mods", help="Run packwiz update in each src-* folder")
	update_mods_parser.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS, help="Print actions without running packwiz")

	add = sp.add_parser("add-remotes", help="Run packwiz mr add for remotes in each src-* folder")
	add.add_argument("--write-unsuccessful", action="store_true", help="Write unsuccessful remotes to unsuccessful.md")
	add.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS, help="Print actions without running packwiz")

	sp.add_parser("completion-helper", help="Check expected files from packinfo against src-* folders")
	build_parser = sp.add_parser("build", help="Run packwiz refresh/export and move renamed .mrpack files to root")
	build_parser.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS, help="Print actions without running packwiz")

	fn = sp.add_parser("run-function", help="Run internal function by name (legacy compatibility)")
	fn.add_argument("name", help="Function name, e.g. readInfo, setupFolders, build")
	fn.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS, help="Print actions without running packwiz or writing changes")

	return p


def main() -> int:
	args = parser().parse_args()

	try:
		if args.command == "read-info":
			return read_info(json_out=args.json)
		if args.command == "guide":
			return guide(goal=args.goal)
		if args.command == "validate":
			return validate(strict=args.strict, report_file=args.report_file)
		if args.command == "setup-folders":
			return setup_folders(yes=args.yes, dry_run=args.dry_run)
		if args.command == "update-updatables":
			return update_updatables(dry_run=args.dry_run)
		if args.command == "update-mods":
			return update_mods(dry_run=args.dry_run)
		if args.command == "add-remotes":
			return add_remotes_option(write_unsuccessful=args.write_unsuccessful, dry_run=args.dry_run)
		if args.command == "completion-helper":
			return completion_helper()
		if args.command == "build":
			return build(dry_run=args.dry_run)
		if args.command == "run-function":
			return run_function(args.name, dry_run=args.dry_run)
		print(f"Unknown command: {args.command}", file=sys.stderr)
		return 2
	except (FileNotFoundError, RuntimeError, ValueError) as exc:
		print(str(exc), file=sys.stderr)
		return 1


if __name__ == "__main__":
	raise SystemExit(main())
