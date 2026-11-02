import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from '../App'
vi.mock('@xyflow/react',async importOriginal=>({...await importOriginal<typeof import('@xyflow/react')>(),ReactFlow:()=> <div>Interactive Flow</div>,Background:()=>null,Controls:()=>null,MiniMap:()=>null}))
vi.mock('recharts',()=>({ResponsiveContainer:()=> <div>Research chart</div>,BarChart:()=>null,Bar:()=>null,CartesianGrid:()=>null,XAxis:()=>null,YAxis:()=>null,Tooltip:()=>null,Legend:()=>null}))
const graph={version_id:'v1',nodes:[{id:'a',name:'Skill A',category:'Core',description:'Alias A'},{id:'b',name:'Skill B',category:'Core',description:''}],edges:[{source:'a',target:'b'}]}
const profiles=['backend','fullstack'].flatMap(role=>['junior','middle'].map(level=>({id:`${role}:${level}`,role,level:level==='junior'?'Junior':'Middle'})))
const dashboard={version_id:'v1',label:'test',is_demo:false,counts:{skills:2,edges:1,profiles:4,roles:2,transitions:12},quality:{errors:[],warnings:[],manifest:{}},categories:['Core']}
const result={source_profile:'backend:junior',target_profile:'fullstack:middle',M1:1,M2:.5,M3:.75,direct_score:.5,prerequisite_burden:.5,weighted_prerequisite_burden:.25,missing_skills:['b'],prerequisite_skills:['a'],learning_order:['a','b'],details:[],unknown_source_skills:['a'],unknown_target_skills:[],fallback_weight_skills:[],scenario:'conservative'}
const provenance={dataset:'v1',run_id:'test-run-1',parameters:{},is_demo:false}
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
function mount(){const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});return render(<QueryClientProvider client={client}><App/></QueryClientProvider>)}
function mockApi(fail=false){vi.stubGlobal('fetch',vi.fn(async(url:unknown)=>{const path=String(url);const data=path.includes('/datasets')?[]:path.includes('/dashboard')?dashboard:path.includes('/skills/graph')?graph:path.includes('/profiles')?profiles:path.includes('/experiments/batch')?{results:[result],provenance}:{result,provenance};return {ok:!fail,status:fail?503:200,statusText:'Unavailable',json:async()=>fail?{detail:'Database unavailable'}:data}}))}
describe('Research workspace integration',()=>{
 it('loads API data, searches skills and calculates a batch from controls',async()=>{
  mockApi();const view=mount()
  await waitFor(()=>expect(view.getByText('Исследовательские данные · 2 навыков')).toBeTruthy())
  fireEvent.click(view.getByRole('button',{name:'Граф навыков'}))
  fireEvent.change(view.getByRole('textbox',{name:'Поиск навыка'}),{target:{value:'Skill B'}})
  fireEvent.click(view.getByRole('button',{name:'Skill B'}))
  expect(view.getByRole('heading',{name:'Skill B'})).toBeTruthy()
  expect(view.getByRole('button',{name:'Skill A'})).toBeTruthy()
  fireEvent.click(view.getByRole('button',{name:'Карьерные переходы'}))
  expect(view.getByRole('combobox',{name:'Исходный профиль: профессия'})).toBeTruthy()
  expect(view.getByRole('combobox',{name:'Целевой профиль: уровень'})).toBeTruthy()
  fireEvent.click(view.getByRole('button',{name:'Эксперименты'}))
  fireEvent.click(await view.findByRole('button',{name:'Рассчитать все переходы'}))
  await waitFor(()=>expect(view.getByText('1 результатов')).toBeTruthy())
  expect(view.getAllByText('RUN test-run-1').length).toBe(2)
  expect(fetch).toHaveBeenCalledWith('/api/experiments/batch',expect.objectContaining({method:'POST'}))
 })
 it('reports database failures instead of showing synthetic results',async()=>{
  mockApi(true);const view=mount()
  expect(await view.findByText('Database unavailable')).toBeTruthy()
  expect(view.getByRole('button',{name:'Повторить подключение'})).toBeTruthy()
  expect(view.queryByText('Interactive Flow')).toBeNull()
 })
})
