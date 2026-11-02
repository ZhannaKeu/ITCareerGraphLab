import { BrowserEngine } from './engine'
import type { Published, Wire } from './model'
import { csv, experimentFile } from './exports'
export class PublicSession {
 readonly engine:BrowserEngine
 constructor(data:Published){const freeze=(value:any)=>{if(value&&typeof value==='object'&&!Object.isFrozen(value)){Object.freeze(value);for(const child of Object.values(value))freeze(child)}};freeze(data);this.engine=new BrowserEngine(data)}
 async request(path:string,body?:Wire):Promise<any>{
  const data=this.engine.data,url=new URL(path,'https://public.invalid'),p=url.pathname,q=url.searchParams,version=q.get('version_id')??body?.version_id
  if(version&&version!==data.dataset.id)throw Error('Only the published dataset is available')
  if(p==='/versions'&&body)throw Error('Public reference data is read-only. Revisions and verification require the local installation.')
  if(p==='/datasets')return [data.dataset]
  if(p==='/dashboard')return data.dashboard
  if(p==='/profiles')return data.profiles
  if(p==='/graph-configurations')return {version_id:data.dataset.id,available:true,configurations:Object.values(data.configurations)}
  if(p==='/skills/graph'){const name=q.get('configuration');if(name!==null&&!Object.hasOwn(data.configurations,name))throw Error('Unknown graph configuration');const config=name?data.configurations[name]:null,ids=config?new Set(config.included_edge_ids):null;return {...data.graph,configuration:config,edges:data.graph.edges.filter((e:Wire)=>!ids||ids.has(e.edge_id))}}
  if(p.startsWith('/data/')){const filename=decodeURIComponent(p.slice(6));if(!Object.hasOwn(data.source_rows,filename))throw Error('Unknown published source file');const offset=Number(q.get('offset')??0),limit=Number(q.get('limit')??100);this.pagination(offset,limit,500);return {version_id:data.dataset.id,source_version:data.dataset.id,content_kind:'immutable_original_csv_rows',rows:data.source_rows[filename].slice(offset,offset+limit)}}
  if(p.startsWith('/versions/')){const match=p.match(/^\/versions\/([^/]+)\/(records|history)$/);if(!match||match[1]!==data.dataset.id)throw Error('Unknown published version');if(match[2]==='history')return data.history;const offset=Number(q.get('offset')??0),limit=Number(q.get('limit')??50);this.pagination(offset,limit,200);const rows=data.records.filter((r:Wire)=>(!q.get('entity')||r.entity===q.get('entity'))&&(!q.get('status')||r.status===q.get('status')));return {total:rows.length,records:rows.slice(offset,offset+limit)}}
  if(p==='/runs'){const offset=Number(q.get('offset')??0),limit=Number(q.get('limit')??50);this.pagination(offset,limit,200);return [...this.engine.runs.values()].reverse().slice(offset,offset+limit).map(r=>({id:r.provenance.run_id,version_id:data.dataset.id,kind:r.provenance.experiment_kind,parameters:r.provenance.parameters,created_at:this.engine.createdAt.get(r.provenance.run_id)}))}
  if(p.startsWith('/runs/')){const run=this.engine.runs.get(p.slice(6));if(!run)throw Error('Run not present in this tab. Reloading clears in-memory experiments.');return run}
  const exportMatch=p.match(/^\/experiments\/(experiment[23])\/([^/]+)\/exports\/([^/]+)$/)
  if(exportMatch){const run=this.engine.runs.get(exportMatch[2]);if(!run||run.provenance.experiment_kind!==exportMatch[1])throw Error('Run not present in this tab');return experimentFile(run,decodeURIComponent(exportMatch[3]))}
  if(!body)throw Error('Unsupported public operation')
  if(p==='/experiments/compare')return this.engine.batch(body,'pair')
  if(p==='/experiments/batch')return this.engine.batch(body)
  if(p==='/experiments/research')return this.engine.research(body)
  if(p==='/experiments/relation-impact')return this.engine.relationImpact(body)
  if(p==='/experiments/experiment2'||p==='/experiments/experiment3'){if(Object.keys(body).some(k=>k!=='version_id'))throw Error('Fixed protocol accepts version_id only');return p.endsWith('experiment2')?this.engine.experiment2(body.version_id):this.engine.experiment3(body.version_id)}
  if(p==='/experiments/export'){const run=await this.engine.batch(body);return {filename:'career-transitions.csv',mediaType:'text/csv;charset=utf-8',body:csv(run.results.map((r:Wire)=>({...r,unknown_source_count:r.unknown_source_skills.length,unknown_target_count:r.unknown_target_skills.length,fallback_weight_count:r.fallback_weight_skills.length,dataset_version:data.dataset.id,run_id:run.provenance.run_id,record_hash:run.provenance.record_hash,export_provenance:JSON.stringify(run.provenance)})))}}
  throw Error('Administrative changes/version creation are unavailable in the read-only public edition')
 }
 private pagination(offset:number,limit:number,max:number){if(!Number.isInteger(offset)||offset<0||!Number.isInteger(limit)||limit<1||limit>max)throw Error('Invalid pagination')}
}
