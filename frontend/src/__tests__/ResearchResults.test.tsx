import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ResearchResults from '../pages/ResearchResults'
import Heatmap from '../components/Heatmap'
import type { Params, Profile, ResearchRun, Result } from '../types'
vi.mock('recharts',()=>({ResponsiveContainer:()=> <div>Analysis chart</div>,BarChart:()=>null,Bar:()=>null,LineChart:()=>null,Line:()=>null,CartesianGrid:()=>null,XAxis:()=>null,YAxis:()=>null,Tooltip:()=>null,Legend:()=>null}))
const params:Params={source_profile:'s',target_profile:'t',version_id:'v',minimum_prerequisite_level:1,lambda:.5,algorithm:'kahn',weight_source:'role_skill_weights.csv',excluded_edges:[],included_edges:[],verification_scope:'all'}
const profiles:Profile[]=[{id:'s',role:'S',level:'Junior'},{id:'t',role:'T',level:'Middle'}]
const result={source_profile:'s',target_profile:'t',M1:2,M2:1,M3:1.5} as Result
const provenance={dataset:'v',record_hash:'h',run_id:'research-run',is_demo:false,implementation:'1.1.0',warning:'Unverified',parameters:params}
const run:ResearchRun={provenance:{...provenance,parameters:{experiment:params,taus:[1],lambdas:[.5],top_k:3},analysis_version:'1.0.0'},baseline:{results:[result],provenance:{...provenance,run_id:'batch'}},max_extra:[{...result,extra:.5}],distribution:[{label:'= 0',lower:0,upper:0,count:0},{label:'0–0.5',lower:0,upper:.5,count:1}],ranking:[{source_profile:'s',spearman:null,top_k:1,top_m2:['t'],top_m3:['t'],overlap:1,targets:[{target_profile:'t',M2:1,M3:1.5,rank_m2:1,rank_m3:1,rank_shift:0}]}],sensitivity:[{tau:1,lambda:.5,run_id:'sweep-batch',pairs:1,affected_pairs:1,mean_extra:.5,max_extra:.5,mean_M2:1,mean_M3:1.5,mean_spearman:null,undefined_spearman_sources:1,mean_top_k_overlap:1}],summary:{pairs:1,affected_pairs:1,mean_extra:.5,max_extra:.5,mean_M2:1,mean_M3:1.5,mean_spearman:null,undefined_spearman_sources:1,mean_top_k_overlap:1}}
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
it('runs a pinned research request and renders saved analyses with exports',async()=>{
 const fetcher=vi.fn(async(_url:unknown,options?:RequestInit)=>({ok:true,json:async()=>options?.method==='POST'?run:[]}));vi.stubGlobal('fetch',fetcher)
 const client=new QueryClient({defaultOptions:{queries:{retry:false}}});const onPair=vi.fn()
 const view=render(<QueryClientProvider client={client}><ResearchResults params={params} profiles={profiles} onPair={onPair}/></QueryClientProvider>)
 fireEvent.change(view.getByRole('textbox',{name:'Значения tau'}),{target:{value:'1'}})
 fireEvent.change(view.getByRole('textbox',{name:'Значения lambda'}),{target:{value:'0.5'}})
 fireEvent.click(view.getByRole('button',{name:'Запустить массовый протокол'}))
 expect(await view.findByText('RUN research-run')).toBeTruthy()
 const post=fetcher.mock.calls.find(([,opt])=>opt?.method==='POST')!
 expect(JSON.parse(String(post[1]?.body))).toMatchObject({experiment:{version_id:'v',algorithm:'kahn'},taus:[1],lambdas:[.5]})
 expect(view.getByRole('button',{name:'Экспорт distance-heatmap-M3 SVG'})).toBeTruthy()
 expect(view.getByRole('button',{name:'Экспорт sensitivity-grid PNG'})).toBeTruthy()
 fireEvent.click(view.getByRole('button',{name:'Открыть переход'}));expect(onPair).toHaveBeenCalledWith('s','t',params)
 expect(view.getByRole('img',{name:/Направленная матрица M3/})).toBeTruthy()
})
it('shows directed heatmap cells and excludes diagonal rather than inventing zero',()=>{
 const view=render(<Heatmap results={[result]} profiles={profiles} metric="M3"/>)
 expect(view.getByLabelText('s → t: 1.5')).toBeTruthy()
 expect(view.getByLabelText('t → s: не рассчитывается')).toBeTruthy()
 expect(view.getByLabelText('s → s: не рассчитывается')).toBeTruthy()
})
