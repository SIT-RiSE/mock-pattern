import os
import subprocess
import csv
from datetime import datetime
from typing import Optional, Tuple
import argparse

ROOT_PATH = r"C:\\Java_projects\\temp_projects"  # Root directory containing project folders
OUTPUT_CSV = "project_report.csv"  # Output file placed in current workspace directory


def run_git_log(repo_path: str) -> Optional[list]:
    """Return list of commit date strings (iso-strict) newest first, or None if not a git repo or error."""
    if not os.path.isdir(os.path.join(repo_path, ".git")):
        return None
    try:
        # iso-strict gives format like 2025-11-30T12:34:56-05:00 which datetime.fromisoformat can parse
        result = subprocess.run(
            ["git", "-C", repo_path, "log", "--pretty=format:%ad", "--date=iso-strict"],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        return lines if lines else None
    except Exception:
        return None


def parse_dates(commit_dates: list) -> Optional[Tuple[str, str, int]]:
    """Given list of commit date strings (newest first) return (start_date, end_date, cycle_days)."""
    if not commit_dates:
        return None
    # Latest commit date (newest) is first line; earliest is last line
    latest_raw = commit_dates[0]
    earliest_raw = commit_dates[-1]
    try:
        latest_dt = datetime.fromisoformat(latest_raw)
        earliest_dt = datetime.fromisoformat(earliest_raw)
    except ValueError:
        return None
    # Inclusive project cycle in days (+1 so same-day project yields 1 day)
    cycle_days = (latest_dt.date() - earliest_dt.date()).days + 1
    return earliest_dt.date().isoformat(), latest_dt.date().isoformat(), cycle_days


def collect_project_data(root_path: str) -> list:
    rows = []
    if not os.path.isdir(root_path):
        raise FileNotFoundError(f"Root path does not exist: {root_path}")
    for name in sorted(os.listdir(root_path)):
        project_path = os.path.join(root_path, name)
        if not os.path.isdir(project_path):
            continue
        commit_dates = run_git_log(project_path)
        if commit_dates:
            date_tuple = parse_dates(commit_dates)
        else:
            date_tuple = None
        if date_tuple:
            start_date, end_date, cycle_days = date_tuple
        else:
            start_date, end_date, cycle_days = "", "", ""  # Missing git data
        rows.append({
            'project': name,
            'start_date': start_date,
            'end_date': end_date,
            'project_cycle_days': cycle_days,
        })
    return rows


def write_csv(rows: list, output_path: str) -> None:
    fieldnames = ['project', 'start_date', 'end_date', 'project_cycle_days']
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Generate project start/end dates and cycle from git logs.")
    parser.add_argument("--root", default=ROOT_PATH, help="Root directory containing project folders (default: %(default)s)")
    parser.add_argument("--output", default=OUTPUT_CSV, help="Output CSV path (default: %(default)s)")
    args = parser.parse_args()

    try:
        rows = collect_project_data(args.root)
    except FileNotFoundError as e:
        print(str(e))
        return 1
    write_csv(rows, args.output)
    print(f"Written {len(rows)} project rows to {args.output}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
