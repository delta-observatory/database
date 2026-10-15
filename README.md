# Delta Observatory database

This repository owns the PostgreSQL schema, migrations, constraints, and record semantics.
It also owns the [cross-component contracts](contracts/README.md) for jobs, results, method parameters, and records.
The current scope is the TESS vertical slice: one index method and one transit-search method.

## Contents

| Path | Content |
|---|---|
| `migrations/` | Numbered SQL migrations. A released migration file does not change. |
| `migrate.sh` | Applies each migration once, in its own transaction, under an advisory lock. |
| `Dockerfile` | Builds `localhost/delta-database:<tag>`, which runs `migrate.sh`. |
| `contracts/` | JSON Schemas and examples for data that crosses a component boundary. |
| `scripts/check_contracts.py` | Checks every schema, every example, and the method parameter defaults. |

## Records

| Table | Meaning |
|---|---|
| `dataset` | One dataset directory in `raw/`, with its index state and findings. |
| `observation` | One distinct file content. A changed file at the same path gets a new row, and the earlier row becomes `missing`. |
| `run` | An immutable method version, parameter set, and input selection. |
| `run_input` | The observations that a run reads. |
| `job` | One unit of execution. The table is also the work queue. `document` holds a `job/1` document and `result` holds a `result/1` document. |
| `measurement` | One calculated quantity with unit, uncertainty or the reason it is unavailable, and quality flags. |
| `artifact` | One stored file, relative to the artifact storage root, with size and SHA-256. |
| `client` | One API client: a person, an agent, or a service. It has a name, a kind, permissions, and the SHA-256 of its bearer token. A disabled client cannot authenticate. |

| `campaign` | A research campaign: question, blinding level, budgets, the checksum of the approved campaign file, and the approval, decisions-fixed, reveal, and close events. |
| `campaign_read` | One row for each distinct observation whose data a campaign read. The observation budget counts these rows. |
| `access_event` | A read or a refused read of an observation that a cohort reservation protects, with client, campaign, reservation, and operation. |

`run.client_id` records the client that created a run. `job.cancelled_by` records the client that cancelled a job.
The permissions are `read`, `run.submit`, `record.write`, `acquire`, `identity.reveal`, and `admin`.
A check constraint prevents an agent from holding `acquire`, `identity.reveal`, or `admin`.
An agent client belongs to one campaign (`client.campaign_id`). A run of an agent records its campaign (`run.campaign_id`).
Blinding levels are `open`, `labels`, and `labels_identity`. The default is `labels_identity`.
Check constraints keep the event order: approval, then decisions fixed, then reveal. Approval needs the campaign file checksum. A reveal needs a reason.

Workers claim queued jobs with `SELECT … FOR UPDATE SKIP LOCKED` and hold a lease while they execute.
A worker that stops without a result leaves an expired lease, and another worker can claim the job again.
An insert of a queued job sends `NOTIFY delta_jobs` with the job ID.
A unique index permits one job for each observation in a run.
A second unique index permits one waiting or running index job for each dataset.

## Checks

```bash
uv run -q --no-project --with jsonschema==4.25.1 python scripts/check_contracts.py
```

Apply migrations in the cluster with `kubernetes/scripts/migrate.sh <database-image-tag>`.
