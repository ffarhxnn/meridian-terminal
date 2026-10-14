// Workspace interaction/layout pattern inspired by OpenTerminal (MIT).
// Independent implementation preserving Meridian's existing functional panels.
import React, {Children,cloneElement,isValidElement,useEffect,useRef,useState,type ReactElement,type ReactNode} from 'react';
import GridLayout,{WidthProvider,type Layout} from 'react-grid-layout';
import {Maximize2,Minimize2,X,GripVertical} from 'lucide-react';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import {defaults,normalizeLayout,type WidgetId} from '../../services/workspace/layout';

const Grid=WidthProvider(GridLayout);
type ElementProps={className?:string;children?:ReactNode;'data-widget-id'?:string};
const titles:Record<WidgetId,string>={market:'Market monitor',chart:'Price chart',fundamentals:'Quote / reference',ticket:'Paper ticket',research:'Research copilot',signals:'Cross-asset pulse',news:'News terminal'};
function collect(children:ReactNode):{id:WidgetId;element:ReactElement<ElementProps>}[]{
 const result:{id:WidgetId;element:ReactElement<ElementProps>}[]=[];
 Children.forEach(children,child=>{
  if(!isValidElement<ElementProps>(child))return;
  const name=child.props.className||'';
  if(name==='center-column'||name==='right-column'){result.push(...collect(child.props.children));return}
  const id:WidgetId|undefined=name.includes('market-panel')?'market':name.includes('chart-panel')?'chart':name.includes('fundamentals')?'fundamentals':name.includes('paper-ticket')?'ticket':name.includes('copilot')?'research':name.includes('signals')?'signals':name.includes('news')?'news':undefined;
  if(id)result.push({id,element:child});
 });return result;
}
function stored(workspace:string):Layout[]{try{return normalizeLayout(JSON.parse(localStorage.getItem(`meridian-widget-layout:${workspace}`)||'null'))}catch{return defaults()}}
function Panel({element,id,onHide,onExpand,expanded}:{element:ReactElement<ElementProps>;id:WidgetId;onHide:()=>void;onExpand:()=>void;expanded:boolean}){
 const children=Children.map(element.props.children,child=>{
  if(!isValidElement<ElementProps>(child)||child.props.className!=='panel-head')return child;
  return cloneElement(child,{},<><GripVertical size={10} className="widget-grip"/>{child.props.children}<span className="widget-controls"><button type="button" aria-label={`${expanded?'Restore':'Maximize'} ${titles[id]}`} title={expanded?'Restore panel':'Maximize panel'} onClick={onExpand}>{expanded?<Minimize2 size={12}/>:<Maximize2 size={12}/>}</button><button type="button" aria-label={`Close ${titles[id]}`} title="Close widget (restore with Add widget)" onClick={onHide}><X size={13}/></button></span></>);
 });
 return cloneElement(element,{'data-widget-id':id,className:`${element.props.className||''} terminal-widget`},children);
}
export default function WidgetWorkspace({children,workspace,visible,onVisibilityChange}:{children:ReactNode;workspace:string;visible:Record<string,boolean>;onVisibilityChange:(id:WidgetId,show:boolean)=>void}){
 const all=collect(children);
 const [layout,setLayout]=useState<Layout[]>(()=>stored(workspace));
 const [expanded,setExpanded]=useState<WidgetId|null>(null);
 const [locked,setLocked]=useState(false);
 const [mobile,setMobile]=useState(window.innerWidth<900);
 const loadedFor=useRef(workspace);
 useEffect(()=>{loadedFor.current=workspace;setLayout(stored(workspace));setExpanded(null)},[workspace]);
 useEffect(()=>{const resize=()=>setMobile(window.innerWidth<900);window.addEventListener('resize',resize);return()=>window.removeEventListener('resize',resize)},[]);
 useEffect(()=>{const close=(e:KeyboardEvent)=>{if(e.key==='Escape')setExpanded(null)};window.addEventListener('keydown',close);return()=>window.removeEventListener('keydown',close)},[]);
 const shown=all.filter(w=>visible[w.id]!==false);
 const save=(next:Layout[])=>{const normalized=normalizeLayout([...layout.filter(l=>!next.some(n=>n.i===l.i)),...next]);setLayout(normalized);if(loadedFor.current===workspace)localStorage.setItem(`meridian-widget-layout:${workspace}`,JSON.stringify(normalized))};
 const panel=(w:typeof all[number],full=false)=><Panel element={w.element} id={w.id} expanded={full} onHide={()=>{onVisibilityChange(w.id,false);setExpanded(null)}} onExpand={()=>setExpanded(full?null:w.id)}/>;
 return <div className="widget-workspace"><div className="workspace-tools"><span>WORKSPACE <b>{workspace.toUpperCase()}</b> · {shown.length} PANELS · DRAG HEADER / RESIZE CORNER</span><div><select aria-label="Add widget" value="" onChange={e=>onVisibilityChange(e.target.value as WidgetId,true)}><option value="">+ ADD WIDGET</option>{all.filter(w=>visible[w.id]===false).map(w=><option value={w.id} key={w.id}>{titles[w.id]}</option>)}</select><button type="button" onClick={()=>setLocked(!locked)}>{locked?'UNLOCK LAYOUT':'LOCK LAYOUT'}</button><button type="button" onClick={()=>save(defaults())}>RESET POSITIONS</button></div></div>
 {mobile?<div className="mobile-widgets">{shown.map(w=><div key={w.id} className={expanded===w.id?'expanded-widget-frame':''}>{panel(w,expanded===w.id)}</div>)}</div>:<Grid key={workspace} className="terminal-layout" layout={layout.filter(l=>shown.some(w=>w.id===l.i))} cols={12} rowHeight={24} margin={[4,4]} containerPadding={[0,0]} draggableHandle=".panel-head" draggableCancel="button,input,select,textarea,a" isDraggable={!locked} isResizable={!locked} onDragStop={next=>save(next)} onResizeStop={next=>save(next)}>{shown.map(w=><div key={w.id} data-widget-frame={w.id} className={expanded===w.id?'expanded-widget-frame':''}>{panel(w,expanded===w.id)}</div>)}</Grid>}
 {shown.length===0&&<p className="workspace-empty">All widgets are closed. Use Add widget to restore a panel.</p>}

 </div>
}
