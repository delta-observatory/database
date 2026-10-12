# Cross-component contracts

This directory holds the reference definitions for data that crosses a component boundary.
The API, workers, and database migrations use these definitions.
No schema files exist yet. G03 and R1 supply the first versions.

## Runtime boundary

The API is stateless.
It keeps no job, run, campaign, or session state in process memory.
Any API replica can serve any request.

The API and workers do not call each other.
They exchange data only through PostgreSQL records and file storage references.
The API remains available when no worker runs.
Workers continue queued work when the API is unavailable.

The contracts in this directory are the only coupling between the API and workers.

## Contracts

| Contract | Producer | Consumer | Content |
|---|---|---|---|
| Job | API | Workers | Contract version, run, method and method version, parameters with units, input references, and resource limits. |
| Result | Workers | API | Contract version, producing job, measurements with units and uncertainty, artifact references, quality flags, and outcome. |
| Method parameters | This directory | API and workers | Parameter names, units, types, allowed ranges, and defaults for each method version. |
| Records | Database migrations | API and workers | Tables, columns, constraints, and states. |

Method parameter schemas live here so that the API can validate requests without a running worker.
The backend owns the HTTP interface between the backend and frontend. That interface is not a contract in this directory.

## Planned layout

```text
contracts/
├── README.md
├── job/v1.schema.json
├── result/v1.schema.json
├── methods/<method-id>/v1.schema.json
└── examples/
```

Schemas use JSON Schema, draft 2020-12.
Examples come from real G03 records for DECam and T01.
Each schema has at least one valid example and one invalid example.

## Versions

Each job and result document carries its contract name and major version, for example `job/1`.
A compatible change adds an optional field.
A rename, removal, type change, unit change, or meaning change requires a new major version.
A new major version is a new file. Do not edit a released schema file.

Workers declare the job versions that they support.
A worker rejects an unsupported job version before execution and records the failure.
The API submits only job versions that the deployed release set supports.
The `kubernetes/` manifests select compatible API, worker, and database releases.

A contract version and the database migrations that it needs release together in one tagged release of this repository.

## Consumers

The API and workers pin a release tag of this repository.
Each consumer copies or generates its models from the pinned schemas.
Generated models are build outputs. The schema files are the source.
Consumers do not import code from sibling repositories.
Each consumer tests its output documents against the pinned schemas and examples.

## Rules for agents

Define job, result, method-parameter, and record shapes only in this repository.
Do not write these shapes by hand in `backend/` or `workers/`.
Change the contract here first. Then update each consumer.
