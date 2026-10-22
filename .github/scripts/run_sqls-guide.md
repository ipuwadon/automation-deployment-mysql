# `run_sqls.py` Guide

This guide explains [`run_sqls.py`](./run_sqls.py) in execution order. The line
numbers refer to the current version of the script.

## Purpose

The script is the SQL deployment engine used by the pull-request workflow. It:

1. Reads repository paths changed by the pull request.
2. Finds changed `backout_script.sql` and `release_script.sql` driver files.
3. Resolves the SQL files included by those drivers.
4. Builds an inventory of database objects owned by the release.
5. Rejects destructive SQL outside that inventory.
6. Executes backout SQL first.
7. Executes release SQL only when every backout succeeds.
8. Returns the MySQL exit code to GitHub Actions.

The script is intentionally fail-fast. The first invalid path, blocked SQL
statement, unreadable file, or MySQL error stops the deployment.

## Inputs and outputs

### Required environment variables

| Variable | Meaning |
|---|---|
| `GITHUB_WORKSPACE` | Repository checkout directory. If absent, the current working directory is used. |
| `DB_HOST` | MySQL server hostname or address. |
| `DB_USER` | MySQL deployment account. |
| `DB_PASS` | MySQL deployment account password. An empty string is accepted, but a missing variable is not. |
| `DB_NAME` | Target database and the only permitted schema qualifier in guarded SQL. |

### Required generated file

`changed_files.txt` must exist at the repository root. The workflow creates it
with one repository-relative changed path per line.

### Exit codes

| Exit code | Meaning |
|---|---|
| `0` | Nothing needed to run, or every selected SQL file succeeded. |
| Nonzero | Configuration, path resolution, safety validation, file reading, or MySQL execution failed. |

## High-level flow

```text
changed_files.txt
        |
        v
find changed backout and release drivers
        |
        v
scan release SQL and build allowed-object inventory
        |
        v
run all backout drivers and their included SQL
        |
        +---- failure ----> stop and return nonzero
        |
        v
run all release drivers and their included SQL
        |
        +---- failure ----> stop and return nonzero
        |
        v
return 0
```

## Line-by-line explanation

### Lines 1-8: interpreter and module documentation

- Line 1 selects Python 3 when the file is run as an executable on a platform
  that honors the shebang.
- Lines 2-8 describe the script's input file and required environment
  variables.

### Lines 10-13: imports

- `os` handles paths and environment variables.
- `re` implements the SQL statement recognizers.
- `subprocess` starts the MySQL command-line client.
- `sys` provides process exit handling.

Only Python standard-library modules are used, so the runner does not need to
install Python packages.

### Lines 15-22: runtime configuration

```python
WORKDIR = os.environ.get("GITHUB_WORKSPACE", os.getcwd())
```

`WORKDIR` is the security boundary for file access. Include paths that resolve
outside it are rejected.

Lines 16-19 read the four database settings. Lines 21-22 define the changed
file path and the two recognized driver filenames.

### Lines 24-29: dangerous-statement baseline

`DANGEROUS_SQL` recognizes destructive or administrative statements that
should be blocked by default:

- `DROP DATABASE`, `DROP SCHEMA`, and database-object drops
- `TRUNCATE TABLE`
- user creation, alteration, and deletion
- `GRANT` and `REVOKE`
- `DELETE FROM`
- suspicious `CALL ... xp_...`
- `KILL`, `FLUSH`, and `SHUTDOWN`

Later logic removes specifically approved object drops and row-clearing
statements from a temporary copy of the SQL. If any dangerous pattern remains,
the file is rejected.

### Lines 31-36: SQL object-name grammar

These constants construct reusable regular-expression fragments:

- `OBJECT_NAME` recognizes an unquoted name or a backtick-quoted name.
- `QUALIFIED_NAME` recognizes `object` or `schema.object`.
- `NAME_LIST` recognizes comma-separated qualified names.
- `QUALIFIED_NAME_RE` extracts names from a matched list.
- `NAME_TOKEN_RE` extracts schema and object tokens without backticks.

