export const shortcuts:Record<string,string>={FA:'Statements',GP:'Overview',DES:'Overview',PORT:'Portfolio',COMP:'Compare',CURVE:'Rates',ALERT:'Alerts',NOTES:'Notebook',NEWS:'Research',TOP:'Research',WS:'Workspace',CALC:'Calculators',EQS:'Screener',SCR:'Screener',CAL:'Calendar',ECO:'Calendar',STATUS:'Coverage',WEI:'Markets',MOV:'Screener'};
export type Command={type:'help'}|{type:'route';tab:string}|{type:'asset';symbol:string;view:string}|{type:'group';group:string}|{type:'lookup';query:string};
export function parseCommand(input:string):Command{
 const text=input.trim().toUpperCase().replace(/\s+/g,' ');
 if(text==='HELP'||text==='?')return {type:'help'};
 if(shortcuts[text])return {type:'route',tab:shortcuts[text]};
 if(text==='FX'||text==='CRYPTO')return {type:'group',group:text==='FX'?'FX':'Crypto'};
 const match=text.match(/^([A-Z0-9.^=/-]+)(?: US EQUITY)?(?: (GP|DES|FA|NEWS))?$/);
 if(match)return {type:'asset',symbol:match[1],view:match[2]||'GP'};
 return {type:'lookup',query:input.trim()};
}
