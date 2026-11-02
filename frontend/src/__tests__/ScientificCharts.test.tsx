import { afterEach, expect, it } from 'vitest'
import { cleanup, render } from '@testing-library/react'
import ScientificChart from '../components/ScientificChart'
import { gridCurves, relationDistribution, wrapLabel } from '../lib/chartData'
import { annotatePNG, crc32 } from '../lib/png'
import { figureSVG } from '../lib/export'
import type { RelationImpactRun } from '../types'
const series=[{key:'a',label:'M2 · длинное название первой серии для научной статьи',color:'#123456'},{key:'b',label:'M3 · вторая серия',color:'#654321'}]
afterEach(cleanup)
it('shows actual singleton zero and nonzero markers with finite geometry and readable series',()=>{
 const {container,getByText}=render(<ScientificChart rows={[{lambda:.25,a:0,b:1.25}]} series={series} xKey="lambda" numericX title="Sensitivity" yLabel="Δ"/>)
 const markers=container.querySelectorAll('circle')
 expect(markers.length).toBe(2)
 expect([...markers].map(x=>x.getAttribute('data-value'))).toEqual(['0','1.25'])
 expect(container.innerHTML).not.toMatch(/NaN|Infinity/)
 expect(getByText(series[0].label)).toBeTruthy()
 const one=render(<ScientificChart rows={[{lambda:.5,a:2}]} series={[series[0]]} xKey="lambda" numericX title="One" yLabel="Δ"/>)
 expect(one.container.querySelectorAll('circle').length).toBe(1)
 expect(one.getByText(/Одна рассчитанная точка/)).toBeTruthy()
})
it('reports empty and undefined data and prevents blank export',()=>{
 const {container,getByRole}=render(<ScientificChart rows={[{lambda:1,a:null,b:NaN}]} series={series} xKey="lambda" title="Empty" yLabel="Δ"/>)
 expect(getByRole('status').textContent).toContain('Нет рассчитанных значений')
 expect(()=>figureSVG(container,{run_id:'run'})).toThrow()
 expect(container.querySelectorAll('circle').length).toBe(0)
})
it('exports multi-series SVG with full long labels and provenance; missing points do not become zero',()=>{
 const name='VeryLongProfessionalProfileWithoutSpaces:middle'.repeat(3)
 const {container}=render(<ScientificChart rows={[{target:name,a:1,b:2},{target:'second',a:null,b:3}]} series={series} xKey="target" title="Ranking" yLabel="Rank"/>)
 expect(container.querySelectorAll('circle').length).toBe(3)
 const xml=figureSVG(container,{run_id:'run-123',dataset:'hash-456',parameters:{taus:[1,2],lambdas:[0,.5]},provenance:'Unverified'})
 const doc=new DOMParser().parseFromString(xml,'image/svg+xml')
 expect(doc.querySelector('parsererror')).toBeNull()
 expect(xml).toContain('run-123');expect(xml).toContain('hash-456');expect(xml).toContain('Unverified')
 const text=[...doc.querySelectorAll('text')].map(n=>n.textContent??'').join('')
 expect(text).toContain(wrapLabel(name,7).join(''))
 expect(doc.querySelectorAll('[data-series]').length).toBe(2)
})
it('normalizes numeric coordinates without inventing absent or ambiguous measurements',()=>{
 const points=[{tau:'1',lambda:'0.5',mean_extra:'2'}]
 expect(gridCurves(points,[1],[0,.5],null)).toEqual([{lambda:0,tau_1:null},{lambda:.5,tau_1:2}])
 expect(gridCurves([...points,...points],[1],[.5],null)[0].tau_1).toBeNull()
})
it('rebuilds common view bins from archived real scores despite inconsistent saved bins',()=>{
 const run={runs:{G1:{results:[{M2:1,M3:3}]},G2:{results:[{M2:1,M3:1}]},G3:{results:[{M2:1,M3:2}]}},distributions:{G1:[{count:1}],G2:[],G3:[]}} as unknown as RelationImpactRun
 const bins=relationDistribution(run)
 expect(bins.length).toBe(9)
 for(const g of ['G1','G2','G3'])expect(bins.reduce((n,b)=>n+Number(b[g]),0)).toBe(1)
 expect(bins[0].G2).toBe(1)
 expect(relationDistribution({runs:{},distributions:{G1:[{count:1}],G2:[],G3:[]}} as unknown as RelationImpactRun)).toEqual([])
})
it('embeds UTF-8 provenance and 300dpi into PNG with valid chunk checksums',()=>{
 expect(crc32(new TextEncoder().encode('123456789'))).toBe(0xcbf43926)
 const source=Uint8Array.from(atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1sAAAAASUVORK5CYII='),c=>c.charCodeAt(0))
 const metadata=JSON.stringify({run_id:'abc',dataset:'hash',status:'Непроверено',parameters:{tau:2,lambda:.25}})
 const result=annotatePNG(source,metadata)
 let offset=8;const types:string[]=[]
 while(offset<result.length){const n=new DataView(result.buffer,offset,4).getUint32(0),type=new TextDecoder().decode(result.slice(offset+4,offset+8));types.push(type)
  if(['pHYs','iTXt'].includes(type))expect(new DataView(result.buffer,offset+8+n,4).getUint32(0)).toBe(crc32(result.slice(offset+4,offset+8+n)))
  if(type==='iTXt')expect(new TextDecoder().decode(result.slice(offset+8,offset+8+n))).toContain(metadata)
  if(type==='pHYs')expect(new DataView(result.buffer,offset+8,4).getUint32(0)).toBe(11811)
  offset+=12+n
 }
 expect(types).toContain('iTXt');expect(types.indexOf('pHYs')).toBeLessThan(types.indexOf('IDAT'))
 expect(()=>annotatePNG(new Uint8Array(),metadata)).toThrow()
})
