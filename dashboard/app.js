'use strict';
const $=id=>document.getElementById(id), names={Bioreactor1:'Bioreactor 01',Bioreactor2:'Bioreactor 02',Chiller1:'Chiller 01'};
let asset='Bioreactor1', mode='waiting', running=false, demoTimer=null, pollTimer=null, epoch=0, sample=0, events=[], previous={}, freshness='', data={source:'none',messages:0,assets:{Bioreactor1:[],Bioreactor2:[],Chiller1:[]},errors:{}};
function log(text){events.unshift({time:Date.now(),text});events=events.slice(0,50);renderEvents();}
function renderEvents(){$('events').replaceChildren();events.forEach(e=>{const row=document.createElement('div');row.className='event';const time=document.createElement('time');time.textContent=new Date(e.time).toLocaleTimeString();const span=document.createElement('span');span.textContent=e.text;row.append(time,span);$('events').append(row);});$('eventCount').textContent=events.length+' events';}
function latest(a=asset){return data.assets[a]?.at(-1);}
function observe(){for(const a of Object.keys(names)){const v=latest(a);if(!v)continue;const alarm=a==='Chiller1'?'LowFlowAlarm':'HighTempAlarm';if(previous[a]!==v[alarm]){if(v[alarm]||previous[a]!==undefined)log(names[a]+(v[alarm]?' · alarm active':' · alarm cleared'));previous[a]=v[alarm];}}}
function chart(id,key,color,range,threshold){const host=$(id),cutoff=Date.now()-Number($('window').value)*1000;const rows=(data.assets[asset]||[]).filter(d=>d.time>=cutoff&&Number.isFinite(d[key]));if(!rows.length){host.innerHTML='<p class="empty">Waiting for process data</p>';return;}
 const width=700,height=id==='temperatureChart'?240:145,l=40,r=10,top=15,bottom=25;
 const vals=rows.map(d=>d[key]);let lo=Math.min(range[0],...vals),hi=Math.max(range[1],...vals);if(hi===lo)hi=lo+1;
 const end=Date.now(),start=end-Number($('window').value)*1000,x=t=>l+(t-start)/(end-start)*(width-l-r),y=v=>top+(hi-v)/(hi-lo)*(height-top-bottom);
 let svg=`<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${key} over time">`;
 for(let i=0;i<5;i++){const v=lo+(hi-lo)*i/4,yy=y(v);svg+=`<line x1="${l}" x2="${width-r}" y1="${yy}" y2="${yy}" stroke="#edf1e9"/><text x="${l-9}" y="${yy+3}" text-anchor="end" fill="#a3afa0" font-size="10">${v.toFixed(key==='PH'?2:1)}</text>`;}
 if(threshold!=null&&threshold>=lo&&threshold<=hi)svg+=`<line x1="${l}" x2="${width-r}" y1="${y(threshold)}" y2="${y(threshold)}" stroke="#ddb984" stroke-dasharray="4 5"/><text x="${width-r}" y="${y(threshold)-5}" text-anchor="end" fill="#b99a6c" font-size="9">High alarm &gt; ${threshold} °C</text>`;
 // Split across gaps instead of connecting missing telemetry.
 const segments=[];let segment=[];rows.forEach((d,i)=>{if(i&&d.time-rows[i-1].time>5000){segments.push(segment);segment=[];}segment.push(d);});segments.push(segment);
 for(const seg of segments){const pts=seg.map(d=>`${x(d.time)},${y(d[key])}`).join(' ');svg+=`<polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2.5" stroke-linejoin="round"/>`;if(seg.length===1)svg+=`<circle cx="${x(seg[0].time)}" cy="${y(seg[0][key])}" r="3" fill="${color}"/>`;}
 for(let i=0;i<4;i++){const t=start+(end-start)*i/3;svg+=`<text x="${x(t)}" y="${height-5}" text-anchor="${i===0?'start':i===3?'end':'middle'}" fill="#a3afa0" font-size="9">${new Date(t).toLocaleTimeString()}</text>`;}
 host.innerHTML=svg+'</svg>';}
