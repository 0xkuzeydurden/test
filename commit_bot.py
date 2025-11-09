#!/usr/bin/env python3
"""Automate randomized commit bursts while trying to look human enough.

Usage examples:
    python commit_bot.py --commits-per-hour 20 --duration-hours 1
    python commit_bot.py --dry-run --message-seed-file phrases.txt
"""

from __future__ import annotations

import argparse
import math
import random
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List


DEFAULT_MESSAGES = [
    "Daily activity checkpoint",
    "Quick sync",
    "Touch base",
    "Health check",
    "Meta tweak",
    "Automation heartbeat",
    "Status refresh",
    "Keep-alive note",
]


class GitCommandError(RuntimeError):
    """Raised when a git invocation fails."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create lightweight randomized commits. Use responsibly."
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path("."),
        help="Path to the git repository (default: current directory).",
    )
    parser.add_argument(
        "--commits-per-hour",
        type=float,
        default=20.0,
        help="Average commits per hour to generate.",
    )
    parser.add_argument(
        "--duration-hours",
        type=float,
        default=1.0,
        help="How many hours to keep the script running.",
    )
    parser.add_argument(
        "--max-commits",
        type=int,
        default=None,
        help="Hard cap on the number of commits regardless of duration.",
    )
    parser.add_argument(
        "--target-file",
        type=Path,
        default=Path("activity-log.md"),
        help="File that will receive small edits for each commit.",
    )
    parser.add_argument(
        "--jitter",
        type=float,
        default=0.5,
        help="Randomization factor for sleep intervals (0 disables jitter).",
    )
    parser.add_argument(
        "--min-wait-seconds",
        type=float,
        default=15.0,
        help="Lower bound on interval seconds to avoid hyper-fast bursts.",
    )
    parser.add_argument(
        "--push-mode",
        choices=["none", "each", "batch", "end"],
        default="end",
        help="When to push commits. 'none' never pushes.",
    )
    parser.add_argument(
        "--push-batch-size",
        type=int,
        default=5,
        help="Number of commits per push when push-mode=batch.",
    )
    parser.add_argument(
        "--message-seed-file",
        type=Path,
        help="Optional file with one commit message fragment per line.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned actions without touching git.",
    )
    return parser.parse_args()


def load_message_seeds(seed_file: Path | None) -> List[str]:
    if not seed_file:
        return DEFAULT_MESSAGES
    try:
        lines = [
            line.strip()
            for line in seed_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except FileNotFoundError:
        raise SystemExit(f"Seed file not found: {seed_file}") from None
    return lines or DEFAULT_MESSAGES


def run_git(args: Iterable[str], repo: Path, dry_run: bool) -> str:
    printable = "git " + " ".join(shlex.quote(str(arg)) for arg in args)
    if dry_run:
        print(f"[dry-run] {printable}")
        return ""
    result = subprocess.run(
        ["git", *map(str, args)],
        cwd=repo,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise GitCommandError(
            f"{printable} failed with exit code {result.returncode}:\n"
            f"{result.stdout}\n{result.stderr}"
        )
    return result.stdout.strip()


def ensure_git_repo(repo: Path, dry_run: bool) -> None:
    if dry_run:
        return
    try:
        run_git(["rev-parse", "--is-inside-work-tree"], repo, dry_run=False)
    except GitCommandError as exc:
        raise SystemExit(f"{repo} is not a git repository:\n{exc}") from exc


def compute_total_commits(commits_per_hour: float, duration_hours: float) -> int:
    if commits_per_hour <= 0 or duration_hours <= 0:
        raise SystemExit("commits-per-hour and duration-hours must be positive.")
    return max(1, math.ceil(commits_per_hour * duration_hours))


def next_wait_seconds(avg_interval: float, jitter: float, min_wait: float) -> float:
    low_factor = max(0.05, 1.0 - abs(jitter))
    high_factor = 1.0 + abs(jitter)
    wait = random.uniform(avg_interval * low_factor, avg_interval * high_factor)
    return max(min_wait, wait)


def mutate_file(target_file: Path, repo: Path, message: str, dry_run: bool) -> None:
    line = f"{datetime.now(timezone.utc).isoformat()} :: {message}\n"
    file_path = repo / target_file
    if dry_run:
        print(f"[dry-run] would append to {target_file}: {line.strip()}")
        return
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("a", encoding="utf-8") as handle:
        handle.write(line)


def make_commit(
    repo: Path,
    target_file: Path,
    commit_message: str,
    dry_run: bool,
) -> None:
    mutate_file(target_file, repo, commit_message, dry_run)
    run_git(["add", str(target_file)], repo, dry_run)
    commit_args = ["commit", "-m", commit_message]
    run_git(commit_args, repo, dry_run)


def push_if_needed(
    repo: Path,
    push_mode: str,
    dry_run: bool,
    *,
    force: bool = False,
) -> None:
    if push_mode == "none":
        return
    args = ["push"]
    if force:
        args.append("--force-with-lease")
    run_git(args, repo, dry_run)


def main() -> None:
    args = parse_args()
    repo = args.repo.resolve()
    ensure_git_repo(repo, args.dry_run)

    total_commits = compute_total_commits(args.commits_per_hour, args.duration_hours)
    if args.max_commits:
        total_commits = min(total_commits, max(1, args.max_commits))

    avg_interval = 3600.0 / args.commits_per_hour
    messages = load_message_seeds(args.message_seed_file)

    print(
        f"Planning {total_commits} commits over ~{args.duration_hours:.2f}h "
        f"(avg interval ≈ {avg_interval:.1f}s)"
    )

    completed = 0
    batch_since_push = 0
    try:
        for idx in range(total_commits):
            if idx:
                wait_seconds = next_wait_seconds(
                    avg_interval, args.jitter, args.min_wait_seconds
                )
                if args.dry_run:
                    print(
                        f"[dry-run] would sleep {wait_seconds:.1f}s "
                        f"before commit {idx + 1}"
                    )
                else:
                    time.sleep(wait_seconds)
            commit_message = (
                f"{random.choice(messages)} #{idx + 1}/{total_commits}"
            )
            make_commit(repo, args.target_file, commit_message, args.dry_run)
            completed += 1
            batch_since_push += 1

            if args.push_mode == "each":
                push_if_needed(repo, "each", args.dry_run)
                batch_since_push = 0
            elif args.push_mode == "batch" and batch_since_push >= args.push_batch_size:
                push_if_needed(repo, "batch", args.dry_run)
                batch_since_push = 0

        if args.push_mode in {"end", "batch"} and batch_since_push:
            push_if_needed(repo, args.push_mode, args.dry_run)

    except KeyboardInterrupt:
        print("\nInterrupted by user. Attempting to push partial work...")
        if completed and args.push_mode != "none":
            push_if_needed(repo, "end", args.dry_run)
        sys.exit(1)

    print(f"Done. Created {completed} commits.")


if __name__ == "__main__":
    main()
