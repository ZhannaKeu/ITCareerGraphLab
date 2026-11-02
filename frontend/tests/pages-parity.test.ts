// @vitest-environment node
import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { gunzipSync } from 'node:zlib'
import { webcrypto } from 'node:crypto'
import { afterAll, beforeAll, expect, it, vi } from 'vitest'
import { BrowserEngine } from '../src/publication/engine'
import type { Published, Wire } from '../src/publication/model'
import { experimentFile } from '../src/publication/exports'
vi.stubGlobal('crypto',webcrypto)
const data=JSON.parse(readFileSync(new URL('../public/data/published.json',import.meta.url),'utf8')) as Published
const refPath=new URL('../.parity/reference.json.gz',import.meta.url)
const present=existsSync(refPath)
if(process.env.PAGES_PARITY==='1'&&!present)throw Error('Run scripts/prepare_pages.py --references before parity tests')
const reference=present?JSON.parse(gunzipSync(readFileSync(refPath)).toString()):null
const engine=new BrowserEngine(data)
// Only execution IDs/runtime differ intentionally. Scientific fields and graph hashes do not.
const ignored=new Set(['id','run_id','scenario_run_id','baseline_id','left_scenario_run_id','right_scenario_run_id','label'])
let maxAbsoluteDifference=0,numericChecks=0
function close(actual:any,expected:any,path='root'){
 if(typeof expected==='number'){numericChecks++;maxAbsoluteDifference=Math.max(maxAbsoluteDifference,Math.abs(actual-expected));if(typeof actual!=='number'||!Number.isFinite(actual)||Math.abs(actual-expected)>1e-10+1e-10*Math.abs(expected))throw Error(`${path}: ${actual} != ${expected}`);return}
 if(expected===null||typeof expected!=='object'){if(actual!==expected)throw Error(`${path}: ${JSON.stringify(actual)} != ${JSON.stringify(expected)}`);return}
 if(Array.isArray(expected)){if(!Array.isArray(actual)||actual.length!==expected.length)throw Error(`${path}: length ${actual?.length} != ${expected.length}`);expected.forEach((v,i)=>close(actual[i],v,`${path}[${i}]`));return}
 for(const key of Object.keys(expected))if(!ignored.has(key))close(actual?.[key],expected[key],`${path}.${key}`)
}
let e2:Wire,e3:Wire
beforeAll(()=>{expect(data.profiles.length).toBe(14);expect(data.graph.nodes.length).toBe(71);expect(data.graph.edges.length).toBe(51);if(present){expect(data.dataset.id).toBe(reference.experiment2.provenance.dataset);expect(data.source_data_hash).toBe(reference.experiment2.provenance.source_data_hash);expect(data.dashboard.data_provenance.record_hash).toBe(reference.experiment2.provenance.record_hash)}})
it.skipIf(!present)('matches backend full results for all 182 transitions, both weight sources, Kahn/DFS and Legacy/G1/G2/G3',async()=>{for(const c of reference.cases){const result=await engine.batch(c.parameters);close(result.results,c.batch.results)}expect(reference.cases.length).toBe(16)},120000)
it.skipIf(!present)('matches backend generic research and Experiment 1 controlled scenarios and rankings',async()=>{
 const p=reference.research.provenance.parameters,run=await engine.research(p)
 for(const k of ['max_extra','distribution','ranking','sensitivity','summary'])close(run[k],reference.research[k],'research.'+k)
 const first=await engine.relationImpact(reference.experiment1.provenance.parameters)
 for(const k of ['summary','transitions','comparisons','against_M2','distributions','sensitivity','sensitivity_comparisons'])close(first[k],reference.experiment1[k],'experiment1.'+k)
 for(const graph of ['G1','G2','G3'])close(first.runs[graph].results,reference.experiment1.runs[graph].results)
},120000)
it.skipIf(!present)('matches every Experiment 2 scenario (60 × 182), aggregate metrics, ranks and graph comparisons',async()=>{e2=await engine.experiment2(data.dataset.id);for(const k of ['scenarios','rankings','graph_rankings','graph_comparisons'])close(e2[k],reference.experiment2[k],'experiment2.'+k);expect(e2.scenarios.length).toBe(60)},120000)
it.skipIf(!present)('matches all Experiment 3 A/B/C scenarios (345 × 182), ties, metrics and 51 edge configurations',async()=>{e3=await engine.experiment3(data.dataset.id);for(const k of ['scenarios','weight_diagnostics','edge_configurations','edge_influence'])close(e3[k],reference.experiment3[k],'experiment3.'+k);expect(e3.scenarios.length).toBe(345)},180000)
it.skipIf(!present)('exports all computed scenarios without supplying test references to the engine',async()=>{e2??=await engine.experiment2(data.dataset.id);e3??=await engine.experiment3(data.dataset.id);for(const [run,name,count] of [[e2,'experiment2-summary.csv',60],[e2,'experiment2-scenarios.csv',10920],[e2,'experiment2-rankings.csv',21840],[e3,'experiment3-summary.csv',345],[e3,'experiment3-results.csv',62790],[e3,'experiment3-rankings.csv',9660],[e3,'experiment3-edges.csv',255]] as const){const file=experimentFile(run,name);expect(file.body.split('\r\n').length-1).toBe(count);expect(file.body).toContain(run.provenance.run_id);expect(file.body).toContain(data.source_data_hash)}for(const run of [e2,e3])expect(JSON.parse(experimentFile(run,`${run.provenance.experiment_kind}-results.json`).body).scenario_count).toBe(run.scenario_count)},120000)

afterAll(()=>{if(present)writeFileSync(new URL('../.parity/comparison.json',import.meta.url),JSON.stringify({comparison:'browser-vs-python',transition_evaluations:83174,scenarios:457,numeric_checks:numericChecks,max_absolute_difference:maxAbsoluteDifference,atol:1e-10,rtol:1e-10,reference_python:data.reference_python}))})
