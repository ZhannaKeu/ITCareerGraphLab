import dagre from '@dagrejs/dagre'
import type { Graph, Result, Params } from '../types'
export const NODE_WIDTH=168, NODE_HEIGHT=56
export function neighbors(graph:Graph, root:string, direction:'incoming'|'outgoing', depth:number):Set<string>{
 const seen=new Set([root]);let frontier=[root]
 for(let layer=0;layer<depth&&frontier.length;layer++){
  const next:string[]=[]
  for(const id of frontier)for(const e of graph.edges){const candidate=direction==='incoming'?(e.target===id?e.source:undefined):(e.source===id?e.target:undefined);if(candidate&&!seen.has(candidate)){seen.add(candidate);next.push(candidate)}}
  frontier=next.sort()
 }
 seen.delete(root);return seen
}
export function localGraph(graph:Graph,selected:string,depth:number):Graph{
 if(!selected)return {...graph,nodes:[],edges:[]}
 const ids=new Set([selected,...neighbors(graph,selected,'incoming',depth),...neighbors(graph,selected,'outgoing',depth)])
 return {...graph,nodes:graph.nodes.filter(n=>ids.has(n.id)),edges:graph.edges.filter(e=>ids.has(e.source)&&ids.has(e.target))}
}
export function directedPath(graph:Graph,source:string,target:string):string[]{
 if(!source||!target)return []
 const queue=[source],previous=new Map<string,string|null>([[source,null]])
 while(queue.length){const id=queue.shift()!;if(id===target){const path:string[]=[];let node:string|null=target;while(node!==null){path.unshift(node);node=previous.get(node)??null}return path}
  for(const next of graph.edges.filter(e=>e.source===id).map(e=>e.target).sort())if(!previous.has(next)){previous.set(next,id);queue.push(next)}
 }return []
}
// Lay out each weak component separately, then pack shelves to viewport aspect.
// The layout is deterministic and never modifies prerequisite edges.
export function layoutGraph(graph:Graph,aspect=1.5,direction:'LR'|'TB'='LR'):Record<string,{x:number;y:number}>{
 const adjacency=new Map(graph.nodes.map(n=>[n.id,[] as string[]]))
 for(const e of graph.edges){adjacency.get(e.source)?.push(e.target);adjacency.get(e.target)?.push(e.source)}
 const visited=new Set<string>();const components:{ids:string[];positions:Record<string,{x:number;y:number}>;width:number;height:number}[]=[]
 for(const root of [...adjacency.keys()].sort()){if(visited.has(root))continue;const queue=[root],ids:string[]=[];visited.add(root)
  while(queue.length){const id=queue.shift()!;ids.push(id);for(const n of [...(adjacency.get(id)??[])].sort())if(!visited.has(n)){visited.add(n);queue.push(n)}}
  const g=new dagre.graphlib.Graph();g.setGraph({rankdir:direction,nodesep:20,ranksep:48,marginx:10,marginy:10});g.setDefaultEdgeLabel(()=>({}))
  for(const id of ids.sort())g.setNode(id,{width:NODE_WIDTH,height:NODE_HEIGHT})
  for(const e of [...graph.edges].sort((a,b)=>`${a.source}:${a.target}`.localeCompare(`${b.source}:${b.target}`)))if(ids.includes(e.source)&&ids.includes(e.target))g.setEdge(e.source,e.target)
  dagre.layout(g)
  components.push({ids,positions:Object.fromEntries(ids.map(id=>{const p=g.node(id);return [id,{x:p.x-NODE_WIDTH/2,y:p.y-NODE_HEIGHT/2}]})),width:g.graph().width??NODE_WIDTH,height:g.graph().height??NODE_HEIGHT})
 }
 components.sort((a,b)=>b.height-a.height||b.width-a.width||a.ids[0].localeCompare(b.ids[0]))
 const area=components.reduce((a,c)=>a+(c.width+36)*(c.height+36),0);const targetWidth=Math.max(1,...components.map(c=>c.width),Math.sqrt(area*Math.max(.5,Math.min(3,aspect))))
 const positions:Record<string,{x:number;y:number}>={};let x=0,y=0,rowHeight=0
 for(const c of components){if(x&&x+c.width>targetWidth){x=0;y+=rowHeight+38;rowHeight=0}for(const id of c.ids)positions[id]={x:x+c.positions[id].x,y:y+c.positions[id].y};x+=c.width+38;rowHeight=Math.max(rowHeight,c.height)}
 return positions
}
export type Metric='M1'|'M2'|'M3'
export function rankedTransitions(results:Result[],source:string,metric:Metric,top:number=0){return results.filter(r=>r.source_profile===source).sort((a,b)=>a[metric]-b[metric]||(a.target_profile<b.target_profile?-1:a.target_profile>b.target_profile?1:0)).slice(0,top||undefined)}
export function distanceColor(value:number,max:number){const t=max>0?Math.max(0,Math.min(1,value/max)):0;const low=[39,171,155],high=[47,65,143];return `rgb(${low.map((v,i)=>Math.round(v+(high[i]-v)*t)).join(',')})`}

export function autoLayoutGraph(graph:Graph,aspect:number){
 const candidates=(['LR','TB'] as const).map(direction=>{const positions=layoutGraph(graph,aspect,direction);const points=Object.values(positions);const width=Math.max(1,...points.map(p=>p.x+NODE_WIDTH)),height=Math.max(1,...points.map(p=>p.y+NODE_HEIGHT));return {direction,positions,fit:Math.min(aspect/width,1/height)}})
 return candidates[1].fit>candidates[0].fit?candidates[1]:candidates[0]
}

export function projectExperimentGraph(graph:Graph,params:Params):Graph{
 const omitted=new Set(params.excluded_edges.map(e=>JSON.stringify(e)))
 const edges=graph.edges.filter(e=>!omitted.has(JSON.stringify([e.source,e.target]))&&(params.verification_scope!=='verified'||e.verification_status==='Expert Verified'||e.verification_status==='Source Verified'))
 const included=new Set(edges.map(e=>JSON.stringify([e.source,e.target])))
 for(const [source,target] of params.included_edges){const pair=JSON.stringify([source,target]);if(!included.has(pair)){edges.push({source,target,verification_status:'Unverified'});included.add(pair)}}
 return {...graph,edges,experiment:params}
}