The grammar intentionally supports at most one schema qualifier.

### Lines 38-62: release object creation patterns

`CREATE_PATTERNS` maps an object kind to a recognizer:

- `table`
- `view`
- `procedure`
- `function`
- `trigger`
- `event`

The patterns support common MySQL variants such as:

- `IF NOT EXISTS`
- `CREATE OR REPLACE VIEW`
- `ALGORITHM=...`
- `DEFINER=...`
- `SQL SECURITY DEFINER|INVOKER`
- aggregate functions

Matches are used only to build the release-owned object inventory. They do not
validate complete MySQL syntax.

### Lines 64-72: release row-write patterns

`ROW_WRITE_PATTERNS` finds tables populated with:

- `INSERT ... INTO`
- `REPLACE ... INTO`

Supported modifiers include `LOW_PRIORITY`, `DELAYED`, `HIGH_PRIORITY`, and
`IGNORE` where MySQL permits them. A backout may delete or truncate these
release-populated tables.

### Lines 74-81: guarded backout patterns

- `DROP_OBJECT` recognizes drops for supported object kinds, optional
  `IF EXISTS`, and comma-separated object lists.
- `DELETE_FROM` recognizes single-table deletes and common modifiers.
- `TRUNCATE_TABLE` recognizes table truncation.
- `OBJECT_KINDS` contains all create kinds plus the special `rows` category.

### Lines 84-86: `die`

`die(message, code=1)` prints a fatal configuration message and exits
immediately.

### Lines 89-99: `is_safe_repo_path`

This function converts the repository root and candidate path to absolute paths
and compares them with `os.path.commonpath`.

It returns `False` when:

- the path is empty;
- the candidate is outside `WORKDIR`; or
- Windows reports incompatible path roots, such as different drives.

This check prevents driver includes such as `..\..\secret.sql` from escaping
the checked-out repository.

### Lines 102-103: environment validation

All database settings are required. `DB_PASS is not None` deliberately permits
an empty password while rejecting a missing `DB_PASS` variable.

### Lines 105-107: no changed-file input

If `changed_files.txt` is absent, the script prints that there is nothing to do
and exits successfully. This is different from an empty file: an empty file is
read normally and produces empty driver lists.

### Lines 109-112: changed-path loading

The script reads `changed_files.txt` as ASCII, ignores undecodable bytes,
strips whitespace, and removes blank lines.

### Lines 115-123: driver discovery

`find_drivers` performs a case-insensitive suffix comparison. A changed path is
a driver when it ends in `backout_script.sql` or `release_script.sql`.

The resulting driver lists are printed to the workflow log.

### Lines 126-132: `clean_path`

This helper trims surrounding whitespace and removes one matching pair of
single or double quotes from an include path.

### Lines 135-153: `resolve_path`

The resolver:

1. Removes quotes and whitespace.
2. Rejects UNC/network paths beginning with `//` or `\\`.
3. Tries the path as written.
4. Tries it relative to `WORKDIR`.
5. Tries it relative to the driver directory.
6. Strips leading `.`, `/`, and `\` characters and tries it from `WORKDIR`.
7. Returns the first existing path that remains inside the repository.

If no safe existing path is found, it returns `None`.

### Lines 156-183: `parse_includes`

This function validates the driver path and reads its include lines. It
recognizes:

```text
source path/to/file.sql
./path/to/file.sql
.\path\to\file.sql
\.path/to/file.sql
@path/to/file.sql
```

It returns:

```python
(absolute_driver_path, include_strings)
```

The include strings are still unresolved at this stage. Comments and ordinary
SQL lines in the driver are ignored by the include parser.

### Lines 186-190: `remove_sql_comments`

For safety scanning, this helper removes:

- `--` line comments;
- `/* ... */` block comments; and
- `#` line comments.

