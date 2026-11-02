import { PUBLIC_MODE } from './publication/mode'
import { downloadBlob } from './lib/export'
import type { Params } from './types'
const base = PUBLIC_MODE ? '' : import.meta.env.VITE_API_URL ?? ''
async function localPublic<T>(path:string,body?:unknown){const {publicRequest}=await import('./publication/client');return publicRequest<T>(path,body)}
async function publicDownload(path:string,body?:unknown){const file=await localPublic<{body:string;mediaType:string;filename:string}>(path,body);downloadBlob(new Blob([file.body],{type:file.mediaType}),file.filename)}
export async function api<T>(path:string, body?:unknown):Promise<T> {
  if(PUBLIC_MODE)return localPublic<T>(path,body)
  const response = await fetch(`${base}/api${path}`, body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
  if(!response.ok){ const error = await response.json().catch(()=>({detail:response.statusText})); throw new Error(typeof error.detail === 'string' ? error.detail : JSON.stringify(error.detail)) }
  return response.json()
}
export async function downloadCSV(params:Params) {
  if(PUBLIC_MODE)return publicDownload('/experiments/export',params)
  const response = await fetch(`${base}/api/experiments/export`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(params)})
  if(!response.ok) {const e=await response.json();throw new Error(typeof e.detail==='string'?e.detail:JSON.stringify(e.detail))}
  const url=URL.createObjectURL(await response.blob()); const a=document.createElement('a');a.href=url;a.download='career-transitions.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)
}
export async function downloadExperiment2(runId:string,filename:string){
 if(PUBLIC_MODE)return publicDownload(`/experiments/experiment2/${encodeURIComponent(runId)}/exports/${encodeURIComponent(filename)}`)
 const response=await fetch(`${base}/api/experiments/experiment2/${encodeURIComponent(runId)}/exports/${encodeURIComponent(filename)}`)
 if(!response.ok){const e=await response.json().catch(()=>({detail:response.statusText}));throw new Error(typeof e.detail==='string'?e.detail:JSON.stringify(e.detail))}
 const url=URL.createObjectURL(await response.blob());const link=document.createElement('a');link.href=url;link.download=filename;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)
}
export async function downloadExperiment3(runId:string,filename:string){
 if(PUBLIC_MODE)return publicDownload(`/experiments/experiment3/${encodeURIComponent(runId)}/exports/${encodeURIComponent(filename)}`)
 const response=await fetch(`${base}/api/experiments/experiment3/${encodeURIComponent(runId)}/exports/${encodeURIComponent(filename)}`)
 if(!response.ok){const e=await response.json().catch(()=>({detail:response.statusText}));throw new Error(typeof e.detail==='string'?e.detail:JSON.stringify(e.detail))}
 const url=URL.createObjectURL(await response.blob());const link=document.createElement('a');link.href=url;link.download=filename;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)
}
