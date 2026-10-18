#!/usr/bin/env python3
"""
Step 1: isolate the stored-procedure part of a PR diff.

Usage: detect_procedure_changes.py <base_sha> <head_sha>
       (or set BASE_SHA / HEAD_SHA)

Writes:
  .unit-test-work/procedure_diff.patch     diff restricted to procedures/
  .unit-test-work/procedure_changes.json   one entry per changed procedure,
                                           with the feature folders that own it
Sets the GitHub output has_procedures=true|false.
"""

import glob
import os
import re
import subprocess
import sys

from unit_test_common import (
    CHANGES_FILE,
    FEATURE_DIR,
    PROCEDURE_DIR,
    WORK_DIR,
    WORKDIR,
    ensure_work_dir,
    rel_path,
    set_github_output,
    write_json,
)

PROCEDURE_NAME_RE = re.compile(
    r"(?is)\bCREATE\s+(?:DEFINER\s*=\s*\S+\s+)?PROCEDURE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"(?:(?:`[^`]+`|\w+)\s*\.\s*)?(`[^`]+`|\w+)"
)


def git(*args):
    proc = subprocess.run(
        ["git"] + list(args), cwd=WORKDIR, capture_output=True, text=True, encoding="utf-8"
    )
    if proc.returncode != 0:
        print(proc.stderr)
        sys.exit("git {} failed".format(" ".join(args)))
    return proc.stdout


def procedure_name(path):
    with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
        match = PROCEDURE_NAME_RE.search(f.read())
    if match:
        return match.group(1).strip("`")
    return os.path.splitext(os.path.basename(path))[0]


def release_references(procedure_path):
    """Feature folders whose release_script.sql sources the procedure file."""
    target = procedure_path.lower()
    features = []
    for driver in sorted(glob.glob(os.path.join(WORKDIR, FEATURE_DIR, "*", "release_script.sql"))):
        with open(driver, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                ref = line.strip().replace("\\", "/").lower()
                if ref.startswith("source "):
                    ref = ref[len("source "):].strip().strip("'\"").lstrip("./")
                    if ref == target:
                        features.append(os.path.basename(os.path.dirname(driver)))
                        break
    return features


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("BASE_SHA")
    head = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("HEAD_SHA")
    if not base or not head:
        sys.exit("ERROR: base and head SHAs are required")

    ensure_work_dir()
    changed_all = [l.strip() for l in git("diff", "--name-only", base, head).splitlines() if l.strip()]
    changed_features = sorted(
        {p.split("/")[1] for p in changed_all if p.startswith(FEATURE_DIR + "/") and p.count("/") >= 2}
    )

    status_lines = git("diff", "--name-status", "--no-renames", base, head, "--", PROCEDURE_DIR + "/")
    entries = []
    patch_parts = []
    for line in status_lines.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status, path = parts[0].strip(), parts[-1].strip()
        if not path.lower().endswith(".sql"):
            continue
        if status.startswith("D"):
            print("Skipping deleted procedure: {}".format(path))
            continue
        abs_path = os.path.join(WORKDIR, path)
        if not os.path.exists(abs_path):
            print("Skipping missing procedure file: {}".format(path))
            continue

        diff = git("diff", base, head, "--", path)
        patch_parts.append(diff)

        owners = release_references(path)
        features = [f for f in owners if f in changed_features] or owners or changed_features
        if not features:
            print("WARNING: no feature folder references {}; skipping".format(path))
            continue

        entries.append(
            {
                "procedure": procedure_name(abs_path),
                "path": path,
                "status": "added" if status.startswith("A") else "modified",
                "diff": diff,
                "features": features,
            }
        )

    patch_file = os.path.join(WORK_DIR, "procedure_diff.patch")
    with open(patch_file, "w", encoding="utf-8") as f:
        f.write("\n".join(patch_parts))
    write_json(CHANGES_FILE, entries)

    print("=== Changed procedures ===")
    for e in entries:
        print("{} ({}) -> {}".format(e["path"], e["status"], ", ".join(e["features"])))
    print("Procedure diff saved to {}".format(rel_path(patch_file)))
    set_github_output("has_procedures", "true" if entries else "false")


if __name__ == "__main__":
    main()
