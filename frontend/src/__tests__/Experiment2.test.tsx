import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Experiment2 from '../pages/Experiment2'
import ParameterHeatmap from '../components/ParameterHeatmap'
import type { Experiment2Scenario } from '../types'
const taus=[1,2,3,4],lambdas=[0,.25,.5,1,2]
const scenarios=(['G1','G2','G3'] as const).flatMap(graph=>taus.flatMap(tau=>lambdas.map(lambda=>({graph,tau,lambda,scenario_run_id:`${graph}-${tau}-${lambda}`,configuration_hash:'c'.repeat(64),metrics:{pairs:182,nodes:71,edges:51,prerequisite_deficit_pairs:1,mean_burden:tau,max_burden:tau,changed_pairs:lambda?1:0,mean_score_change:tau*lambda,max_absolute_score_change:tau*lambda,mean_M2:2,mean_M3:2+tau*lambda,mean_extra:tau*lambda,max_extra:tau*lambda,weighted_extra_pairs:lambda?1:0,mean_spearman:lambda?null:1,mean_kendall_tau_b:lambda?null:1,undefined_spearman_sources:lambda?14:0,undefined_kendall_tau_b_sources:lambda?14:0,mean_top3_overlap:1,mean_top5_overlap:1,top3_replaced_targets:0,top5_replaced_targets:0,top3_membership_changed_sources:0,top5_membership_changed_sources:0,top3_order_changed_sources:0,top5_order_changed_sources:0},results:[]}))))
const run={scenario_count:60,scenarios,rankings:[],graph_rankings:[],graph_comparisons:[],configurations:Object.fromEntries(['G1','G2','G3'].map(name=>[name,{name,configuration_hash:'c'.repeat(64)}])),provenance:{run_id:'experiment2-test',dataset:'version',source_data_hash:'s'.repeat(64),record_hash:'r'.repeat(64),implementation:'1.1.0',analysis_version:'experiment2-sensitivity-1.0.0',parameters:{taus,lambdas,experiment:{algorithm:'kahn'}}}}
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
it('submits only the pinned version, renders sixty scenarios and seven exportable figures, restores saved results',async()=>{
 const fetcher=vi.fn(async(url:unknown,options?:RequestInit)=>({ok:true,json:async()=>String(url).includes('graph-configurations')?{available:true}:options?.method==='POST'||String(url).includes('/runs/experiment2-test')?run:[{id:'experiment2-test',kind:'experiment2',created_at:'2026-10-31'}]}));vi.stubGlobal('fetch',fetcher)
 const client=new QueryClient({defaultOptions:{queries:{retry:false}}})
 const view=render(<QueryClientProvider client={client}><Experiment2 versionId="version"/></QueryClientProvider>)
 await view.findByRole('option',{name:/experiment2-test/})
 fireEvent.change(view.getByLabelText('Сохранённый Experiment 2'),{target:{value:'experiment2-test'}})
 expect(await view.findByText('EXPERIMENT 2 RUN experiment2-test')).toBeTruthy()
 expect(view.container.querySelectorAll('tbody')[1].querySelectorAll('tr').length).toBe(60)
 expect(view.container.querySelectorAll('svg[data-export-figure]').length).toBe(7)
 expect(view.container.querySelectorAll('circle').length).toBe(15)
 fireEvent.change(view.getByLabelText('Tau Experiment 2'),{target:{value:'4'}})
 expect(view.container.querySelector('[data-series="G1"] circle:last-child')?.getAttribute('data-value')).toBe('8')
 for(const name of ['summary.csv','scenarios.csv','rankings.csv','results.json'])expect(view.getByRole('button',{name:`experiment2-${name} ↓`})).toBeTruthy()
 fireEvent.click(view.getByRole('button',{name:'Рассчитать Experiment 2 · 60 сценариев'}))
 await view.findByText('EXPERIMENT 2 RUN experiment2-test')
 const post=fetcher.mock.calls.find(([,opts])=>opts?.method==='POST')
 expect(JSON.parse(String(post?.[1]?.body))).toEqual({version_id:'version'})
})
it('heatmap marks undefined correlations explicitly without substituting zero',()=>{
 const {container}=render(<ParameterHeatmap scenarios={scenarios as Experiment2Scenario[]} graph="G1" taus={[1]} lambdas={[0,.25]} metric="mean_spearman" maximum={1}/>)
 expect(container.querySelector('[data-lambda="0.25"]')?.getAttribute('aria-label')).toContain('нет определённого значения')
 expect(container.querySelector('[data-lambda="0.25"] text')?.textContent).toBe('—')
 expect(container.querySelector('[data-lambda="0"] text')?.textContent).toBe('1')
})
