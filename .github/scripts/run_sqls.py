#!/usr/bin/env python3
"""
Run SQL files referenced by driver/control files detected in changed_files.txt.

Expected environment variables:
  DB_HOST, DB_USER, DB_PASS, DB_NAME
The workflow must create changed_files.txt (repo-root relative).
"""

import os
import re
import subprocess
import sys

WORKDIR = os.environ.get("GITHUB_WORKSPACE", os.getcwd())
DB_HOST = os.environ.get("DB_HOST")
DB_USER = os.environ.get("DB_USER")
DB_PASS = os.environ.get("DB_PASS")
DB_NAME = os.environ.get("DB_NAME")

CHANGED_FILE = os.path.join(WORKDIR, "changed_files.txt")
BACKOUT_NAME = "backout_script.sql"
RELEASE_NAME = "release_script.sql"
DANGEROUS_SQL = re.compile(
    r"(?is)(?:\bDROP\s+(?:DATABASE|SCHEMA|TABLE|VIEW|PROCEDURE|TRIGGER|EVENT)\b|"
    r"\bTRUNCATE\s+TABLE\b|\bALTER\s+USER\b|\bCREATE\s+USER\b|\bDROP\s+USER\b|"
    r"\bGRANT\b|\bREVOKE\b|\bDELETE\s+FROM\b|\bCALL\s+.*?xp_|"
    r"\bKILL\b|\bFLUSH\b|\bSHUTDOWN\b)"
)


def die(msg, code=1):
    print(msg)
    sys.exit(code)


def is_safe_repo_path(path):
    if not path:
        return False
    try:
        repo_root = os.path.abspath(WORKDIR)
        abs_path = os.path.abspath(path)
        if os.path.commonpath([repo_root, abs_path]) != repo_root:
            return False
    except ValueError:
        return False
    return True


if not all([DB_HOST, DB_USER, DB_PASS is not None, DB_NAME]):
    die("ERROR: Missing DB_* environment variables (DB_HOST/DB_USER/DB_PASS/DB_NAME)")

if not os.path.exists(CHANGED_FILE):
    print("No changed_files.txt found — nothing to do.")
    sys.exit(0)

with open(CHANGED_FILE, "r", encoding="ascii", errors="ignore") as f:
    changed = [line.strip() for line in f if line.strip()]

print("Changed files:", changed)


def find_drivers(changed_list, name):
    return [p for p in changed_list if p.lower().endswith(name.lower())]


backout_drivers = find_drivers(changed, BACKOUT_NAME)
release_drivers = find_drivers(changed, RELEASE_NAME)

print("Backout drivers:", backout_drivers)
print("Release drivers:", release_drivers)


def clean_path(s):
    if not s:
        return s
    s = s.strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1]
    return s.strip()


def resolve_path(candidate, driver_dir):
    if not candidate:
        return None
    candidate = candidate.replace('"', '').replace("'", "").strip()
    if candidate.startswith("//") or candidate.startswith("\\\\"):
        return None
    try_paths = []
    try_paths.append(os.path.normpath(candidate))
    try_paths.append(os.path.join(WORKDIR, candidate))
    if driver_dir:
        try_paths.append(os.path.join(driver_dir, candidate))
    stripped = candidate.lstrip("./\\")
    try_paths.append(os.path.join(WORKDIR, stripped))

    for p in try_paths:
        abs_path = os.path.abspath(p)
        if is_safe_repo_path(abs_path) and os.path.exists(abs_path):
            return abs_path
    return None


def parse_includes(driver_file):
    """
    Return (abs_driver_path, [include_path_strings])
    include path strings are as written in the driver (unresolved).
    """
    driver_abs = os.path.join(WORKDIR, driver_file) if not os.path.isabs(driver_file) else driver_file
    if not is_safe_repo_path(driver_abs) or not os.path.exists(driver_abs):
        print(f"Driver not found or outside repo: {driver_file}")
        return None, []
    includes = []
    with open(driver_abs, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            low = line.lower()
            if low.startswith("source "):
                parts = line.split(None, 1)
                if len(parts) > 1:
                    includes.append(parts[1].strip())
                continue
            if line.startswith("\\.") or line.startswith("./") or line.startswith(".\\"):
                includes.append(line[2:].strip())
                continue
            if line.startswith("@"):
                includes.append(line[1:].strip())
                continue
    return driver_abs, includes


def contains_disallowed_sql(content):
    cleaned = re.sub(r"--.*?$", "", content, flags=re.MULTILINE)
    cleaned = cleaned.replace("\r", " ")
    return bool(DANGEROUS_SQL.search(cleaned))


def run_sql_file(path):
    print(f"\n--- Running SQL: {path}")
    if not is_safe_repo_path(path):
        print(f"Refusing to run SQL outside the repository: {path}")
        return 1
    try:
        with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        print(f"Failed to read {path}: {e}")
        return 1

    if contains_disallowed_sql(content):
        print(f"Refusing to run SQL containing unsafe statements: {path}")
        return 1

    cmd = ["mysql", "-h", DB_HOST, "-u", DB_USER, f"-p{DB_PASS}", DB_NAME]
    print("Running:", " ".join(cmd))
    proc = subprocess.run(cmd, input=content, text=True, encoding="utf-8", capture_output=True)
    if proc.stdout:
        print("stdout:")
        print(proc.stdout)
    if proc.stderr:
        print("stderr:")
        print(proc.stderr)
    return proc.returncode


overall_rc = 0

# process backout drivers first
for d in backout_drivers:
    driver_abs, includes = parse_includes(d)
    if driver_abs is None:
        overall_rc = 1
        break
    if not includes:
        rc = run_sql_file(driver_abs)
        if rc != 0:
            overall_rc = rc
            break
    else:
        for inc in includes:
            inc_clean = clean_path(inc)
            resolved = resolve_path(inc_clean, os.path.dirname(driver_abs))
            if not resolved:
                print(f"Included file not found: {inc} (from {d})")
                overall_rc = 1
                break
            rc = run_sql_file(resolved)
            if rc != 0:
                overall_rc = rc
                break
    if overall_rc != 0:
        break

# if backouts ok, run releases
if overall_rc == 0:
    for d in release_drivers:
        driver_abs, includes = parse_includes(d)
        if driver_abs is None:
            overall_rc = 1
            break
        if not includes:
            rc = run_sql_file(driver_abs)
            if rc != 0:
                overall_rc = rc
                break
        else:
            for inc in includes:
                inc_clean = clean_path(inc)
                resolved = resolve_path(inc_clean, os.path.dirname(driver_abs))
                if not resolved:
                    print(f"Included file not found: {inc} (from {d})")
                    overall_rc = 1
                    break
                rc = run_sql_file(resolved)
                if rc != 0:
                    overall_rc = rc
                    break
        if overall_rc != 0:
            break

print("Overall exit code:", overall_rc)
sys.exit(overall_rc)