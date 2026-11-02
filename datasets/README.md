# Research CSVs

The application imports the ten original CSVs in this directory **read-only**. `docs/dataset-audit.json` records their SHA-256 checksums and full audit. No importer/generator edits originals.

| File | Observed schema | Semantics |
|---|---|---|
| skills.csv | skill_id,name,category,aliases,source | 71 canonical skills |
| skill_mapping.csv | survey_name,skill_id,action | 71 survey-name mappings; dropped rows may have empty skill_id |
| skill_groups.csv | group_id,group_name,skill_id | 41 memberships, 11 ANY groups |
| skill_levels.csv | level,name,description | Ordinal scale 0..4 |
| prerequisites.csv | from_skill,to_skill | 51 directed edges: prerequisite → dependent |
| skill_dependents.csv | skill_id,dependents,prerequisites | **Transitive counts**, not edges; verified against graph |
| role_skill_weights.csv | role,skill_id,weight,source | 202 role weights, kept separate |
| role_requirements.csv | role,grade,item_id,item_type,required,weight,weight_source | 204 requirements; 167 skills used, 37 groups excluded |
| course_skills.csv | course_id,skill_id,contribution,note | 48 relations; preserved, not used to infer proficiency |
| skill_weights_by_role_final_v2.csv | role,skill,raw_frequency,relative_weight,weight_0_1 | 232 survey-name weights; map explicitly, aggregate aliases with MAX |

UTF-8 CSV with optional BOM. Required schema and numeric ranges are checked; absent or inconsistent schemas fail rather than being guessed. Blank `required` is unknown and reported. Blank auxiliary `relative_weight` is retained with a warning when selected `weight_0_1` exists. `skill_levels.csv` must declare 0,1,2,3,4; grades must be junior/middle. Duplicate keys, contradictory mappings, dangling references, count mismatches and cycles block import atomically.

A repeated import of identical bytes/protocol is idempotent. A changed dataset creates a new immutable version; activate it explicitly with `--activate`. Previously imported data stays in the database.

The `demo/` files and `generate_demo.py` are early synthetic fixtures in a different schema, retained separately. They are **not used** by the application or accepted by the real-data importer. The generator only writes `demo/` and refuses to overwrite existing files. They are not research data.

See [methodology](../docs/methodology.md) for formulas and source-selection rules.
