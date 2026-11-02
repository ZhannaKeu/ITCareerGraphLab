import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Experiment3 from '../pages/Experiment3'
import RobustnessHeatmap from '../components/RobustnessHeatmap'
import type { RobustScenario } from '../types'
import { figureSVG } from '../lib/export'
const controls=[{tau:1,lambda:1},{tau:2,lambda:1},{tau:3,lambda:1},{tau:4,lambda:1},{tau:4,lambda:2}]
const metric={mean:2,baseline_mean:3,mean_difference:-1,mean_absolute_difference:1,max_absolute_difference:2,changed_pairs:1,mean_score_change:-1,max_absolute_score_change:2,mean_spearman:null,mean_kendall_tau_b:null,undefined_spearman_sources:14,undefined_kendall_tau_b_sources:14,mean_top3_overlap:.9,mean_top5_overlap:1,top3_membership_changed_sources:1,top5_membership_changed_sources:0,top3_replaced_targets:1,top5_replaced_targets:0,top3_order_changed_sources:1,top5_order_changed_sources:0}
const scenario=(study:'A'|'B'|'C',variant:string,graph:string,tau:number,lambda:number,edge:number|null=null)=>({id:`${study}-${variant}-${graph}-${tau}-${lambda}-${edge}`,study,variant,graph,tau,lambda,unknown_source_level:0,weight_mode:'B0',weight_source:'file',excluded_edge_id:edge===null?null:`edge-${edge}`,excluded_edge:edge===null?null:[`source_${edge}`,'target_skill'],configuration_hash:'h'.repeat(64),baseline_id:'base',baseline_configuration_hash:'b'.repeat(64),metrics:{pairs:182,unknown_source_occurrences:10,assumed_source_occurrences:5,fallback_weight_occurrences:2,pairs_with_unknown_source:1,pairs_with_fallback_weights:1,M2:metric,M3:metric},rankings:{M2:[],M3:[]},results:[]})
const edges=Array.from({length:51},(_,i)=>({edge_id:`edge-${i}`,from_skill:`source_${i}`,to_skill:'target_skill'}))
const scenarios=[...(['A','B'] as const).flatMap(study=>[0,1,2].flatMap(n=>['G1','G2','G3'].flatMap(g=>controls.map(c=>scenario(study,study+n,g,c.tau,c.lambda))))),...edges.flatMap((_,i)=>controls.map(c=>scenario('C','LOO','G1',c.tau,c.lambda,i)))]
const run={provenance:{run_id:'experiment3-test',dataset:'version',source_data_hash:'h'.repeat(64),record_hash:'r'.repeat(64),parameters:{controls,algorithm:'kahn'},implementation:'1.1.0',analysis_version:'experiment3-robustness-1.0.0'},scenario_count:345,scenarios,configurations:Object.fromEntries(['G1','G2','G3'].map(name=>[name,{name,configuration_hash:name,edges}])),edge_configurations:Object.fromEntries(edges.map(e=>[e.edge_id,{name:'G1-LOO'}])),edge_influence:edges.flatMap((e,i)=>controls.map(c=>({...c,...metric,id:`influence-${i}-${c.tau}-${c.lambda}`,excluded_edge_id:e.edge_id,excluded_edge:[e.from_skill,e.to_skill],score_rank:i+1,ranking_rank:null,top3_rank:i+1,top5_rank:i+1}))),weight_diagnostics:[]}
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
it('restores a pinned run, keeps studies separate, renders all C rows, and submits only the version',async()=>{
 const fetcher=vi.fn(async(url:unknown,opts?:RequestInit)=>({ok:true,json:async()=>String(url).includes('graph-configurations')?{available:true}:opts?.method==='POST'||String(url).includes('/runs/experiment3-test')?run:[{id:'experiment3-test',kind:'experiment3',created_at:'2026-11-02'}]}));vi.stubGlobal('fetch',fetcher)
 const view=render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><Experiment3 versionId="version"/></QueryClientProvider>)
 await view.findByRole('option',{name:/experiment3-test/})
 fireEvent.change(view.getByLabelText('Сохранённый Experiment 3'),{target:{value:'experiment3-test'}})
 expect(await view.findByText('EXPERIMENT 3 RUN experiment3-test')).toBeTruthy()
 expect(view.container.querySelector('tbody')?.querySelectorAll('tr').length).toBe(15)
 expect(view.container.querySelectorAll('svg[data-export-figure]').length).toBe(2)
 for(const name of ['summary.csv','results.csv','rankings.csv','edges.csv','results.json'])expect(view.getByRole('button',{name:`experiment3-${name} ↓`})).toBeTruthy()
 fireEvent.change(view.getByLabelText('Исследование Experiment 3'),{target:{value:'B'}})
 expect(view.container.querySelector('tbody')?.textContent).toContain('B1 · role_skill_weights')
 fireEvent.change(view.getByLabelText('Исследование Experiment 3'),{target:{value:'C'}})
 expect((view.getByLabelText('Граф Experiment 3') as HTMLSelectElement).disabled).toBe(true)
 expect(view.container.querySelector('tbody')?.querySelectorAll('tr').length).toBe(255)
 expect(view.container.querySelectorAll('tbody')[1].querySelectorAll('tr').length).toBe(51)
 fireEvent.change(view.getByLabelText('Критерий влияния рёбер'),{target:{value:'ranking_rank'}})
 expect(view.getByRole('status').textContent).toContain('Нет рассчитанных значений')
 fireEvent.click(view.getByRole('button',{name:'Рассчитать Experiment 3 · 345 сценариев'}))
 await waitFor(()=>expect(fetcher.mock.calls.some(([,opts])=>opts?.method==='POST')).toBe(true))
 const post=fetcher.mock.calls.find(([,opts])=>opts?.method==='POST')
 expect(JSON.parse(String(post?.[1]?.body))).toEqual({version_id:'version'})
})
it('exports long labels and missing correlations without inventing zero values',()=>{
 const row=scenario('A','A1','G1',4,2)
 const label='very_long_skill_name_and_profile:middle'.repeat(2)
 const {container,getByLabelText}=render(<RobustnessHeatmap scenarios={[row] as RobustScenario[]} rows={[{id:'A1',label}]} controls={[{tau:4,lambda:2}]} model="M3" metric="mean_spearman" maximum={1} title="Robustness"/>)
 expect(getByLabelText(`${label}; τ=4; λ=2: не определено`)).toBeTruthy()
 const svg=figureSVG(container,{run_id:'experiment3-test',dataset:'dataset-hash',parameters:{controls},warning:'Unverified; assumptions only'})
 const doc=new DOMParser().parseFromString(svg,'image/svg+xml')
 expect(doc.querySelector('parsererror')).toBeNull();expect(svg).toContain('dataset-hash');expect(svg).toContain('assumptions only')
 expect(container.textContent).toContain('—')
 expect([...doc.querySelectorAll('text')].map(n=>n.textContent).join('')).toContain(label)
})
it('has an explicit empty-state heatmap',()=>{
 const view=render(<RobustnessHeatmap scenarios={[]} rows={[]} controls={[]} model="M3" metric="mean_absolute_difference" maximum={0} title="Empty"/>)
 expect(view.getByRole('status').textContent).toContain('Нет рассчитанных сценариев')
})
