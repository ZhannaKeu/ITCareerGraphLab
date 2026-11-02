import type { GraphAvailability, GraphName } from '../types'
export default function GraphConfigurationSelect({value,onChange,availability}:{value?:GraphName|null;onChange:(name:GraphName|null)=>void;availability?:GraphAvailability}){
 return <label className="configuration-select">Конфигурация графа<select aria-label="Конфигурация графа пререквизитов" value={value??''} onChange={e=>onChange((e.target.value||null) as GraphName|null)}><option value="">Legacy · текущий граф версии</option>{(['G1','G2','G3'] as const).map((g,i)=><option key={g} value={g} disabled={!availability?.available}>{g} · {['Original · все 51','Strict · Required 14','Extended · Required + Recommended 50'][i]}</option>)}</select>{availability?.available===false&&<small>{availability.reason}</small>}</label>
}
