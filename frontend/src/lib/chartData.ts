import type { Ranking, ResearchRun, RelationImpactRun } from '../types'
export function finiteNumber(value:unknown):number|null{if(typeof value==='number')return Number.isFinite(value)?value:null;if(typeof value==='string'&&value.trim()!==''){const n=Number(value);return Number.isFinite(n)?n:null}return null}
export type ScientificRow=Record<string,unknown>
export type ScientificSeries={key:string;label:string;color:string}
export function gridCurves(points:ScientificRow[],taus:unknown[],lambdas:unknown[],tau:unknown,graphNames?:string[]){
 const selected=finiteNumber(tau);const xs=[...new Set(lambdas.map(finiteNumber).filter((x):x is number=>x!==null))].sort((a,b)=>a-b)
 if(selected===null&&!graphNames){return xs.map(lambda=>Object.fromEntries([['lambda',lambda],...taus.map(t=>{const tValue=finiteNumber(t);const matches=points.filter(p=>finiteNumber(p.tau)===tValue&&finiteNumber(p.lambda)===lambda);return [`tau_${t}`,matches.length===1?finiteNumber(matches[0].mean_extra):null]})]))}
 return xs.map(lambda=>Object.fromEntries([['lambda',lambda],...(graphNames??[]).map(g=>{const matches=points.filter(p=>p.graph===g&&finiteNumber(p.tau)===selected&&finiteNumber(p.lambda)===lambda);return [g,matches.length===1?finiteNumber(matches[0].mean_extra):null]})]))
}
export function rankRows(ranking:Ranking|undefined):ScientificRow[]{return (ranking?.targets??[]).map(t=>({...t,rank_m2:finiteNumber(t.rank_m2),rank_m3:finiteNumber(t.rank_m3)}))}
export function researchCurves(run:ResearchRun){return gridCurves(run.sensitivity,run.provenance.parameters.taus,run.provenance.parameters.lambdas,null)}
export function relationDistribution(run:RelationImpactRun):ScientificRow[]{
 const names=['G1','G2','G3'] as const
 // Old archives can have independently sized bins. Rebuild shared VIEW bins
 // from saved pair values; do not alter/recalculate any stored model result.
 const pairs=Object.fromEntries(names.map(g=>[g,(run.runs?.[g]?.results??[]).flatMap(r=>{const m2=finiteNumber(r.M2),m3=finiteNumber(r.M3);return m2===null||m3===null?[]:[m3-m2]})])) as Record<string,number[]>
 if(names.every(g=>pairs[g].length>0)){
  const max=Math.max(0,...names.flatMap(g=>pairs[g]));const boundaries=max>0?Array.from({length:8},(_,i)=>({lower:i*max/8,upper:(i+1)*max/8})):[]
  return [{label:'= 0',...Object.fromEntries(names.map(g=>[g,pairs[g].filter(v=>v===0).length]))},...boundaries.map((b,i)=>({label:`${b.lower.toPrecision(3)}–${b.upper.toPrecision(3)}`,...b,...Object.fromEntries(names.map(g=>[g,pairs[g].filter(v=>v>0&&Math.min(7,Math.floor(v/(max/8)))===i).length]))}))]
 }
 // Lossless fallback only when archived bin boundaries actually agree.
 const histograms=names.map(g=>run.distributions?.[g]??[])
 if(!histograms[0].length||!histograms.every(h=>h.length===histograms[0].length&&h.every((b,i)=>finiteNumber(b.lower)!==null&&finiteNumber(b.upper)!==null&&b.lower===histograms[0][i].lower&&b.upper===histograms[0][i].upper)))return []
 return histograms[0].map((b,i)=>({label:b.label,...Object.fromEntries(names.map((g,j)=>[g,finiteNumber(histograms[j][i].count)]))}))
}
export function paddedDomain(values:number[],requested?:readonly[number,number]):[number,number]{
 let lo=requested?.[0]??Math.min(0,...values),hi=requested?.[1]??Math.max(0,...values)
 if(!Number.isFinite(lo)||!Number.isFinite(hi))return [0,1]
 if(lo===hi){const delta=Math.max(.5,Math.abs(lo)*.1);lo-=delta;hi+=delta}
 return [lo,hi]
}
export function wrapLabel(text:string,maxChars:number):string[]{
 const result:string[]=[];let line=''
 for(const token of text.split(/(?<=[\s:_–])/u)){let word=token
  while(word.length>maxChars){if(line){result.push(line.trim());line=''}result.push(word.slice(0,maxChars));word=word.slice(maxChars)}
  if(line.length+word.length>maxChars){result.push(line.trim());line=''}line+=word
 }if(line.trim())result.push(line.trim());return result.length?result:['']
}
