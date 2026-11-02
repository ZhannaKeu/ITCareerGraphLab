"""Version-bound G1/G2/G3 configurations. Never edits a dataset or promotes trust."""
import hashlib
import json
from collections import Counter
from importlib.resources import files
from sqlalchemy import select
from ..models import DatasetVersion, PrerequisiteClassification, SourceRecord
from ..research.graph import build_graph

SPEC = json.loads(files('app.research').joinpath('prerequisite_relations_v2.json').read_text(encoding='utf-8'))
PROTOCOL = SPEC['protocol']
GRAPH_TYPES = {'G1': ('Required','Recommended','Related'), 'G2': ('Required',), 'G3': ('Required','Recommended')}
GRAPH_NAMES = {'G1': 'Original', 'G2': 'Strict', 'G3': 'Extended'}


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def edge_id(source,target):
    return digest([source,target])


def ensure_classification(session,root_id):
    """Called by idempotent import, not by reads. Guard against row-order mistakes."""
    dataset=session.get(DatasetVersion,root_id)
    if dataset.manifest.get('prerequisites.csv',{}).get('sha256')!=SPEC['source_sha256']:
        return  # Other datasets retain full legacy behavior; never guess classifications.
    rows=list(session.scalars(select(SourceRecord).where(SourceRecord.version_id==root_id,SourceRecord.filename=='prerequisites.csv').order_by(SourceRecord.row_number)))
    expected=SPEC['relations']
    if len(rows)!=51 or any(r.row_number!=i+2 or r.data!={'from_skill':e['from_skill'],'to_skill':e['to_skill']} for i,(r,e) in enumerate(zip(rows,expected))):
        raise ValueError('V2 classification does not match the pinned original CSV order')
    existing=list(session.scalars(select(PrerequisiteClassification).where(PrerequisiteClassification.version_id==root_id)))
    if existing:
        if classification_manifest(session,root_id)['classification_hash']!=digest({'protocol':PROTOCOL,'source_sha256':SPEC['source_sha256'],'relations':expected}):
            raise ValueError('Persisted classification differs from immutable V2 protocol')
        return
    session.add_all(PrerequisiteClassification(version_id=root_id,edge_id=edge_id(e['from_skill'],e['to_skill']),
        classification_source=SPEC['classification_source'],protocol=PROTOCOL,**e) for e in expected)
    session.flush()


def classification_manifest(session,root_id):
    rows=list(session.scalars(select(PrerequisiteClassification).where(PrerequisiteClassification.version_id==root_id).order_by(PrerequisiteClassification.source_row)))
    if not rows:
        return None
    relations=[{k:getattr(r,k) for k in ('source_row','from_skill','to_skill','relation_type','min_level','verification_status')} for r in rows]
    return {'protocol':PROTOCOL,'source_sha256':SPEC['source_sha256'],'classification_source':SPEC['classification_source'],
        'classification_hash':digest({'protocol':PROTOCOL,'source_sha256':SPEC['source_sha256'],'relations':relations}),
        'root_version_id':root_id,'relations':[{**r,'edge_id':edge_id(r['from_skill'],r['to_skill']),
        'classification_source':SPEC['classification_source']} for r in relations]}


def graph_configuration(snapshot,name):
    if name not in GRAPH_TYPES:
        raise ValueError('Unknown graph configuration')
    classification=snapshot.classification
    if not classification:
        raise ValueError('V2 classification unavailable: import the pinned 51-edge source after migration 0004')
    expected={(e['from_skill'],e['to_skill']) for e in classification['relations']}
    actual={(e.prerequisite_id,e.skill_id) for e in snapshot.edges}
    if actual!=expected:
        raise ValueError('G1/G2/G3 require the pinned 51-edge population in this version; edited edge populations need a separately reviewed classification protocol. Legacy mode remains available.')
    edges=[e for e in classification['relations'] if e['relation_type'] in GRAPH_TYPES[name]]
    nodes=sorted(s.id for s in snapshot.skills)
    build_graph(nodes,[(e['from_skill'],e['to_skill']) for e in edges])
    payload={'name':name,'label':GRAPH_NAMES[name],'dataset_version':snapshot.version.id,
        'record_hash':snapshot.metadata['record_hash'],'classification_hash':classification['classification_hash'],
        'classification_protocol':PROTOCOL,'classification_source':SPEC['classification_source'],
        'verification_status':'Unverified','source_sha256':SPEC['source_sha256'],
        'node_ids':nodes,'node_count':len(nodes),'edge_count':len(edges),
        'included_edge_ids':sorted(e['edge_id'] for e in edges),
        'relation_counts':dict(Counter(e['relation_type'] for e in edges)),
        'min_level_policy':'unset; global tau remains the explicit scenario threshold',
        'edges':sorted(edges,key=lambda e:e['edge_id'])}
    return {**payload,'configuration_hash':digest(payload)}


def validate_named_request(request):
    if request.graph_configuration:
        if request.included_edges or request.excluded_edges:
            raise ValueError('Named G1/G2/G3 edge sets are immutable; remove experimental overrides or use legacy mode')
        if request.verification_scope!='all':
            raise ValueError('V2 classifications are Unverified; this preliminary protocol requires verification_scope=all')
