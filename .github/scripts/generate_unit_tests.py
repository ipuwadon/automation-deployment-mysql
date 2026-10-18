#!/usr/bin/env python3
"""
Step 2: ask Qwen (via Ollama) to analyse each changed procedure and generate a
MySQL unit-test script, saved to feature/<Feature>/unit-test/ut_<procedure>.sql.

Input : .unit-test-work/procedure_changes.json  (from detect_procedure_changes.py)
Output: the unit-test scripts + .unit-test-work/generated_tests.json

Environment:
  QWEN_MODEL         Ollama model tag (default qwen2.5-coder:1.5b)
  OLLAMA_HOST        Ollama endpoint (default http://127.0.0.1:11434)
  QWEN_MAX_ATTEMPTS  generation retries when the answer is unusable (default 3)
  QWEN_TIMEOUT       seconds per model call (default 600)
  UT_DRY_RUN         when DB_* are set, execute each candidate and feed MySQL
                     errors back to the model for another attempt (default true)

Generated assertions follow one contract so run_unit_tests.py can grade them:
  SELECT 'UT_RESULT', '<test_case>', IF(<condition>, 'PASS', 'FAIL'), <details>;
"""

import glob
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

from unit_test_common import (
    CHANGES_FILE,
    GENERATED_FILE,
    RESULT_MARKER,
    db_configured,
    find_unsafe_sql,
    read_json,
    rel_path,
    repo_path,
    run_mysql,
    strip_sql_comments,
    unit_test_file,
    utc_now,
    write_json,
)

MODEL = os.environ.get("QWEN_MODEL", "qwen2.5-coder:1.5b")
MAX_ATTEMPTS = max(1, int(os.environ.get("QWEN_MAX_ATTEMPTS", "3")))
TIMEOUT = int(os.environ.get("QWEN_TIMEOUT", "600"))
DRY_RUN = os.environ.get("UT_DRY_RUN", "true").lower() != "false"
CONTEXT_DIRS = ("tables", "views")
MAX_CONTEXT_CHARS = 4000

