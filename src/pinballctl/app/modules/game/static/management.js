(() => {
  'use strict';
  const root=document.getElementById('manager-root');if(!root)return;
  const kind=root.dataset.manager,body=document.getElementById('manager-body'),footer=document.getElementById('manager-footer'),notice=document.getElementById('manager-notice');
  const drawer=bootstrap.Offcanvas.getOrCreateInstance(document.getElementById('manager-drawer'));
  let view,hardware=[],busy=false;
  let pendingCommand;try{pendingCommand=JSON.parse(sessionStorage.getItem('manager-pending-'+kind)||'null');}catch{}
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
  const btn=(text,fn,cls='btn btn-outline-secondary')=>{const n=el('button',text,cls);n.type='button';n.onclick=()=>run(fn);return n;};
  async function run(fn){if(busy)return;busy=true;try{notice.textContent='';await fn();}catch(e){notice.textContent=e.message;notice.className='alert alert-warning';}finally{busy=false;}}
  async function api(path,data){const response=await fetch('/api/'+kind+path,data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const result=await response.json();if(!response.ok||!result.ok){const error=new Error(result.error||'Operation failed');error.definitive=true;throw error;}return result;}
  async function command(command,params={}){
    if(pendingCommand&&(pendingCommand.command!==command||JSON.stringify(pendingCommand.params)!==JSON.stringify(params)))throw new Error('The previous request is unconfirmed. Retry that same operation first.');
    pendingCommand=pendingCommand||{command,params,id:crypto.randomUUID()};sessionStorage.setItem('manager-pending-'+kind,JSON.stringify(pendingCommand));
    try{await api('/command',pendingCommand);pendingCommand=null;sessionStorage.removeItem('manager-pending-'+kind);await load();}
    catch(error){if(error.definitive){pendingCommand=null;sessionStorage.removeItem('manager-pending-'+kind);}throw error;}
  }
  function field(parent,label,value,type='text',options){const wrap=el('div',undefined,'mb-3'),id='manager-'+crypto.randomUUID(),lab=el('label',label,'form-label');lab.htmlFor=id;let input;
    if(options){input=el('select',undefined,'form-select');for(const option of options){const node=el('option',typeof option==='string'?option:option.label);node.value=typeof option==='string'?option:option.value;input.append(node);}input.value=String(value??'');}
    else {input=el('input',undefined,'form-control');input.type=type;input.value=String(value??'');}input.id=id;wrap.append(lab,input);parent.append(wrap);return input;}
  function open(title){document.getElementById('manager-title').textContent=title;body.replaceChildren();footer.replaceChildren(btn('Close',()=>drawer.hide()));drawer.show();}
  function stats(items){const summary=document.getElementById('manager-summary');summary.replaceChildren();for(const [label,value] of items){const card=el('div',undefined,'manager-stat');card.append(el('span',label,'small text-secondary'),el('strong',value===null?'Unknown':String(value)));summary.append(card);}}
  function table(headings,rows){document.getElementById('manager-head').replaceChildren();const tr=el('tr');headings.forEach(h=>{const th=el('th',h);th.scope='col';tr.append(th);});document.getElementById('manager-head').append(tr);const target=document.getElementById('manager-rows');target.replaceChildren();for(const cells of rows){const row=el('tr');cells.forEach(c=>row.append(el('td',c)));target.append(row);}if(!rows.length){const row=el('tr'),cell=el('td','Nothing recorded yet.','text-secondary');cell.colSpan=headings.length;row.append(cell);target.append(row);}}
  function render(){
    const g=view.game,b=view.ball,c=view.gameConfig,controls=document.getElementById('manager-controls');controls.replaceChildren();
    if(kind==='game'){
      stats([['Status',g.status.replaceAll('_',' ')],['Player',g.currentPlayer||'—'],['Ball',g.ballNumber||'—'],['Credits',c.freePlay?'Free play':g.credits],['Coin units',g.creditUnits]]);
      controls.append(btn('Start game',()=>command('REQUEST_START_GAME'), 'btn btn-success'),btn('Add player',()=>command('REQUEST_ADD_PLAYER')),btn('Pause',()=>command('REQUEST_PAUSE_GAME')),btn('Resume',()=>command('REQUEST_RESUME_GAME')),btn('End game',async()=>{if(confirm('End the current game?'))await command('REQUEST_END_GAME');},'btn btn-outline-danger'));
      controls.append(btn('Award extra ball',()=>command('REQUEST_AWARD_EXTRA_BALL',{count:1})),btn('Activate ball save',()=>command('REQUEST_BALL_SAVE',{durationMs:c.ballSaveMs||10000})));
      for(const button of controls.children){const allowed={'Start game':['IDLE','GAME_ENDED'],'Add player':['PREPARING','BALL_ACTIVE'],'Pause':['PREPARING','BALL_ACTIVE'],'Resume':['PAUSED'],'End game':['PREPARING','BALL_ACTIVE','PAUSED','RECOVERY_REQUIRED'],'Award extra ball':['PREPARING','BALL_ACTIVE'],'Activate ball save':['BALL_ACTIVE']}[button.textContent];button.disabled=allowed&&!allowed.includes(g.status);}
      if(c.testCredits)controls.append(btn('Test credit',()=>command('REQUEST_AWARD_CREDIT',{units:c.unitsPerCredit})));
      document.getElementById('manager-table-title').textContent='Players and scores';
      table(['Player','Score','Extra balls','Turn'],g.players.map(p=>[p.name,String(view.scores[p.id]?.score||0),String(p.extraBalls),Number(p.id)===g.currentPlayer?'Current':'Waiting']));
    }else{
      stats([['Physical inventory',view.ballConfig.inventory],['In-play estimate',b.inPlay],['Confidence',b.confidence],['Pending movements',b.pending.length],['Last observation',b.lastObservation?new Date(b.lastObservation).toLocaleTimeString('en-GB'):'Never']]);
      controls.append(btn('Reconcile physical state',reconcile));
      document.getElementById('manager-table-title').textContent='Sensors and observations';
      table(['Sensor','Role','Observation','Last seen'],view.ballConfig.sensors.map(s=>{const obs=b.sensors[s.source];return [hardware.find(h=>h.id===s.source)?.friendly||s.source,s.role,obs?(obs.active?'Active':'Inactive'):'Unknown',obs?new Date(obs.at).toLocaleTimeString('en-GB'):'Never'];}));
      const extra=document.getElementById('manager-extra');extra.replaceChildren();
      for(const [source,reason] of Object.entries(b.alerts||{}))extra.append(el('p',source+': '+reason,'alert alert-warning'));
      for(const d of view.ballConfig.devices){const row=el('div',undefined,'card p-3 mb-3'),observed=b.zones[d.id];row.append(el('h2',d.name||d.id,'h5'),el('p',`${observed?.count??'Unknown'} / ${d.capacity} · ${observed?.confidence||'unknown'}`),btn('Request movement',()=>command('REQUEST_BALL_MOVEMENT',{deviceId:d.id})));extra.append(row);}
      if(c.testCredits){const simulation=el('div',undefined,'card p-3 mb-3');simulation.append(el('h2','Input simulation','h5'),el('p','Test mode only. Does not operate outputs.','text-secondary'));for(const s of view.ballConfig.sensors){simulation.append(btn((hardware.find(h=>h.id===s.source)?.friendly||s.source)+' active',()=>command('OBSERVE',{sensor:s.source,active:true})),btn('Clear',()=>command('OBSERVE',{sensor:s.source,active:false})));}extra.append(simulation);}
    }
    if(g.reason){const reason=el('p',g.reason,g.status==='RECOVERY_REQUIRED'?'alert alert-warning':'text-secondary');document.getElementById('manager-summary').append(reason);}
    const timeline=document.getElementById('manager-timeline');timeline.replaceChildren();for(const e of view.timeline||[]){timeline.append(el('div',`${e.params.timestampMs?new Date(e.params.timestampMs).toLocaleTimeString('en-GB')+' · ':''}${e.name.replaceAll('_',' ')} · player ${e.params.playerId||'—'}`,'list-group-item'));}
  }
  function reconcile(){open('Reconcile physical state');body.append(el('p','Inspect the machine first. This records your observation; it does not launch balls or energise outputs. Pause an active game before reconciling.'));const count=field(body,'Balls currently in play',view.ball.inPlay??0,'number'),reason=field(body,'Reason / physical evidence','');footer.append(btn('Record reconciliation',async()=>{await command('RECONCILE',{inPlay:Number(count.value),reason:reason.value});drawer.hide();},'btn btn-success'));}
  function settings(){
    open(kind==='game'?'Game settings':'Ball settings');body.append(el('p','Settings apply to the next game. End the active game before saving.','text-secondary'));
    if(kind==='game'){
      const cfg={...view.gameConfig},inputs={};const labels={maxPlayers:'Maximum players',ballsPerPlayer:'Balls per player',creditCost:'Credits per player',unitsPerCredit:'Coin units per credit',ballSaveMs:'Ball save after launch (ms)',bonusPoints:'End-of-turn bonus points'};
      for(const [key,label] of Object.entries(labels))inputs[key]=field(body,label,cfg[key],'number');
      const inputOptions=[{value:'',label:'None / use Rules'},...hardware.filter(h=>['button','switch'].includes(h.deviceClass)).map(h=>({value:h.id,label:h.friendly}))];
      const start=field(body,'Start button',cfg.startInput,'text',inputOptions),startPolicy=field(body,'Start button during a game',cfg.startButton,'text',[{value:'start_or_join',label:'Add player when joining is open'},{value:'start_only',label:'Start only'}]);
      const free=field(body,'Free play',cfg.freePlay,'text',['true','false']),join=field(body,'Joining policy',cfg.joinPolicy,'text',[{value:'first_ball',label:'During first ball'},{value:'before_launch',label:'Before first launch'},{value:'never',label:'No additional players'}]);
      const advanced=el('details');advanced.append(el('summary','Advanced / test settings'));body.append(advanced);const test=field(advanced,'Allow operator test credits and simulation',cfg.testCredits,'text',['false','true']),denoms=field(advanced,'Accepted coin denominations (units, comma separated)',cfg.denominations.join(', '));
      const coinRows=el('div');advanced.append(el('h3','Coin inputs','h6'),coinRows);
      function coinRow(coin){const row=el('fieldset'),source=field(row,'Coin input',coin.source,'text',inputOptions),units=field(row,'Denomination (units)',coin.units||100,'number');row.read=()=>({source:source.value,units:Number(units.value)});row.append(btn('Remove',()=>row.remove()));coinRows.append(row);}
      cfg.coinInputs.forEach(coinRow);advanced.append(btn('Add coin input',()=>coinRow({})));
      footer.append(btn('Save settings',async()=>{for(const key in inputs)cfg[key]=Number(inputs[key].value);cfg.freePlay=free.value==='true';cfg.testCredits=test.value==='true';cfg.joinPolicy=join.value;cfg.startInput=start.value;cfg.startButton=startPolicy.value;cfg.coinInputs=[...coinRows.children].map(row=>row.read()).filter(row=>row.source);cfg.denominations=denoms.value.split(',').map(v=>Number(v.trim()));await api('/config',cfg);drawer.hide();await load();notice.textContent='Settings saved. Sync Rules to deploy input observations to the ESP.';},'btn btn-success'));
    }else{
      const cfg=structuredClone(view.ballConfig),inventory=field(body,'Physical balls in machine',cfg.inventory,'number');
      body.append(el('h3','Sensors','h5'));const sensors=el('div');body.append(sensors);
      function sensorRow(s){const group=el('fieldset');sensors.append(group);const source=field(group,'Mapped input',s.source,'text',[{value:'',label:'Choose input…'},...hardware.filter(h=>['button','switch'].includes(h.deviceClass)).map(h=>({value:h.id,label:h.friendly}))]);const role=field(group,'Role',s.role,'text',['launch','drain','occupancy','entrance','exit','lock']),zone=field(group,'Device / zone ID (optional)',s.zone||''),active=field(group,'Active level',s.active??true,'text',['true','false']),debounce=field(group,'Debounce (ms)',s.debounceMs??50,'number');group.read=()=>({source:source.value,role:role.value,zone:zone.value,active:active.value==='true',debounceMs:Number(debounce.value)});group.append(btn('Remove sensor',()=>group.remove(),'btn btn-outline-danger'));}
      cfg.sensors.forEach(sensorRow);body.append(btn('Add sensor',()=>sensorRow({role:'launch'})));
      const advanced=el('details',undefined,'mt-3');advanced.append(el('summary','Devices and advanced settings'));body.append(advanced);const devices=el('div');advanced.append(devices);
      function deviceRow(d){const group=el('fieldset');devices.append(group);const id=field(group,'Device ID',d.id||''),name=field(group,'Friendly name',d.name||''),capacity=field(group,'Capacity',d.capacity||1,'number'),destination=field(group,'Expected destination ID',d.destination||''),timeout=field(group,'Movement timeout (ms)',d.timeoutMs||5000,'number');const output=field(group,'Release output (optional)',d.releaseOutput||'','text',[{value:'',label:'Observation only'},...hardware.filter(h=>!['button','switch'].includes(h.deviceClass)).map(h=>({value:h.id,label:h.friendly}))]),pulse=field(group,'Release pulse (ms, maximum 250)',d.pulseMs||30,'number');group.read=()=>({id:id.value,name:name.value,capacity:Number(capacity.value),destination:destination.value,timeoutMs:Number(timeout.value),releaseOutput:output.value,pulseMs:Number(pulse.value)});group.append(btn('Remove device',()=>group.remove(),'btn btn-outline-danger'));}
      cfg.devices.forEach(deviceRow);advanced.append(btn('Add device',()=>deviceRow({})));const stale=field(advanced,'Sensor freshness timeout (ms)',cfg.staleMs,'number');
      footer.append(btn('Save settings',async()=>{cfg.inventory=Number(inventory.value);cfg.staleMs=Number(stale.value);cfg.sensors=[...sensors.children].map(g=>g.read());cfg.devices=[...devices.children].map(g=>g.read());await api('/config',cfg);drawer.hide();await load();notice.textContent='Settings saved. Sync Rules to deploy input observations to the ESP.';},'btn btn-success'));
    }
  }
  async function load(){view=await api('/status');render();}
  document.getElementById('manager-config').onclick=()=>run(settings);
  run(async()=>{hardware=(await (await fetch('/api/rules/hardware')).json()).devices||[];await load();});
  setInterval(()=>{if(!busy&&!document.hidden)run(load);},1500);
})();
