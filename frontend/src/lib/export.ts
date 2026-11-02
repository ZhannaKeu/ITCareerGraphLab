import type { Edge, Node } from '@xyflow/react'
import { wrapLabel } from './chartData'
import { annotatePNG } from './png'
export type ExportMeta=Record<string,unknown>
const escape=(s:unknown)=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;')
export function downloadBlob(blob:Blob,name:string){const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
export function downloadJSON(data:unknown,name:string){downloadBlob(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}),name+'.json')}
export function downloadTable(rows:Record<string,unknown>[],name:string,meta:ExportMeta){
 if(!rows.length)throw new Error('Нет строк для экспорта')
 const items=rows.map(r=>({...r,dataset_version:meta.dataset??meta.version_id,run_id:meta.run_id,record_hash:meta.record_hash,export_provenance:JSON.stringify(meta)}))
 const headers=[...new Set(items.flatMap(Object.keys))];const cell=(v:unknown)=>'"'+String(typeof v==='object'?JSON.stringify(v):v??'').replaceAll('"','""')+'"'
 downloadBlob(new Blob(['\uFEFF'+[headers.map(cell).join(','),...items.map(r=>headers.map(k=>cell((r as Record<string,unknown>)[k])).join(','))].join('\r\n')],{type:'text/csv;charset=utf-8'}),name+'.csv')
}
function footerLines(meta:ExportMeta,width:number){
 const params=(meta.parameters??meta) as Record<string,unknown>
 const experiment=(params.experiment??params) as Record<string,unknown>
 const config=meta.graph_configuration as {name?:string;configuration_hash?:string;classification_hash?:string;edge_count?:number}|undefined|null
 const configHashes=meta.configuration_hashes as Record<string,string>|undefined
 const configCaption=config?`${config.name} · ${config.edge_count} edges · config ${config.configuration_hash?.slice(0,16)}`:configHashes?Object.entries(configHashes).map(([g,h])=>`${g}:${h.slice(0,10)}`).join(' '):''
 const classification=(meta.classification_hash??config?.classification_hash??(meta.classification as {classification_hash?:string}|undefined)?.classification_hash) as string|undefined
 const visualization=meta.visualization as {tau?:number}|undefined
 const grid=params.taus&&params.lambdas?` | grid tau ${JSON.stringify(params.taus)} / lambda ${JSON.stringify(params.lambdas)}`:''
 const lines=[`IT Career Graph Lab ${configCaption} | dataset ${meta.dataset??meta.version_id??'—'}`,
  `run ${meta.run_id??'visualization'} | hash ${meta.record_hash??'—'}`,
  `algorithm ${experiment.algorithm??meta.layout??'—'} | tau ${visualization?.tau??experiment.minimum_prerequisite_level??'—'} | lambda ${grid?'varied':experiment.lambda??'—'} | weights ${experiment.weight_source??'—'}${classification?` | classification ${classification.slice(0,16)}`:''}${grid}`,
  'Model outputs on research inputs; AI-assisted / unverified unless explicitly reviewed. Not factual transition difficulty.']
 return lines.flatMap(line=>wrapLabel(line,Math.floor((width-36)/5.5)))
}
function footerHeight(meta:ExportMeta,width:number){return footerLines(meta,width).length*18+23}
function footer(meta:ExportMeta,width:number,y:number){
 return `<rect x="0" y="${y}" width="${width}" height="${footerHeight(meta,width)}" fill="white"/>`+footerLines(meta,width).map((line,i)=>`<text x="18" y="${y+18+i*18}" fill="#63768a" font-family="Arial,sans-serif" font-size="10">${escape(line)}</text>`).join('')
}
export function graphSVG(nodes:Node[],edges:Edge[],meta:ExportMeta):string{
 const visible=nodes.filter(n=>!n.hidden);if(!visible.length)throw new Error('В графе нет видимых вершин')
 const bounds=visible.map(n=>({x:n.position.x,y:n.position.y,w:Number(n.style?.width??186),h:Number(n.style?.height??64)}))
 const minX=Math.min(...bounds.map(b=>b.x))-30,minY=Math.min(...bounds.map(b=>b.y))-30
 const width=Math.max(1050,Math.max(...bounds.map(b=>b.x+b.w))-minX+30),height=Math.max(...bounds.map(b=>b.y+b.h))-minY+45
 const map=new Map(visible.map(n=>[n.id,n]));let body=''
 for(const edge of edges.filter(e=>!e.hidden&&map.has(e.source)&&map.has(e.target))){const a=map.get(edge.source)!,b=map.get(edge.target)!;const point=(n:Node,side:string)=>({x:n.position.x+(side==='right'?Number(n.style?.width??186):side==='left'?0:Number(n.style?.width??186)/2),y:n.position.y+(side==='bottom'?Number(n.style?.height??64):side==='top'?0:Number(n.style?.height??64)/2)})
  const sideA=a.sourcePosition??'right',sideB=b.targetPosition??'left',p=point(a,sideA),q=point(b,sideB),x=p.x,y=p.y,tx=q.x,ty=q.y
  const dxA=sideA==='right'?55:sideA==='left'?-55:0,dyA=sideA==='bottom'?55:sideA==='top'?-55:0,dxB=sideB==='right'?55:sideB==='left'?-55:0,dyB=sideB==='bottom'?55:sideB==='top'?-55:0
  const color=edge.style?.stroke??'#96adbf'
  body+=`<path d="M ${x-minX} ${y-minY} C ${x-minX+dxA} ${y-minY+dyA}, ${tx-minX+dxB} ${ty-minY+dyB}, ${tx-minX} ${ty-minY}" fill="none" stroke="${escape(color)}" stroke-width="${edge.style?.strokeWidth??1.5}" ${edge.style?.strokeDasharray?`stroke-dasharray="${escape(edge.style.strokeDasharray)}"`:''} marker-end="url(#arrow)"/>`
  if(typeof edge.label==='string')body+=`<text x="${(x+tx)/2-minX}" y="${(y+ty)/2-minY-7}" text-anchor="middle" fill="#52677d" font-family="Arial" font-size="11">${escape(edge.label)}</text>`
 }
 for(const n of visible){const label=String(n.data.exportLabel??n.id),words=label.split(/\s+/);const lines:string[]=[];let line='';for(const word of words){if((line+' '+word).length>24&&line){lines.push(line);line=word}else line+=(line?' ':'')+word}if(line)lines.push(line)
  body+=`<g transform="translate(${n.position.x-minX},${n.position.y-minY})"><rect width="${Number(n.style?.width??186)}" height="${Number(n.style?.height??64)}" rx="9" fill="${escape(n.style?.background??'white')}" stroke="${escape(n.data.exportStroke??'#b8cbe0')}" stroke-width="${n.selected?2:1}"/>${lines.map((s,i)=>`<text x="12" y="${19+i*15}" font-family="Arial,sans-serif" font-size="12" fill="#29425d">${escape(s)}</text>`).join('')}</g>`
 }
 const legendHeight=meta.relation_legend?30:0
 const relationLegend=meta.relation_legend?`<g transform="translate(18,${height+12})"><path d="M0 0 H30" stroke="#3d77d5" stroke-width="2"/><text x="36" y="4" font-family="Arial" font-size="10">Required</text><path d="M130 0 H160" stroke="#249e96" stroke-width="2" stroke-dasharray="7 3"/><text x="166" y="4" font-family="Arial" font-size="10">Recommended</text><path d="M310 0 H340" stroke="#9aa7b6" stroke-width="2" stroke-dasharray="2 4"/><text x="346" y="4" font-family="Arial" font-size="10">Related</text><text x="445" y="4" font-family="Arial" font-size="10" fill="#9d855c">AI-assisted preliminary review · Unverified · min_level unset</text></g>`:''
 return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height+legendHeight+footerHeight(meta,width)}" viewBox="0 0 ${width} ${height+legendHeight+footerHeight(meta,width)}"><metadata>${escape(JSON.stringify({...meta,node_positions:visible.map(n=>({id:n.id,position:n.position})),edges:edges.map(e=>({source:e.source,target:e.target}))}))}</metadata><defs><marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#7894aa"/></marker></defs><rect width="100%" height="100%" fill="white"/>${body}${relationLegend}${footer(meta,width,height+legendHeight)}</svg>`
}
export function figureSVG(element:HTMLElement,meta:ExportMeta):string{
 const original=element.querySelector('svg.recharts-surface, svg[data-export-figure]') as SVGSVGElement|null
 if(!original)throw new Error('График ещё не готов к экспорту')
 if(original.getAttribute('data-export-empty')==='true')throw new Error('Нет рассчитанных значений для экспорта')
 const clone=original.cloneNode(true) as SVGSVGElement
 const props=['fill','stroke','stroke-width','font-family','font-size','font-weight','text-anchor','opacity','dominant-baseline']
 const originals=[original,...original.querySelectorAll('*')],copies=[clone,...clone.querySelectorAll('*')]
 originals.forEach((node,i)=>{const style=getComputedStyle(node);props.forEach(prop=>{const value=style.getPropertyValue(prop);if(value)(copies[i] as SVGElement).style.setProperty(prop,value)})})
 const width=original.viewBox.baseVal.width||Number(original.getAttribute('width'))||original.getBoundingClientRect().width
 const height=original.viewBox.baseVal.height||Number(original.getAttribute('height'))||original.getBoundingClientRect().height
 if(!(width>0&&height>0))throw new Error('Размеры графика ещё не определены; экспорт отменён')
 const padded=Math.max(width,1050)
 const title=String(meta.figure_title??'IT Career Graph Lab'),titleLines=wrapLabel(title,Math.floor((padded-40)/9))
 const headerHeight=14+titleLines.length*22
 clone.setAttribute('y',String(headerHeight))
 const content=new XMLSerializer().serializeToString(clone)
 const legend=[...element.querySelectorAll('.recharts-legend-item')].map(item=>{const label=item.querySelector('.recharts-legend-item-text')??item;return {text:label.textContent?.trim()??'',color:getComputedStyle(label).color||'#557b9a'}})
 let legendHeight=0
 const legendSVG=legend.map(item=>{const lines=wrapLabel(item.text,Math.floor((padded-75)/8));const y=height+headerHeight+20+legendHeight;legendHeight+=lines.length*20+10;return `<g transform="translate(18,${y})"><rect width="12" height="10" fill="${escape(item.color)}"/>${lines.map((line,i)=>`<text x="22" y="${10+i*20}" font-size="14" font-family="Arial,sans-serif" fill="#45617c">${escape(line)}</text>`).join('')}</g>`}).join('')
 const footerY=height+headerHeight+legendHeight+30,exportHeight=footerY+footerHeight(meta,padded)
 return `<svg xmlns="http://www.w3.org/2000/svg" width="${padded}" height="${exportHeight}" viewBox="0 0 ${padded} ${exportHeight}"><metadata>${escape(JSON.stringify(meta))}</metadata><rect width="100%" height="100%" fill="white"/>${titleLines.map((line,i)=>`<text x="18" y="${24+i*22}" font-family="Arial,sans-serif" font-size="16" fill="#29425d">${escape(line)}</text>`).join('')}${content}${legendSVG}${footer(meta,padded,footerY)}</svg>`

}
export async function saveSVG(svg:string,name:string,format:'svg'|'png'){
 if(format==='svg'){downloadBlob(new Blob([svg],{type:'image/svg+xml;charset=utf-8'}),name+'.svg');return}
 const blob=new Blob([svg],{type:'image/svg+xml;charset=utf-8'}),url=URL.createObjectURL(blob)
 try{const image=new Image();image.src=url;await image.decode();const ratio=Math.min(Math.max(2,2400/image.width),8192/Math.max(image.width,image.height));const canvas=document.createElement('canvas');canvas.width=Math.ceil(image.width*ratio);canvas.height=Math.ceil(image.height*ratio);const ctx=canvas.getContext('2d');if(!ctx)throw new Error('Canvas недоступен');ctx.scale(ratio,ratio);ctx.drawImage(image,0,0);const png=await new Promise<Blob>((resolve,reject)=>canvas.toBlob(b=>b?resolve(b):reject(new Error('Не удалось создать PNG')),'image/png'));const svgDocument=new DOMParser().parseFromString(svg,'image/svg+xml');const provenance=svgDocument.querySelector('metadata')?.textContent??'{}';const annotated=annotatePNG(new Uint8Array(await png.arrayBuffer()),provenance);downloadBlob(new Blob([annotated.buffer as ArrayBuffer],{type:'image/png'}),name+'.png')}
 finally{URL.revokeObjectURL(url)}
}
