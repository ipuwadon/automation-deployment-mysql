"""Shared helpers for the AI procedure unit-test pipeline."""

import datetime
import json
import os
import re
import subprocess

WORKDIR = os.path.abspath(os.environ.get("GITHUB_WORKSPACE", os.getcwd()))
WORK_DIR = os.path.join(WORKDIR, ".unit-test-work")
CHANGES_FILE = os.path.join(WORK_DIR, "procedure_changes.json")
GENERATED_FILE = os.path.join(WORK_DIR, "generated_tests.json")
PROCEDURE_DIR = "procedures"
FEATURE_DIR = "feature"
UNIT_TEST_DIR = "unit-test"
RESULT_MARKER = "UT_RESULT"

# Statements that would escape the test transaction (implicit commit) or touch
# anything beyond throw-away fixture data.
_BLOCKED_SQL = re.compile(
    r"(?is)\b(?:"
    r"DROP\s+(?!TEMPORARY\b)\w+|"
    r"CREATE\s+(?!TEMPORARY\s+TABLE\b)(?:OR\s+REPLACE\s+)?\w+|"
    r"ALTER\s+\w+|RENAME\s+\w+|TRUNCATE\b|GRANT\b|REVOKE\b|"
    r"COMMIT\b|SAVEPOINT\b|LOCK\s+TABLES?\b|UNLOCK\s+TABLES?\b|"
    r"SET\s+(?:@@(?:(?:GLOBAL|SESSION)\.)?)?(?:GLOBAL\s+|SESSION\s+)?autocommit\b|"
    r"USE\s+\w+|LOAD\s+DATA\b|INTO\s+(?:OUT|DUMP)FILE\b|"
    r"KILL\b|FLUSH\b|SHUTDOWN\b|INSTALL\b|UNINSTALL\b|DELIMITER\b"
    r")"
)
_CALL_RE = re.compile(r"(?is)\bCALL\s+((?:`[^`]+`|\w+)(?:\s*\.\s*(?:`[^`]+`|\w+))?)")


def ensure_work_dir():
    os.makedirs(WORK_DIR, exist_ok=True)


def read_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    ensure_work_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def repo_path(*parts):
    return os.path.join(WORKDIR, *parts)


def rel_path(path):
    return os.path.relpath(path, WORKDIR).replace("\\", "/")


def is_inside_repo(path):
    try:
        return os.path.commonpath([WORKDIR, os.path.abspath(path)]) == WORKDIR
    except ValueError:
        return False


def strip_sql_comments(sql):
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"--[^\n]*", " ", sql)
    return re.sub(r"(?m)^\s*#[^\n]*", " ", sql)


def strip_sql_strings(sql):
    """Blank out string literals so keywords inside messages are not flagged."""
    return re.sub(r"'(?:[^'\\]|\\.|'')*'|\"(?:[^\"\\]|\\.)*\"", "''", sql)


def find_unsafe_sql(sql, procedure_name):
    """Return a description of the first disallowed statement, or None."""
    cleaned = strip_sql_strings(strip_sql_comments(sql))
    match = _BLOCKED_SQL.search(cleaned)
    if match:
        return " ".join(match.group(0).split())
    target = procedure_name.lower()
    for raw in _CALL_RE.findall(cleaned):
        name = raw.replace("`", "").split(".")[-1].strip().lower()
        if name != target:
            return "CALL " + raw
    return None


def unit_test_file(feature, procedure):
    return repo_path(FEATURE_DIR, feature, UNIT_TEST_DIR, "ut_{}.sql".format(procedure))


def result_file(feature):
    return repo_path(FEATURE_DIR, feature, UNIT_TEST_DIR, "unit_test_result.md")


def set_github_output(name, value):
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as f:
            f.write("{}={}\n".format(name, value))


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def db_configured():
    return all(os.environ.get(k) for k in ("DB_HOST", "DB_USER", "DB_NAME")) and "DB_PASS" in os.environ


def run_mysql(sql):
    """Run a script with the mysql client; returns (returncode, assertions, stderr_lines)."""
    cmd = ["mysql", "-h", os.environ["DB_HOST"], "-u", os.environ["DB_USER"], "--batch",
           "--skip-column-names", "--default-character-set=utf8mb4", os.environ["DB_NAME"]]
    env = dict(os.environ, MYSQL_PWD=os.environ.get("DB_PASS", ""))
    proc = subprocess.run(cmd, input=sql, capture_output=True, text=True, encoding="utf-8", env=env)
    assertions = []
    for line in proc.stdout.splitlines():
        cols = line.split("\t")
        if len(cols) >= 3 and cols[0] == RESULT_MARKER:
            assertions.append(
                {
                    "name": _unescape(cols[1]),
                    "result": cols[2].strip().upper(),
                    "details": _unescape(cols[3]) if len(cols) > 3 else "",
                }
            )
    errors = [l.strip() for l in proc.stderr.splitlines() if l.strip()]
    return proc.returncode, assertions, errors


def _unescape(value):
    return value.replace("\\t", "\t").replace("\\n", " ").replace("\\\\", "\\")
