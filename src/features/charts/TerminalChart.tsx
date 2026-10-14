// Original integration of TradingView Lightweight Charts (Apache-2.0).
// The library attribution logo/link is deliberately enabled.
import {useEffect,useMemo,useRef,useState} from 'react';
import {createChart,CandlestickSeries,BarSeries,LineSeries,AreaSeries,HistogramSeries,ColorType,CrosshairMode,type IChartApi,type Time} from 'lightweight-charts';
import type {Bar,IndicatorPoint} from '../../types/market';
import {sma,ema,rsi,macd,bollinger} from './indicators';
import {dateKey} from './time';

const names=['SMA20','SMA50','EMA20','BOLL','RSI','MACD'] as const;
type Indicator=typeof names[number];
const color={SMA20:'#ffd966',SMA50:'#4fc3f7',EMA20:'#ff8a65',BOLL:'#b87800',RSI:'#ff9900',MACD:'#4fc3f7'};
function preferences(){try{const value=JSON.parse(localStorage.getItem('meridian-chart-preferences')||'{}');return value&&typeof value==='object'?value:{}}catch{return {}}}
const fmt=(v:number|undefined)=>v==null?'—':v.toLocaleString('en-US',{maximumFractionDigits:4});
export default function TerminalChart({bars,symbol,range,onRange}:{bars:Bar[];symbol:string;range:string;onRange:(value:string)=>void}){
 const container=useRef<HTMLDivElement>(null);
 const chartRef=useRef<IChartApi|null>(null);
 const [kind,setKind]=useState(()=>['Candles','OHLC','Line','Area'].includes(preferences().kind)?preferences().kind:'Candles');
 const [indicators,setIndicators]=useState<Indicator[]>(()=>Array.isArray(preferences().indicators)?preferences().indicators.filter((n:Indicator)=>names.includes(n)):['SMA20']);
 const [volume,setVolume]=useState(()=>preferences().volume!==false);
 const [hover,setHover]=useState<Bar|null>(null);
 const [error,setError]=useState('');
 useEffect(()=>{localStorage.setItem('meridian-chart-preferences',JSON.stringify({kind,indicators,volume}))},[kind,indicators,volume]);
 const ordered=useMemo(()=>Array.from(new Map(bars.filter(b=>Number.isFinite(b.value)).map(b=>[b.date,b])).values()).sort((a,b)=>a.date.localeCompare(b.date)),[bars]);
 const computed=useMemo(()=>({SMA20:sma(ordered,20),SMA50:sma(ordered,50),EMA20:ema(ordered,20),BOLL:bollinger(ordered),RSI:rsi(ordered),MACD:macd(ordered)}),[ordered]);
 const hasCandles=ordered.some(b=>[b.open,b.high,b.low].every(v=>typeof v==='number'&&Number.isFinite(v)));
 const hasVolume=ordered.some(b=>b.volume!=null&&b.volume>0);
 const actualKind=!hasCandles&&['Candles','OHLC'].includes(kind)?'Line':kind;
 useEffect(()=>{
  if(!container.current)return;
  setHover(null);setError('');let disposed=false;let observer:ResizeObserver|undefined;let chart:IChartApi|undefined;
  try{
   chart=createChart(container.current,{width:container.current.clientWidth||500,height:Math.max(140,container.current.clientHeight||250),layout:{background:{type:ColorType.Solid,color:'#0a0a0a'},textColor:'#888',fontFamily:'Consolas, monospace',fontSize:10,attributionLogo:true},grid:{vertLines:{color:'#1c1c1c'},horzLines:{color:'#1c1c1c'}},rightPriceScale:{borderColor:'#262626'},timeScale:{borderColor:'#262626',timeVisible:false},crosshair:{mode:CrosshairMode.Normal,vertLine:{color:'#777',labelBackgroundColor:'#8a5900'},horzLine:{color:'#777',labelBackgroundColor:'#8a5900'}},handleScroll:true,handleScale:true});
   chartRef.current=chart;
   const closes=ordered.map(b=>({time:b.date as Time,value:b.value}));
   const candles=ordered.filter(b=>b.open!=null&&b.high!=null&&b.low!=null).map(b=>({time:b.date as Time,open:b.open!,high:b.high!,low:b.low!,close:b.value}));
   if(actualKind==='Candles')chart.addSeries(CandlestickSeries,{upColor:'#00c853',downColor:'#ff3d3d',wickUpColor:'#00c853',wickDownColor:'#ff3d3d',borderVisible:false}).setData(candles);
   else if(actualKind==='OHLC')chart.addSeries(BarSeries,{upColor:'#00c853',downColor:'#ff3d3d',thinBars:true}).setData(candles);
   else if(actualKind==='Area')chart.addSeries(AreaSeries,{lineColor:'#ff9900',topColor:'#ff990030',bottomColor:'#ff990000',lineWidth:1}).setData(closes);
   else chart.addSeries(LineSeries,{color:'#ddd',lineWidth:1}).setData(closes);
   const addLine=(data:IndicatorPoint[],lineColor:string,pane=0,title='')=>{const series=chart!.addSeries(LineSeries,{color:lineColor,lineWidth:1,priceLineVisible:false,lastValueVisible:false,title},pane);series.setData(data.map(p=>({time:p.date as Time,value:p.value})));return series};
   for(const name of indicators){
    if(name==='SMA20'||name==='SMA50'||name==='EMA20')addLine(computed[name],color[name]);
    if(name==='BOLL'){addLine(computed.BOLL.upper,color.BOLL);addLine(computed.BOLL.lower,color.BOLL)}
   }
   if(volume&&hasVolume){const series=chart.addSeries(HistogramSeries,{priceScaleId:'volume',priceFormat:{type:'volume'},priceLineVisible:false,lastValueVisible:false});series.priceScale().applyOptions({scaleMargins:{top:.83,bottom:0}});series.setData(ordered.flatMap((b,i)=>b.volume==null?[]:[{time:b.date as Time,value:b.volume,color:b.value>=(b.open??ordered[Math.max(0,i-1)]?.value??b.value)?'#00c85366':'#ff3d3d66'}]))}
   let pane=1;
   if(indicators.includes('RSI')){const series=addLine(computed.RSI,color.RSI,pane++,'RSI14');series.applyOptions({autoscaleInfoProvider:()=>({priceRange:{minValue:0,maxValue:100}})});series.createPriceLine({price:70,color:'#555',lineWidth:1,axisLabelVisible:false,title:''});series.createPriceLine({price:30,color:'#555',lineWidth:1,axisLabelVisible:false,title:''})}
   if(indicators.includes('MACD')){addLine(computed.MACD.line,color.MACD,pane,'MACD12/26');addLine(computed.MACD.signal,'#ddd',pane,'Signal9');chart.addSeries(HistogramSeries,{priceLineVisible:false,lastValueVisible:false},pane).setData(computed.MACD.histogram.map(p=>({time:p.date as Time,value:p.value,color:p.value>=0?'#00c853':'#ff3d3d'})))}
   chart.panes().forEach((p,i)=>p.setStretchFactor(i===0?4:1));
   const count=range==='1W'?7:range==='1M'?30:range==='6M'?180:range==='1Y'?365:90;
   if(ordered.length){const end=ordered[ordered.length-1].date;
const cutoff=new Date(Date.parse(end)-(count-1)*86400000).toISOString().slice(0,10);const first=ordered.find(b=>b.date>=cutoff)?.date||ordered[0].date;if(first!==end)chart.timeScale().setVisibleRange({from:first as Time,to:end as Time});else chart.timeScale().fitContent()}
   const byDate=new Map(ordered.map(b=>[b.date,b]));
   chart.subscribeCrosshairMove(event=>{if(!disposed)setHover(event.time?byDate.get(dateKey(event.time))||null:null)});
   observer=new ResizeObserver(()=>{if(chart&&!disposed&&container.current)chart.resize(container.current.clientWidth,Math.max(140,container.current.clientHeight))});observer.observe(container.current);
  }catch(e){setError((e as Error).message)}
  return()=>{disposed=true;observer?.disconnect();chart?.remove();chartRef.current=null};
 },[ordered,actualKind,indicators,computed,volume,hasVolume,range]);
 const shown=hover||ordered[ordered.length-1];
 const inspect=(direction:number)=>{if(!ordered.length)return;const current=ordered.findIndex(b=>b.date===shown?.date);const index=Math.max(0,Math.min(ordered.length-1,current+direction));setHover(ordered[index]);const scale=chartRef.current?.timeScale();const visible=scale?.getVisibleLogicalRange();if(visible&&(index<visible.from||index>visible.to)){const span=visible.to-visible.from;scale?.setVisibleLogicalRange({from:index-span/2,to:index+span/2})}};
 const indicatorValue=(name:Indicator)=>{const data=name==='BOLL'?computed.BOLL.middle:name==='MACD'?computed.MACD.line:computed[name];return data.find(p=>p.date===shown?.date)?.value};
 return <div className="professional-chart"><div className="chart-toolbar"><div>{['1W','1M','3M','6M','1Y'].map(value=><button type="button" key={value} className={range===value?'active':''} onClick={()=>onRange(value)}>{value}</button>)}</div><div>{['Candles','OHLC','Line','Area'].map(value=><button type="button" key={value} className={kind===value?'active':''} onClick={()=>setKind(value)}>{value.toUpperCase()}</button>)}</div><div>{names.map(name=><button type="button" key={name} className={indicators.includes(name)?'active':''} onClick={()=>setIndicators(indicators.includes(name)?indicators.filter(n=>n!==name):[...indicators,name])}>{name}</button>)}<button type="button" className={volume?'active':''} disabled={!hasVolume} onClick={()=>setVolume(!volume)}>VOL</button><button type="button" onClick={()=>chartRef.current?.timeScale().fitContent()}>FIT</button><button type="button" aria-label="Inspect previous chart observation" disabled={!ordered.length} onClick={()=>inspect(-1)}>◀</button><button type="button" aria-label="Inspect next chart observation" disabled={!ordered.length} onClick={()=>inspect(1)}>▶</button></div></div>
 <div className="chart-live-legend" aria-live="polite"><b>{symbol}</b> {shown?.date||'NO OBSERVATIONS'} <span>O {fmt(shown?.open)}</span> <span className="up">H {fmt(shown?.high)}</span> <span className="down">L {fmt(shown?.low)}</span> <span>C {fmt(shown?.value)}</span> <span>VOL {fmt(shown?.volume)}</span>{indicators.map(name=><span style={{color:color[name]}} key={name}>{name} {fmt(indicatorValue(name))}</span>)}</div>
 {!hasCandles&&ordered.length>0&&['Candles','OHLC'].includes(kind)&&<div className="chart-source-note">Source supplies reference observations without OHLC; showing a line.</div>}
 {error&&<p role="alert" className="notice">Chart unavailable: {error}</p>}<div ref={container} className="lightweight-host" role="img" aria-label={`${symbol} interactive ${actualKind.toLowerCase()} chart with crosshair and zoom`}/>{!ordered.length&&<div className="chart-empty">No source history loaded.</div>}
 <a className="chart-attribution" href="https://www.tradingview.com/" target="_blank" rel="noreferrer">Charts by TradingView</a></div>
}
