# Delta Observatory database

This repository is one component of [Delta Observatory](https://github.com/delta-observatory/delta-observatory). The entry repository describes the application and restores every component.

This repository owns the PostgreSQL schema, migrations, constraints, and record semantics.
It also owns the [cross-component contracts](contracts/README.md) for jobs, results, method parameters, and records.
The current scope is the TESS vertical slice: one index method and one transit-search method.
The research records for agent work are candidates, assessments, decisions, notes, and agent tasks.

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
| `observation` | One distinct file content. A changed file at the same path gets a new row, and the earlier row becomes `missing`. `provenance` names the selection manifest, owner, source identifier, and registration of a selected file. |
| `run` | An immutable method version, parameter set, and input selection. `retry_of` names the earlier run that a retry run repeats. |
| `run_input` | The observations that a run reads. |
| `job` | One unit of execution. The table is also the work queue. `document` holds a `job/1` document and `result` holds a `result/1` document. |
| `measurement` | One calculated quantity with unit, uncertainty or the reason it is unavailable, and quality flags. |
| `artifact` | One stored file, relative to the artifact storage root, with size and SHA-256. |
| `client` | One API client: a person, an agent, or a service. It has a name, a kind, permissions, and the SHA-256 of its bearer token. A disabled client cannot authenticate. |
| `campaign` | A research campaign: question, blinding level, budgets, the checksum of the approved campaign file, and the approval, decisions-fixed, reveal, and close events. |
| `campaign_read` | One row for each distinct observation whose data a campaign read. The observation budget counts these rows. |
| `access_event` | A read or a refused read of an observation that a cohort reservation protects, with client, campaign, reservation, and operation. |
| `candidate` | A possible object or event: kind, tier (`platform` or `lab`), summary, optional label, campaign, and writer. It holds no measured values and no status. |
| `candidate_observation` | The observations of a candidate. |
| `assessment` | One status of a candidate on one axis, with basis, method or decision, reason, quality flags, and the corrected assessment. |
| `decision` | One advisory judgment about a candidate. It has the question, judge, model, packet checksum, policy, judged evidence status, recommended action, reason, response, and scores. It also has the values that blinding withheld from the writer. |
| `note` | Free text about one or more records. |
| `agent_task` | A unit of agent work in a campaign, with state, priority, lease, attempts, and its end. The table is also the queue of agent work. |
| `record_link` | One reference from a candidate, assessment, decision, note, or agent task to a platform record or an external file. |

`run.client_id` records the client that created a run. `job.cancelled_by` records the client that cancelled a job.
The permissions are `read`, `run.submit`, `record.write`, `acquire`, `identity.reveal`, and `admin`.
A check constraint prevents an agent from holding `acquire`, `identity.reveal`, or `admin`.
An agent client belongs to one campaign (`client.campaign_id`). A run of an agent records its campaign (`run.campaign_id`).
Blinding levels are `open`, `labels`, and `labels_identity`. The default is `labels_identity`.
Check constraints keep the event order: approval, then decisions fixed, then reveal. Approval needs the campaign file checksum. A reveal needs a reason.

### Research records

[contracts/records/](contracts/README.md#research-records) defines the documents that clients and workers write.
Candidates, assessments, decisions, notes, links, and the observations of a candidate do not change after the insert.
A correction is a new record. An assessment or a decision can name the record that it corrects in `supersedes`.
A candidate, assessment, decision, or note can have an `import_key`. A unique index refuses a second record with the same key.

| Axis | Statuses | Basis |
|---|---|---|
| `evidence` | `unreviewed`, `supported`, `ambiguous`, `rejected` | `method`, `review`, or `model_judgment` |
| `identity` | `unchecked`, `matched`, `unmatched`, `ambiguous` | `method` or `review` |

The view `candidate_status` applies rule `candidate-status/1`. The newest assessment on each axis gives the current status.
Without an assessment, the evidence status is `unreviewed` and the identity status is `unchecked`.
A decision holds a judgment. It does not change a status. An assessment with basis `model_judgment` cites its decision.
A decision with judge `model` names its model or gives the reason that the model is unknown.
The packet checksum and the policy follow the same rule: a value or a reason.

`record_link` holds one foreign key for each kind of target, so each platform reference exists.
An external file needs its URI, SHA-256, and size.
The writer inserts each link in the transaction that inserts its record. For an agent task, that is the transaction that changes the task.
A record of a campaign refers only to records of the same campaign or to records without a campaign.

Triggers keep the campaign rules for every writer:

| Campaign state | Candidates, evidence assessments, decisions | Identity assessments | Agent tasks |
|---|---|---|---|
| Not approved | Refused | Refused (no candidate exists) | Accepted, not claimable by agents |
| Approved | Accepted | Accepted | Accepted |
| Decisions fixed | Refused | Accepted | Accepted |
| Closed | Refused | Refused | Refused. The close cancels queued and claimed tasks. |

Each trigger error has its own SQLSTATE:

- `RC001`: the campaign state refuses the write.
- `RC002`: the record does not change after the insert.
- `RC003`: a reference or a link is not consistent with its record.

Clients claim agent tasks with `SELECT … FOR UPDATE SKIP LOCKED`, as workers claim jobs.
Each claim increments `attempts` and sets a new `lease_id`. Only `claimed_by` with the current `lease_id` can extend, release, or end the lease.
A claim also takes a claimed task whose lease expired, while attempts remain. A task whose last lease expired becomes `failed` at the next claim in its campaign.
A finished task does not change. The campaign, writer, and work description of a task do not change.

### Jobs

Workers claim queued jobs with `SELECT … FOR UPDATE SKIP LOCKED` and hold a lease while they execute.
A worker that stops without a result leaves an expired lease, and another worker can claim the job again.
An insert of a queued job sends `NOTIFY delta_jobs` with the job ID.
A job in a finished state (`complete`, `inconclusive`, `failed`, or `cancelled`) does not change. A trigger refuses the update with `RC002`.

The API can cancel a queued job or a running job. It sets the state `cancelled`.
The worker that holds a running job loses the lease at its next lease extension, at most one third of the lease length later.
The worker then stops the method process and discards the output of the attempt.
The files of that attempt stay on disk without artifact rows. The worker time of a cancelled job is not recorded.
A method does not resume partial work. A worker restart returns its running job to the queue, and the next attempt starts again.

A retry run repeats the `failed` and `cancelled` jobs of an earlier run in a new run.
A trigger requires the same method version, parameters, and campaign. It refuses another run with `RC003`.
The completed jobs of the earlier run stay, and the retry does not repeat them. Measurements are therefore not duplicated.
A unique index permits one job for each observation in a run.
A second unique index permits one waiting or running index job for each dataset.

## Checks

```bash
uv run -q --no-project --with jsonschema==4.25.1 python scripts/check_contracts.py
```

Apply migrations in the cluster with `kubernetes/scripts/migrate.sh <database-image-tag>`.

## License

The code is under the [MIT License](LICENSE).
