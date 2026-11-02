import { loadPublished } from './load'
import type { PublicSession } from './session'
let session:Promise<PublicSession>|undefined
let queue=Promise.resolve()
self.onmessage=(event:MessageEvent)=>{const {id,path,body}=event.data;queue=queue.then(async()=>{try{session??=loadPublished(fetch,import.meta.env.BASE_URL).catch(error=>{session=undefined;throw error});const value=await(await session).request(path,body);self.postMessage({id,value})}catch(e){self.postMessage({id,error:(e as Error).message})}})}
