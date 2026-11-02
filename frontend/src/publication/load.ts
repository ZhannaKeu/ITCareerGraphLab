import { PublicSession } from './session'
import type { Published } from './model'
type Fetcher=(url:string)=>Promise<{ok:boolean;text:()=>Promise<string>;json:()=>Promise<any>}>
export async function loadPublished(fetcher:Fetcher,base:string){
 const [dataResponse,manifestResponse]=await Promise.all([fetcher(base+'data/published.json'),fetcher(base+'data/manifest.json')])
 if(!dataResponse.ok||!manifestResponse.ok)throw Error('Published dataset assets are unavailable')
 const text=await dataResponse.text(),manifest=await manifestResponse.json(),hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text)))].map(n=>n.toString(16).padStart(2,'0')).join('')
 if(hash!==manifest.sha256)throw Error('Published dataset integrity check failed')
 const data=JSON.parse(text) as Published
 if(data.schema!=='career-pages-data-1'||data.dataset.id!==manifest.dataset||data.dashboard.counts.profiles!==14||data.graph.edges.length!==51)throw Error('Invalid published dataset schema')
 return new PublicSession(data)
}
