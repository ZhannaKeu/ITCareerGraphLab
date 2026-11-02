// @vitest-environment node
import { readFileSync } from 'node:fs'
import { webcrypto } from 'node:crypto'
import { expect, it, vi } from 'vitest'
import { PublicSession } from '../src/publication/session'
import { sum, topological, validate, canonical } from '../src/publication/model'
import type { Published } from '../src/publication/model'
import { correlations } from '../src/publication/statistics'
import { pageFromHash, PUBLIC_PAGES } from '../src/publication/mode'
vi.stubGlobal('crypto',webcrypto)
const data=JSON.parse(readFileSync(new URL('../public/data/published.json',import.meta.url),'utf8')) as Published
const session=new PublicSession(data),params={source_profile:'backend:junior',target_profile:'fullstack:middle',version_id:data.dataset.id}
it('provides all public read contracts, pagination, unchanged configurations and immutable source records',async()=>{
 expect((await session.request('/datasets')).length).toBe(1)
 expect((await session.request('/dashboard')).counts.transitions).toBe(182)
 expect((await session.request('/profiles')).length).toBe(14)
 for(const [g,count] of [['G1',51],['G2',14],['G3',50]] as const)expect((await session.request(`/skills/graph?configuration=${g}`)).edges.length).toBe(count)
 for(const filename of Object.keys(data.source_rows))expect((await session.request(`/data/${filename}?limit=1`)).rows.length).toBe(1)
 expect((await session.request(`/versions/${data.dataset.id}/records?entity=requirement&limit=20`)).records.length).toBe(20)
 expect((await session.request(`/versions/${data.dataset.id}/history`)).length).toBe(1)
 expect(()=>{data.graph.edges.pop()}).toThrow()
 await expect(session.request('/versions',{parent_id:data.dataset.id})).rejects.toThrow('read-only')
 await expect(session.request('/data/.env')).rejects.toThrow('Unknown')
 await expect(session.request('/data/skills.csv?limit=9999')).rejects.toThrow('pagination')
 await expect(session.request('/dashboard?version_id=private')).rejects.toThrow('published')
})
it('calculates and exports fresh transitions without fetch/server, then loses runs in a new session',async()=>{
 const fetcher=vi.fn(()=>{throw Error('Network forbidden')});vi.stubGlobal('fetch',fetcher)
 const run=await session.request('/experiments/batch',params)
 expect(run.results.length).toBe(182);expect(run.provenance.run_id).toMatch(/^browser-[a-f0-9]{64}$/)
 expect(await session.request(`/runs/${run.provenance.run_id}`)).toBe(run)
 const replay=await session.request('/experiments/batch',params);expect(replay).toBe(run)
 const file=await session.request('/experiments/export',params);expect(file.filename).toBe('career-transitions.csv');expect(file.body).toContain(run.provenance.run_id)
 expect(fetcher).not.toHaveBeenCalled()
 expect((await new PublicSession(data).request('/runs')).length).toBe(0)
 vi.unstubAllGlobals();vi.stubGlobal('crypto',webcrypto)
})
it('supports graph interventions and rejects cycles, unknown profiles, verified-only gaps and named overrides',async()=>{
 const edge=data.graph.edges[0],excluded=[[edge.source,edge.target]]
 const run=await session.request('/experiments/compare',{...params,excluded_edges:excluded,algorithm:'dfs'})
 expect(run.result.learning_order.length).toBeGreaterThan(0)
 await expect(session.request('/experiments/compare',{...params,included_edges:[[edge.target,edge.source]]})).rejects.toThrow('cycle')
 for(const patch of [{lambda:-1},{graph_configuration:''},{graph_configuration:'__proto__'},{source_profile:'bad'},{verification_scope:'verified'},{graph_configuration:'G1',excluded_edges:excluded}])await expect(session.request('/experiments/batch',{...params,...patch})).rejects.toThrow()
 expect(()=>validate(data,{...params,unexpected:true})).toThrow('Unknown')
})
it('uses hash deep links for each section and correct legacy/compensated summation semantics',()=>{
 for(const p of PUBLIC_PAGES)expect(pageFromHash('#/'+p)).toBe(p)
 expect(pageFromHash('#/bad')).toBe('dashboard')
 expect(sum([1e16,1,1,-1e16],false)).toBe(0);expect(sum([1e16,1,1,-1e16],true)).toBe(2)
 expect(topological(['b','a'],[['a','b']])).toEqual(['a','b'])
 expect(correlations([1,1,2],[1,2,2]).kendall_tau_b).toBe(.5)
 expect(correlations([1,1],[1,2])).toEqual({spearman:null,kendall_tau_b:null})
 expect(canonical({b:1,a:[null,2]})).toBe('{"a":[null,2],"b":1}')
})

it('loads only base-relative static assets and rejects corrupted bytes before any calculation',async()=>{
 const {loadPublished}=await import('../src/publication/load')
 const raw=readFileSync(new URL('../public/data/published.json',import.meta.url),'utf8'),seal=JSON.parse(readFileSync(new URL('../public/data/manifest.json',import.meta.url),'utf8'))
 const fetcher=vi.fn(async(url:string)=>({ok:true,text:async()=>raw,json:async()=>url.endsWith('manifest.json')?seal:JSON.parse(raw)}))
 expect((await(await loadPublished(fetcher,'/ITCareerGraphLab/')).request('/profiles')).length).toBe(14)
 expect(fetcher.mock.calls.map(([url])=>url)).toEqual(['/ITCareerGraphLab/data/published.json','/ITCareerGraphLab/data/manifest.json'])
 const broken=async()=>({ok:true,text:async()=>raw+' ',json:async()=>seal})
 await expect(loadPublished(broken,'/ITCareerGraphLab/')).rejects.toThrow('integrity')
})
