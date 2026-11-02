import csv
import hashlib
import shutil
from pathlib import Path
import pytest
from sqlalchemy import select,func
from app.models import Skill, SkillWeight, SourceRecord, Requirement, DatasetVersion
from app.services.importer import inspect_dataset,import_dataset,ImportFailure


def test_real_dataset_schema_and_integrity(dataset_dir):
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in dataset_dir.glob('*.csv')}
    tables,report=inspect_dataset(dataset_dir)
    assert report['stats']['skills']==71
    assert report['stats']['profiles']==14
    assert report['stats']['edges']==51
    assert report['stats']['group_requirements_excluded']==37
    assert report['stats']['transitions']==182
    assert not report['errors']
    assert report['stats']['final_weight_rows_dropped']==24
    assert report['stats']['final_weight_alias_merges']==6
    assert len([w for w in report['warnings'] if w['code']=='missing_auxiliary_weight'])==4
    assert hashes=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in dataset_dir.glob('*.csv')}


def test_import_is_idempotent_and_lossless(session,dataset_dir):
    count=lambda m:session.scalar(select(func.count()).select_from(m))
    before=count(SourceRecord)
    import_dataset(session,dataset_dir)
    assert count(SourceRecord)==before==996
    assert count(Skill)==71
    assert count(DatasetVersion)==1
    assert count(Requirement)==204


def test_final_weights_max_aliases_without_blending(session,dataset_dir):
    source=list(csv.DictReader((dataset_dir/'skill_weights_by_role_final_v2.csv').open()))
    mapping={r['survey_name']:r['skill_id'] for r in csv.DictReader((dataset_dir/'skill_mapping.csv').open())}
    expected=max(float(r['weight_0_1']) for r in source if r['role']=='backend' and mapping[r['skill']]=='aspnet_core')
    actual=session.scalar(select(SkillWeight.weight).where(SkillWeight.source=='skill_weights_by_role_final_v2.csv',SkillWeight.role=='backend',SkillWeight.skill_id=='aspnet_core'))
    assert actual==expected
    assert session.scalar(select(func.count()).select_from(SkillWeight).where(SkillWeight.skill_id==''))==0


@pytest.mark.parametrize('kind',['cycle','dangling','duplicate','nan','counts','unknown_mapping','group','missing_file'])
def test_bad_dataset_rejected(dataset_dir,tmp_path,kind):
    copy=tmp_path/'input';shutil.copytree(dataset_dir,copy,ignore=shutil.ignore_patterns('demo','*.py','*.md'))
    if kind=='cycle':
        with (copy/'prerequisites.csv').open('a') as f:f.write('design_patterns,oop\n')
    elif kind=='dangling':
        with (copy/'prerequisites.csv').open('a') as f:f.write('nonexistent,oop\n')
    elif kind=='duplicate':
        p=copy/'skills.csv';p.write_text(p.read_text()+p.read_text().splitlines()[1]+'\n')
    elif kind=='nan':
        p=copy/'role_skill_weights.csv';p.write_text(p.read_text().replace('1.0','NaN',1))
    elif kind=='counts':
        p=copy/'skill_dependents.csv';p.write_text(p.read_text().replace('html_css,11,0','html_css,999,0'))
    elif kind=='unknown_mapping':
        p=copy/'skill_weights_by_role_final_v2.csv';p.write_text(p.read_text().replace('JavaScript','Unmapped-Tool',1))
    elif kind=='group':
        p=copy/'role_requirements.csv';p.write_text(p.read_text().replace('backend_language','unknown_group',1))
    else:
        (copy/'skills.csv').unlink()
    with pytest.raises(ImportFailure) as exc:inspect_dataset(copy)
    assert exc.value.report['errors']
