# Architecture

```text
React / Vite / TypeScript / Tailwind
  TanStack Query       React Flow        Recharts / Motion
         │                  │                   │
         └────────────── FastAPI ────────────────┘
                           │
                  application services
                 /                     \
       immutable snapshots         CSV validation/import CLI
              │                           │
       pure research core           SQLAlchemy 2 / Alembic
       M1 / M2 / M3 / DAG                 │
              └────────────── PostgreSQL 16 + pgvector
```

`backend/app/research/` has pure functions and no database/API dependency. `services/` loads a versioned snapshot, interprets observed CSV contracts, applies graph interventions and orchestrates runs. `api/` holds validated Pydantic requests. `models.py` normalizes skill/group membership, survey mappings, level dictionary, role-grade profiles, requirements, independent weight sources, prerequisites, transitive counts and course contributions. Composite foreign keys always include version_id. `source_records` keeps all logical original rows; dataset versions contain byte hashes and validation reports. `active_dataset` is a pointer: switching it does not delete past versions.

Alembic revisions are standalone and do not import mutable application models. The first migration creates the pgvector extension; the second reflects the observed source schemas. No embedding column or fabricated vector is needed in MVP. Future embedding tables should be added with a separate migration once an embedding model and dimensionality are selected.

`frontend/src/pages/` separates dashboard, graph explorer, career comparison, experiments and audit. API-derived queries are keyed by dataset version and parameters. Failed API requests show visible error states. The browser has no synthetic-data fallback. Batch tables and CSV use the parameters of the saved batch, with a warning when controls have since changed. Graph editing in experiments changes the experiment copy only.

Docker Compose starts database → migration/idempotent import init job → API → nginx frontend. `datasets` is mounted read-only and PostgreSQL data lives in a named volume. Environment values configure DB, dataset path and CORS. The local app requires no Sites hosting service and does not publish datasets remotely.

`extensions/contracts.py` reserves interfaces for embedding, document extraction and LLM adapters. Optional Python `nlp` dependencies include sentence-transformers, an LLM API client, pdfplumber and python-docx. They are not installed in the default runtime, loaded at import time, or exposed as unfinished MVP features.


## Provenance and immutable revisions (migration 0003)

`dataset_lineage` records original/corrected kind, parent, root source version, author/reason, owner declarations and the hash of canonical records plus status/evidence. `record_provenance` is keyed by version, entity type and stable natural key. It separates declared source/method from verification status and retains original file/row references. All imported rows are Unverified; no CSV source label upgrades trust.

`change_events` stores ordered before/after data and provenance, author, reason and timestamp for each revision, including derived count recalculation. Curation APIs only create new full snapshots. They do not mutate/delete previous snapshots or activate a revision globally. Composite FKs and DAG validation apply to edited snapshots. Status upgrades require explicit reviewer/evidence, and value edits reset verification. The statuses reflect manual attestations; there is no credential authority or external source verification service.

`experiment_runs` persists exact pair/batch payloads. The run hash binds resolved dataset, record/status content hash, parameters, implementation and kind. A version comparison runs the same experiment on two snapshots and returns both run IDs and signed deltas. Original raw CSV data remains an independent audit layer even when a corrected graph has different derived counts. A global version picker controls graph/statistics/experiments; the new curation page separates original rows, corrections, reviews and history.
