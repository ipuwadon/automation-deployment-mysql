#!/usr/bin/env python3
"""
Step 3: execute the generated unit tests and write a markdown report.

Usage:
  run_unit_tests.py                 run the tests listed in .unit-test-work/generated_tests.json
  run_unit_tests.py <Feature> ...   run every feature/<Feature>/unit-test/ut_*.sql (manual re-run)

Environment: DB_HOST, DB_USER, DB_PASS, DB_NAME
             UT_FAIL_ON_ERROR (default true) - exit 1 when any test does not pass

Writes feature/<Feature>/unit-test/unit_test_result.md for each feature, and the
combined report to .unit-test-work/unit_test_summary.md and $GITHUB_STEP_SUMMARY.
"""

import datetime
import glob
import os
import sys

from unit_test_common import (
    FEATURE_DIR,
    GENERATED_FILE,
    UNIT_TEST_DIR,
    WORK_DIR,
    db_configured,
    ensure_work_dir,
    find_unsafe_sql,
    is_inside_repo,
    read_json,
    rel_path,
    repo_path,
    result_file,
    run_mysql,
    utc_now,
)

FAIL_ON_ERROR = os.environ.get("UT_FAIL_ON_ERROR", "true").lower() != "false"
ICONS = {"PASS": "✅", "FAIL": "❌", "ERROR": "💥", "NO_ASSERTIONS": "⚠️", "BLOCKED": "⛔"}


def discover(features):
    tests = []
    for feature in features:
        for path in sorted(glob.glob(repo_path(FEATURE_DIR, feature, UNIT_TEST_DIR, "ut_*.sql"))):
            procedure = os.path.splitext(os.path.basename(path))[0][len("ut_"):]
            tests.append({"feature": feature, "procedure": procedure, "test_file": rel_path(path)})
    return tests


def execute(test):
    path = repo_path(test["test_file"])
    result = {"assertions": [], "errors": [], "status": "ERROR"}
    if not is_inside_repo(path) or not os.path.exists(path):
        result["errors"].append("Test file not found: {}".format(test["test_file"]))
        return result
    with open(path, "r", encoding="utf-8-sig") as f:
        sql = f.read()

    unsafe = find_unsafe_sql(sql, test["procedure"])
    if unsafe:
        result["status"] = "BLOCKED"
        result["errors"].append("Refused to run unsafe statement: {}".format(unsafe))
        return result

    started = datetime.datetime.now()
    returncode, result["assertions"], errors = run_mysql(sql)
    result["duration"] = (datetime.datetime.now() - started).total_seconds()
    result["errors"] += errors

    if returncode != 0:
        result["status"] = "ERROR"
    elif not result["assertions"]:
        result["status"] = "NO_ASSERTIONS"
    elif all(a["result"] == "PASS" for a in result["assertions"]):
        result["status"] = "PASS"
    else:
        result["status"] = "FAIL"
    return result


def md(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def render(title, runs):
    total = len(runs)
    passed = sum(1 for t, r in runs if r["status"] == "PASS")
    asserts = [a for t, r in runs for a in r["assertions"]]
    asserts_ok = sum(1 for a in asserts if a["result"] == "PASS")
    overall = "PASS" if passed == total else "FAIL"
    lines = [
        "# {} {}".format(ICONS[overall], title),
        "",
        "- **Run at:** {}".format(utc_now()),
    ]
    if os.environ.get("GITHUB_SHA"):
        lines.append("- **Commit:** `{}`".format(os.environ.get("PR_HEAD_SHA") or os.environ["GITHUB_SHA"]))
    lines += [
        "- **Procedures:** {}/{} passed".format(passed, total),
        "- **Assertions:** {}/{} passed".format(asserts_ok, len(asserts)),
        "",
        "| Feature | Procedure | Status | Assertions | Generation | Test script |",
        "|---|---|---|---|---|---|",
    ]
    for t, r in runs:
        ok = sum(1 for a in r["assertions"] if a["result"] == "PASS")
        lines.append("| {} | `{}` | {} {} | {}/{} | {} | [{}]({}) |".format(
            md(t["feature"]), md(t["procedure"]), ICONS[r["status"]], r["status"], ok, len(r["assertions"]),
            md(t.get("generation", "-")), os.path.basename(t["test_file"]), os.path.basename(t["test_file"])))

    for t, r in runs:
        lines += ["", "## {} `{}`".format(ICONS[r["status"]], t["procedure"]), ""]
        meta = ["Source: `{}`".format(t["source_path"])] if t.get("source_path") else []
        if t.get("model"):
            meta.append("Model: `{}` ({} after {} attempt(s))".format(t["model"], t.get("generation"), t.get("attempts")))
        if "duration" in r:
            meta.append("Duration: {:.2f}s".format(r["duration"]))
        lines += ["- " + m for m in meta]
        if t.get("generation_error"):
            lines.append("- ⚠️ AI generation fell back to baseline checks: {}".format(md(t["generation_error"])))
        if r["assertions"]:
            lines += ["", "| # | Test case | Result | Details |", "|---|---|---|---|"]
            for i, a in enumerate(r["assertions"], 1):
                lines.append("| {} | {} | {} {} | {} |".format(
                    i, md(a["name"]), ICONS.get(a["result"], "❔"), md(a["result"]), md(a["details"])))
        if r["errors"]:
            lines += ["", "**Errors**", "", "```text"] + r["errors"] + ["```"]
        if t.get("analysis"):
            lines += ["", "<details><summary>AI analysis</summary>", "", t["analysis"], "", "</details>"]
    lines.append("")
    return "\n".join(lines), overall


def main():
    if not db_configured():
        sys.exit("ERROR: Missing DB_* environment variables (DB_HOST/DB_USER/DB_PASS/DB_NAME)")

    tests = discover(sys.argv[1:]) if len(sys.argv) > 1 else read_json(GENERATED_FILE, [])
    if not tests:
        print("No unit tests to run.")
        return 0

    runs = []
    for test in tests:
        print("\n--- Running {} ({})".format(test["test_file"], test["feature"]))
        result = execute(test)
        for a in result["assertions"]:
            print("  [{}] {} - {}".format(a["result"], a["name"], a["details"]))
        for e in result["errors"]:
            print("  {}".format(e))
        print("  => {}".format(result["status"]))
        runs.append((test, result))

    any_failed = False
    for feature in sorted({t["feature"] for t, r in runs}):
        report, overall = render("Unit test result - {}".format(feature), [x for x in runs if x[0]["feature"] == feature])
        target = result_file(feature)
        with open(target, "w", encoding="utf-8", newline="\n") as f:
            f.write(report)
        print("Report written to {}".format(rel_path(target)))
        any_failed = any_failed or overall != "PASS"

    summary, _ = render("Procedure unit test summary", runs)
    ensure_work_dir()
    with open(os.path.join(WORK_DIR, "unit_test_summary.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(summary)
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as f:
            f.write(summary)

    if any_failed and FAIL_ON_ERROR:
        print("::error::One or more procedure unit tests did not pass")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
