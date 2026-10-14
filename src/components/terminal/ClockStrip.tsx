import {useEffect,useState} from 'react';
export default function ClockStrip(){
 const [now,setNow]=useState(new Date());
 useEffect(()=>{const timer=setInterval(()=>setNow(new Date()),1000);return()=>clearInterval(timer)},[]);
 return <span className="clock-strip">{[['NY','America/New_York'],['LDN','Europe/London'],['TKY','Asia/Tokyo']].map(([label,zone])=><span key={label}>{label} <b>{now.toLocaleTimeString('en-GB',{timeZone:zone,hour12:false})}</b></span>)}</span>
}
