import csv
import io
import json
import logging
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import text, select
from sqlalchemy.exc import SQLAlchemyError
from .config import settings
from .db import get_db
from .models import DatasetVersion, SourceRecord, ExperimentRun
from .api.schemas import ExperimentRequest, RevisionRequest, VersionComparisonRequest, Entity, VerificationStatus, ResearchRequest, RelationImpactRequest, Experiment2Request, Experiment3Request
from .services.versions import key
from .services.experiments import load_snapshot, run_experiment, provenance, execute_run, DatasetUnavailable

app = FastAPI(title="IT Career Graph Lab", version="0.1.0", description="Reproducible career-transition experiments. /docs for API contract.")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

@app.exception_handler(SQLAlchemyError)
def database_error(request, exc):
    logging.getLogger(__name__).error("Database operation failed", exc_info=exc)
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=503, content={"detail": "Database unavailable or migrations missing; check server logs and /health/ready"})

@app.exception_handler(DatasetUnavailable)
def dataset_error(request, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=409, content={"detail": str(exc)})

@app.exception_handler(ValueError)
def input_error(request, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=422, content={"detail": str(exc)})

@app.get("/health/live")
def live():
    return {"status": "ok"}

@app.get("/health/ready")
def ready(db=Depends(get_db)):
    db.execute(text("SELECT 1"))
    snapshot = load_snapshot(db)
    return {"status": "ready", "dataset_version": snapshot.version.id}

@app.get("/api/datasets")
def datasets(db=Depends(get_db)):
    from .services.versions import metadata
    return [{"id": v.id, "label": v.label, "is_demo": v.is_demo, "imported_at": v.imported_at, **metadata(db,v.id)}
            for v in db.scalars(select(DatasetVersion).order_by(DatasetVersion.imported_at.desc()))]

@app.get("/api/dashboard")
def dashboard(version_id: str | None = None, db=Depends(get_db)):
    s = load_snapshot(db, version_id)
    return {"version_id": s.version.id, "label": s.version.label, "is_demo": s.version.is_demo,
            "data_provenance": s.metadata, "quality": s.version.quality, "counts": {"skills": len(s.skills), "roles": len({p.role for p in s.profiles}),
            "profiles": len(s.profiles), "edges": len(s.edges), "transitions": len(s.profiles)*(len(s.profiles)-1)},
            "categories": sorted({x.category for x in s.skills})}

@app.get("/api/skills/graph")
def graph(version_id: str | None = None, configuration: str | None = None, db=Depends(get_db)):
    s = load_snapshot(db, version_id)
    from .services.relation_graphs import graph_configuration, edge_id
    config=graph_configuration(s,configuration) if configuration else None
    classification={(e['from_skill'],e['to_skill']):e for e in (s.classification or {}).get('relations',[])}
    allowed=set(config['included_edge_ids']) if config else None
    edges=[]
    for e in s.edges:
        identifier=edge_id(e.prerequisite_id,e.skill_id)
        if allowed is not None and identifier not in allowed: continue
        label=classification.get((e.prerequisite_id,e.skill_id))
        edges.append({'source':e.prerequisite_id,'target':e.skill_id,'edge_id':identifier,
            'verification_status':s.record_provenance['prerequisite',key([e.prerequisite_id,e.skill_id])]['status'],
            **({'relation_type':label['relation_type'],'min_level':label['min_level'],
                'classification_source':label['classification_source'],'classification_verification_status':label['verification_status'],
                'source_row':label['source_row']} if label else {})})
    return {'version_id':s.version.id,'record_hash':s.metadata['record_hash'],'configuration':config,
        'classification':s.classification,'nodes':[{'id':x.id,'name':x.name,'category':x.category,'description':x.description,
        'verification_status':s.record_provenance['skill',key([x.id])]['status']} for x in s.skills], 'edges':edges}

@app.get("/api/profiles")
def profiles(version_id: str | None = None, db=Depends(get_db)):
    s = load_snapshot(db, version_id)
    return [{"id": p.id, "role": p.role, "level": p.level} for p in s.profiles]

@app.get("/api/data/{filename}")
def source_rows(filename: str, version_id: str | None = None, offset: int = 0, limit: int = 100, db=Depends(get_db)):
    s = load_snapshot(db, version_id)
    if filename not in s.version.manifest:
        raise HTTPException(404, "Unknown source file")
    if offset < 0 or not 1 <= limit <= 500:
        raise HTTPException(422, "offset >= 0 and 1 <= limit <= 500")
    records = db.scalars(select(SourceRecord).where(SourceRecord.version_id == s.version.id, SourceRecord.filename == filename)
                         .order_by(SourceRecord.row_number).offset(offset).limit(limit))
    return {"version_id": s.version.id, "source_version": s.metadata["root_id"], "content_kind": "immutable_original_csv_rows", "rows": [{"row": r.row_number, "data": r.data} for r in records]}

