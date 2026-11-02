import { finiteNumber, paddedDomain, wrapLabel } from '../lib/chartData'
import type { ScientificRow, ScientificSeries } from '../lib/chartData'
type Props={rows:ScientificRow[];series:ScientificSeries[];xKey:string;title:string;yLabel:string;xLabel?:string;kind?:'line'|'bar';numericX?:boolean;domain?:readonly[number,number];reversed?:boolean;emptyMessage?:string}
const fmt=(n:number)=>Number.isInteger(n)?String(n):Number(n.toPrecision(4)).toString()
/** Native static SVG: no measurement, animation state, or hidden responsive canvas. */
export default function ScientificChart({rows,series,xKey,title,yLabel,xLabel='',kind='line',numericX=false,domain,reversed=false,emptyMessage='Нет рассчитанных значений. Выполните эксперимент или выберите сценарий с доступными данными.'}:Props){
 const data=rows.filter(r=>numericX?finiteNumber(r[xKey])!==null:r[xKey]!==undefined&&r[xKey]!==null)
 const values=data.flatMap(r=>series.flatMap(s=>{const n=finiteNumber(r[s.key]);return n===null?[]:[n]}))
 if(!data.length||!values.length)return <div className="scientific-chart-empty" role="status"><svg data-export-figure data-export-empty="true" width="960" height="140" viewBox="0 0 960 140" aria-hidden="true"><text x="24" y="64" fontSize="16">{emptyMessage}</text></svg><p>{emptyMessage}</p></div>
 const width=Math.max(960,Math.min(1700,data.length*65+125)),left=95,right=35,plotWidth=width-left-right,plotHeight=280
 const titleLines=wrapLabel(title,Math.floor((width-48)/9)),top=30+titleLines.length*23
 const labels=data.map(r=>wrapLabel(String(r[xKey]),numericX?12:Math.max(7,Math.floor(plotWidth/data.length/8))))
 const bottom=56+Math.max(...labels.map(l=>l.length))*17
 const legendLines=series.map(s=>wrapLabel(s.label,Math.floor((width-70)/9)))
 const legendHeight=legendLines.reduce((n,lines)=>n+lines.length*19+10,0)
 const height=top+plotHeight+bottom+legendHeight+20
 const [yMin,yMax]=paddedDomain(values,domain)
 const xs=data.map(r=>finiteNumber(r[xKey])??0);const [xMin,xMax]=paddedDomain(xs,[Math.min(...xs),Math.max(...xs)])
 const x=(i:number)=>numericX?left+(xs[i]-xMin)/(xMax-xMin)*plotWidth:left+plotWidth*(i+.5)/data.length
 const y=(value:number)=>top+(reversed?(value-yMin)/(yMax-yMin):1-(value-yMin)/(yMax-yMin))*plotHeight
 const validCount=values.length,possibleCount=data.length*series.length
 let legendY=top+plotHeight+bottom
 return <div className="scientific-chart"><svg data-export-figure data-chart-kind={kind} width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={title} fontFamily="Arial, sans-serif">
 <title>{title}</title><rect width={width} height={height} fill="white"/>{titleLines.map((line,i)=><text key={i} x="24" y={25+i*23} fontSize="18" fill="#2e4861">{line}</text>)}
 {Array.from({length:5},(_,i)=>{const value=yMin+(yMax-yMin)*i/4,py=y(value);return <g key={i}><line x1={left} y1={py} x2={width-right} y2={py} stroke="#e0e8f1"/><text x={left-12} y={py+5} textAnchor="end" fontSize="14" fill="#526b85">{fmt(value)}</text></g>})}
 <text transform={`translate(22,${top+plotHeight/2}) rotate(-90)`} textAnchor="middle" fontSize="14" fill="#526b85">{yLabel}</text>
 <line x1={left} x2={width-right} y1={top+plotHeight} y2={top+plotHeight} stroke="#9db0c3"/>
 {data.map((row,i)=><g key={i}>{labels[i].map((line,j)=><text key={j} x={x(i)} y={top+plotHeight+24+j*17} textAnchor="middle" fontSize="13" fill="#526b85">{line}</text>)}<title>{String(row[xKey])}</title></g>)}
 <text x={left+plotWidth/2} y={top+plotHeight+bottom-13} textAnchor="middle" fontSize="14" fill="#526b85">{xLabel}</text>
 {series.map((s,j)=>{const segments:string[]=[];let path='';data.forEach((r,i)=>{const n=finiteNumber(r[s.key]);if(n===null){if(path)segments.push(path);path=''}else path+=`${path?' L':'M'} ${x(i)} ${y(n)}`});if(path)segments.push(path)
  const barWidth=Math.min(42,plotWidth/data.length*.76/series.length)
  return <g key={s.key} data-series={s.key}>{kind==='line'&&segments.map((d,i)=><path key={i} d={d} fill="none" stroke={s.color} strokeWidth="2.5"/>)}{data.map((r,i)=>{const n=finiteNumber(r[s.key]);if(n===null)return null;const label=`${s.label}; ${String(r[xKey])}: ${n}`
   return kind==='line'?<circle key={i} cx={x(i)} cy={y(n)} r="5" fill={s.color} stroke="white" strokeWidth="1.5" data-value={n} aria-label={label}><title>{label}</title></circle>:<rect key={i} x={x(i)+(j-series.length/2)*barWidth} y={Math.min(y(0),y(n))} width={barWidth-2} height={Math.max(1,Math.abs(y(0)-y(n)))} fill={s.color} data-value={n} aria-label={label}><title>{label}</title></rect>})}</g>
 })}
 {series.map((s,i)=>{const py=legendY;legendY+=legendLines[i].length*19+10;return <g key={s.key} transform={`translate(30,${py})`}><rect width="15" height="5" y="-5" fill={s.color}/>{legendLines[i].map((line,j)=><text key={j} x="25" y={j*19} fontSize="15" fill="#425e79">{line}</text>)}</g>})}
 </svg>{possibleCount>validCount&&<p className="chart-data-note">Отсутствующие или неопределённые значения не изображены: {possibleCount-validCount}. Они не заменены нулём.</p>}{validCount===1&&<p className="chart-data-note">Одна рассчитанная точка показана маркером; линия между точками отсутствует.</p>}</div>
}
