"""HTTP integration check against the running stack; no browser/screen access."""
import argparse
import csv
import hashlib
import io
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

parser=argparse.ArgumentParser()
parser.add_argument('--url',default='http://localhost:8080')
parser.add_argument('--save',type=Path)
args=parser.parse_args()
def get(path):
    with urlopen(args.url+path,timeout=60) as r:
        assert r.status==200
        return r.read()
def post(path,payload):
    req=Request(args.url+path,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with urlopen(req,timeout=60) as r:
        assert r.status==200
        return r.read()
html=get('/').decode()
assert 'IT Career Graph Lab' in html
for asset in re.findall(r'(?:src|href)="(/assets/[^\"]+)"',html):
    assert len(get(asset))>100
ready=json.loads(get('/health/ready'))
dashboard=json.loads(get('/api/dashboard'))
assert dashboard['counts']=={'skills':71,'roles':7,'profiles':14,'edges':51,'transitions':182}
assert dashboard['is_demo'] is False
graph=get('/api/skills/graph')
payload={'source_profile':'backend:junior','target_profile':'fullstack:middle','lambda':.5,'minimum_prerequisite_level':1,'algorithm':'kahn','weight_source':'skill_weights_by_role_final_v2.csv','included_edges':[],'excluded_edges':[],'version_id':dashboard['version_id']}
one=json.loads(post('/api/experiments/compare',payload))
assert one==json.loads(post('/api/experiments/compare',payload))
batch=json.loads(post('/api/experiments/batch',payload))
assert len(batch['results'])==182
export=post('/api/experiments/export',payload).decode()
rows=list(csv.DictReader(io.StringIO(export)))
assert len(rows)==182
for result,row in zip(batch['results'],rows):
    for model in ['M1','M2','M3']:
        assert float(row[model])==result[model]
    assert row['dataset_version']==dashboard['version_id']
    assert json.loads(row['included_edges'])==[]
assert batch['provenance']['run_id']!=one['provenance']['run_id']
assert json.loads(get('/api/runs/'+one['provenance']['run_id']))==one
assert one['provenance']['data_provenance']['verification_counts']['requirement']=={'Unverified':204}
try:
    post('/api/experiments/compare',{**payload,'included_edges':[['architecture','oop']]})
    raise AssertionError('Cycle accepted')
except HTTPError as exc:
    assert exc.code==422
assert graph==get('/api/skills/graph')
if args.save:
    args.save.mkdir(exist_ok=True,parents=True)
    (args.save/'baseline-comparison.json').write_text(json.dumps(one,indent=2,ensure_ascii=False)+'\n')
    (args.save/'baseline-transitions.csv').write_text(export)
print(json.dumps({'status':'passed','dataset':dashboard['version_id'],'run':one['provenance']['run_id'],'counts':dashboard['counts'],'baseline_scores':{k:one['result'][k] for k in ['M1','M2','M3']},'csv_rows':len(rows),'csv_sha256':hashlib.sha256(export.encode()).hexdigest()},indent=2))
