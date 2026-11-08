(() => {
  'use strict';
  const root=document.getElementById('manager-root');if(!root)return;
  const kind=root.dataset.manager,body=document.getElementById('manager-body'),footer=document.getElementById('manager-footer'),notice=document.getElementById('manager-notice');
  const drawer=bootstrap.Offcanvas.getOrCreateInstance(document.getElementById('manager-drawer'));
  let view,hardware=[],busy=false,refreshReset;
  let pendingCommand;try{pendingCommand=JSON.parse(sessionStorage.getItem('manager-pending-'+kind)||'null');}catch{}
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
  const btn=(text,fn,cls='btn btn-outline-secondary',iconClass)=>{
    const n=el('button',text,cls);n.type='button';n.onclick=()=>run(fn);
    if(iconClass){
      const icon=el('i',undefined,'fa '+iconClass);
      icon.setAttribute('aria-hidden','true');
      n.prepend(icon,' ');
    }
    return n;
  };
  async function run(fn){if(busy)return;busy=true;try{await fn();}catch(e){
    const target=body.closest('.offcanvas').classList.contains('show')?body.querySelector('[role="alert"]'):notice;
    target.textContent=e.message;target.className='alert alert-warning';
  }finally{busy=false;}}
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
  function open(title){refreshReset=null;document.getElementById('manager-title').textContent=title;body.replaceChildren();const error=el('div');error.setAttribute('role','alert');body.append(error);footer.replaceChildren(btn('Close',()=>drawer.hide(),undefined,'fa-xmark'));drawer.show();}
  function stats(items){const summary=document.getElementById('manager-summary');summary.replaceChildren();for(const [label,value] of items){const card=el('div',undefined,'manager-stat');card.append(el('span',label,'small text-secondary'),el('strong',value===null?'Unknown':String(value)));summary.append(card);}}
  function table(headings,rows){document.getElementById('manager-head').replaceChildren();const tr=el('tr');headings.forEach(h=>{const th=el('th',h);th.scope='col';tr.append(th);});document.getElementById('manager-head').append(tr);const target=document.getElementById('manager-rows');target.replaceChildren();for(const cells of rows){const row=el('tr');cells.forEach(c=>row.append(el('td',c)));target.append(row);}if(!rows.length){const row=el('tr'),cell=el('td','Nothing recorded yet.','text-secondary');cell.colSpan=headings.length;row.append(cell);target.append(row);}}
  async function endGame(){
    const modalEl=document.getElementById('generic-confirm-modal');
    const modal=bootstrap.Modal.getOrCreateInstance(modalEl,{backdrop:'static'});
    const accept=modalEl.querySelector('[data-confirm-accept]');
    const trigger=document.activeElement;
    modalEl.querySelector('.modal-title').textContent='End game?';
    modalEl.querySelector('.modal-body').textContent='This ends the current game for all players.';
    accept.textContent='End game';
    accept.disabled=true;
    modalEl.addEventListener('shown.bs.modal',()=>{accept.disabled=false;},{once:true});
    let confirmed=false;
    const confirmEnd=()=>{
      confirmed=true;
      modal.hide();
    };
    accept.addEventListener('click',confirmEnd,{once:true});
    await new Promise(resolve=>{
      modalEl.addEventListener('hidden.bs.modal',resolve,{once:true});
      modal.show();
    });
    accept.removeEventListener('click',confirmEnd);
    if(confirmed)await command('REQUEST_END_GAME');
    else trigger?.focus();
  }
  function render(){
    const g=view.game,b=view.ball,c=view.gameConfig,controls=document.getElementById('manager-controls');controls.replaceChildren();
    if(kind==='game'){
      const labels={IDLE:'Idle',PREPARING:'Waiting for launch',BALL_ACTIVE:'Ball active',PAUSED:'Paused',RECOVERY_REQUIRED:'Recovery required',GAME_ENDED:'Game ended'};
      const idle=['IDLE','GAME_ENDED'].includes(g.status);
      const active=['PREPARING','BALL_ACTIVE'].includes(g.status);
      const policy=idle?c:g.policy;
      const canPay=policy.freePlay||g.credits>=policy.creditCost;
      stats([['Status',labels[g.status]||g.status],['Player',idle?'—':g.currentPlayer||'—'],['Ball',idle?'—':g.ballNumber||'—'],['Credits',c.freePlay?'Free play':g.credits],['Coin units',g.creditUnits]]);
      const add=(label,name,icon,cls,params)=>controls.append(btn(label,()=>command(name,params),cls,icon));
      if(idle&&!view.settlingSeconds&&!b.pending.length&&(b.inPlay===null||b.inPlay===0)){
        add('Start game','REQUEST_START_GAME','fa-play','btn btn-success');
        controls.lastElementChild.disabled=!canPay;
        if(!canPay)controls.append(el('span',`Requires ${policy.creditCost} credit(s).`,'align-self-center text-secondary'));
      }
      if(active){
        if(canPay&&g.players.length<policy.maxPlayers&&g.ballNumber===1&&policy.joinPolicy!=='never'&&(policy.joinPolicy!=='before_launch'||g.status==='PREPARING')){
          add('Add player','REQUEST_ADD_PLAYER','fa-user-plus');
        }
        add('Pause','REQUEST_PAUSE_GAME','fa-pause');
        if((g.players[g.currentPlayer-1]?.extraBalls??1000)<1000)add('Award extra ball','REQUEST_AWARD_EXTRA_BALL','fa-circle-plus',undefined,{count:1});
        if(g.status==='BALL_ACTIVE')add('Activate ball save','REQUEST_BALL_SAVE','fa-shield',undefined,{durationMs:policy.ballSaveMs||10000});
      }
      if(g.status==='PAUSED'&&b.inPlay!==null&&!b.pending.length)add('Resume','REQUEST_RESUME_GAME','fa-play');
      if(!idle)controls.append(btn('End game',endGame,'btn btn-outline-danger','fa-stop'));
      if(pendingCommand)controls.append(btn('Retry unconfirmed request',()=>command(pendingCommand.command,pendingCommand.params),undefined,'fa-rotate-right'));
      document.getElementById('game-credit-summary').textContent=
        `${g.credits} credits available · ${g.creditUnits} / ${c.unitsPerCredit} units toward the next credit · ${c.freePlay?'Free play':c.creditCost+' credits per player'}`;
      const sources=document.getElementById('game-credit-sources');
      sources.replaceChildren();
      for(const coin of c.coinInputs){
        const row=el('tr');
        row.append(el('td','Coin input'),el('td',inputName(coin.source)),el('td',String(coin.units)));
        sources.append(row);
      }
      if(!c.coinInputs.length){
        const row=el('tr'),cell=el('td','No coin inputs configured.','text-secondary');
        cell.colSpan=3;
        row.append(cell);
        sources.append(row);
      }
      const tests=document.getElementById('game-test-controls');
      if(!tests.firstElementChild){
        tests.append(btn('Add test credit',()=>command('REQUEST_AWARD_CREDIT',{units:view.gameConfig.unitsPerCredit}),'btn btn-sm btn-outline-secondary','fa-coins'));
      }
      document.getElementById('manager-table-title').textContent='Players and scores';
      table(['Player','Score','Extra balls','Turn'],g.players.map(p=>[p.name,String(view.scores[p.id]?.score||0),String(p.extraBalls),Number(p.id)===g.currentPlayer?'Current':'Waiting']));
    }else{
      renderBallConfig();
      const resetButton=document.getElementById('ball-locations-reset');
      resetButton.disabled=!view.ballConfig.devices.length;
      if(refreshReset)refreshReset();
      stats([['Physical inventory',view.ballConfig.inventory],['In-play estimate',b.inPlay],['Confidence',b.confidence],['Pending movements',b.pending.length],['Last observation',b.lastObservation?new Date(b.lastObservation).toLocaleTimeString('en-GB'):'Never']]);
      document.getElementById('manager-table-title').textContent='Sensors and observations';
      table(['Sensor','Role','Observation','Last seen'],view.ballConfig.sensors.map(s=>{const obs=b.sensors[s.source];return [hardware.find(h=>h.id===s.source)?.friendly||s.source,roleLabel(s.role),obs?(obs.active?'Active':'Inactive'):'Unknown',obs?new Date(obs.at).toLocaleTimeString('en-GB'):'Never'];}));
      const extra=document.getElementById('manager-extra');extra.replaceChildren();
      for(const [source,reason] of Object.entries(b.alerts||{}))extra.append(el('p',inputName(source)+': '+reason,'alert alert-warning'));
      const locationStatus=document.getElementById('ball-location-status');
      locationStatus.replaceChildren();
      locationStatus.hidden=!view.ballConfig.devices.length;
      for(const d of view.ballConfig.devices){
        const row=el('div',undefined,'card p-3');
        const estimate=view.troughEstimate?.location===d.id?view.troughEstimate:null;
        const observed=estimate||b.zones[d.id];
        const confidence=observed?.confidence||'unknown';
        row.append(el('h2',locationName(d),'h5'),el('p',`${observed?.count??'Unknown'} / ${d.capacity} balls · ${estimate?roleLabel(confidence):confidence}`,'mb-0'));
        const manual=b.manualLocations?.counts?.[d.id];
        if(manual!==undefined)row.append(el('p',`Manual count: ${manual}`,'small text-secondary mb-0'));
        if(d.destination)row.append(btn('Request movement',()=>command('REQUEST_BALL_MOVEMENT',{deviceId:d.id}),'btn btn-outline-secondary align-self-start mt-2','fa-chevron-right'));
        locationStatus.append(row);
      }
      if(c.testCredits){const simulation=el('div',undefined,'card p-3 mb-3');simulation.append(el('h2','Input simulation','h5'),el('p','Test mode only. Does not operate outputs.','text-secondary'));for(const s of view.ballConfig.sensors){simulation.append(btn((hardware.find(h=>h.id===s.source)?.friendly||s.source)+' active',()=>command('OBSERVE',{sensor:s.source,active:true}),undefined,'fa-play'),btn('Clear',()=>command('OBSERVE',{sensor:s.source,active:false}),undefined,'fa-stop'));}extra.append(simulation);}
    }
    const reason=document.getElementById('manager-status-reason');
    const recoveryRequired=g.status==='RECOVERY_REQUIRED';
    const settling=view.settlingSeconds>0;
    reason.hidden=!settling&&(!g.reason||(kind==='ball'&&!recoveryRequired));
    reason.className=recoveryRequired?'alert alert-warning':'text-secondary';
    reason.textContent=settling?'Waiting for balls to settle after startup.':reason.hidden?'':g.reason;

  }
  function saveGameSettings(edit){
    footer.append(btn('Save settings',async()=>{
      const cfg={...view.gameConfig};
      edit(cfg);
      await api('/config',cfg);
      drawer.hide();
      await load();
      notice.textContent='Settings saved. Sync Rules after changing mapped inputs.';
    },'btn btn-success','fa-floppy-disk'));
  }
  function creditSettings(){
    open('Credit settings');
    body.append(el('p','End the active game before saving changes.','text-secondary'));
    const cfg=view.gameConfig;
    const free=field(body,'Play mode',cfg.freePlay,'text',[{value:'true',label:'Free play'},{value:'false',label:'Credit-based play'}]);
    const cost=field(body,'Credits per player',cfg.creditCost,'number');
    const unitsPerCredit=field(body,'Units per credit',cfg.unitsPerCredit,'number');
    const denominations=field(body,'Accepted coin values (units, comma separated)',cfg.denominations.join(', '));
    const options=[{value:'',label:'Choose a mapped switch…'},...hardware.filter(h=>['button','switch'].includes(h.deviceClass)).map(h=>({value:h.id,label:h.friendly}))];
    const rows=el('div');
    body.append(el('h3','Coin inputs','h6'),rows);
    function coinRow(coin){
      const row=el('fieldset');
      const source=field(row,'Coin input',coin.source,'text',options);
      const units=field(row,'Value in units',coin.units??Number(unitsPerCredit.value),'number');
      row.read=()=>({source:source.value,units:Number(units.value)});
      row.append(btn('Remove',()=>row.remove(),undefined,'fa-trash'));
      rows.append(row);
    }
    cfg.coinInputs.forEach(coinRow);
    body.append(btn('Add coin input',()=>coinRow({}),undefined,'fa-plus'));
    saveGameSettings(next=>{
      next.freePlay=free.value==='true';
      next.creditCost=Number(cost.value);
      next.unitsPerCredit=Number(unitsPerCredit.value);
      next.denominations=denominations.value.split(',').map(value=>Number(value.trim()));
      next.coinInputs=[...rows.children].map(row=>row.read()).filter(row=>row.source);
    });
  }
  function settings(){
    open(kind==='game'?'Game settings':'Ball settings');body.append(el('p','Settings apply to the next game. End the active game before saving.','text-secondary'));
    if(kind==='game'){
      const cfg={...view.gameConfig},inputs={};const labels={maxPlayers:'Maximum players',ballsPerPlayer:'Balls per player',ballSaveMs:'Ball save after launch (ms)',bonusPoints:'End-of-turn bonus points'};
      for(const [key,label] of Object.entries(labels))inputs[key]=field(body,label,cfg[key],'number');
      const inputOptions=[{value:'',label:'None / use Rules'},...hardware.filter(h=>['button','switch'].includes(h.deviceClass)).map(h=>({value:h.id,label:h.friendly}))];
      const start=field(body,'Start button',cfg.startInput,'text',inputOptions),startPolicy=field(body,'Start button during a game',cfg.startButton,'text',[{value:'start_or_join',label:'Add player when joining is open'},{value:'start_only',label:'Start only'}]);
      const join=field(body,'Joining policy',cfg.joinPolicy,'text',[{value:'first_ball',label:'During first ball'},{value:'before_launch',label:'Before first launch'},{value:'never',label:'No additional players'}]);
      const simulation=field(body,'Enable Ball Management input simulation',cfg.testCredits,'text',[{value:'false',label:'Off'},{value:'true',label:'On'}]);
      saveGameSettings(cfg=>{
        for(const key in inputs)cfg[key]=Number(inputs[key].value);
        cfg.testCredits=simulation.value==='true';
        cfg.joinPolicy=join.value;
        cfg.startInput=start.value;
        cfg.startButton=startPolicy.value;
      });
    }else{
      const inventory=field(body,'Physical balls in machine',view.ballConfig.inventory,'number');
      const stale=field(body,'Sensor freshness timeout (ms)',view.ballConfig.staleMs,'number');
      const locations=view.ballConfig.devices;
      const trough=field(body,'Infer trough count',view.ballConfig.inferredTrough||'','text',
        locationOptions(locations,'Off'));
      const launcher=field(body,'Launcher for trough inference',view.ballConfig.inferredLauncher||'','text',
        locationOptions(locations.filter(d=>d.capacity===1),'Choose a single-ball launcher…'));
      launcher.disabled=!trough.value;
      trough.addEventListener('change',()=>{launcher.disabled=!trough.value;});
      body.append(el('p','Choose an unsensed trough and a launcher with an occupancy switch. The estimate subtracts balls in play and at other locations.','form-text'));
      saveButton('Save settings',cfg=>{
        cfg.inventory=Number(inventory.value);
        cfg.staleMs=Number(stale.value);
        cfg.inferredTrough=trough.value;
        cfg.inferredLauncher=trough.value?launcher.value:'';
      });
    }
  }

  const roles={
    launch:'Ball leaves the shooter lane and enters play.',
    drain:'Ball leaves play at the drain.',
    occupancy:'Switch stays active while a ball is parked at this location.',
    entrance:'Switch detects a ball entering this location.',
    exit:'Switch detects a ball leaving this location.',
    lock:'Switch detects a ball entering a lock.'
  };
  const roleLabel=role=>role.charAt(0).toUpperCase()+role.slice(1);
  const switchInput=h=>['button','switch'].includes(h.deviceClass);
  const inputName=id=>hardware.find(h=>h.id===id)?.friendly||id;
  const locationName=d=>d.name||d.id;

  async function saveBall(change){
    // Use the latest configuration from polling and apply only this edit.
    const cfg=structuredClone(view.ballConfig);
    change(cfg);
    await api('/config',cfg);
    drawer.hide();
    await load();
    notice.className='alert alert-success';
    notice.textContent='Settings saved. Run Sync Rules to deploy sensor watches to the ESP.';
  }

  function saveButton(label,change){
    footer.append(btn(label,()=>saveBall(change),'btn btn-success','fa-floppy-disk'));
  }

  function hardwareOptions(predicate,selected,emptyLabel){
    const options=[{value:'',label:emptyLabel},...hardware.filter(predicate).map(h=>({value:h.id,label:h.friendly||h.id}))];
    if(selected&&!options.some(o=>o.value===selected))options.push({value:selected,label:selected+' (unavailable)'});
    return options;
  }

  function locationOptions(devices,emptyLabel){
    return [{value:'',label:emptyLabel},...devices.map(d=>({value:d.id,label:locationName(d)}))];
  }

  function resetLocations(){
    if(!['IDLE','GAME_ENDED'].includes(view.game.status)){
      throw new Error('End the current game before resetting ball locations.');
    }
    if(!view.locationEvidence){
      throw new Error('The running app has not loaded the ball reset update. Reload the app service and refresh this page.');
    }
    open('Reset ball locations');
    body.append(el('p','Inspect the machine and enter how many balls are at each location. Use zero for an empty location.','text-secondary'));
    const locations=view.ballConfig.devices;
    const entries=locations.map(location=>{
      const group=el('div');
      body.append(group);
      const reading=view.locationEvidence?.[location.id];
      const complete=reading?.configured&&reading.read===reading.configured;
      const value=view.ball.manualLocations?.counts?.[location.id]??(complete?reading.active:'');
      const input=field(group,locationName(location),value,'number');
      input.min='0';
      input.max=String(location.capacity);
      input.step='1';
      const feedback=el('p',undefined,'small');
      feedback.id=input.id+'-reading';
      input.setAttribute('aria-describedby',feedback.id);
      group.append(feedback);
      return {location,input,feedback};
    });
    const total=el('p',undefined,'fw-semibold');
    total.setAttribute('role','status');
    const confirmMismatch=el('input',undefined,'form-check-input');
    confirmMismatch.type='checkbox';
    const confirmLabel=el('label',undefined,'form-check mb-3');
    confirmLabel.append(confirmMismatch,el('span','Use my counts despite the sensor differences','form-check-label'));
    body.append(total,confirmLabel);
    let counts,mismatches,signature;
    const save=btn('Confirm ball counts',async()=>{
      await command('RESET_BALL_LOCATIONS',{counts,confirmedMismatches:mismatches});
      drawer.hide();
      notice.className='alert alert-success';
      notice.textContent='Manual ball counts saved.';
    },'btn btn-success','fa-check');
    footer.append(save);
    refreshReset=()=>{
      counts=Object.create(null);
      mismatches=Object.create(null);
      let valid=true;
      for(const {location,input,feedback} of entries){
        const count=input.valueAsNumber;
        counts[location.id]=count;
        valid=valid&&Number.isInteger(count)&&count>=0&&count<=location.capacity;
        const reading=view.locationEvidence?.[location.id];
        const complete=reading?.configured&&reading.read===reading.configured;
        const mismatch=reading&&(count<reading.active||(complete&&Number.isInteger(count)&&count!==reading.active));
        if(mismatch)mismatches[location.id]=reading;
        const evidence=complete?`Sensors see ${reading.active}.`:reading?.read
          ?`${reading.active} detected so far (${reading.read} of ${reading.configured} switches read).`
          :reading?.configured?'Waiting for occupancy readings.':'No occupancy switches configured.';
        feedback.className=mismatch?'small text-warning':'small text-secondary';
        feedback.textContent=`${evidence}${mismatch?' Differs from your count.':''} Capacity: ${location.capacity}.`;
      }
      const sum=Object.values(counts).reduce((n,count)=>n+(Number.isFinite(count)?count:0),0);
      const inventory=view.ballConfig.inventory;
      total.textContent=`${sum} of ${inventory} balls accounted for`;
      const nextSignature=JSON.stringify([counts,mismatches]);
      if(signature!==nextSignature)confirmMismatch.checked=false;
      signature=nextSignature;
      const hasMismatch=Object.keys(mismatches).length>0;
      confirmLabel.hidden=!hasMismatch;
      save.disabled=!valid||sum!==inventory||(hasMismatch&&!confirmMismatch.checked);
    };
    for(const {input} of entries)input.addEventListener('input',refreshReset);
    confirmMismatch.addEventListener('change',refreshReset);
    refreshReset();
  }

  function editSensor(sensor){
    const s=sensor||{role:'launch'};
    open(sensor?'Edit sensor':'Add sensor');
    const source=field(body,'Mapped switch',s.source,'text',hardwareOptions(
      h=>switchInput(h)&&!view.ballConfig.sensors.some(other=>other.source===h.id&&h.id!==s.source),
      s.source,'Choose a switch…'));
    const role=field(body,'Role',s.role,'text',Object.keys(roles).map(value=>({value,label:roleLabel(value)})));
    const help=el('p',roles[role.value],'form-text mb-3');
    role.addEventListener('change',()=>{help.textContent=roles[role.value];});
    body.append(help);
    const zone=field(body,'Ball location',s.zone,'text',locationOptions(view.ballConfig.devices,'No location'));
    body.append(el('p','Leave this blank for Launch and Drain. For a switch that tracks a trough or lock, add that location in Ball Locations, then select it here.','form-text mb-3'));
    const active=field(body,'Active level',s.active??true,'text',[
      {value:'true',label:'Active when switch reports on'},
      {value:'false',label:'Active when switch reports off'}
    ]);
    const debounce=field(body,'Debounce (ms)',s.debounceMs??50,'number');
    saveButton('Save sensor',cfg=>{
      if(!source.value)throw new Error('Choose a mapped switch.');
      const updated={source:source.value,role:role.value,zone:zone.value,active:active.value==='true',debounceMs:Number(debounce.value)};
      replaceEntry(cfg.sensors,sensor,updated,'source');
    });
  }

  function editLocation(location){
    const d=location||{};
    open(location?'Edit ball location':'Add ball location');
    const name=field(body,'Name',d.name||d.id||'');
    const capacity=field(body,'Maximum balls it can hold',d.capacity??1,'number');
    const advanced=el('details',undefined,'mt-3');
    advanced.append(el('summary','Movement and release options'));
    body.append(advanced);
    const destination=field(advanced,'Expected destination',d.destination,'text',locationOptions(view.ballConfig.devices,'No destination'));
    const timeout=field(advanced,'Movement timeout (ms)',d.timeoutMs??5000,'number');
    const output=field(advanced,'Release output',d.releaseOutput,'text',hardwareOptions(h=>['output','coil'].includes(h.deviceClass),d.releaseOutput,'Observation only'));
    const pulse=field(advanced,'Release pulse (ms, maximum 250)',d.pulseMs??30,'number');
    saveButton('Save location',cfg=>{
      if(!name.value.trim())throw new Error('Enter a name for this location.');
      const updated={id:d.id||crypto.randomUUID(),name:name.value.trim(),capacity:Number(capacity.value),
        destination:destination.value,timeoutMs:Number(timeout.value),releaseOutput:output.value,pulseMs:Number(pulse.value)};
      replaceEntry(cfg.devices,location,updated,'id');
    });
  }

  function replaceEntry(entries,original,updated,key){
    if(!original){entries.push(updated);return;}
    const index=entries.findIndex(entry=>entry[key]===original[key]);
    if(index<0||JSON.stringify(entries[index])!==JSON.stringify(original))throw new Error('This entry changed. Close the panel and reopen it before editing.');
    entries[index]=updated;
  }

  function configRow(target,values,label,edit,remove){
    const row=el('tr');
    values.forEach(value=>row.append(el('td',value)));
    const actions=el('td',undefined,'text-end text-nowrap');
    const editButton=btn(undefined,edit,'btn btn-sm btn-outline-secondary me-1');
    const removeButton=btn(undefined,async()=>{
      if(confirm('Remove '+label+'?'))await saveBall(remove);
    },'btn btn-sm btn-outline-danger');
    for(const [button,action,iconClass] of [[editButton,'Edit','fa-pen'],[removeButton,'Remove','fa-trash']]){
      const description=action+' '+label;
      button.setAttribute('aria-label',description);
      button.title=description;
      const icon=el('i',undefined,'fa '+iconClass);
      icon.setAttribute('aria-hidden','true');
      button.append(icon);
    }
    actions.append(editButton,removeButton);
    row.append(actions);
    target.append(row);
  }

  let renderedBallConfig;
  function renderBallConfig(){
    const {sensors,devices}=view.ballConfig;
    const snapshot=JSON.stringify([sensors,devices]);
    if(snapshot===renderedBallConfig)return;
    renderedBallConfig=snapshot;
    const sensorRows=document.getElementById('ball-sensors-rows'),locationRows=document.getElementById('ball-locations-rows');
    sensorRows.replaceChildren();
    locationRows.replaceChildren();
    for(const sensor of sensors){
      const name=inputName(sensor.source),location=devices.find(d=>d.id===sensor.zone);
      configRow(sensorRows,[name,roleLabel(sensor.role),location?locationName(location):'—'],name,
        ()=>editSensor(sensor),cfg=>{
          cfg.sensors=cfg.sensors.filter(s=>s.source!==sensor.source);
        });
    }
    for(const location of devices){
      const name=locationName(location);
      const count=sensors.filter(s=>s.zone===location.id).length;
      configRow(locationRows,[name,String(location.capacity),String(count)],name,()=>editLocation(location),cfg=>{
        if([cfg.inferredTrough,cfg.inferredLauncher].includes(location.id)){
          throw new Error('Turn off trough inference in Settings before removing this location.');
        }
        if(cfg.sensors.some(s=>s.zone===location.id)||cfg.devices.some(d=>d.destination===location.id&&d.id!==location.id)){
          throw new Error('Remove this location from its sensors and movement destinations first.');
        }
        cfg.devices=cfg.devices.filter(d=>d.id!==location.id);
      });
    }
    for(const [target,message] of [[sensorRows,'No sensors configured.'],[locationRows,'No ball locations configured.']]){
      if(target.children.length)continue;
      const row=el('tr'),cell=el('td',message,'text-secondary');
      cell.colSpan=4;
      row.append(cell);
      target.append(row);
    }
  }
  async function load(){view=await api('/status');render();}
  document.getElementById('manager-config').onclick=()=>run(settings);
  {
    const tabKey='pinballctl.'+kind+'.activeTab.v1';
    const tabs=root.querySelectorAll('[data-bs-toggle="tab"]');
    let savedTab;
    try{savedTab=localStorage.getItem(tabKey);}catch{}
    for(const tab of tabs){
      tab.addEventListener('shown.bs.tab',()=>{
        try{localStorage.setItem(tabKey,tab.id);}catch{}
      });
      if(tab.id===savedTab)bootstrap.Tab.getOrCreateInstance(tab).show();
    }
  }
  if(kind==='ball'){
    document.getElementById('ball-sensors-add').onclick=()=>run(()=>editSensor());
    document.getElementById('ball-locations-add').onclick=()=>run(()=>editLocation());
    document.getElementById('ball-locations-reset').onclick=()=>run(resetLocations);
    document.getElementById('manager-drawer').addEventListener('hidden.bs.offcanvas',()=>{refreshReset=null;});
  }
  if(kind==='game')document.getElementById('game-credit-settings').onclick=()=>run(creditSettings);
  run(async()=>{hardware=(await (await fetch('/api/rules/hardware')).json()).devices||[];await load();});
  setInterval(()=>{if(!busy&&!document.hidden)run(load);},1500);
})();
