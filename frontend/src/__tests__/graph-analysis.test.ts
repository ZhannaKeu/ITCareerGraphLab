import { describe, expect, it } from 'vitest'
import { directedPath, layoutGraph, localGraph, neighbors, rankedTransitions, distanceColor, NODE_WIDTH, NODE_HEIGHT } from '../lib/graph'
import { figureSVG, graphSVG } from '../lib/export'
import { stableJSON } from '../lib/provenance'
import type { Graph, Result } from '../types'
const graph:Graph={version_id:'version',nodes:['a','b','c','d','e','f'].map(id=>({id,name:id,category:'Test',description:''})),edges:[{source:'a',target:'b'},{source:'b',target:'c'},{source:'c',target:'d'},{source:'e',target:'f'}]}
describe('visual graph analyses',()=>{
 it('limits both ancestor and descendant neighborhoods by depth',()=>{
  expect(localGraph(graph,'c',1).nodes.map(n=>n.id)).toEqual(['b','c','d'])
  expect(localGraph(graph,'c',2).nodes.map(n=>n.id)).toEqual(['a','b','c','d'])
  expect(localGraph(graph,'',2).nodes).toEqual([])
  expect([...neighbors(graph,'a','outgoing',2)]).toEqual(['b','c'])
 })
 it('finds a deterministic directed shortest path and never reverses arrows',()=>{
  expect(directedPath(graph,'a','d')).toEqual(['a','b','c','d'])
  expect(directedPath(graph,'d','a')).toEqual([])
  expect(directedPath(graph,'a','f')).toEqual([])
 })
 it('packs disconnected components deterministically without overlapping labels',()=>{
  const positions=layoutGraph(graph,1.5)
  expect(layoutGraph(graph,1.5)).toEqual(positions)
  expect(Object.keys(positions).sort()).toEqual(graph.nodes.map(n=>n.id))
  for(const a of graph.nodes)for(const b of graph.nodes)if(a.id!==b.id){const x=positions[a.id],y=positions[b.id];expect(Math.abs(x.x-y.x)>=NODE_WIDTH||Math.abs(x.y-y.y)>=NODE_HEIGHT).toBe(true)}
  expect(graph.nodes[0]).not.toHaveProperty('position')
 })
 it('ranks Top-K on the selected model with lexical tie breaks',()=>{
  const rows=[{source_profile:'s',target_profile:'c',M1:3,M2:1,M3:3},{source_profile:'s',target_profile:'b',M1:2,M2:1,M3:2},{source_profile:'s',target_profile:'a',M1:1,M2:2,M3:1}] as Result[]
  expect(rankedTransitions(rows,'s','M2',2).map(r=>r.target_profile)).toEqual(['b','c'])
  expect(rankedTransitions(rows,'s','M3',2).map(r=>r.target_profile)).toEqual(['a','b'])
  expect(distanceColor(1,0)).not.toContain('NaN')
 })
 it('exports real SVG with XML-escaped names, positions and provenance',()=>{
  const svg=graphSVG([{id:'x',position:{x:0,y:0},data:{exportLabel:'A < B & C'},style:{width:186,height:64}}],[],{version_id:'abc',record_hash:'def',layout:'dagre',relation_legend:true})
  const parsed=new DOMParser().parseFromString(svg,'image/svg+xml')
  expect(parsed.querySelector('parsererror')).toBeNull()
  expect(parsed.querySelector('metadata')?.textContent).toContain('"version_id":"abc"')
  expect(parsed.querySelector('text')?.textContent).toBe('A < B & C')
  expect(svg).not.toContain('foreignObject');expect(parsed.documentElement.textContent).toContain('Required');expect(parsed.documentElement.textContent).toContain('Unverified')
 })
 it('compares parameter objects independently of JSON key order',()=>{
  expect(stableJSON({version:'v',params:{lambda:.5,tau:1}})).toBe(stableJSON({params:{tau:1,lambda:.5},version:'v'}))
 })
})

it('exports chart/heatmap SVG with inline styles and immutable run metadata',()=>{
 const element=document.createElement('div')
 element.innerHTML='<svg xmlns="http://www.w3.org/2000/svg" data-export-figure="true" width="320" height="200" viewBox="0 0 320 200"><rect x="10" y="10" width="40" height="60" fill="#28a998"/><text x="10" y="100">M3 − M2</text></svg><ul><li class="recharts-legend-item"><span class="recharts-legend-item-text" style="color: #397cdb">Ранг M2</span></li></ul>'
 document.body.appendChild(element)
 try{const xml=figureSVG(element,{dataset:'v1',record_hash:'h1',run_id:'r1',parameters:{algorithm:'kahn',lambda:.5,minimum_prerequisite_level:1}});const parsed=new DOMParser().parseFromString(xml,'image/svg+xml');expect(parsed.querySelector('parsererror')).toBeNull();expect(parsed.querySelector('metadata')?.textContent).toContain('"run_id":"r1"');expect(parsed.documentElement.textContent).toContain('M3 − M2');expect(parsed.documentElement.textContent).toContain('Ранг M2')}
 finally{element.remove()}
})

it('projects experimental overrides without modifying the versioned graph',async()=>{
 const {projectExperimentGraph}=await import('../lib/graph')
 const before=JSON.stringify(graph)
 const params={source_profile:'s',target_profile:'t',minimum_prerequisite_level:1,lambda:.5,algorithm:'kahn' as const,weight_source:'role_skill_weights.csv',included_edges:[['a','d']] as [string,string][],excluded_edges:[['a','b']] as [string,string][]}
 const projected=projectExperimentGraph(graph,params)
 expect(projected.edges).toContainEqual({source:'a',target:'d',verification_status:'Unverified'})
 expect(projected.edges.some(e=>e.source==='a'&&e.target==='b')).toBe(false)
 expect(JSON.stringify(graph)).toBe(before)
 expect(projected.version_id).toBe(graph.version_id)
})
