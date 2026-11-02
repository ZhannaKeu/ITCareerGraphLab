"""Inspect production files without serving them or making HTTP requests."""
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DIST=ROOT/'frontend/dist';BASE='/ITCareerGraphLab/'
class Assets(HTMLParser):
    def __init__(self): super().__init__();self.urls=[]
    def handle_starttag(self,tag,attrs):
        for key,value in attrs:
            if key in ('src','href') and value and tag in ('script','link'): self.urls.append(value)
def check():
    parser=Assets();parser.feed((DIST/'index.html').read_text())
    assert parser.urls,'No production entry assets'
    assert "connect-src 'self'" in (DIST/'index.html').read_text(),'Public CSP absent'
    for url in parser.urls:
        assert url.startswith(BASE),f'Incorrect base: {url}'
        assert (DIST/url[len(BASE):]).is_file(),f'Missing asset: {url}'
    files=[p for p in DIST.rglob('*') if p.is_file()]
    allowed=re.compile(r'^(index\.html|\.nojekyll|assets/[A-Za-z0-9_-]+\.(js|css)|data/(published|manifest)\.json)$')
    for p in files:
        name=p.relative_to(DIST).as_posix();assert allowed.fullmatch(name),f'Unexpected file in public artifact: {name}'
        content=p.read_text()
        assert not re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bgh[pousr]_[A-Za-z0-9]{30,}|\bAKIA[A-Z0-9]{16}\b',content),f'Secret-like credential: {name}'
        if name.endswith('.css'): assert not re.search(r'@import\s+url\([\"\']?https?://',content),'External stylesheet request in public edition'
        if name.endswith('.js'):
            assert not any(marker in content for marker in ('reference.json.gz','must-not-be-published.invalid','http://localhost:8000/docs')),'Test reference or backend-only configuration leaked'
            for ref in re.findall(r'["\']('+re.escape(BASE)+r'assets/[^"\']+)["\']',content):assert (DIST/ref[len(BASE):]).is_file(),f'Missing chunk: {ref}'
    raw=(DIST/'data/published.json').read_bytes();data=json.loads(raw);seal=json.loads((DIST/'data/manifest.json').read_text())
    assert hashlib.sha256(raw).hexdigest()==seal['sha256']
    expected={'schema','reference_python','model_summation','dataset','dashboard','graph','profiles','configurations','requirements','weights','records','history','source_rows','source_data_hash','input_manifest'}
    assert set(data)==expected,'Unreviewed public bundle fields'
    assert len(data['profiles'])==14 and len(data['graph']['nodes'])==71
    assert [data['configurations'][g]['edge_count'] for g in ('G1','G2','G3')]==[51,14,50]
    assert all(r['status']=='Unverified' for r in data['records'])
    assert len(data['source_rows'])==len(seal['files'])==10
    for filename,meta in data['input_manifest'].items():assert hashlib.sha256((ROOT/'datasets'/filename).read_bytes()).hexdigest()==meta['sha256']
    workers=[p for p in files if p.name.startswith('worker-') and p.suffix=='.js'];assert len(workers)==1,'Calculation worker absent'
    assert 'data/published.json' in workers[0].read_text() and 'data/manifest.json' in workers[0].read_text()
    print(f'Pages artifact verified: {len(files)} files, base={BASE}, 71 skills / 14 profiles / 51 edges; no parity results or non-allowlisted files')
if __name__=='__main__': check()
