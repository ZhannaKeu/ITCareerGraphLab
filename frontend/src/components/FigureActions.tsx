import { useEffect, useState } from 'react'
import type { RefObject } from 'react'
import { figureSVG, saveSVG } from '../lib/export'
import type { ExportMeta } from '../lib/export'
export default function FigureActions({target,name,meta}:{target:RefObject<HTMLDivElement|null>;name:string;meta:ExportMeta}){
 const [error,setError]=useState('');const [busy,setBusy]=useState(false);const [available,setAvailable]=useState(false)
 useEffect(()=>{const element=target.current;if(!element)return;const update=()=>{const svg=element.querySelector('svg.recharts-surface, svg[data-export-figure]');setAvailable(!!svg&&svg.getAttribute('data-export-empty')!=='true')};update();const observer=new MutationObserver(update);observer.observe(element,{childList:true,subtree:true,attributes:true,attributeFilter:['data-export-empty']});return ()=>observer.disconnect()},[target])
 async function save(format:'svg'|'png'){setError('');setBusy(true);try{if(!target.current)throw new Error('График недоступен');await saveSVG(figureSVG(target.current,{...meta,figure_title:meta.figure_title??name}),name,format)}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 return <div className="figure-actions"><button disabled={busy||!available} title={available?'Экспорт рассчитанных значений':'Нет рассчитанного графика для экспорта'} onClick={()=>save('svg')} aria-label={`Экспорт ${name} SVG`}>SVG ↓</button><button disabled={busy||!available} title={available?'Экспорт рассчитанных значений':'Нет рассчитанного графика для экспорта'} onClick={()=>save('png')} aria-label={`Экспорт ${name} PNG`}>PNG ↓</button>{error&&<span role="alert">{error}</span>}</div>
}
