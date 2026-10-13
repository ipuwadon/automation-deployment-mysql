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
    r"(?is)(?:\bDROP\s+(?:DATABASE|SCHEMA|TABLE|VIEW|PROCEDURE|FUNCTION|TRIGGER|EVENT)\b|"
    r"\bTRUNCATE\s+TABLE\b|\bALTER\s+USER\b|\bCREATE\s+USER\b|\bDROP\s+USER\b|"
    r"\bGRANT\b|\bREVOKE\b|\bDELETE\s+FROM\b|\bCALL\s+.*?xp_|"
    r"\bKILL\b|\bFLUSH\b|\bSHUTDOWN\b)"
)

# Object names may be bare, backtick-quoted, and optionally schema-qualified.
OBJECT_NAME = r"(?:`[^`]+`|[A-Za-z0-9_$]+)"
QUALIFIED_NAME = r"(?:{n}\s*\.\s*)?{n}".format(n=OBJECT_NAME)
NAME_LIST = r"{q}(?:\s*,\s*{q})*".format(q=QUALIFIED_NAME)
QUALIFIED_NAME_RE = re.compile(QUALIFIED_NAME)
NAME_TOKEN_RE = re.compile(r"`([^`]+)`|([A-Za-z0-9_$]+)")

DEFINER = r"(?:DEFINER\s*=\s*\S+\s+)?"
CREATE_PATTERNS = {
    "table": re.compile(
        r"(?is)\bCREATE\s+(?:TEMPORARY\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?({q})".format(q=QUALIFIED_NAME)
    ),
    "view": re.compile(
        r"(?is)\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:ALGORITHM\s*=\s*\w+\s+)?{d}"
        r"(?:SQL\s+SECURITY\s+(?:DEFINER|INVOKER)\s+)?VIEW\s+(?:IF\s+NOT\s+EXISTS\s+)?({q})".format(
            d=DEFINER, q=QUALIFIED_NAME
        )
    ),
    "procedure": re.compile(
        r"(?is)\bCREATE\s+{d}PROCEDURE\s+(?:IF\s+NOT\s+EXISTS\s+)?({q})".format(d=DEFINER, q=QUALIFIED_NAME)
    ),
    "function": re.compile(
        r"(?is)\bCREATE\s+{d}(?:AGGREGATE\s+)?FUNCTION\s+(?:IF\s+NOT\s+EXISTS\s+)?({q})".format(
            d=DEFINER, q=QUALIFIED_NAME
        )
    ),
    "trigger": re.compile(
        r"(?is)\bCREATE\s+{d}TRIGGER\s+(?:IF\s+NOT\s+EXISTS\s+)?({q})".format(d=DEFINER, q=QUALIFIED_NAME)
    ),
    "event": re.compile(
        r"(?is)\bCREATE\s+{d}EVENT\s+(?:IF\s+NOT\s+EXISTS\s+)?({q})".format(d=DEFINER, q=QUALIFIED_NAME)
    ),
}
ROW_WRITE_PATTERNS = (
    re.compile(
        r"(?is)\bINSERT\s+(?:LOW_PRIORITY\s+|DELAYED\s+|HIGH_PRIORITY\s+|IGNORE\s+)*INTO\s+({q})".format(
            q=QUALIFIED_NAME
        )
    ),
    re.compile(
        r"(?is)\bREPLACE\s+(?:LOW_PRIORITY\s+|DELAYED\s+)*INTO\s+({q})".format(q=QUALIFIED_NAME)
    ),
)
DROP_OBJECT = re.compile(
    r"(?is)\bDROP\s+(TABLE|VIEW|PROCEDURE|FUNCTION|TRIGGER|EVENT)\s+(?:IF\s+EXISTS\s+)?({l})".format(l=NAME_LIST)
)
DELETE_FROM = re.compile(
    r"(?is)\bDELETE\s+(?:LOW_PRIORITY\s+|QUICK\s+|IGNORE\s+)*FROM\s+({q})".format(q=QUALIFIED_NAME)
)
TRUNCATE_TABLE = re.compile(r"(?is)\bTRUNCATE\s+TABLE\s+({q})".format(q=QUALIFIED_NAME))
OBJECT_KINDS = tuple(CREATE_PATTERNS) + ("rows",)


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


def remove_sql_comments(content):
    cleaned = re.sub(r"--.*?$", "", content, flags=re.MULTILINE)
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"#.*?$", "", cleaned, flags=re.MULTILINE)
    return cleaned.replace("\r", " ")


def split_qualified_name(raw):
    return [m.group(1) if m.group(1) is not None else m.group(2) for m in NAME_TOKEN_RE.finditer(raw)]


