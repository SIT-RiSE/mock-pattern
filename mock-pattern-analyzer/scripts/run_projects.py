"""批量运行 mock-pattern v2（不编译被测项目、不需要 token）。

对 `apache project list.csv` 中的每个项目：浅克隆默认分支最新版本并记录 commit，
运行 edu.mock.mockpattern.v2.PatternPipeline，结果写入 <work>/results/<project>/。
已有 summary.json 的项目会被跳过，因此中断后重跑即可续跑。

Batch runner for mock-pattern v2 (no compilation, no tokens). Shallow-clones each project,
records its commit, runs the pipeline and aggregates every summary.json into summary.csv.
Projects that already have a summary.json are skipped, so an interrupted run resumes.

用法 / usage:
    python run_projects.py --work D:/Java_projects/mock-pattern-v2
    python run_projects.py --work ... --only Dubbo Druid      # 只跑指定项目
    python run_projects.py --work ... --aggregate-only        # 只重新汇总
"""

import argparse
import concurrent.futures
import csv
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ANALYZER_DIR = SCRIPT_DIR.parent
DEFAULT_PROJECTS = ANALYZER_DIR / "apache project list.csv"
MAIN_CLASS = "edu.mock.mockpattern.v2.PatternPipeline"
MVN = "mvn.cmd" if os.name == "nt" else "mvn"


def slug(name):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")


def run(cmd, **kwargs):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kwargs)


def build(work):
    """用 Maven 解析依赖 classpath，javac 编译到 <work>/bin，不改动仓库里已提交的 target/。
    Resolves the classpath with Maven and compiles into <work>/bin, leaving the committed target/ alone."""
    bin_dir = work / "bin"
    classes = bin_dir / "classes"
    cp_file = bin_dir / "cp.txt"
    bin_dir.mkdir(parents=True, exist_ok=True)
    r = run([MVN, "-q", "dependency:build-classpath", f"-Dmdep.outputFile={cp_file}"], cwd=ANALYZER_DIR)
    if r.returncode != 0:
        sys.exit("Maven classpath failed:\n" + r.stdout + r.stderr)
    sources = [str(p) for p in (ANALYZER_DIR / "src" / "main" / "java").rglob("*.java")]
    args_file = bin_dir / "sources.txt"
    args_file.write_text("\n".join(f'"{s}"' for s in sources).replace("\\", "/"), encoding="utf-8")
    dep_cp = cp_file.read_text(encoding="utf-8").strip()
    r = run(["javac", "-encoding", "UTF-8", "-Xlint:none", "-cp", dep_cp, "-d", str(classes), f"@{args_file}"])
    if r.returncode != 0:
        sys.exit("javac failed:\n" + r.stdout + r.stderr)
    return str(classes) + os.pathsep + dep_cp


def clone(url, dest, retries=3):
    """blobless 克隆：保留默认分支完整提交历史（RQ2 年度快照需要），文件内容按需下载。源码保留不删除。
    Blobless clone: keeps the default branch's full commit history (needed for RQ2 yearly snapshots)
    while fetching file contents on demand. Sources are kept, never deleted."""
    if (dest / ".git").exists():
        return ensure_history(dest)
    for attempt in range(1, retries + 1):
        r = run(["git", "-c", "core.longpaths=true", "clone", "--filter=blob:none", "--single-branch",
                 url, str(dest)])
        if r.returncode == 0:
            run(["git", "-C", str(dest), "config", "core.longpaths", "true"])
            return None
        if dest.exists():
            run(["cmd", "/c", "rmdir", "/s", "/q", str(dest)] if os.name == "nt" else ["rm", "-rf", str(dest)])
        time.sleep(10 * attempt)
    return (r.stderr or r.stdout).strip().splitlines()[-1:] or ["clone failed"]


def ensure_history(dest, retries=3):
    """早期浅克隆（--depth 1）补全历史 / unshallows clones made by the earlier --depth 1 runner."""
    r = run(["git", "-C", str(dest), "rev-parse", "--is-shallow-repository"])
    if r.stdout.strip() != "true":
        return None
    for attempt in range(1, retries + 1):
        r = run(["git", "-C", str(dest), "fetch", "--unshallow", "--filter=blob:none"])
        if r.returncode == 0:
            return None
        time.sleep(10 * attempt)
    return ["unshallow failed: " + ((r.stderr or r.stdout).strip().splitlines() or [""])[-1]]


