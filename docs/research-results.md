# Graph visualization and Research Results · IEEE DG 2027

The original M1/M2/M3 implementation and prerequisite-processing formulas are unchanged. The added service describes saved model outputs and performs sensitivity analysis; it does not validate career recommendations or AI-assisted input assumptions.

## Skill Graph Explorer

- **Full / local graph**: local mode is the selected skill plus the union of directed ancestors and descendants within the chosen number of edges. It does not add unrelated siblings. The depth selector controls the neighborhood and transitive highlight depth.
- **Automatic layout**: Dagre lays out each weakly connected component. Components are packed into shelves for the available viewport aspect ratio. Automatic mode evaluates LR and TB arrangements and selects the better fit. Manual LR/TB, reset layout, zoom, node dragging and an expanded canvas remain available.
- **Labels**: compact full-graph cards prioritize skill names; local cards include category. Full graphs can be zoomed or expanded; local views reduce clutter. The implementation does not claim that all 71 labels are readable at every viewport size/zoom.
- **Selected path**: selected skill is the start; “Путь к” is the end. A shortest **directed** BFS path is highlighted in purple. Equal-length alternatives use sorted neighbor IDs. No reverse prerequisite edge is invented. A visible message reports no path within the current filtered/local graph.
- **SVG / PNG**: export the full visible subgraph, including current node positions and path styling. SVG is native vector XML with no HTML foreignObject. It records dataset/version hash, layout direction, neighborhood, depth, selected path and positions. PNG rasterizes that SVG, with a maximum dimension of 8192 pixels.

## Career Transition Explorer

Select **M1 / M2 / M3 immediately above the graph**, and all / Top-3 / Top-5 outgoing transitions. Lower model scores come first; exact score ties use lexical target ID. Node/edge click selects the target. Hover displays the calculated edge value; edge labels show rounded values, while API/CSV retain full precision.

The color range is computed for the current source and metric before Top-N filtering. It maps lower to higher **model deficit**, not factual difficulty. M1 is a skill count and has its own scale; M2/M3 use weighted normalized proficiency deficits.

**Compare M2/M3** uses the same source, union of displayed targets, node positions and joint color range. Top-N selection is independent for each model. Some union vertices therefore have no displayed edge in one panel. This preserves comparable geometry while making ranking changes visible.

The skill-gap subgraph reflects experiment exclusions, additions and verification scope. It does not mutate the versioned prerequisite graph. Career exports retain full batch provenance and visualization metric/filter/scale.

## Research Results workflow

1. Choose a dataset version in the global selector.
2. Set baseline source/target, weight source, verification scope, topological algorithm, τ and λ in Experiments. The complete batch uses every distinct directed profile pair, irrespective of the selected pair.
3. Open **Research Results**. Enter τ and λ lists, using commas between numbers and a decimal point, and choose ranking Top-3 or Top-5. At most 25 grid combinations are allowed.
4. Run the protocol or load a saved research run for that version. Every grid cell is an ordinary persisted batch using the unchanged research core.
5. Inspect maximum M3−M2 pairs, matrices, distribution, sensitivity and source-specific ranking changes. Controls changed after a run do not change saved results: a stale-results notice appears. “Открыть переход” restores the baseline parameters from that saved run before opening Career Explorer.
6. Export figure SVG/PNG, table CSV or full JSON. Export metadata always corresponds to the displayed saved run.

### Additional deficit

`extra = M3 − M2 = λ × prerequisite_burden`. Sort descending, breaking ties by source then target IDs. This is a model quantity; at λ=0 it is zero regardless of the unscaled prerequisite burden. The histogram gives exact zeros a separate bucket, then uses 8 equal-width positive bins; the final positive bin includes the maximum. Counts sum to the number of directed pairs.

### Directed heatmaps

Rows are source profiles, columns are target profiles. M1, M2, M3 and M3−M2 can be viewed separately; each has its own color range. The diagonal is excluded and shown as “—”, never imputed as zero. Missing off-diagonal pairs are also shown as unavailable rather than fabricated.

### Sensitivity

The grid varies **only** minimum prerequisite level τ and λ. Weights, version, scope, graph interventions and topological algorithm stay fixed. The baseline and every grid cell are persisted with resolved version, parameters, record/status hash, algorithm implementation and runtime. A research envelope stores an analysis-version identifier and references the baseline and cell run IDs. Sensitivity summaries include mean/max M3−M2, affected-pair count, mean M2/M3, mean defined Spearman and mean Top-K overlap.

### Ranking

Targets are ranked in ascending model distance. For Spearman, exact score ties receive average ranks. Spearman is Pearson correlation of those rank vectors; it is **undefined** when either vector is constant and is represented as null, not zero or one. A mean Spearman excludes undefined sources, and their count is reported. For deterministic Top-K membership, ties are resolved by target ID; overlap is `|TopK(M2) ∩ TopK(M3)| / K`, with K capped by available targets. Ranking shift is `rank(M2) − rank(M3)`.

These are descriptive sensitivity statistics, not hypothesis tests, external validation, estimates of learning time, or proof that M3 improves recommendations. Source/Expert verification metadata and all original scientific cautions remain intact.

## API / persistence

`POST /api/experiments/research`

```json
{
  "experiment": {
    "source_profile": "backend:junior",
    "target_profile": "fullstack:middle",
    "version_id": "<selected 64-character version hash>",
    "minimum_prerequisite_level": 1,
    "lambda": 0.5,
    "algorithm": "kahn",
    "weight_source": "skill_weights_by_role_final_v2.csv",
    "verification_scope": "all",
    "included_edges": [],
    "excluded_edges": []
  },
  "taus": [1, 2, 3],
  "lambdas": [0, 0.5, 1],
  "top_k": 3
}
```

The returned `baseline`, `max_extra`, `distribution`, `ranking`, `sensitivity`, `summary` and `provenance` are saved in the existing `experiment_runs` table with kind `research`. No migration is needed. Canonical sorted grids and an analysis-version identifier are part of the research run hash. `GET /api/runs/{run_id}` retrieves the exact saved payload. Model runtime and analysis runtime are recorded separately. Existing version/history APIs and M1/M2/M3 code remain unchanged.

## Exports

- Graph SVG contains native paths/text and complete metadata, including positions. PNG is generated from that vector image; visible footer captions retain dataset/run/hash and algorithm information.
- Chart SVG captures vector shapes, text and inline styles and reconstructs Recharts' HTML legend as vector text. Rank chart metadata and title identify the chosen source profile. Heatmaps are native SVG.
- CSV includes exact numeric values and repeated dataset/run/hash/full provenance columns. Histogram, sensitivity and ranking tables have their own CSV exports. M1 is labeled as skill count and is not plotted on the weighted-deficit scale.
- JSON retains the complete research envelope and all reported analyses. The existing source CSVs are never edited.

A baseline research envelope for the supplied version is archived in `reports/research-results-v1/run.json`. It is a computational artifact on mostly AI-assisted Unverified inputs, not empirical evidence.
