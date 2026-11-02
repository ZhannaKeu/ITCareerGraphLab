import { BarChart, Bar, CartesianGrid, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import type { Result, Skill, Batch } from '../types'
const f=(n:number)=>n.toLocaleString('ru-RU',{maximumFractionDigits:3})
export function ScoreCards({result}:{result:Result}){
 return <div className="score-grid">{[['M1','Unweighted gap',result.M1,'недостающих навыков'],['M2','Weighted gap',result.M2,'прямой взвешенный дефицит'],['M3','Prerequisite-aware gap',result.M3,'с учётом prerequisite-нагрузки']].map(([id,name,value,sub])=><div className={`score-card ${id==='M3'?'featured':''}`} key={id}><span className="eyebrow">{id} <span>· {name}</span></span><strong>{f(Number(value))}</strong><small>{sub}</small></div>)}</div>
}
export function ResultChart({result}:{result:Result}){
 const data=[{name:'M2',direct:result.direct_score,prerequisite:0},{name:'M3',direct:result.direct_score,prerequisite:result.weighted_prerequisite_burden}]
 return <div className="chart"><ResponsiveContainer width="100%" height={230}><BarChart data={data} barSize={45}><CartesianGrid vertical={false} stroke="#e8edf4"/><XAxis dataKey="name" axisLine={false} tickLine={false}/><YAxis axisLine={false} tickLine={false}/><Tooltip formatter={v=>f(Number(v))}/><Legend/><Bar name="Прямой дефицит" dataKey="direct" stackId="a" fill="#397cdb"/><Bar name="λ × prerequisite-нагрузка" dataKey="prerequisite" stackId="a" fill="#28b3a6" radius={[5,5,0,0]}/></BarChart></ResponsiveContainer><p className="muted text-xs">M1 = {result.M1} навыков. Он имеет другую размерность и показан отдельно.</p></div>
}
export function DetailTable({result,skills}:{result:Result;skills:Skill[]}){
 return <div className="table-scroll"><table><thead><tr><th>Навык · топологический порядок</th><th>Исходный</th><th>Целевой</th><th>Прямой Δ</th><th>Доп. Δ</th><th>Вес</th></tr></thead><tbody>{result.details.map(r=><tr key={r.skill_id}><td><span className={`table-dot ${r.additional_deficit>0?'teal':''}`}/>{skills.find(s=>s.id===r.skill_id)?.name??r.skill_id}</td><td>{r.known_level??<span className="unknown">? → 0*</span>}</td><td>{r.target_level??'—'}</td><td>{f(r.direct_deficit)}</td><td>{f(r.additional_deficit)}</td><td>{f(r.weight)}</td></tr>)}{!result.details.length&&<tr><td colSpan={6}>Дефицит в заданном сценарии отсутствует.</td></tr>}</tbody></table></div>
}
export function BatchChart({batch}:{batch:Batch}){
 const data=batch.results.map((r,i)=>({name:String(i+1),M1:r.M1,M2:r.M2,M3:r.M3,pair:`${r.source_profile} → ${r.target_profile}`}))
 return <ResponsiveContainer width="100%" height={260}><BarChart data={data}><CartesianGrid vertical={false} stroke="#e8edf4"/><XAxis dataKey="name" interval={25} tickLine={false} axisLine={false}/><YAxis yAxisId="weighted" tickLine={false} axisLine={false}/><YAxis yAxisId="count" orientation="right" tickLine={false} axisLine={false}/><Tooltip labelFormatter={(_,payload)=>payload?.[0]?.payload.pair} formatter={v=>f(Number(v))}/><Legend/><Bar yAxisId="count" dataKey="M1" name="M1 · число навыков (правая ось)" fill="#bac9e3"/><Bar yAxisId="weighted" dataKey="M2" fill="#397cdb"/><Bar yAxisId="weighted" dataKey="M3" fill="#28b3a6"/></BarChart></ResponsiveContainer>
}
export function Scenario({result}:{result:Result}){
 return <div className="notice"><strong>Консервативный сценарий</strong><p>Неизвестный исходный уровень → 0 ({result.unknown_source_skills.length}); неизвестное требование → 4 ({result.unknown_target_skills.length}); отсутствующий вес → 1 ({result.fallback_weight_skills.length}). Это допущения, а не измерения навыков человека. Групповые требования исключены.</p></div>
}