@app.post("/api/experiments/compare")
def comparison(request: ExperimentRequest, db=Depends(get_db)):
    s = load_snapshot(db, request.version_id)
    return execute_run(db, s, request, "pair")


def calculate_batch(s, request):
    # Ordered pairs of distinct profiles; 14 profiles -> 14*13 = 182.
    return [run_experiment(s, request, a.id, b.id) for a in s.profiles for b in s.profiles if a.id != b.id]

@app.post("/api/experiments/batch")
def batch(request: ExperimentRequest, db=Depends(get_db)):
    s = load_snapshot(db, request.version_id)
    return execute_run(db, s, request, "batch")

@app.post("/api/experiments/export")
def export(request: ExperimentRequest, db=Depends(get_db)):
    s = load_snapshot(db, request.version_id)
    saved = execute_run(db, s, request, "batch")
    results, meta = saved["results"], saved["provenance"]
    output = io.StringIO(newline="")
    fields = ["source_profile", "target_profile", "M1", "M2", "M3", "direct_score", "prerequisite_burden",
              "weighted_prerequisite_burden", "unknown_source_count", "unknown_target_count", "fallback_weight_count",
              "dataset_version", "run_id", "is_demo", "weight_source", "lambda", "minimum_prerequisite_level", "algorithm", "scenario", "implementation", "included_edges", "excluded_edges", "runtime", "verification_scope", "record_hash", "data_provenance", "interpretation", "graph_configuration", "configuration_hash", "classification_hash", "included_edge_ids"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for r in results:
        row = {key: r[key] for key in fields if key in r}
        row.update(unknown_source_count=len(r["unknown_source_skills"]), unknown_target_count=len(r["unknown_target_skills"]),
                   fallback_weight_count=len(r["fallback_weight_skills"]), dataset_version=s.version.id, run_id=meta["run_id"],
                   is_demo=s.version.is_demo, weight_source=request.weight_source, algorithm=request.algorithm,
                   minimum_prerequisite_level=request.minimum_prerequisite_level, implementation=meta["implementation"])
        configuration=meta.get('graph_configuration')
        row['graph_configuration']=json.dumps(configuration,ensure_ascii=False,sort_keys=True) if configuration else ''
        row['configuration_hash']=configuration['configuration_hash'] if configuration else ''
        row['classification_hash']=configuration['classification_hash'] if configuration else ''
        row['included_edge_ids']=json.dumps(configuration['included_edge_ids']) if configuration else ''
        row["record_hash"] = meta["record_hash"]
        row["data_provenance"] = json.dumps(meta["data_provenance"], ensure_ascii=False, sort_keys=True)
        row["included_edges"] = json.dumps(request.included_edges, separators=(",", ":"))
        row["excluded_edges"] = json.dumps(request.excluded_edges, separators=(",", ":"))
        row["runtime"] = json.dumps(meta["runtime"], sort_keys=True)
        row["lambda"] = request.lambda_
        writer.writerow(row)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": 'attachment; filename="career-transitions.csv"',
                                      "X-Dataset-Version": s.version.id, "X-Run-ID": meta["run_id"]})


@app.get("/api/versions/{version_id}/records")
def version_records(version_id: str, entity: Entity | None = None, status: VerificationStatus | None = None,
                    offset: int = 0, limit: int = 50, db=Depends(get_db)):
    from .services.versions import public_records
    load_snapshot(db, version_id)
    if offset < 0 or not 1 <= limit <= 200:
        raise HTTPException(422, "offset >= 0; limit=1..200")
    return public_records(db, version_id, entity, status, offset, limit)


@app.get("/api/versions/{version_id}/history")
def version_history(version_id: str, db=Depends(get_db)):
    from .services.versions import history
    return history(db, version_id)


@app.post("/api/versions", status_code=201)
def revise(request: RevisionRequest, db=Depends(get_db)):
    from .services.versions import create_revision
    return create_revision(db, request)


@app.get("/api/runs")
def saved_runs(version_id: str | None = None, offset: int = 0, limit: int = 50, db=Depends(get_db)):
    if offset < 0 or not 1 <= limit <= 200:
        raise HTTPException(422, "offset >= 0; limit=1..200")
    query = select(ExperimentRun)
    if version_id: query = query.where(ExperimentRun.version_id == version_id)
    return [{"id": r.id, "version_id": r.version_id, "kind": r.kind, "parameters": r.parameters, "created_at": r.created_at}
            for r in db.scalars(query.order_by(ExperimentRun.created_at.desc(), ExperimentRun.id).offset(offset).limit(limit))]