Carriage returns are replaced with spaces. This is a regex-based preprocessing
step, not a SQL lexer, so comment-like text inside string literals can be
misinterpreted.

### Lines 193-194: `split_qualified_name`

This helper extracts unquoted token values from an object name. Examples:

| Input | Output |
|---|---|
| `orders` | `["orders"]` |
| `` `orders` `` | `["orders"]` |
| `` `dev`.`orders` `` | `["dev", "orders"]` |

### Lines 197-212: `resolve_object_name`

The function normalizes an object reference to a lowercase, unqualified name.

- A bare name is accepted.
- A qualified name is accepted only when its schema equals `DB_NAME`,
  case-insensitively.
- A foreign schema or malformed name returns `None`.

For example, with `DB_NAME=dev`:

| Input | Result |
|---|---|
| `orders` | `orders` |
| `dev.orders` | `orders` |
| `production.orders` | `None` |

This is what prevents a backout from using an approved object name against
another database.

### Lines 215-227: `driver_sql_files`

The function converts a driver into the SQL files that it represents:

- When includes exist, it returns all successfully resolved include files.
- When no includes exist, it returns the driver itself so a driver may contain
  executable SQL directly.
- An invalid driver produces an empty list.

### Lines 230-238: `companion_release_drivers`

For every changed backout driver, the function looks for a sibling
`release_script.sql`.

This matters when a pull request changes only backout SQL. The unchanged
companion release still defines which objects that backout is allowed to drop
or clear.

### Lines 241-272: `collect_released_objects`

This is the core ownership-inventory function:

1. Create an empty set for each object kind and for `rows`.
2. Expand every release driver into executable SQL files.
3. Deduplicate files by normalized absolute path.
4. Read each file after removing a UTF-8 byte-order mark when present.
5. Remove SQL comments.
6. Apply every `CREATE_PATTERNS` recognizer.
7. Normalize each matched object name and add it to the correct set.
8. Apply the `INSERT` and `REPLACE` patterns and add those table names to
   `rows`.
9. Add every created table to `rows`, because a release-owned table may also
   be cleared during backout.

The result has this shape:

```python
{
    "table": {"customer", "orders"},
    "view": {"customer_summary"},
    "procedure": {"refresh_summary"},
    "function": set(),
    "trigger": set(),
    "event": set(),
    "rows": {"customer", "orders"},
}
```

### Lines 275-277: `describe_allowed_objects`

This function produces a readable, sorted summary for the workflow log. Empty
categories are omitted. If every category is empty, it returns `"none"`.

### Lines 280-302: `find_disallowed_sql`

This function decides whether a SQL file contains a blocked statement.

#### Drop approval

For each recognized drop:

1. Read the object kind, such as `table` or `view`.
2. Normalize every object in the drop list.
3. Confirm that every name belongs to the corresponding release inventory set.
4. Replace the approved statement with a space in the temporary SQL text.

If even one name is unapproved, the entire drop stays in the text and is later
caught by `DANGEROUS_SQL`.

#### Row-change approval

For each recognized `DELETE FROM` or `TRUNCATE TABLE`, normalize the table and
confirm that it belongs to the `rows` inventory. Approved statements are
removed from the temporary text.

#### Final decision

After approved operations are removed, `DANGEROUS_SQL` searches what remains.
The function returns the first blocked statement fragment or `None`.

Examples:

| Release inventory | SQL | Result |
|---|---|---|
| table `orders` | `DROP TABLE IF EXISTS orders;` | Allowed |
| table `orders` | `DROP TABLE users;` | Blocked |
| tables `orders`, `customer` | `DROP TABLE orders, customer;` | Allowed |
| table `orders` | `DROP TABLE orders, mysql.user;` | Blocked |
| rows `orders` | `DELETE FROM orders;` | Allowed |
| rows `orders` | `TRUNCATE TABLE audit_log;` | Blocked |
| any inventory | `DROP DATABASE dev;` | Blocked |

### Lines 305-332: `run_sql_file`

The executor handles one SQL file:

