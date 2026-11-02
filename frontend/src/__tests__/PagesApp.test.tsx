import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from '../App'
vi.mock('../publication/mode',async original=>({...await original<typeof import('../publication/mode')>(),PUBLIC_MODE:true}))
vi.mock('../api',()=>({api:vi.fn(),downloadCSV:vi.fn(),downloadExperiment2:vi.fn(),downloadExperiment3:vi.fn()}))
vi.mock('recharts',()=>({ResponsiveContainer:()=>null,BarChart:()=>null,Bar:()=>null,CartesianGrid:()=>null,XAxis:()=>null,YAxis:()=>null,Tooltip:()=>null,Legend:()=>null}))
import { api } from '../api'
afterEach(()=>{cleanup();window.location.hash='';vi.restoreAllMocks()})
it('opens a public hash deep link and exposes provenance with no revision controls or API link',async()=>{
 window.location.hash='#/versions'
 const dashboard={version_id:'v',label:'public',is_demo:false,counts:{skills:1,roles:2,profiles:2,edges:0,transitions:2},categories:['Core'],quality:{errors:[],warnings:[],manifest:{}},data_provenance:{verification_counts:{},record_hash:'hash',root_id:'v'}}
 const graph={version_id:'v',nodes:[{id:'a',name:'A',category:'Core',description:''}],edges:[]}
 vi.mocked(api).mockImplementation(async(path:string)=>path.startsWith('/dashboard')?dashboard:path.startsWith('/datasets')?[{id:'v',kind:'original',label:'public'}]:path.startsWith('/skills/graph')?graph:path.startsWith('/profiles')?[{id:'backend:junior',role:'backend',level:'Junior'},{id:'fullstack:middle',role:'fullstack',level:'Middle'}]:path.includes('/records')?{total:0,records:[]}:path.includes('graph-configurations')?{available:true,configurations:[]}:path.includes('/experiments/compare')?undefined:[])
 const view=render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><App/></QueryClientProvider>)
 expect(await view.findByText('Публичный набор — только для чтения')).toBeTruthy()
 expect(view.getByRole('heading',{name:'Data & Provenance · опубликованный снимок'})).toBeTruthy()
 expect(view.queryByRole('button',{name:'Сохранить новую версию'})).toBeNull()
 expect(view.queryByRole('link',{name:/API Docs/})).toBeNull()
 fireEvent.click(view.getByRole('button',{name:'Данные и качество'}))
 await waitFor(()=>expect(window.location.hash).toBe('#/data'))
 expect(view.getByText('Вычисления выполняются в браузере · без регистрации и сервера')).toBeTruthy()
})
