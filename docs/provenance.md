# Provenance, verification and revision protocol

## Declared origins

The dataset owner stated that most data was AI-assisted and remains unverified. This statement is stored separately from original byte hashes in each version's disclosure.

| Input | Recorded origin | Initial status |
|---|---|---|
| Role skill weights | Python calculation in Google Colab | Unverified |
| Some ML-library weights | Sources discovered by AI; exact row-level citations not supplied | Unverified |
| Curriculum discipline IDs/names | Copied from a real curriculum according to owner; original curriculum not checked | Unverified |
| Course-skill mappings | Preliminary AI-generated associations | Unverified |
| Junior/Middle requirements | Preliminary AI-generated requirements | Unverified |
| Prerequisite relationships | Preliminary AI-generated relationships | Unverified |
| Other records | Row-level origin not established | Unverified |

No source URL, expert name, Colab notebook ID, curriculum document identity or observation is fabricated. Original CSV `expert`, `survey`, `manual` labels are preserved as source assertions. A source declaration is not an attestation; successful import/DAG checks are not scientific verification.

## Record identity and source references

Natural keys are stable across snapshots: requirement `[profile_id, skill|group, item_id]`, edge `[prerequisite_id, skill_id]`, weight `[source_file, role, skill_id]`, course mapping `[course_id, skill_id]`, raw source row `[filename, row_number]`. Every canonical record has a separate provenance row with original version/file/row references, declared method, status and review evidence. Aggregated final-v2 weights reference all contributing survey-name rows, with the declared MAX aggregation rule.

Canonical rows, original source rows, verification metadata and edits are distinct layers. `/api/data/{filename}` always returns immutable original CSV rows and identifies their root version. `/api/versions/{version}/records` returns the selected canonical snapshot and per-record status. Reviewing a canonical mapping does not automatically mark its original source row reviewed, and reviewing one source row does not verify the corresponding derived record.

## Status rules

- **Unverified**: no recorded expert/source attestation.
- **Expert Verified**: explicit expert-assessment claim; named reviewer and assessment reference required.
- **Source Verified**: explicit source-check claim; named reviewer and source/reference required.

Source Verified and Expert Verified are distinct categories, not an ordered confidence scale. The app does not authenticate reviewer credentials or inspect reference documents. The local research team is responsible for entering truthful review metadata. A value edit resets its previous attestation unless a new review is explicitly supplied for that edit. A status-only review also creates a new version. Verification never implies that an entire dataset or recommendation system is validated.

## Copy-on-write curation

`POST /api/versions` accepts a parent snapshot and one or more operations. Requirements and prerequisite edges support upsert/delete; all record types support a status-only verify operation. Group requirements may be edited/reviewed but remain excluded from M1/M2/M3 until their semantics are resolved.

The service validates natural keys, referenced profiles/skills/groups, level scale, explicit unknown levels, reviewer/evidence, and acyclicity before writing. Duplicate operations on the same key in one request are rejected. No source snapshot or CSV is changed. The new version stores cloned canonical rows, inherited original source rows, fresh metadata and ordered audit events. Derived ancestor/descendant counts are recomputed for corrected graphs and remain Unverified; original CSV counts remain available as historical source data.

Revision IDs hash parent, record/status content, complete request and protocol. Identical revision requests are idempotent. The new version is selected in the current browser session; the global active pointer remains unchanged. To make a correction to an earlier branch, explicitly select that version before saving.

Example (substitute an actual parent hash):

```json
{
  "parent_id": "<64-character version ID>",
  "label": "SQL requirement reviewed",
  "author": "<actual change author>",
  "reason": "<actual reason>",
  "changes": [{
    "entity": "requirement",
    "key": ["fullstack:middle", "skill", "sql"],
    "operation": "upsert",
    "required_level": 4,
    "verification": {"status": "Unverified"}
  }]
}
```

This is a schema example, not a recommendation to change this requirement. To attest a review, supply the actual reviewer and evidence along with the chosen status. Missing evidence is rejected. `required_level: null` explicitly means unknown; omission on upsert is rejected.

## Experiments and comparisons

Pair/batch runs persist complete results and provenance to `experiment_runs`. The hash binds implementation 1.1.0, kind, resolved dataset, canonical record/status hash and all parameters, including scope and edge interventions. Runtime, original-byte hashes, lineage, status counts, assumptions and data-origin disclosures are recorded. `/api/runs` lists runs; `/api/runs/{id}` returns the exact saved JSON. A repeated identical request retrieves the saved payload, including its original runtime metadata.

`POST /api/experiments/versions` accepts `original_version`, `corrected_version`, `experiment` (without `version_id`) and `batch`. Both versions use identical parameters. Output contains both complete saved runs, per-pair before/after scores, signed deltas and changed-pair count. It can compare all 182 pairs. JSON export is available from the curation UI; each version's batch CSV also records provenance and statuses.

`verification_scope=all` explicitly permits unverified assumptions. `verified` filters requirements, edges and weights by status and refuses absent source/target requirement coverage or target weights rather than producing a misleading zero. Unreviewed simulated edge additions are rejected in that scope. A reviewed subset can be incomplete; unknown proficiency and missing individual weights still use the visibly stated conservative assumptions.

Scores and score deltas are outputs of the declared model on the chosen snapshots. They are not empirical learning time, factual transition difficulty, or evidence that an edit improves recommendation quality. External validation remains required for empirical claims.

## Upgrade and archives

Run `docker compose up -d --build`. Migration 0003 adds provenance/revision/run tables without altering old dataset IDs or original source rows. The idempotent import initializes the current original dataset's Unverified provenance envelope. For any other previously imported original dataset, rerun its import to initialize its envelope. The archived implementation-1.0 baseline files are retained as historical computation outputs predating the disclosure, not validated evidence. No new corrected/verified dataset is fabricated on startup.