def head(dest):
    r = run(["git", "-C", str(dest), "log", "-1", "--format=%H|%cI"])
    return r.stdout.strip().split("|") if r.returncode == 0 else ["", ""]


def process(project, url, work, classpath, xmx, timeout_min):
    name = slug(project)
    src = work / "sources" / name
    out = work / "results" / name
    log = work / "logs" / f"{name}.log"
    row = {"project": project, "repository": url, "status": "", "commit": "", "commitDate": "", "seconds": ""}
    if (out / "summary.json").exists():
        if (src / ".git").exists():
            ensure_history(src)
        meta = out / "run.json"
        if meta.exists():
            row.update(json.loads(meta.read_text(encoding="utf-8")))
        row["status"] = row.get("status") or "ok"
        return row
    error = clone(url, src)
    if error:
        row["status"] = "clone-failed: " + error[0][:200]
        return row
    row["commit"], row["commitDate"] = head(src)
    row["branch"] = run(["git", "-C", str(src), "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    out.mkdir(parents=True, exist_ok=True)
    start = time.time()
    cmd = ["java", f"-Xmx{xmx}", "-Xss16m", "-cp", classpath, MAIN_CLASS, str(src), str(out)]
    try:
        with open(log, "w", encoding="utf-8") as fh:
            p = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, timeout=timeout_min * 60)
        row["status"] = "ok" if p.returncode == 0 and (out / "summary.json").exists() else f"exit-{p.returncode}"
    except subprocess.TimeoutExpired:
        row["status"] = "timeout"
    row["seconds"] = round(time.time() - start, 1)
    (out / "run.json").write_text(json.dumps(row, ensure_ascii=False, indent=1), encoding="utf-8")
    return row


def aggregate(work, rows):
    results = work / "results"
    table = []
    for row in rows:
        summary_file = results / slug(row["project"]) / "summary.json"
        merged = dict(row)
        if summary_file.exists():
            summary = json.loads(summary_file.read_text(encoding="utf-8"))
            summary.pop("projectRoot", None)
            merged.update(summary)
        table.append(merged)
    keys = []
    for t in table:
        for k in t:
            if k not in keys:
                keys.append(k)
    with open(work / "summary.csv", "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=keys)
        writer.writeheader()
        writer.writerows(table)
    ok = sum(1 for t in table if t.get("status") == "ok")
    print(f"[SUMMARY] {ok}/{len(table)} ok -> {work / 'summary.csv'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True, type=Path)
    ap.add_argument("--projects", type=Path, default=DEFAULT_PROJECTS)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--xmx", default="8g")
    ap.add_argument("--timeout-min", type=int, default=90)
    ap.add_argument("--aggregate-only", action="store_true")
    args = ap.parse_args()

    work = args.work.resolve()
    for d in ("sources", "results", "logs"):
        (work / d).mkdir(parents=True, exist_ok=True)
    with open(args.projects, encoding="utf-8-sig") as fh:
        projects = [(r["project"].strip(), r["repository"].strip()) for r in csv.DictReader(fh)]
    if args.only:
        wanted = {w.lower() for w in args.only}
        projects = [p for p in projects if p[0].lower() in wanted]

    if args.aggregate_only:
        rows = []
        for project, url in projects:
            meta = work / "results" / slug(project) / "run.json"
            rows.append(json.loads(meta.read_text(encoding="utf-8")) if meta.exists()
                        else {"project": project, "repository": url, "status": "not-run"})
        aggregate(work, rows)
        return

    classpath = build(work)
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process, p, u, work, classpath, args.xmx, args.timeout_min): p for p, u in projects}
        for i, f in enumerate(concurrent.futures.as_completed(futures), 1):
            row = f.result()
            rows.append(row)
            print(f"[{i}/{len(projects)}] {row['project']}: {row['status']} {row.get('seconds', '')}s", flush=True)
    order = {p: i for i, (p, _) in enumerate(projects)}
    rows.sort(key=lambda r: order.get(r["project"], 0))
    aggregate(work, rows)


if __name__ == "__main__":
    main()
