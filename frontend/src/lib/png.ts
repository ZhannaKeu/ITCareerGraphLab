/** Add provenance and 300-dpi density to a valid PNG without changing pixels. */
export function crc32(bytes:Uint8Array):number{let crc=0xffffffff;for(const byte of bytes){crc^=byte;for(let bit=0;bit<8;bit++)crc=(crc>>>1)^((crc&1)?0xedb88320:0)}return (crc^0xffffffff)>>>0}
function concatenate(parts:Uint8Array[]){const result=new Uint8Array(parts.reduce((n,p)=>n+p.length,0));let offset=0;for(const p of parts){result.set(p,offset);offset+=p.length}return result}
function chunk(type:string,data:Uint8Array){const name=new TextEncoder().encode(type),result=new Uint8Array(12+data.length),view=new DataView(result.buffer);view.setUint32(0,data.length);result.set(name,4);result.set(data,8);view.setUint32(8+data.length,crc32(concatenate([name,data])));return result}
export function annotatePNG(bytes:Uint8Array,provenance:string):Uint8Array{
 const signature=[137,80,78,71,13,10,26,10];if(!signature.every((n,i)=>bytes[i]===n))throw new Error('Некорректный PNG')
 const parts=[bytes.slice(0,8)];let offset=8,ended=false
 const density=new Uint8Array(9),view=new DataView(density.buffer);view.setUint32(0,11811);view.setUint32(4,11811);density[8]=1
 const text=concatenate([new TextEncoder().encode('ITCareerGraphLab'),new Uint8Array([0,0,0,0,0]),new TextEncoder().encode(provenance)])
 while(offset+12<=bytes.length){const size=new DataView(bytes.buffer,bytes.byteOffset+offset,4).getUint32(0);if(offset+size+12>bytes.length)throw new Error('Повреждённая структура PNG');const type=new TextDecoder().decode(bytes.slice(offset+4,offset+8));if(type==='IEND'){parts.push(chunk('iTXt',text),bytes.slice(offset,offset+size+12));ended=true;break}if(type!=='pHYs')parts.push(bytes.slice(offset,offset+size+12));if(type==='IHDR')parts.push(chunk('pHYs',density));offset+=size+12}
 if(!ended)throw new Error('PNG не содержит IEND');return concatenate(parts)
}