function render(){const v=latest(), ch=asset==='Chiller1',age=v?(Date.now()-v.time)/1000:Infinity,failed=!!data.errors?.[asset],isFresh=age<=(data.source==='snowflake'?30:5)&&!failed&&(mode!=='demo'||running);
 const status=mode==='demo'?(running?'Demo running':'Demo paused'):v?(isFresh?'Live data':'Stale data'):'Awaiting data';$('status').textContent=(isFresh?'● ':'○ ')+status;$('status').className='mode-badge '+(isFresh?'fresh':v?'stale':'');
 if(status!==freshness){if(freshness)log(names[asset]+' · '+status.toLowerCase());freshness=status;}
 $('modeTitle').textContent=mode==='demo'?'Browser demo · synthetic data':mode==='live'?'Live bridge · '+(data.source==='snowflake'?'Snowflake Cloud (polling) ':data.source==='mqtt'?'HighByte / HiveMQ':'direct Modbus'):'Showcase ready';
 $('modeHelp').textContent=mode==='demo'?'Illustrative signals generated in this browser. Your simulator is not connected.':mode==='live'?(failed?data.errors[asset]:data.source==='snowflake'?'Snowflake query every 10 seconds · stale after 30 seconds · latest 500 rows':'Read-only telemetry · updates every second · 600 samples per asset'):'Start the demo, or run the local bridge to see your actual simulator.';
 $('demo').textContent=mode==='demo'&&running?'Ⅱ Pause demo':mode==='demo'?'▶ Resume demo':'▶ Start demo';
 const metrics=ch?[['Supply temperature','SupplyTemp','°C','Scaled from input register'],['Return temperature','ReturnTemp','°C','Scaled from input register'],['Flow rate','Flow','L/min','45 L/min when running'],['Supply setpoint','SupplySetpoint','°C','Stored target temperature']]:[['Temperature','Temperature','°C','High alarm above 38.0 °C'],['pH level','PH','pH','Decoded at 0.01 resolution'],['RPM setpoint','RpmSetpoint','rpm','Commanded value · not measured'],['Heater status','HeaterOn','','Threshold flag below 36.5 °C']];
 $('metrics').innerHTML=metrics.map(([name,key,unit,note])=>{const value=!v?'—':typeof v[key]==='boolean'?(v[key]?'ON':'OFF'):Number(v[key]).toFixed(key==='PH'?2:['RpmSetpoint','Flow'].includes(key)?0:1);return `<div class="metric"><div class="metric-label">${name}<span>↗</span></div><div class="metric-value">${value}<small>${unit}</small></div><div class="metric-note">${note}</div></div>`;}).join('');
 $('chartTitle').textContent=ch?'Supply & cooling trend':'Temperature trend';$('chartSubtitle').textContent=ch?'Supply temperature · °C':'Measured temperature · °C';$('legend').textContent=ch?'Supply temperature':'Temperature';
 $('secondaryTitle').textContent=ch?'Return temperature trend':'pH trend';$('secondarySubtitle').textContent=ch?'Chiller return · °C':'Acidity / alkalinity';
 chart('temperatureChart',ch?'SupplyTemp':'Temperature','#5bab8b',ch?[4,22]:[35,39],ch?null:38);chart('secondaryChart',ch?'ReturnTemp':'PH','#99a779',ch?[5,25]:[6.5,7.5]);
 $('update').textContent=v?'Last sample '+new Date(v.time).toLocaleTimeString()+(isFresh?'':' · not current'):'Waiting for readings';$('vesselName').textContent=names[asset];$('unitBadge').textContent='UNIT '+(ch?2:asset==='Bioreactor1'?1:3);$('vesselTemp').textContent=v?Number(v[ch?'SupplyTemp':'Temperature']).toFixed(1)+' °C':'—';$('vessel').style.opacity=isFresh?'1':'.55';$('heater').textContent=ch?'Running · '+(!v?'unknown':v.Running?'yes':'no'):'Heater · '+(!v?'unknown':v.HeaterOn?'on':'off');$('alarm').textContent=!v?'Awaiting data':v[ch?'LowFlowAlarm':'HighTempAlarm']?'Alarm active':isFresh?'No active alarm':'Status stale';$('alarm').style.color=v?.[ch?'LowFlowAlarm':'HighTempAlarm']?'#b45737':'';
 $('assetmeta').textContent=(ch?'UTILITIES':'UPSTREAM')+' / LINE 1 / '+$('unitBadge').textContent;$('topic').textContent='PharmaCo/Dublin/'+(ch?'Utilities':'Upstream')+'/Line1/'+asset;$('messages').textContent=data.messages+' samples';$('pipelineNote').textContent=mode==='demo'?'Designed architecture · browser demo bypasses all external services.':mode==='live'?(data.source==='snowflake'?'Active path: HighByte → Snowflake table → read-only dashboard API (polled every 10s).':data.source==='modbus'?'Active path: simulator → Modbus bridge → dashboard. HighByte and HiveMQ are bypassed.':'Active input: HiveMQ → MQTT bridge → dashboard. Upstream service health is not independently verified.'):'Designed architecture · connections are not independently monitored.';
}
function reset(){data={source:'demo',messages:0,assets:{Bioreactor1:[],Bioreactor2:[],Chiller1:[]},errors:{}};events=[];previous={};freshness='';renderEvents();}
function demoTick(){sample++;const time=Date.now();for(const [a,phase] of [['Bioreactor1',0],['Bioreactor2',1.4]]){const t=37+1.2*Math.sin(sample/24+phase);data.assets[a].push({time,Temperature:Math.round(t*10)/10,PH:Math.round((7+.15*Math.sin(sample/17+phase))*100)/100,RpmSetpoint:a==='Bioreactor1'?100:150,HeaterOn:t<36.5,HighTempAlarm:t>38});}data.assets.Chiller1.push({time,SupplyTemp:7+.3*Math.sin(sample/20),ReturnTemp:12+.3*Math.sin(sample/20),Flow:45,SupplySetpoint:7,Running:true,LowFlowAlarm:false});for(const a in data.assets)data.assets[a]=data.assets[a].slice(-600);data.messages+=3;observe();render();}
$('demo').onclick=()=>{epoch++;clearTimeout(pollTimer);if(mode!=='demo'){reset();mode='demo';running=false;sample=0;log('Browser demo selected · synthetic signals');}running=!running;clearInterval(demoTimer);if(running){demoTick();demoTimer=setInterval(demoTick,1000);}log(running?'Demo started':'Demo paused');render();};
async function connect(initial=false){if(mode==='demo'){reset();mode='waiting';}clearInterval(demoTimer);running=false;clearTimeout(pollTimer);const myEpoch=++epoch;try{const response=await fetch('/api/snapshot',{cache:'no-store',signal:AbortSignal.timeout(4000)});if(!response.ok)throw Error('No bridge');const body=await response.json();if(!body.assets||!['modbus','mqtt','snowflake'].includes(body.source))throw Error('Invalid bridge');if(myEpoch!==epoch)return;if(mode!=='live'){reset();log('Connected to '+body.source+' bridge');}mode='live';data=body;observe();render();pollTimer=setTimeout(()=>connect(true),data.source==='snowflake'?5000:1000);}catch(e){if(myEpoch!==epoch)return;if(mode==='live'){data.errors={Bioreactor1:'Bridge unavailable; reconnecting…',Bioreactor2:'Bridge unavailable; reconnecting…',Chiller1:'Bridge unavailable; reconnecting…'};render();pollTimer=setTimeout(()=>connect(true),2000);}else{mode='waiting';render();if(!initial)$('connectionDialog').showModal();}}}
$('live').onclick=()=>connect();$('closeDialog').onclick=()=>$('connectionDialog').close();
document.querySelectorAll('[data-asset]').forEach(b=>b.onclick=()=>{asset=b.dataset.asset;freshness='';document.querySelectorAll('[data-asset]').forEach(x=>x.classList.toggle('selected',x===b));render();});$('window').onchange=render;
$('export').onclick=()=>{const rows=data.assets[asset]||[];if(!rows.length){log('No samples to export · start a data source first');return;}const keys=Object.keys(rows[0]),csv=[['source',...keys].join(','),...rows.map(r=>[mode==='demo'?'browser-demo':data.source,...keys.map(k=>k==='time'?new Date(r[k]).toISOString():r[k])].join(','))].join('\r\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv'})),a=document.createElement('a');a.href=url;a.download=`PharmaCo-${asset}-${mode}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);log('Exported '+rows.length+' samples for '+names[asset]);};
setInterval(render,1000);render();connect(true);

async function refreshHistory(){
 const status=$('historyStatus'), body=$('historyBody');
 status.textContent='Loading historical records…';
 try{
   const response=await fetch('/api/history?hours='+encodeURIComponent($('historyHours').value),{cache:'no-store',signal:AbortSignal.timeout(20000)});
   if(!response.ok)throw new Error('HTTP '+response.status);
   const result=await response.json();
   body.replaceChildren();
   if(result.status!=='ok'){status.textContent=result.message||'Snowflake history unavailable ('+result.status+')';return;}
   status.textContent=result.count+' records loaded from Snowflake (read-only).';
   for(const record of result.rows){
     const row=document.createElement('tr');
     const get=(...names)=>{for(const n of names){const key=Object.keys(record).find(k=>k.toUpperCase()===n.toUpperCase());if(key!==undefined)return record[key];}return '—';};
     const cells=[record.time,record.asset,get('Temperature'),get('PH'),get('RpmSetpoint'),get('HeaterOn'),get('HighTempAlarm')];
     for(const value of cells){const td=document.createElement('td');td.textContent=String(value??'—');td.style.padding='8px 10px';td.style.borderBottom='1px solid #e3eae5';row.append(td);}
     body.append(row);
   }
 }catch(error){status.textContent='Could not load history. Check the local bridge and Snowflake connection.';}
}
$('historyRefresh').onclick=refreshHistory;