TRANSACTION_CONTROL = re.compile(
    r"(?im)^\s*(?:START\s+TRANSACTION|BEGIN(?:\s+WORK)?|COMMIT(?:\s+WORK)?|ROLLBACK(?:\s+WORK)?)\s*;\s*$"
)
SQL_BLOCK = re.compile(r"```(?:sql|mysql)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)

PROMPT_TEMPLATE = """You are a senior MySQL 8 database engineer.

TASK
1. Analyse the stored procedure `{name}` below: purpose, parameters, tables used, business rules, edge cases, and the risk introduced by the PR diff.
2. Write a MySQL unit-test script for it.

RULES FOR THE TEST SCRIPT
- It already runs inside a transaction that is rolled back afterwards. Do NOT write START TRANSACTION, COMMIT or ROLLBACK.
- Allowed: INSERT/UPDATE/DELETE of fixture rows, SET @variables, SELECT, CREATE TEMPORARY TABLE, DROP TEMPORARY TABLE, and CALL {name}(...).
- Forbidden: CREATE/ALTER/DROP of permanent objects, TRUNCATE, DELIMITER, USE, GRANT, calling any other procedure.
- Use fixture ids that will not clash with real data (for example 900001 and above) and respect the table definitions given.
- Every assertion MUST be exactly one statement of this form (4 columns, first column literally 'UT_RESULT'):
  SELECT 'UT_RESULT', '<test_case_name>', IF(<condition>, 'PASS', 'FAIL'), CONCAT('<what was checked>: ', <actual value>);
- MySQL cannot SELECT from a CALL result set and `CALL ... INTO` does not exist, so assert on OUT parameters, on rows the procedure changes, or on the same calculation applied to your fixture rows.
- Cover the happy path, edge cases (no matching rows, NULL / zero values, boundaries) and the behaviour changed by the diff.

RESPONSE FORMAT (follow exactly)
### ANALYSIS
<concise bullet points>
### TEST
```sql
<the unit-test script>
```

EXAMPLE ASSERTION
SELECT 'UT_RESULT', 'total_is_sum_of_lines', IF(@total = 150.00, 'PASS', 'FAIL'), CONCAT('expected 150.00, got ', IFNULL(@total, 'NULL'));

PROCEDURE SOURCE ({path})
```sql
{source}
```

PR DIFF FOR THIS PROCEDURE
```diff
{diff}
```

RELATED TABLE / VIEW DEFINITIONS
{context}
"""


def ollama_url():
    host = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434").strip().rstrip("/")
    if "://" not in host:
        host = "http://" + host
    return host.replace("://0.0.0.0", "://127.0.0.1") + "/api/generate"


def ask_qwen(prompt):
    payload = json.dumps(
        {
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2, "num_ctx": 8192},
        }
    ).encode("utf-8")
    request = urllib.request.Request(ollama_url(), data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8")).get("response", "")
    except (urllib.error.URLError, OSError) as e:
        print("Ollama HTTP API unavailable ({}); falling back to the ollama CLI".format(e))

    proc = subprocess.run(
        ["ollama", "run", MODEL],
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=TIMEOUT,
    )
    if proc.returncode != 0:
        raise RuntimeError("ollama run failed: {}".format(proc.stderr.strip()))
    return proc.stdout


def related_definitions(source):
    """DDL of tables/views whose file name is referenced by the procedure."""
    code = strip_sql_comments(source).lower()
    blocks = []
    for folder in CONTEXT_DIRS:
        for path in sorted(glob.glob(repo_path(folder, "*.sql"))):
            name = os.path.splitext(os.path.basename(path))[0].lower()
            if re.search(r"\b{}\b".format(re.escape(name)), code):
                with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
                    ddl = f.read()[:MAX_CONTEXT_CHARS]
                blocks.append("-- {}\n```sql\n{}\n```".format(rel_path(path), ddl.strip()))
    return "\n\n".join(blocks) or "(none found)"


def parse_response(text):
    blocks = SQL_BLOCK.findall(text)
    sql = blocks[-1] if blocks else ""
    analysis = text.split("```", 1)[0]
    analysis = re.sub(r"(?is)###\s*TEST.*$", "", analysis)
    analysis = re.sub(r"(?i)###\s*ANALYSIS\s*", "", analysis).strip()
    sql = TRANSACTION_CONTROL.sub("", sql).strip()
    return analysis, sql


def validate(sql, procedure):
    if not sql:
        return "no ```sql block in the answer"
    if RESULT_MARKER not in sql:
        return "no '{}' assertions in the script".format(RESULT_MARKER)
    unsafe = find_unsafe_sql(sql, procedure)
    if unsafe:
        return "forbidden statement: {}".format(unsafe)
    return None


def has_no_parameters(source, procedure):
    pattern = r"(?is)PROCEDURE\s+(?:(?:`[^`]+`|\w+)\s*\.\s*)?`?{}`?\s*\(\s*\)".format(re.escape(procedure))
    return re.search(pattern, source) is not None


def baseline_sql(procedure, callable_without_args):
    name = procedure.replace("'", "''")
    sql = (
        "SELECT 'UT_RESULT', 'procedure_exists', IF(COUNT(*) = 1, 'PASS', 'FAIL'),\n"
        "       CONCAT('routines found: ', COUNT(*))\n"
        "FROM information_schema.routines\n"
        "WHERE routine_schema = DATABASE() AND routine_type = 'PROCEDURE' AND routine_name = '{}';\n"
    ).format(name)
    if callable_without_args:
        sql += (
            "\nCALL `{0}`();\n"
            "SELECT 'UT_RESULT', 'procedure_executes', 'PASS', 'CALL {0}() completed without error';\n"
        ).format(procedure)
    return sql


def build_script(entry, analysis, ai_sql, generation, attempts):
    procedure = entry["procedure"]
    stamp = utc_now()
    analysis_comment = "\n".join("--   " + l for l in (analysis or "(no analysis)").splitlines())
    parts = [
        "-- Auto-generated unit test for procedure `{}`".format(procedure),
        "-- Source     : {}".format(entry["path"]),
        "-- Model      : {} | generation: {} | attempts: {}".format(MODEL, generation, attempts),
        "-- Generated  : {}".format(stamp),
        "-- Contract   : each assertion returns 'UT_RESULT', <test_case>, 'PASS'|'FAIL', <details>",
        "-- AI analysis:",
        analysis_comment,
        "",
        "-- Baseline checks",
        baseline_sql(procedure, generation == "fallback" and has_no_parameters(entry["source"], procedure)),
        "START TRANSACTION;",
        "",
    ]
    if ai_sql:
        parts += ["-- AI generated tests", ai_sql, ""]
    parts += ["ROLLBACK;", ""]
    return "\n".join(parts)


def generate(entry):
    procedure = entry["procedure"]
    prompt = PROMPT_TEMPLATE.format(
        name=procedure,
        path=entry["path"],
        source=entry["source"],
        diff=entry["diff"] or "(new file)",
        context=related_definitions(entry["source"]),
    )
    feedback = ""
    analysis, last_error = "", None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        print("Asking {} about {} (attempt {}/{})".format(MODEL, procedure, attempt, MAX_ATTEMPTS))
        try:
            answer = ask_qwen(prompt + feedback)
        except Exception as e:  # model offline, timeout, ...
            last_error = str(e)
            print("WARNING: {}".format(last_error))
            continue
        analysis, sql = parse_response(answer)
        last_error = validate(sql, procedure)
        if not last_error:
            last_error = dry_run(entry, analysis, sql, attempt)
        if not last_error:
            return analysis, sql, "ai", attempt, None
        print("Rejected answer: {}".format(last_error))
        feedback = (
            "\n\nYOUR PREVIOUS TEST SCRIPT WAS REJECTED: {}\n```sql\n{}\n```\n"
            "Fix it, answer again in the required format and follow every rule.".format(last_error, sql)
        )
    return analysis, "", "fallback", MAX_ATTEMPTS, last_error


def dry_run(entry, analysis, sql, attempt):
    """Execute the candidate (inside its rolled-back transaction) so MySQL errors can be fed back to the model."""
    if not DRY_RUN or not db_configured():
        return None
    returncode, _, errors = run_mysql(build_script(entry, analysis, sql, "ai", attempt))
    if returncode != 0:
        return "MySQL error when executing it: {}".format(" ".join(errors) or "exit code {}".format(returncode))
    return None


def main():
    changes = read_json(CHANGES_FILE, [])
    if not changes:
        print("No changed procedures - nothing to generate.")
        write_json(GENERATED_FILE, [])
        return 0

    manifest = []
    for entry in changes:
        with open(repo_path(entry["path"]), "r", encoding="utf-8-sig", errors="ignore") as f:
            entry["source"] = f.read()

        analysis, sql, generation, attempts, error = generate(entry)
        if generation == "fallback":
            print("::warning::AI test generation failed for {} ({}); using baseline checks only".format(
                entry["procedure"], error))
        script = build_script(entry, analysis, sql, generation, attempts)

        for feature in entry["features"]:
            target = unit_test_file(feature, entry["procedure"])
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8", newline="\n") as f:
                f.write(script)
            print("Saved {}".format(rel_path(target)))
            manifest.append(
                {
                    "feature": feature,
                    "procedure": entry["procedure"],
                    "source_path": entry["path"],
                    "change": entry["status"],
                    "test_file": rel_path(target),
                    "model": MODEL,
                    "generation": generation,
                    "attempts": attempts,
                    "generation_error": error,
                    "analysis": analysis,
                }
            )

    write_json(GENERATED_FILE, manifest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
