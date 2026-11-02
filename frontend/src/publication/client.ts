let worker:Worker|undefined;let sequence=0
const pending=new Map<number,{resolve:(v:any)=>void;reject:(e:Error)=>void}>()
export function publicRequest<T>(path:string,body?:unknown):Promise<T>{
 if(!worker){worker=new Worker(new URL('./worker.ts',import.meta.url),{type:'module'});worker.onmessage=e=>{const p=pending.get(e.data.id);if(!p)return;pending.delete(e.data.id);if(e.data.error)p.reject(new Error(e.data.error));else p.resolve(e.data.value)};worker.onerror=()=>{for(const p of pending.values())p.reject(new Error('Public calculation worker failed'));pending.clear();worker?.terminate();worker=undefined}}
 return new Promise<T>((resolve,reject)=>{const id=++sequence;pending.set(id,{resolve,reject});worker!.postMessage({id,path,body})})
}
