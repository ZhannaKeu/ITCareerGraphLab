"""Build-time only: allowlisted CSV -> isolated SQLite -> public JSON. No servers."""
import argparse
import gzip
import hashlib
import json
import platform
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db import Base
from app.models import SourceRecord
from app.services.importer import import_dataset, SCHEMAS
from app.services.experiments import load_snapshot,execute_run
from app.services.relation_graphs import graph_configuration,digest
from app.services.versions import public_records,history
from app.main import dashboard,graph,datasets,profiles

def prepare(references=False):
    engine=create_engine('sqlite://');Base.metadata.create_all(engine)
    with Session(engine,expire_on_commit=False) as db:
        import_dataset(db,ROOT/'datasets');s=load_snapshot(db)
        records=public_records(db,s.version.id,limit=100000)['records']
        if any(r['status']!='Unverified' for r in records): raise ValueError('Only the unverified published CSV root may be bundled')
        files=sorted(SCHEMAS)
        bundle={'schema':'career-pages-data-1','reference_python':platform.python_version(),
            'model_summation':'compensated' if sys.version_info>=(3,12) else 'legacy',
            'dataset':datasets(db)[0],'dashboard':dashboard(db=db),'graph':graph(db=db),'profiles':profiles(db=db),
            'configurations':{g:graph_configuration(s,g) for g in ('G1','G2','G3')},
            'requirements':[{'profile_id':r.profile_id,'skill_id':r.skill_id,'group_id':r.group_id,'required_level':r.required_level} for r in s.requirements],
            'weights':[{'source':w.source,'role':w.role,'skill_id':w.skill_id,'weight':w.weight} for w in s.weights],
            'records':records,'history':history(db,s.version.id),
            'source_rows':{f:[{'row':r.row_number,'data':r.data} for r in db.query(SourceRecord).filter_by(version_id=s.version.id,filename=f).order_by(SourceRecord.row_number)] for f in files},
            'source_data_hash':digest(s.version.manifest),'input_manifest':s.version.manifest}
        bundle['dataset']['imported_at']=None # local/private import time is unknown in a source-derived public snapshot
        bundle['dataset']['publication_timestamp_policy']='Source-derived snapshot; original local import timestamps are not published'
        serialized=json.dumps(bundle,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False,default=str)
        output=ROOT/'frontend/public/data/published.json';output.write_text(serialized)
        seal={'sha256':hashlib.sha256(serialized.encode()).hexdigest(),'dataset':s.version.id,'record_hash':s.metadata['record_hash'],
              'source_data_hash':bundle['source_data_hash'],'reference_python':bundle['reference_python'],'files':files}
        (output.parent/'manifest.json').write_text(json.dumps(seal,sort_keys=True,indent=2))
        print(f'Public dataset: {len(s.skills)} skills, {len(s.profiles)} profiles, {len(s.edges)} edges; {len(serialized.encode())} bytes')
        if references:
            from app.api.schemas import ExperimentRequest,RelationImpactRequest,ResearchRequest
            from app.services.relation_impact import execute_relation_impact
            from app.services.research_results import execute_research
            from app.services.experiment2 import execute_experiment2
            from app.services.experiment3 import execute_experiment3
            request=ExperimentRequest(source_profile='backend:junior',target_profile='fullstack:middle',version_id=s.version.id)
            cases=[]
            for algorithm in ('kahn','dfs'):
                for source in ('role_skill_weights.csv','skill_weights_by_role_final_v2.csv'):
                    for name in (None,'G1','G2','G3'):
                        p=request.model_copy(update={'algorithm':algorithm,'weight_source':source,'graph_configuration':name})
                        cases.append({'parameters':p.model_dump(mode='json',by_alias=True),'batch':execute_run(db,s,p,'batch')})
            ref={'cases':cases,'research':execute_research(db,s,ResearchRequest(experiment=request)),
                'experiment1':execute_relation_impact(db,s,RelationImpactRequest(experiment=request)),
                'experiment2':execute_experiment2(db,s),'experiment3':execute_experiment3(db,s)}
            folder=ROOT/'frontend/.parity';folder.mkdir(exist_ok=True)
            with gzip.open(folder/'reference.json.gz','wt',encoding='utf-8') as f: json.dump(ref,f,ensure_ascii=False,allow_nan=False,default=str)
            print('Private test-only references generated; never copied to public/dist')
    engine.dispose()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--references',action='store_true');prepare(p.parse_args().references)
