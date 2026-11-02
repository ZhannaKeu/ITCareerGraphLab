// Regression for unstable default array props causing an effect/setState render loop.
// Flow's visual shell is replaced; its actual state hooks and our graph logic execute.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render } from '@testing-library/react'
import SkillGraph, { related } from '../components/SkillGraph'
import type { Graph } from '../types'

let renders=0
vi.mock('@xyflow/react',async importOriginal=>{
 const actual=await importOriginal<typeof import('@xyflow/react')>()
 return {...actual,ReactFlow:()=>{renders++;if(renders>20)throw new Error('Render loop detected');return <div>Flow rendered</div>},Background:()=>null,Controls:()=>null,MiniMap:()=>null}
})
afterEach(()=>{cleanup();renders=0})
const graph:Graph={version_id:'test',nodes:[{id:'a',name:'A',category:'Core',description:''},{id:'b',name:'B',category:'Core',description:''},{id:'c',name:'C',category:'Core',description:''},{id:'d',name:'D',category:'Core',description:''}],edges:[{source:'a',target:'b'},{source:'a',target:'c'},{source:'b',target:'d'},{source:'c',target:'d'}]}

describe('SkillGraph',()=>{
 it('settles with omitted array props and does not enter a render loop',()=>{
  const view=render(<SkillGraph graph={graph} selected="" onSelect={()=>{}}/>)
  expect(view.getByText('Flow rendered')).toBeTruthy()
  expect(renders).toBeLessThan(8)
  view.rerender(<SkillGraph graph={graph} selected="d" onSelect={()=>{}}/>)
  expect(renders).toBeLessThan(12)
 })
 it('deduplicates transitive ancestors and respects direction',()=>{
  expect([...related(graph,'d','incoming',true)].sort()).toEqual(['a','b','c'])
  expect([...related(graph,'d','incoming',false)].sort()).toEqual(['b','c'])
  expect([...related(graph,'a','outgoing',true)].sort()).toEqual(['b','c','d'])
  expect(related(graph,'a','incoming',true).size).toBe(0)
 })
})
