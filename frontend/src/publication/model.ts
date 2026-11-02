/** Semantic port of backend/app/research/{models,graph}.py. No network or storage. */
import type { Params, Result } from '../types'
export type Wire = Record<string, any> // existing Python JSON contracts, validated at the public boundary
export type Published = Wire & {model_summation:'legacy'|'compensated'; requirements:{profile_id:string;skill_id:string|null;group_id:string|null;required_level:number|null}[];weights:{source:string;role:string;skill_id:string;weight:number}[]}
export const lex=(a:string,b:string)=>a<b?-1:a>b?1:0
export function sum(values:number[],compensated=false){let total=0,c=0;for(const x of values){const t=total+x;if(compensated)c+=Math.abs(total)>=Math.abs(x)?(total-t)+x:(x-t)+total;total=t}return total+c}
export function fsum(values:number[]){const partials:number[]=[];for(let x of values){let i=0;for(let y of partials){if(Math.abs(x)<Math.abs(y))[x,y]=[y,x];const hi=x+y,lo=y-(hi-x);if(lo)partials[i++]=lo;x=hi}partials.length=i;partials.push(x)}return partials.reduceRight((a,b)=>a+b,0)}
export const mean=(values:number[])=>values.length?fsum(values)/values.length:null
export const canonical=(v:any):string=>v===null?'null':Array.isArray(v)?'['+v.map(canonical).join(',')+']':typeof v==='object'?'{'+Object.keys(v).sort(lex).map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}':JSON.stringify(v)
export async function digest(v:any){const bytes=new TextEncoder().encode(canonical(v));return [...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(n=>n.toString(16).padStart(2,'0')).join('')}
export function topological(skills:string[],edges:[string,string][],algorithm='kahn'){
 const next=new Map(skills.slice().sort(lex).map(id=>[id,[] as string[]])),degree=new Map(skills.map(id=>[id,0]))
 for(const [a,b] of edges){if(!next.has(a)||!next.has(b))throw Error(`Unknown skill: ${a} → ${b}`);next.get(a)!.push(b);degree.set(b,degree.get(b)!+1)}
 for(const children of next.values())children.sort(lex)
 const ready=skills.filter(s=>degree.get(s)===0).sort(lex),kahn:string[]=[]
 while(ready.length){const node=ready.shift()!;kahn.push(node);for(const b of next.get(node)!){degree.set(b,degree.get(b)!-1);if(degree.get(b)===0){ready.push(b);ready.sort(lex)}}}
 if(kahn.length!==skills.length)throw Error('Prerequisite cycle')
 if(algorithm==='kahn')return kahn
 if(algorithm!=='dfs')throw Error('Unsupported algorithm')
 const seen=new Set<string>(),result:string[]=[]
 for(const root of skills.slice().sort(lex).reverse()){
  const stack:[string,boolean][]=[[root,false]]
  while(stack.length){const [node,expanded]=stack.pop()!;if(expanded)result.push(node);else if(!seen.has(node)){seen.add(node);stack.push([node,true]);for(const child of next.get(node)!.slice().reverse())if(!seen.has(child))stack.push([child,false])}}
 }return result.reverse()
}
export function validate(data:Published,input:Wire):Params{
 const allowed=['source_profile','target_profile','version_id','minimum_prerequisite_level','lambda','algorithm','weight_source','included_edges','excluded_edges','verification_scope','graph_configuration']
 if(Object.keys(input).some(k=>!allowed.includes(k)))throw Error('Unknown experiment parameter')
 const p={minimum_prerequisite_level:1,lambda:.5,algorithm:'kahn',weight_source:'skill_weights_by_role_final_v2.csv',included_edges:[],excluded_edges:[],verification_scope:'all',...input,source_profile:input.source_profile as string,target_profile:input.target_profile as string,version_id:input.version_id??data.dataset.id} as Params
 if(p.version_id!==data.dataset.id)throw Error('Only the published dataset version is available')
 const ids=data.profiles.map((r:Wire)=>r.id)
 if(!ids.includes(p.source_profile)||!ids.includes(p.target_profile)||p.source_profile===p.target_profile)throw Error('Choose two different published profiles')
 if(!Number.isFinite(p.minimum_prerequisite_level)||p.minimum_prerequisite_level<0||p.minimum_prerequisite_level>4||!Number.isFinite(p.lambda)||p.lambda<0||p.lambda>10)throw Error('Invalid tau/lambda')
 if(!['kahn','dfs'].includes(p.algorithm)||!['role_skill_weights.csv','skill_weights_by_role_final_v2.csv'].includes(p.weight_source))throw Error('Unknown algorithm or weight source')
 if(!['all','verified'].includes(p.verification_scope??''))throw Error('Unknown verification scope')
 if(p.verification_scope==='verified')throw Error('Published inputs are Unverified; verified-only coverage is unavailable, not zero gap')
 if(p.graph_configuration!=null&&!Object.hasOwn(data.configurations,p.graph_configuration))throw Error('Unknown graph configuration')
 for(const name of ['included_edges','excluded_edges'] as const){if(!Array.isArray(p[name])||p[name].length>10000||p[name].some(e=>!Array.isArray(e)||e.length!==2||e.some(v=>typeof v!=='string')))throw Error('Invalid edge overrides')}
 if(p.graph_configuration&&(p.included_edges.length||p.excluded_edges.length))throw Error('Named G1/G2/G3 are immutable; use Legacy for interventions')
 return p
}
export function calculate(data:Published,p:Params,sourceId=p.source_profile,targetId=p.target_profile,overlay:{unknown?:number;unit?:boolean;edges?:[string,string][]}={}):Result & Wire{
 const skills=data.graph.nodes.map((s:Wire)=>s.id).sort(lex) as string[]
 const original: [string,string][]=(p.graph_configuration?data.configurations[p.graph_configuration].edges:data.graph.edges).map((e:Wire)=>[e.from_skill??e.source,e.to_skill??e.target])
 const key=(e:[string,string])=>JSON.stringify(e),stored=new Set(original.map(key)),excluded=new Set(p.excluded_edges.map(key))
 if(p.excluded_edges.some(e=>!stored.has(key(e))))throw Error('Excluded edge does not exist')
 if(p.included_edges.some(e=>excluded.has(key(e))))throw Error('Edge cannot be both included and excluded')
 const edgeMap=new Map(original.filter(e=>!excluded.has(key(e))).map(e=>[key(e),e]));for(const e of p.included_edges)edgeMap.set(key(e),e)
 const edges=(overlay.edges??[...edgeMap.values()]).slice().sort((a,b)=>lex(a[0],b[0])||lex(a[1],b[1]))
 const order=topological(skills,edges,p.algorithm),parents=new Map(skills.map(s=>[s,[] as string[]]))
 for(const [a,b] of edges)parents.get(b)!.push(a)
 const source:Record<string,number|null>={},target:Record<string,number|null>={}
 for(const r of data.requirements)if(r.skill_id!==null){if(r.profile_id===sourceId)source[r.skill_id]=r.required_level;if(r.profile_id===targetId)target[r.skill_id]=r.required_level}
 if(overlay.unknown)for(const s of skills)if(source[s]==null)source[s]=overlay.unknown
 const role=data.profiles.find((r:Wire)=>r.id===targetId)?.role
 const weights:Record<string,number>={}
 for(const w of data.weights)if(w.source===p.weight_source&&w.role===role)weights[w.skill_id]=w.weight
 if(overlay.unit)for(const s of skills)weights[s]=1
 if(!Object.keys(weights).length)throw Error('No weights for target role')
 const unknownSource=new Set<string>(),unknownTarget=new Set<string>(),fallback=new Set<string>()
 const known=(s:string)=>{if(source[s]==null){unknownSource.add(s);return 0}return source[s]!}
 const required:Record<string,number>={},direct:Record<string,number>={}
 for(const s of Object.keys(target).sort(lex)){if(target[s]===null)unknownTarget.add(s);required[s]=target[s]??4;const d=Math.max(0,required[s]-known(s));if(d>0)direct[s]=d}
 const closure=new Set<string>(),stack=Object.keys(direct).sort(lex).reverse()
 while(stack.length){const node=stack.pop()!;for(const parent of parents.get(node)!){if(!closure.has(parent)){closure.add(parent);stack.push(parent)}}}
 const weight=(s:string)=>{if(!(s in weights))fallback.add(s);return weights[s]??1}
 const gap=(ds:Record<string,number>)=>sum(Object.keys(ds).sort(lex).map(s=>weight(s)*Math.max(0,ds[s])/4),data.model_summation==='compensated')
 const directScore=gap(direct),additional:Record<string,number>={}
 for(const s of [...closure].sort(lex)){const extra=Math.max(0,Math.max(0,p.minimum_prerequisite_level-known(s))-(direct[s]??0));if(extra>0)additional[s]=extra}
 const burden=gap(additional),active=new Set([...Object.keys(direct),...Object.keys(additional)]),learning=order.filter(s=>active.has(s))
 const details=learning.map(s=>({skill_id:s,known_level:source[s]??null,target_level:required[s]??null,direct_deficit:direct[s]??0,additional_deficit:additional[s]??0,weight:weight(s),is_prerequisite:closure.has(s)}))
 return {source_profile:sourceId,target_profile:targetId,M1:Object.keys(direct).length,M2:directScore,M3:directScore+p.lambda*burden,direct_score:directScore,prerequisite_burden:burden,weighted_prerequisite_burden:p.lambda*burden,missing_skills:Object.keys(direct).sort(lex),prerequisite_skills:[...closure].sort(lex),learning_order:learning,details,unknown_source_skills:[...unknownSource].sort(lex),unknown_target_skills:[...unknownTarget].sort(lex),fallback_weight_skills:[...fallback].sort(lex),scenario:'conservative: unknown source=0; unknown target=4; missing target weight=1',units:'dimensionless; M1=count, M2/M3=weighted normalized proficiency deficits',verification_scope:p.verification_scope,interpretation:'Model-based proficiency deficit, not factual career transition difficulty'}
}
