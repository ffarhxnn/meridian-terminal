import {useEffect,useState} from 'react';
type Metric={label:string;value:number|null;unit:string;start?:string;end:string;filed?:string;tag?:string;source_url?:string;reason?:string;period_type?:string};
type Result={symbol:string;entity?:string;as_of:string|null;retrieved_at?:string;source:string;source_url:string;mode:string;warning?:string;metrics:Metric[]};
export default function Statements({request,selected,revision}:{request:(path:string)=>Promise<Result>;selected:string;revision:number}){
 const [data,setData]=useState<Result|null>(null);
 const [error,setError]=useState('');
 // biome-ignore lint/correctness/useExhaustiveDependencies: revision deliberately refreshes this view after the application refresh.
 useEffect(()=>{let current=true;setData(null);setError('');request(`statements/${encodeURIComponent(selected)}`).then(value=>{if(current)setData(value)}).catch(e=>{if(current)setError(e.message)});return()=>{current=false}},[request,selected,revision]);
 return <section className="panel tool-panel"><div className="panel-head"><h2>{selected} · Annual financial facts</h2><span>SEC EDGAR · KEYLESS</span></div><div className="tool-body">
 {error&&<p role="alert">{error}</p>}{!data&&!error&&<output>Loading issuer filings…</output>}
 {data&&<><h3>{data.entity||selected}</h3><p>Fiscal year ended {data.as_of||'unavailable'} · {data.mode} · retrieved {data.retrieved_at||'unavailable'}</p><p>{data.warning}</p><a href={data.source_url} target="_blank" rel="noreferrer">{data.source} ↗</a>
 {data.metrics.length>0?<div className="table-scroll"><table><thead><tr><th>Reported metric</th><th>Value</th><th>Units</th><th>Period</th><th>Filed</th><th>Source</th></tr></thead><tbody>{data.metrics.map(m=><tr key={m.label}><td>{m.label}<small className="source-line">{m.tag||m.reason}</small></td><td>{m.value==null?'Unavailable':m.value.toLocaleString('en-US',{maximumFractionDigits:4})}</td><td>{m.unit}</td><td>{m.start?`${m.start} → `:''}{m.end}<small className="source-line">{m.period_type}</small></td><td>{m.filed||'—'}</td><td>{m.source_url?<a href={m.source_url} target="_blank" rel="noreferrer">SEC filing ↗</a>:'—'}</td></tr>)}</tbody></table></div>:<p>No supported statement facts available for this instrument.</p>}</>}
 </div></section>
}
