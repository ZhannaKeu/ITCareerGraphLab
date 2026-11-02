export const PUBLIC_MODE=import.meta.env.VITE_PUBLIC_MODE==='true'
export const PUBLIC_PAGES=['dashboard','skills','career','experiments','results','versions','data']
export function pageFromHash(hash:string){const page=hash.replace(/^#\/?/,'');return PUBLIC_PAGES.includes(page)?page:'dashboard'}
