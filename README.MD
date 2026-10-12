# MySQL Automation Deployment

This repository contains SQL files and GitHub Actions workflows for deploying MySQL changes to a development database. Deployments run from a Windows self-hosted GitHub Actions runner that has network access to the database.

## Current workflows

| Workflow | Trigger | What it does |
|---|---|---|
| [PR to DEV](.github/workflows/pr-to-dev.yaml) | A pull request targeting `dev` is opened, updated, reopened, or marked ready for review | Finds changed `backout_script.sql` and `release_script.sql` drivers, runs backout SQL first, then release SQL |
| [Deploy](.github/workflows/deploy.yaml) | A push to `main` | Runs `scripts/schema.sql`, then `scripts/migrations.sql` |

The PR workflow runs **before the pull request is merged**. It only runs for non-draft pull requests from branches in this same repository; forked pull requests are skipped. It checks out the PR head commit and uses the self-hosted runner. Python and the MySQL command-line client (`mysql`) must already be installed and available to the runner account.

The `main` workflow is separate from the PR-to-DEV workflow. It currently runs the schema and migration scripts on `main`; it does not use the PR driver-file discovery flow.

## Repository layout

```text
.
├── .github/
│   ├── scripts/
│   │   └── run_sqls.py
│   └── workflows/
│       ├── deploy.yaml
│       └── pr-to-dev.yaml
├── events/
├── feature/
│   └── Test-PR-Dev/
│       ├── backout_script.sql
│       ├── release_script.sql
│       ├── rollback/
│       └── test/
├── indexes/
├── procedures/
├── scripts/
│   ├── migrations.sql
│   └── schema.sql
├── tables/
├── triggers/
└── views/
```

The `events`, `indexes`, `procedures`, `tables`, `triggers`, and `views` folders are locations for database object SQL. `feature/<change>/` holds feature-specific deployment drivers and related rollback or test SQL.

## Pull request deployment

### Driver files

The PR workflow calculates the changed paths between the PR base and head commits. The runner looks for changed files whose names end with:

- `backout_script.sql`
- `release_script.sql`

SQL statements are not deployed just because a `.sql` file changed; the changed PR must include one or both driver files for the runner to discover them.

Drivers list SQL files to run. The current project uses MySQL `source` statements:

```sql
-- feature/my-change/release_script.sql
source tables/my_table.sql
source feature/my-change/test/my_table.sql
```

The runner also recognizes `source <path>`, `./<path>`, `.\<path>`, `\.<path>`, and `@<path>` include lines. Included files must resolve to files inside the checked-out repository.

### Execution order

For each changed backout driver, the runner executes its included SQL files (or the driver itself if it has no includes). Only if all backout drivers succeed does it execute the changed release drivers. It does not automatically execute the feature `test/` SQL as a separate test phase; a test file runs only if a driver includes it.

**Important:** because backout runs before release, review the backout SQL carefully. It may alter or remove existing DEV objects before the release runs. The runner blocks several destructive statements, but permits `DROP TABLE IF EXISTS <table>` in a backout only when a matching `CREATE TABLE <table>` is found in the changed release driver's SQL. This is a narrow guard, not a complete SQL security parser or a substitute for review. Use a disposable development database while validating new deployment flows.

## Database credentials and runner setup

Configure these GitHub Actions repository secrets:

| Secret | Used for |
|---|---|
| `DB_HOST` | MySQL server host |
| `DB_USER` | Deployment account |
| `DB_PASS` | Deployment account password |
| `DB_NAME` | Database name required by the PR SQL runner |

Do not put real credentials in SQL files, workflow files, or this README. Grant the deployment account only the permissions required for the target environment. Anyone able to run a qualifying same-repository PR workflow may cause the runner to execute SQL with the configured credentials, so protect write access to the repository and review PRs before allowing this workflow to run.

The self-hosted runner must:

1. Run on a Windows machine with access to the target MySQL server.
2. Have Python 3 available as `py -3` or `python` to the runner service account.
3. Have the MySQL client (`mysql`) on `PATH`.
4. Be configured in GitHub to accept jobs for this repository.

The PR workflow deliberately uses the runner's installed Python rather than `actions/setup-python`; this avoids setup-python's symbolic-link privilege issue on this runner.

## Main-branch schema deployment

The `Deploy` workflow invokes:

```text
scripts/schema.sql
scripts/migrations.sql
```

in that order using the `DB_HOST`, `DB_USER`, and `DB_PASS` repository secrets. The scripts currently contain `USE dev;` in `migrations.sql`, but `schema.sql` does not select a database, and the workflow's MySQL commands do not pass a database name. Confirm the intended default database or add an explicit database selection before relying on this workflow.

## Working with the repository

1. Create a feature branch from the appropriate base branch.
2. Add or update SQL under the relevant object or feature folder.
3. Add/update the feature's `release_script.sql` and `backout_script.sql` drivers as appropriate.
4. Check that each driver includes the intended SQL files using repository-relative paths.
5. Open a pull request targeting `dev` and review the Actions run and SQL changes.
6. Merge only after the deployment result and database state have been verified.

Example:

```text
feature/add-example-table/
├── backout_script.sql
├── release_script.sql
├── rollback/
│   └── example_table.sql
└── test/
    └── example_table.sql
```

Keep rollback and test SQL clearly separated. Test SQL is not automatically invoked unless it is included by a driver.

## Limitations and follow-up

- The PR workflow executes against the configured database before merge; there is no separate approval/environment gate in the workflow currently.
- SQL safety checks are pattern-based and do not parse all MySQL syntax or guarantee that a script is safe.
- The workflow only discovers changed driver files; changing an included SQL file without changing its driver may not trigger execution.
- The main-branch workflow's database selection should be made explicit.
- Deployment history, automated test assertions, and UAT/production workflows are not currently implemented.
