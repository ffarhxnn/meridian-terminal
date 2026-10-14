import {test} from 'node:test';
import assert from 'node:assert/strict';
import {sma,ema,rsi,bollinger,macd} from '../features/charts/indicators.ts';
import {dateKey} from '../features/charts/time.ts';
import {normalizeLayout,defaults} from '../services/workspace/layout.ts';
const bars=(values:number[])=>values.map((value,i)=>({date:`2026-01-${String(i+1).padStart(2,'0')}`,value}));
test('moving averages seed only after sufficient observations',()=>{
 assert.deepEqual(sma(bars([1,2,3,4]),3).map(p=>p.value),[2,3]);
 assert.deepEqual(ema(bars([1,2,3,4]),3).map(p=>p.value),[2,3]);
 assert.deepEqual(ema(bars([1,2]),3),[]);
 assert.throws(()=>sma([],0));
});
test('Wilder RSI handles rising, falling and flat prices',()=>{
 assert.equal(rsi(bars([1,2,3,4]),3)[0].value,100);
 assert.equal(rsi(bars([4,3,2,1]),3)[0].value,0);
 assert.equal(rsi(bars([2,2,2,2]),3)[0].value,50);
});
test('Bollinger uses population deviation and flat MACD is zero',()=>{
 const b=bollinger(bars([1,2,3]),3,2);
 assert.equal(b.middle[0].value,2);
 assert.ok(Math.abs(b.upper[0].value-(2+2*Math.sqrt(2/3)))<1e-12);
 assert.ok(macd(bars(Array(40).fill(10))).histogram.every(p=>p.value===0));
});
test('crosshair dates support business days and Unix seconds',()=>{
 assert.equal(dateKey({year:2026,month:1,day:2}),'2026-01-02');
 assert.equal(dateKey(Date.UTC(2026,0,2)/1000),'2026-01-02');
 assert.equal(dateKey('2026-01-02'),'2026-01-02');
});
test('corrupt saved layouts are bounded and missing widgets restored',()=>{
 assert.deepEqual(normalizeLayout(null),defaults());
 const result=normalizeLayout([{i:'chart',x:-5,y:Number.POSITIVE_INFINITY,w:0,h:0},{i:'market',x:100,y:-1,w:100,h:100}]);
 assert.equal(result.length,7);
 assert.deepEqual(result[0],defaults()[0]);
 assert.equal(result.find(p=>p.i==='market')?.w,12);
 assert.equal(result.find(p=>p.i==='market')?.x,0);
});

import {parseCommand} from '../services/commands.ts';
test('commands parse qualified securities and reject trailing garbage',()=>{
 assert.deepEqual(parseCommand(' aapl us equity gp '),{type:'asset',symbol:'AAPL',view:'GP'});
 assert.deepEqual(parseCommand('BTC NEWS'),{type:'asset',symbol:'BTC',view:'NEWS'});
 assert.deepEqual(parseCommand('FA'),{type:'route',tab:'Statements'});
 assert.deepEqual(parseCommand('ECO'),{type:'route',tab:'Calendar'});
 assert.deepEqual(parseCommand('FX'),{type:'group',group:'FX'});
 assert.equal(parseCommand('AAPL GP nonsense').type,'lookup');
});
