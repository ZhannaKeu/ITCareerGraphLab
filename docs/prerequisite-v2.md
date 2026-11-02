# Prerequisite V2: compatibility and controlled relation-type protocol

This is an AI-assisted preliminary classification, not an expert or source review. It is an independent immutable overlay on the 51 original prerequisite data rows. Numbering is **one-based, excluding the header**. `datasets/prerequisite_relations_v2.json` pins the exact source-byte SHA-256, row number, endpoints, type, null min_level and Unverified status. The packaged backend copy is identical. Migration 0004 adds overlay storage; the user's next ordinary import initializes it idempotently. No CSV, canonical source record, historical verification, version ID or existing record/status hash is rewritten.

Required: 15,16,17,18,19,21,22,24,27,28,29,30,31,45 (14).
Related: 14 (1). Recommended: the remaining 36.

Every classification has `classification_source = AI-assisted preliminary review`, `verification_status = Unverified`, `min_level = null`. These fields describe **classification trust**, separately from any previous review of the original relationship. Existing expert/source statuses are not inherited into the taxonomy.

## Parameter semantics and backward compatibility

M1/M2/M3 formulas are unchanged. No per-edge threshold is inferred. **τ remains the existing explicit global scenario threshold**, and λ scales the separate additional burden as before. Null edge min_level never becomes zero or an asserted threshold. A future per-edge level algorithm requires its own protocol/implementation and compatibility tests; it is not introduced here.

A new optional `graph_configuration` selects G1, G2 or G3. When omitted/null, it is omitted from canonical stored parameters so historical legacy run IDs and cached results remain valid. Named-graph runs additionally bind complete graph configuration, classification hash and included edge IDs. No old experiment is relabeled or overwritten.

- G1 Original: all 51 pinned edges, including Related, solely as the historical baseline.
- G2 Strict: only 14 Required edges.
- G3 Extended: 14 Required + 36 Recommended = 50 edges.

All three retain every skill vertex, including isolated ones. Each configuration hashes dataset version, canonical data/status hash, classification protocol/hash, node IDs, included stable edge IDs, relation metadata and null-level policy. All three are formed from **one selected immutable snapshot**. Pair-based SHA-256 edge IDs remain stable across G1/G2/G3.

The controlled protocol requires the snapshot's edge population to equal the pinned 51 source relationships. Requirements-only corrected snapshots are supported. If a corrected version adds/deletes an edge, named configurations are rejected explicitly until a new classification protocol is supplied; legacy exploration/calculations still work. Deleted edges are never silently restored and added edges are never silently dropped or guessed as Required.

Named configurations reject additional include/exclude overrides (which would invalidate their definitions) and require `verification_scope=all` because this taxonomy is preliminary. Legacy overrides and verified-only workflows remain available unchanged. Visual relation-type filtering is a display filter, recorded separately from the fixed computational configuration.

## Comparison design

`POST /api/experiments/relation-impact` takes the same experiment parameters and τ/λ grid as Research Results. It runs all three named graphs with identical profiles, target-role weight source, τ, λ and topological algorithm on the selected version. A directed population of exactly 14×13=182 is required. M1 and **M2 are asserted identical for every pair**, at baseline and every sensitivity cell; an inconsistency blocks the comparison.

Unscaled prerequisite burden B and λB=M3−M2 are reported separately. `prerequisite_deficit_pairs` counts B>0 even if λ=0. `weighted_extra_pairs` counts M3−M2>0, which is zero at λ=0. Means/maxima are reported for both quantities. Signed M3 changes use right−left; a reduction is not an improvement claim.

Rankings are ascending costs; exact ties get average ranks for Spearman and pairwise tie handling for **Kendall τ-b**. A constant-vector correlation/zero τ-b denominator is null, never fabricated as zero or one. Top-3/Top-5 use lexical target ID for deterministic boundary ties. Both membership changes and order changes are recorded. Comparisons include G1/G2, G1/G3, G2/G3 and each M3 graph against the common M2 ranking. Sensitivity varies only τ and λ and records per-scenario summaries, ranking comparisons and individual persisted batch IDs.

The `relation_impact` envelope in existing experiment_runs stores complete baseline G1/G2/G3 runs, configuration hashes/edge IDs, common M2 values, 182 joined transition records, distributions, ranking metrics and sensitivity cells. Its hash binds version, classification/configuration hashes, parameters and analysis version. The original scientific cautions and provenance remain attached.

Results measure sensitivity to an **unverified taxonomy**, not factual career transition difficulty or quality/efficacy of recommendations.

## UI and exports

- **Skill Graph Explorer:** choose G1/G2/G3 or Legacy, then optionally filter Required/Recommended/Related as a *visual* filter. Required is blue/solid, Recommended teal/dashed, Related gray/dotted. The purple selected path overrides color for emphasis; the inspector retains the actual type. Local/full modes, depth, layout, path selection, drag and export remain available. All 71 source skills are retained in a full configuration; local/category filters have their own visible counts.
- Click an edge or choose its original data-row entry in “Инспектор связи”. Type, classification source, class Unverified status, null min_level, source data-row number and stable ID are displayed. The original relationship's verification status is shown separately. Clicking a skill returns to the skill inspector.
- **Research Experiments:** graph selection applies to pair/batch calculations and exports. Named configs disable arbitrary include/exclude edits; switching back to Legacy restores that workflow. Verified-only scope is not silently replaced by all: the user must choose the preliminary all-record protocol explicitly.
- **Research Results:** a separate relation-impact workspace runs/loads the controlled experiment. It displays 3-row summaries, all 182 joined transitions, common-scale directed heatmaps, common-bin distributions, pairwise/M2-baseline ranks and sensitivity curves/tables.
- JSON contains the complete comparison. CSV tables, SVG metadata and visible figure captions retain version, data hash, classification hash, graph hashes, edge IDs and algorithm parameters. Individual batch CSV adds the full selected graph configuration. Graph exports preserve a vector type legend and visual relation filter separately from the fixed computational configuration.

### Request

```json
{
  "experiment": {
    "source_profile": "backend:junior",
    "target_profile": "fullstack:middle",
    "version_id": "<chosen 64-character dataset version>",
    "minimum_prerequisite_level": 1,
    "lambda": 0.5,
    "algorithm": "kahn",
    "weight_source": "skill_weights_by_role_final_v2.csv",
    "verification_scope": "all",
    "included_edges": [],
    "excluded_edges": []
  },
  "taus": [1, 2, 3],
  "lambdas": [0, 0.5, 1]
}
```

This new endpoint always evaluates **both** Top-3 and Top-5; it has no `top_k` parameter. The existing Research Results endpoint retains its original `top_k` semantics. A selected graph in the ordinary controls is not submitted in this controlled request: the new endpoint itself selects all G1/G2/G3. Other baseline parameters are retained exactly. Additional edge interventions or a verified-only scope reject the request rather than silently changing the study design.

`GET /api/graph-configurations?version_id=...` reports eligibility and the three fixed configurations. `GET /api/skills/graph?version_id=...&configuration=G2` returns typed edges and configuration metadata. As before, `GET /api/runs/{run_id}` restores the exact saved payload. The sensitivity grid is capped at 25 τ×λ combinations (up to 75 graph-specific batch runs).

## Launch policy for this change

The application was **not started** during this implementation: no Docker Compose, FastAPI/Vite servers, browser automation or network HTTP checks. Verification uses isolated SQLite/ASGI-in-process tests, frontend DOM/unit tests, build and offline SQL rendering. The PostgreSQL extension, live upgrade, live API and browser downloads require the user's manual check after launch.
