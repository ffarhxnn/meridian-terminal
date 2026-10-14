// Independently implemented standard indicators. EMA is seeded with its first
// full-period SMA; RSI uses Wilder smoothing. No synthetic observations added.
import type {Bar,IndicatorPoint} from '../../types/market';
export function sma(bars:Bar[],period:number):IndicatorPoint[]{
 if(period<1||!Number.isInteger(period))throw new Error('Period must be a positive integer');
 const result:IndicatorPoint[]=[];let sum=0;
 bars.forEach((bar,i)=>{sum+=bar.value;if(i>=period)sum-=bars[i-period].value;if(i>=period-1)result.push({date:bar.date,value:sum/period})});return result;
}
export function ema(bars:Bar[],period:number):IndicatorPoint[]{
 if(period<1||!Number.isInteger(period))throw new Error('Period must be a positive integer');
 if(bars.length<period)return [];
 let previous=bars.slice(0,period).reduce((s,b)=>s+b.value,0)/period;
 const result=[{date:bars[period-1].date,value:previous}];
 const alpha=2/(period+1);
 for(let i=period;i<bars.length;i++){previous=alpha*bars[i].value+(1-alpha)*previous;result.push({date:bars[i].date,value:previous})}return result;
}
export function rsi(bars:Bar[],period=14):IndicatorPoint[]{
 if(period<1||!Number.isInteger(period))throw new Error('Period must be a positive integer');
 if(bars.length<=period)return [];
 let gain=0;
 let loss=0;
 for(let i=1;i<=period;i++){const delta=bars[i].value-bars[i-1].value;gain+=Math.max(delta,0)/period;loss+=Math.max(-delta,0)/period}
 const level=()=>gain===0&&loss===0?50:loss===0?100:100-100/(1+gain/loss);
 const result=[{date:bars[period].date,value:level()}];
 for(let i=period+1;i<bars.length;i++){const delta=bars[i].value-bars[i-1].value;gain=(gain*(period-1)+Math.max(delta,0))/period;loss=(loss*(period-1)+Math.max(-delta,0))/period;result.push({date:bars[i].date,value:level()})}return result;
}
export function bollinger(bars:Bar[],period=20,multiplier=2){
 const middle=sma(bars,period);
 const upper:IndicatorPoint[]=[];
 const lower:IndicatorPoint[]=[];
 middle.forEach((point,index)=>{const end=index+period;const variance=bars.slice(index,end).reduce((s,b)=>s+(b.value-point.value)**2,0)/period;const width=multiplier*Math.sqrt(variance);upper.push({date:point.date,value:point.value+width});lower.push({date:point.date,value:point.value-width})});return {middle,upper,lower};
}
export function macd(bars:Bar[],fast=12,slow=26,signalPeriod=9){
 const fastMap=new Map(ema(bars,fast).map(p=>[p.date,p.value]));
 const line=ema(bars,slow).filter(p=>fastMap.has(p.date)).map(p=>({date:p.date,value:fastMap.get(p.date)!-p.value}));
 const signal=ema(line,signalPeriod);
 const signalMap=new Map(signal.map(p=>[p.date,p.value]));
 const histogram=line.filter(p=>signalMap.has(p.date)).map(p=>({date:p.date,value:p.value-signalMap.get(p.date)!}));return {line,signal,histogram};
}