def resolve_object_name(raw):
    """
    Normalize an object name to a bare lowercase name.

    Returns None when the name is schema-qualified with anything other than the
    target database, so a backout can never reach another schema.
    """
    tokens = split_qualified_name(raw or "")
    if not tokens or len(tokens) > 2:
        return None
    if len(tokens) == 2:
        schema, name = tokens
        if not DB_NAME or schema.lower() != DB_NAME.lower():
            return None
        return name.lower()
    return tokens[0].lower()


def driver_sql_files(driver):
    """Return the SQL files a driver executes (its includes, or the driver itself)."""
    driver_abs, includes = parse_includes(driver)
    if driver_abs is None:
        return []
    if not includes:
        return [driver_abs]
    resolved_files = []
    for include in includes:
        resolved = resolve_path(clean_path(include), os.path.dirname(driver_abs))
        if resolved:
            resolved_files.append(resolved)
    return resolved_files


def companion_release_drivers(backout_list):
    """Find each backout driver's sibling release driver, even when it is unchanged."""
    companions = []
    for driver in backout_list:
        driver_abs = driver if os.path.isabs(driver) else os.path.join(WORKDIR, driver)
        candidate = os.path.join(os.path.dirname(os.path.abspath(driver_abs)), RELEASE_NAME)
        if is_safe_repo_path(candidate) and os.path.exists(candidate) and candidate not in companions:
            companions.append(candidate)
    return companions


def collect_released_objects(drivers):
    """
    Map each object kind to the names the release creates, plus the tables it
    populates. A backout may only drop or clear objects found here.
    """
    objects = {kind: set() for kind in OBJECT_KINDS}
    seen_files = set()
    for driver in drivers:
        for path in driver_sql_files(driver):
            key = os.path.normcase(os.path.abspath(path))
            if key in seen_files:
                continue
            seen_files.add(key)
            try:
                with open(path, "r", encoding="utf-8-sig", errors="ignore") as sql_file:
                    content = remove_sql_comments(sql_file.read())
            except OSError as e:
                print(f"Failed to read release SQL {path}: {e}")
                continue
            for kind, pattern in CREATE_PATTERNS.items():
                for raw in pattern.findall(content):
                    name = resolve_object_name(raw)
                    if name:
                        objects[kind].add(name)
            for pattern in ROW_WRITE_PATTERNS:
                for raw in pattern.findall(content):
                    name = resolve_object_name(raw)
                    if name:
                        objects["rows"].add(name)
    # Any table the release creates may also have its rows cleared by the backout.
    objects["rows"].update(objects["table"])
    return objects


def describe_allowed_objects(allowed_objects):
    summary = {kind: sorted(names) for kind, names in allowed_objects.items() if names}
    return summary or "none"


def find_disallowed_sql(content, allowed_objects=None):
    """Return the first blocked statement fragment, or None when the SQL is allowed."""
    cleaned = remove_sql_comments(content)
    allowed_objects = allowed_objects or {}

    def approve_drop(match):
        permitted = allowed_objects.get(match.group(1).lower(), set())
        names = [resolve_object_name(raw) for raw in QUALIFIED_NAME_RE.findall(match.group(2))]
        if names and all(name in permitted for name in names):
            return " "
        return match.group(0)

    def approve_row_change(match):
        name = resolve_object_name(match.group(1))
        if name and name in allowed_objects.get("rows", set()):
            return " "
        return match.group(0)

    cleaned = DROP_OBJECT.sub(approve_drop, cleaned)
    cleaned = DELETE_FROM.sub(approve_row_change, cleaned)
    cleaned = TRUNCATE_TABLE.sub(approve_row_change, cleaned)
    match = DANGEROUS_SQL.search(cleaned)
    return " ".join(match.group(0).split()) if match else None


def run_sql_file(path, allowed_objects=None):
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

    blocked = find_disallowed_sql(content, allowed_objects)
    if blocked:
        print(f"Refusing to run SQL containing unsafe statements: {path}")
        print(f"Blocked statement: {blocked}")
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
allowed_objects = collect_released_objects(release_drivers + companion_release_drivers(backout_drivers))
print("Objects created by the release:", describe_allowed_objects(allowed_objects))

# process backout drivers first
for d in backout_drivers:
    driver_abs, includes = parse_includes(d)
    if driver_abs is None:
        overall_rc = 1
        break
    if not includes:
        rc = run_sql_file(driver_abs, allowed_objects)
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
            rc = run_sql_file(resolved, allowed_objects)
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
            rc = run_sql_file(driver_abs, allowed_objects)
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
                rc = run_sql_file(resolved, allowed_objects)
                if rc != 0:
                    overall_rc = rc
                    break
        if overall_rc != 0:
            break

print("Overall exit code:", overall_rc)
sys.exit(overall_rc)