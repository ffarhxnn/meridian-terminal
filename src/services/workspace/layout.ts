import type {Layout} from 'react-grid-layout';
export type WidgetId='market'|'chart'|'fundamentals'|'ticket'|'research'|'signals'|'news';
export function defaults():Layout[]{return [
 {i:'chart',x:0,y:0,w:7,h:14,minW:4,minH:8},
 {i:'fundamentals',x:7,y:0,w:2,h:10,minW:2,minH:6},
 {i:'market',x:9,y:0,w:3,h:14,minW:3,minH:5},
 {i:'ticket',x:7,y:10,w:2,h:4,minW:2,minH:4},
 {i:'news',x:0,y:14,w:7,h:9,minW:3,minH:5},
 {i:'research',x:7,y:14,w:5,h:9,minW:3,minH:5},
 {i:'signals',x:0,y:23,w:12,h:4,minW:3,minH:3},
]}
export function normalizeLayout(value:unknown):Layout[]{
 const fallback=defaults();if(!Array.isArray(value))return fallback;
 return fallback.map(base=>{
  const candidate=value.find(v=>v&&typeof v==='object'&&v.i===base.i);
  if(!candidate||!['x','y','w','h'].every(k=>Number.isFinite(candidate[k])))return base;
  const w=Math.max(base.minW||1,Math.min(12,Math.round(candidate.w)));
  return {...base,w,h:Math.max(base.minH||1,Math.min(80,Math.round(candidate.h))),x:Math.max(0,Math.min(12-w,Math.round(candidate.x))),y:Math.max(0,Math.min(1000,Math.round(candidate.y)))};
 });
}
