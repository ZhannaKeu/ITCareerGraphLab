import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render } from '@testing-library/react'
import SkillGraph from '../components/SkillGraph'
// Actual React Flow component in an isolated DOM; no browser or screen access.
// Resize observation is a platform primitive absent in jsdom, so only it is stubbed.
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
it('mounts the real React Flow runtime with stable graph defaults',()=>{
 vi.stubGlobal('ResizeObserver',class {observe(){}unobserve(){}disconnect(){}})
 const view=render(<div style={{width:1000,height:600}}><SkillGraph graph={{version_id:'test',nodes:[{id:'a',name:'Runtime skill A',category:'Test',description:''},{id:'b',name:'Runtime skill B',category:'Test',description:''}],edges:[{source:'a',target:'b'}]}} selected="" onSelect={()=>{}}/></div>)
 expect(view.getByText('Runtime skill A')).toBeTruthy()
 expect(view.getByText('Runtime skill B')).toBeTruthy()
 expect(view.container.querySelector('.react-flow')).toBeTruthy()
})
