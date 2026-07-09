#!/usr/bin/env python3
"""Prepare a small artifact directory for internal remote runs."""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


DEFAULT_BUDGET = 96 * 1024
TRUNCATED_SUFFIX = ".truncated-tail"


def parse_budget(value: str) -> int:
    text = value.strip().upper()
    if not text:
        return DEFAULT_BUDGET

    multiplier = 1
    if text[-1] in {"K", "M", "G"}:
        suffix = text[-1]
        text = text[:-1]
        multiplier = {"K": 1024, "M": 1024**2, "G": 1024**3}[suffix]

    return max(0, int(float(text) * multiplier))


def parse_paths(value: str) -> list[Path]:
    paths: list[Path] = []
    for line in value.replace(",", "\n").splitlines():
        item = line.strip()
        if item:
            paths.append(Path(item))
    return paths


def artifact_relative_path(path: Path) -> Path:
    if path.is_absolute():
        return Path("absolute") / Path(*path.parts[1:])
    return Path("files") / path


def is_inside(path: Path, directory: Path) -> bool:
    try:
        path.resolve().relative_to(directory.resolve())
        return True
    except ValueError:
        return False


def copy_limited_file(src: Path, dst: Path, remaining: int) -> tuple[int, str]:
    if remaining <= 0:
        return 0, "skipped: budget exhausted"

    size = src.stat().st_size
    dst.parent.mkdir(parents=True, exist_ok=True)

    if size <= remaining:
        shutil.copy2(src, dst)
        return size, "copied"

    truncated_dst = dst.with_name(dst.name + TRUNCATED_SUFFIX)
    with src.open("rb") as input_file:
        input_file.seek(max(0, size - remaining))
        data = input_file.read(remaining)
    truncated_dst.write_bytes(data)
    return len(data), f"truncated tail: original_size={size}"


def iter_files(path: Path, output_dir: Path) -> list[Path]:
    if not path.exists():
        return []
    if path.is_file():
        return [path]
    if not path.is_dir():
        return []

    files: list[Path] = []
    for root, dirs, names in os.walk(path):
        root_path = Path(root)
        dirs[:] = sorted(
            directory for directory in dirs
            if directory != ".git"
            and not is_inside(root_path / directory, output_dir)
        )
        for name in sorted(names):
            candidate = root_path / name
            if candidate.is_file() and not candidate.is_symlink():
                files.append(candidate)
    return files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paths", default="")
    parser.add_argument("--budget", default="96K")
    parser.add_argument("--output", required=True)
    parser.add_argument("--log", required=True)
    args = parser.parse_args()

    output_dir = Path(args.output)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    budget = parse_budget(args.budget)
    remaining = budget
    manifest: list[str] = [
        f"budget_bytes={budget}",
        f"output_dir={output_dir}",
        "",
    ]

    candidates: list[Path] = []
    command_log = Path(args.log)
    if command_log.exists():
        candidates.append(command_log)
    candidates.extend(parse_paths(args.paths))

    seen: set[Path] = set()
    for candidate in candidates:
        if not candidate.exists():
            manifest.append(f"{candidate}: missing")
            continue

        for src in iter_files(candidate, output_dir):
            resolved = src.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)

            dst = output_dir / artifact_relative_path(src)
            used, status = copy_limited_file(src, dst, remaining)
            remaining -= used
            manifest.append(f"{src}: {status}, bytes={used}")

    manifest.append("")
    manifest.append(f"remaining_bytes={remaining}")
    (output_dir / "manifest.txt").write_text("\n".join(manifest) + "\n",
                                             encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
