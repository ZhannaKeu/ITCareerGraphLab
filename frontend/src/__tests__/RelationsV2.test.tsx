import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Skills from '../pages/Skills'
import RelationImpact from '../pages/RelationImpact'
import type { Graph, GraphAvailability, Params, Profile } from '../types'
vi.mock('@xyflow/react',async importOriginal=>({...await importOriginal<typeof import('@xyflow/react')>(),ReactFlow:()=> <div>V2 flow</div>,Background:()=>null,Controls:()=>null,MiniMap:()=>null}))
vi.mock('recharts',()=>({ResponsiveContainer:()=> <div>Chart</div>,BarChart:()=>null,Bar:()=>null,LineChart:()=>null,Line:()=>null,CartesianGrid:()=>null,XAxis:()=>null,YAxis:()=>null,Tooltip:()=>null,Legend:()=>null}))
const graph:Graph={version_id:'v',nodes:[{id:'a',name:'Skill A',description:'',category:'Core'},{id:'b',name:'Skill B',description:'',category:'Core'},{id:'c',name:'Skill C',description:'',category:'Core'}],edges:[{source:'a',target:'b',edge_id:'required-edge',source_row:15,relation_type:'Required',min_level:null,classification_source:'AI-assisted preliminary review',classification_verification_status:'Unverified',verification_status:'Unverified'},{source:'b',target:'c',edge_id:'related-edge',source_row:14,relation_type:'Related',min_level:null,classification_source:'AI-assisted preliminary review',classification_verification_status:'Unverified',verification_status:'Unverified'}]}
const availability:GraphAvailability={version_id:'v',available:true,configurations:[]}
const params:Params={source_profile:'s',target_profile:'t',version_id:'v',minimum_prerequisite_level:1,lambda:.5,algorithm:'kahn',weight_source:'role_skill_weights.csv',excluded_edges:[],included_edges:[],verification_scope:'all',graph_configuration:'G2'}
const profiles:Profile[]=[{id:'s',role:'S',level:'Junior'},{id:'t',role:'T',level:'Middle'}]
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
it('selects G2, filters relation types and inspects Unverified null min_level',()=>{
 const onConfiguration=vi.fn();const view=render(<Skills graph={graph} availability={availability} onConfiguration={onConfiguration}/>)
 fireEvent.change(view.getByRole('combobox',{name:'Конфигурация графа пререквизитов'}),{target:{value:'G2'}})
 expect(onConfiguration).toHaveBeenCalledWith('G2')
 fireEvent.change(view.getByRole('combobox',{name:'Тип зависимости'}),{target:{value:'Required'}})
 expect(view.getByText('3 vertices / 1 edges')).toBeTruthy()
 fireEvent.change(view.getByRole('combobox',{name:'Связь для инспекции'}),{target:{value:'required-edge'}})
 expect(view.getByRole('heading',{name:'Инспектор связи'})).toBeTruthy()
 expect(view.getByText('Не установлен')).toBeTruthy()
 expect(view.getAllByText(/AI-assisted preliminary review/).length).toBeGreaterThan(0)
 expect(view.getByText('Unverified',{selector:'span.verification-badge'})).toBeTruthy()
 fireEvent.click(view.getByRole('button',{name:'Локальный граф'}))
 expect(view.getByText('0 vertices / 0 edges')).toBeTruthy()
 fireEvent.change(view.getByRole('textbox',{name:'Поиск навыка'}),{target:{value:'Skill A'}})
 fireEvent.click(view.getByRole('button',{name:'Skill A'}))
 expect(view.getByRole('heading',{name:'Инспектор навыка'})).toBeTruthy()
 expect(view.getByText('2 vertices / 1 edges')).toBeTruthy()
})
it('submits a controlled all-graphs request pinned to the version and common parameters',async()=>{
 const fetcher=vi.fn(async(url:unknown,options?:RequestInit)=>({ok:!options?.method,json:async()=>options?.method?{detail:'Isolated test: no calculation needed'}:String(url).includes('graph-configurations')?{available:true}:[]}))
 vi.stubGlobal('fetch',fetcher)
 const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}})
 const view=render(<QueryClientProvider client={client}><RelationImpact params={params} profiles={profiles}/></QueryClientProvider>)
 await waitFor(()=>expect(view.getByRole('button',{name:'Рассчитать G1/G2/G3 · 182 перехода'}).hasAttribute('disabled')).toBe(false))
 fireEvent.click(view.getByRole('button',{name:'Рассчитать G1/G2/G3 · 182 перехода'}))
 await waitFor(()=>expect(fetcher.mock.calls.some(([,o])=>o?.method==='POST')).toBe(true))
 const post=fetcher.mock.calls.find(([,o])=>o?.method==='POST')!
 expect(post[0]).toBe('/api/experiments/relation-impact')
 const body=JSON.parse(String(post[1]?.body))
 expect(body.experiment.version_id).toBe('v');expect(body.experiment.algorithm).toBe('kahn');expect(body.experiment.lambda).toBe(.5)
 expect(body.experiment).not.toHaveProperty('graph_configuration')
 expect(body.taus).toEqual([1,2,3]);expect(body.lambdas).toEqual([0,.5,1])
 expect(await view.findByText('Isolated test: no calculation needed')).toBeTruthy()
})
it('does not silently allow overrides for fixed G1/G2/G3 comparison',()=>{
 vi.stubGlobal('fetch',vi.fn(async(url:unknown)=>({ok:true,json:async()=>String(url).includes('graph-configurations')?{available:true}:[]})))
 const client=new QueryClient({defaultOptions:{queries:{retry:false}}})
 const view=render(<QueryClientProvider client={client}><RelationImpact params={{...params,excluded_edges:[['a','b']]}} profiles={profiles}/></QueryClientProvider>)
 expect(view.getByRole('button',{name:'Рассчитать G1/G2/G3 · 182 перехода'}).hasAttribute('disabled')).toBe(true)
 expect(view.getByText(/Удалите дополнительные интервенции/)).toBeTruthy()
})