1. Print the file path.
2. Reject a path outside the repository.
3. Read the file as UTF-8, accepting an optional byte-order mark.
4. Run the safety check.
5. Print the blocked fragment and return `1` if validation fails.
6. Build the MySQL command as an argument list.
7. Pass the SQL content to the client's standard input.
8. Capture and print MySQL standard output and standard error.
9. Return the MySQL client's exit code unchanged.

Each SQL file starts a separate MySQL client process and therefore a separate
database session. Session variables, temporary tables, transactions, and other
connection-local state do not carry from one included file to the next.

The command currently prints its argument list, including the password
argument. GitHub Actions normally masks registered secrets, but local logs must
still be handled carefully.

### Lines 335-337: build the allowed-object inventory

The script combines:

- changed release drivers; and
- companion release drivers found next to changed backout drivers.

It scans that combined list and prints the resulting inventory before any SQL
is executed.

### Lines 340-363: backout execution

Backout drivers always run first.

For each driver:

1. Parse the driver.
2. If it has no includes, execute the driver as SQL.
3. Otherwise, clean and resolve each include in listed order.
4. Stop immediately when a path cannot be resolved.
5. Stop immediately when MySQL or safety validation returns nonzero.

The script does not reorder SQL dependencies. The driver author must list
views/routines before dependent tables, child tables before parent tables, and
child-row deletes before parent-row deletes.

### Lines 366-389: release execution

Release processing begins only when `overall_rc` is still `0`, meaning every
backout succeeded.

The release loop uses the same parsing, path validation, safety check, ordered
execution, and fail-fast behavior as the backout loop.

Files under a feature's `test/` directory have no special behavior. They run
only when a release driver explicitly includes them, and a query that returns
zero rows is still a successful MySQL command unless the SQL explicitly raises
an error.

### Lines 392-393: final result

The script prints the final exit code and exits with that value. GitHub Actions
marks the step failed when the value is nonzero.

## Example using Bicycle Online

Given:

```text
feature/Bicycle-Online/backout_script.sql
feature/Bicycle-Online/release_script.sql
```

the execution is:

1. Discover both changed drivers.
2. Scan release includes and inventory:
   - tables: `customer`, `products`, `orders`, `order_details`
   - view: `external_customer_products`
   - procedure: `customer_product_summary`
   - row-owned tables: the four created/populated tables
3. Approve backout drops only for those objects.
4. Execute the backout includes in driver order.
5. Execute the release includes in driver order.
6. Return the first failure, or `0` after all files succeed.

## Important limitations

1. The safety checks use regular expressions, not a complete MySQL parser.
2. SQL comments are removed without understanding string literals.
3. Object creation hidden inside dynamic SQL is not added to the inventory.
4. Nested include statements are not recursively inventoried by the Python
   parser.
5. Included files run in independent MySQL sessions.
6. Test queries do not assert their expected values automatically.
7. The script cannot overcome MySQL privileges or `DEFINER` rules. A deployment
   account cannot drop an object owned by a `SYSTEM_USER` definer merely because
   the Python safety check approves it.
8. Anyone who can modify both release and backout SQL can influence the
   allowed-object inventory. Repository permissions and pull-request review
   remain essential controls.

## Troubleshooting

### `Included file not found`

Confirm the path is repository-relative, exists with the same spelling, and
does not leave the repository.

### `Refusing to run SQL containing unsafe statements`

Read the `Blocked statement` line. Confirm the target object is created or
populated by the companion release SQL and uses the same object kind and
database.

### `ERROR 1227 ... SYSTEM_USER`

The Python guard approved the SQL, but MySQL rejected it. Check the object's
`DEFINER`. Recreate development objects using the deployment account rather
than a privileged root account.

### Foreign-key failure during backout

Put child-table drops/deletes before parent-table drops/deletes.

### Release does not run

Look for an earlier backout, include-resolution, or safety failure. Release
processing is intentionally skipped whenever backout processing is nonzero.
