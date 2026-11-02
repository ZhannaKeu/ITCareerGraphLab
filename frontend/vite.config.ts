import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
export default defineConfig(({mode})=>{
 const pages=mode==='pages'
 return {
  base:pages?'/ITCareerGraphLab/':'/',
  envDir:pages?false:undefined,
  define:{'import.meta.env.VITE_PUBLIC_MODE':JSON.stringify(pages?'true':'false')},
  plugins:[react(),{
   name:'public-edition-isolation',enforce:'pre',
   transform(code,id){if(pages&&id.endsWith('/src/styles.css'))return code.replace(/@import url\('https:\/\/fonts\.googleapis\.com[^']*'\);/,'')},
   transformIndexHtml(html){return pages?html.replace('<head>',`<head><meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; worker-src 'self'; object-src 'none'; base-uri 'self'; form-action 'none'">`):html}
  }],
  build:{rollupOptions:{output:{manualChunks:{'react-flow':['@xyflow/react'],'charts':['recharts'],'motion':['motion/react']}}}},
  server:{proxy:{'/api':'http://127.0.0.1:8000','/health':'http://127.0.0.1:8000'}}
 }
})
