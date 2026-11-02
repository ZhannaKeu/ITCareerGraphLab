import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Versions from '../pages/Versions'
import type { Dashboard, DatasetVersion, Params, ResearchRecord } from '../types'
vi.mock('recharts',()=>({ResponsiveContainer:()=> <div>Version chart</div>,BarChart:()=>null,Bar:()=>null,CartesianGrid:()=>null,XAxis:()=>null,YAxis:()=>null,Tooltip:()=>null,Legend:()=>null}))
const original='a'.repeat(64),corrected='b'.repeat(64)
const meta={parent_id:null,root_id:original,kind:'original' as const,author:'Owner',reason:'Initial disclosure',record_hash:'c'.repeat(64),disclosure:{independently_verified:false},verification_counts:{requirement:{Unverified:1}}}
const data:Dashboard={version_id:original,label:'input',is_demo:false,counts:{skills:1,edges:0,profiles:2,roles:2,transitions:2},categories:[],quality:{errors:[],warnings:[],manifest:{}},data_provenance:meta}
const datasets:DatasetVersion[]=[{id:original,label:'Original',is_demo:false,imported_at:'2026-10-31',...meta},{id:corrected,label:'Corrected',is_demo:false,imported_at:'2026-10-31',...meta,parent_id:original,kind:'corrected'}]
const record:ResearchRecord={entity:'requirement',key:['fullstack:middle','skill','sql'],data:{required_level:3},status:'Unverified',origin:{kind:'imported',declared_origin:'AI-assisted'},reviewer:null,evidence:null,verification_note:null}
const graph={version_id:original,nodes:[{id:'sql',name:'SQL',category:'Data',description:''}],edges:[]}
const profiles=[{id:'backend:junior',role:'backend',level:'Junior'},{id:'fullstack:middle',role:'fullstack',level:'Middle'}]
const params:Params={source_profile:'backend:junior',target_profile:'fullstack:middle',version_id:original,minimum_prerequisite_level:1,lambda:.5,algorithm:'kahn',weight_source:'role_skill_weights.csv',excluded_edges:[],included_edges:[],verification_scope:'all'}
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
function mount(onVersion=vi.fn()) {const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});return {view:render(<QueryClientProvider client={client}><Versions data={data} datasets={datasets} graph={graph} profiles={profiles} params={params} onVersion={onVersion}/></QueryClientProvider>),onVersion}}
function mockFetch(){const fetcher=vi.fn(async(url:unknown,options?:RequestInit)=>{const path=String(url);const response=options?.method==='POST'?{version_id:corrected}:path.includes('/history')?[]:{total:1,records:[record]};return {ok:true,json:async()=>response}});vi.stubGlobal('fetch',fetcher);return fetcher}
it('creates a reviewed child snapshot with explicit author, evidence and parent version',async()=>{
 const fetcher=mockFetch();const {view,onVersion}=mount()
 fireEvent.click(await view.findByRole('button',{name:'Редактировать / проверить'}))
 expect(view.getByText(/текущий статус: Unverified/)).toBeTruthy()
 fireEvent.change(view.getByRole('combobox',{name:'Требуемый уровень'}),{target:{value:'4'}})
 fireEvent.change(view.getByRole('combobox',{name:'Новый статус проверки'}),{target:{value:'Expert Verified'}})
 fireEvent.change(view.getByRole('textbox',{name:'Рецензент'}),{target:{value:'Domain expert'}})
 fireEvent.change(view.getByRole('textbox',{name:'Основание проверки'}),{target:{value:'Expert assessment E-01'}})
 fireEvent.change(view.getByRole('textbox',{name:'Автор изменения'}),{target:{value:'Researcher'}})
 fireEvent.change(view.getByRole('textbox',{name:'Название новой версии'}),{target:{value:'Reviewed SQL'}})
 fireEvent.change(view.getByRole('textbox',{name:'Причина изменения'}),{target:{value:'Corrected requirement after assessment'}})
 fireEvent.click(view.getByRole('button',{name:'Сохранить новую версию'}))
 await waitFor(()=>expect(onVersion).toHaveBeenCalledWith(corrected))
 const call=fetcher.mock.calls.find(([,options])=>options?.method==='POST')!
 const body=JSON.parse(String(call[1]?.body))
 expect(body.parent_id).toBe(original)
 expect(body.changes[0]).toMatchObject({entity:'requirement',key:record.key,required_level:4,verification:{status:'Expert Verified',reviewer:'Domain expert',evidence:'Expert assessment E-01'}})
})
it('filters reviewed records explicitly and prevents comparing identical versions',async()=>{
 const fetcher=mockFetch();const {view}=mount()
 expect(view.getByRole('button',{name:'Сравнить версии'}).hasAttribute('disabled')).toBe(true)
 fireEvent.change(view.getByRole('combobox',{name:'Фильтр верификации'}),{target:{value:'Source Verified'}})
 await waitFor(()=>expect(fetcher.mock.calls.some(([url])=>String(url).includes('status=Source%20Verified'))).toBe(true))
 fireEvent.change(view.getByRole('combobox',{name:'Версия B'}),{target:{value:corrected}})
 expect(view.getByRole('button',{name:'Сравнить версии'}).hasAttribute('disabled')).toBe(false)
})
