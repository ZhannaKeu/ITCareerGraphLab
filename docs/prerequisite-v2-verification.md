# V2 / G1-G2-G3 verification · 31 October 2026

## Execution boundary

The main application was not launched or contacted. No Docker Compose command, ASGI/Vite listening server, browser, browser automation, network HTTP check or production-database operation was executed. Existing running services, if any, were not inspected or modified.

Allowed checks used temporary SQLite databases, direct service calls and in-process isolated ASGI simulation with database dependency overrides. TestClient does not start uvicorn or bind a listening network port. The migration test runs Alembic against a temporary SQLite file; PostgreSQL DDL was generated offline with `--sql` and never executed against PostgreSQL.

## Results

| Check | Result |
|---|---|
| Backend isolated regression suite | **82 passed, 5 skipped** |
| Skipped tests | PostgreSQL integration tests; deliberately disabled with RUN_POSTGRES_TESTS=0 |
| Backend runtime available locally | Python 3.11; Python 3.12/PostgreSQL container runtime not launched under the user's restriction |
| Frontend Vitest/jsdom | **20 passed** |
| TypeScript / Vite production build | Successful |
| Alembic upgrade through 0004 + metadata comparison | Successful on temporary SQLite |
| PostgreSQL migration DDL | Generated statically, including classification FK/check constraints |
| Original CSVs | All 10 SHA-256 hashes match before implementation and the original audit |
| M1/M2/M3 and prerequisite kernel | `app/research/models.py` and `graph.py` byte hashes unchanged |
| Classification packaging | Dataset sidecar and packaged backend specification are byte-identical |

One existing Starlette/TestClient warning about a future httpx change remains; tests pass. No claim is made that live PostgreSQL, Python 3.12 container startup or browser rendering/downloads were checked during this task.

## Scientific and compatibility assertions

- Every one-based data row maps to the correct original endpoints. Required = 14 exact supplied row indices; Related = row 14; Recommended = remaining 36. Row 14 is html_css→javascript and row 15 is javascript→typescript, guarding against a header/off-by-one error.
- All 51 classifications have exact AI-assisted preliminary review provenance, Unverified status and null min_level. No source/canonical verification is upgraded. A separately reviewed original edge does not promote the taxonomy.
- G1/G2/G3 have 51/14/50 edges, 71 vertices, matching selected version IDs, stable included edge IDs, deterministic configuration hashes and no cycles. Required ⊂ Extended ⊂ Original by edge membership.
- G1 calculations equal the original legacy batch exactly. A fixture extracted from the archived pre-V2 batch proves unchanged historical run ID/parameters when graph_configuration is absent.
- All 182 unique directed pairs are compared. M1/M2 coincide exactly across the three graphs; the common M2 baseline also remains unchanged across the sensitivity grid. G1/G3/G2 M3 monotonicity follows the tested edge-subset scenario with nonnegative weights.
- Sensitivity cells pin the same version, graph IDs/hash, parameters and individual saved batch IDs. At λ=0 all M3=M2, but unscaled prerequisite deficit counts can remain positive; the two counts are reported separately.
- Histograms conserve all 182 pairs and use common boundaries across graphs. Pairwise rankings include all 14 source profiles, both Top-3/Top-5 and explicit tie semantics. Kendall τ-b tests cover concordance, reversal, asymmetric ties and undefined constants.
- Repeating the request retrieves the identical saved comparison. The complete comparison can be restored by run ID in the isolated database.
- Original data/history stays intact. Edge-population changes in a corrected version disable this fixed 51-edge protocol explicitly; legacy calculations still work without silently restoring a deleted edge.
- Additional overrides and verified-only claims are rejected for fixed preliminary graph configurations.
- Frontend tests cover configuration choice, relation filtering/counts, edge inspector, null-level/Unverified labels, return to skill inspection, local-mode preservation and pinned controlled-comparison requests. Existing graph/figure XML, legend, provenance, research and curation tests continue to pass.

## Commands used (no application server)

```bash
RUN_POSTGRES_TESTS=0 .venv/bin/python -m pytest backend/tests -q
npm test --prefix frontend
npm run build --prefix frontend
```

The isolated migration subprocess overrides DATABASE_URL to a temporary SQLite file. PostgreSQL offline rendering was done separately using `alembic upgrade head --sql`; it does not connect to a service.

## User launch and manual checks

From the repository root, the **user** runs:

```bash
docker compose up -d --build
```

Then open http://localhost:8080 manually and check:

1. Migration/init completes, source CSV import stays idempotent, V2 classification becomes available for the original 51-edge version. Existing history and saved legacy runs remain accessible.
2. Skill Explorer G1/G2/G3 counts are 71/51, 71/14 and 71/50. Verify colors/line styles/legend, Required/Recommended/Related display filters, local/full modes, depth/path and edge inspector fields. min_level must say unset; no automatic Expert/Source Verified status should appear.
3. Research Experiments switches graphs with fixed hashes; M2 is unchanged, M3 may differ. Named graphs reject extra overrides and verified-only scope. Use Legacy for the previous workflows.
4. Research Results → relation impact: run all 182 pairs with identical weights/τ/λ and inspect counts before/after λ, signed M3 differences, common-scale heatmaps, common-bin distributions, Top-3/5, Spearman/Kendall and sensitivity.
5. Save/load the comparison on the selected version; download CSV/JSON and SVG/PNG. Verify metadata, included edge IDs, legends, captions and browser rasterization. These native browser interactions remain manually unverified.
6. Select a requirements-only corrected version and verify its own configuration hashes; a version with added/deleted prerequisite edges must show an explicit eligibility warning, not reuse or repair the original graph silently.

The figures/results describe an Unverified AI-assisted classification; score or ranking changes are not evidence of improved recommendations.