@app.get("/api/runs/{run_id}")
def saved_run(run_id: str, db=Depends(get_db)):
    run = db.get(ExperimentRun, run_id)
    if not run: raise HTTPException(404, "Unknown run")
    return run.payload


@app.post("/api/experiments/versions")
def compare_versions(request: VersionComparisonRequest, db=Depends(get_db)):
    if request.original_version == request.corrected_version:
        raise HTTPException(422, "Select two different dataset versions")
    if request.experiment.version_id is not None:
        raise HTTPException(422, "Set versions in original_version/corrected_version, not experiment.version_id")
    kind = "batch" if request.batch else "pair"
    left = execute_run(db, load_snapshot(db, request.original_version), request.experiment, kind)
    right = execute_run(db, load_snapshot(db, request.corrected_version), request.experiment, kind)
    a = left["results"] if request.batch else [left["result"]]
    b = right["results"] if request.batch else [right["result"]]
    indexed = {(r["source_profile"], r["target_profile"]): r for r in b}
    if set(indexed) != {(r["source_profile"],r["target_profile"]) for r in a}:
        raise HTTPException(422, "Profile populations differ; comparisons require matching directed pairs")
    rows = [{"source_profile": r["source_profile"], "target_profile": r["target_profile"],
        "original": {m: r[m] for m in ("M1","M2","M3")},
        "corrected": {m: indexed[r["source_profile"],r["target_profile"]][m] for m in ("M1","M2","M3")},
        "delta": {m: indexed[r["source_profile"],r["target_profile"]][m]-r[m] for m in ("M1","M2","M3")}} for r in a]
    return {"original": left, "corrected": right, "rows": rows,
        "changed_pairs": sum(any(value != 0 for value in row["delta"].values()) for row in rows),
        "warning": "Differences show sensitivity to data revisions under identical parameters, not demonstrated improvement in real-world recommendation quality."}


@app.post("/api/experiments/research")
def research_results(request: ResearchRequest, db=Depends(get_db)):
    from .services.research_results import execute_research
    return execute_research(db, load_snapshot(db, request.experiment.version_id), request)


@app.get("/api/graph-configurations")
def named_graphs(version_id: str | None = None, db=Depends(get_db)):
    from .services.relation_graphs import graph_configuration
    s=load_snapshot(db,version_id)
    try:
        configs=[graph_configuration(s,g) for g in ('G1','G2','G3')]
        return {'version_id':s.version.id,'available':True,'configurations':configs}
    except ValueError as exc:
        return {'version_id':s.version.id,'available':False,'reason':str(exc),'configurations':[]}


@app.post("/api/experiments/relation-impact")
def relation_impact(request: RelationImpactRequest, db=Depends(get_db)):
    from .services.relation_impact import execute_relation_impact
    return execute_relation_impact(db,load_snapshot(db,request.experiment.version_id),request)


@app.post("/api/experiments/experiment2")
def experiment2(request: Experiment2Request, db=Depends(get_db)):
    from .services.experiment2 import execute_experiment2
    return execute_experiment2(db, load_snapshot(db, request.version_id))


@app.get("/api/experiments/experiment2/{run_id}/exports/{filename}")
def experiment2_export(run_id: str, filename: str, db=Depends(get_db)):
    from .services.experiment2 import export_file, EXPORTS
    if filename not in EXPORTS:
        raise HTTPException(404, "Unknown export file")
    saved = db.get(ExperimentRun, run_id)
    if not saved or saved.kind != 'experiment2':
        raise HTTPException(404, "Unknown Experiment 2 run")
    body, media_type = export_file(saved.payload, filename)
    return StreamingResponse(iter([body]), media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "X-Run-ID": run_id,
                 "X-Dataset-Version": saved.version_id})


@app.post('/api/experiments/experiment3')
def experiment3(request: Experiment3Request, db=Depends(get_db)):
    from .services.experiment3 import execute_experiment3
    return execute_experiment3(db,load_snapshot(db,request.version_id))


@app.get('/api/experiments/experiment3/{run_id}/exports/{filename}')
def experiment3_export(run_id: str, filename: str, db=Depends(get_db)):
    from .services.experiment3 import export_file, EXPORTS
    if filename not in EXPORTS:
        raise HTTPException(404,'Unknown export file')
    saved=db.get(ExperimentRun,run_id)
    if not saved or saved.kind!='experiment3':
        raise HTTPException(404,'Unknown Experiment 3 run')
    body,media_type=export_file(saved.payload,filename)
    return StreamingResponse(iter([body]),media_type=media_type,headers={
        'Content-Disposition':f'attachment; filename="{filename}"','X-Run-ID':run_id,'X-Dataset-Version':saved.version_id})
