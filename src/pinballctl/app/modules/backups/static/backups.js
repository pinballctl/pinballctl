(() => {
  'use strict';
  const root=document.getElementById('backup-root');if(!root)return;
  const list=document.getElementById('backup-list'), status=document.getElementById('backup-status');
  const panel=document.getElementById('backup-drawer'),body=document.getElementById('backup-drawer-body'),footer=document.getElementById('backup-drawer-footer'),title=document.getElementById('backup-drawer-title');
  const drawer=bootstrap.Offcanvas.getOrCreateInstance(panel);
  let rows=[],components={},sort='createdAt',descending=true,busy=false,restoreSequence=[],clearOthers=false;
  function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
  function button(text,action,cls='btn btn-outline-secondary'){const b=el('button',text,cls);b.type='button';b.onclick=()=>run(action);return b;}
  function actionButton(text,icon,action,cls){const b=button(text,action,cls);const i=el('i',undefined,'fa fa-'+icon+' me-1');i.setAttribute('aria-hidden','true');b.prepend(i);return b;}
  function setStatus(text){status.textContent=text;const live=document.getElementById('backup-drawer-status');if(live)live.textContent=text;}
  function show(name){title.textContent=name;body.replaceChildren();const live=el('div',undefined,'small text-secondary mb-2');live.id='backup-drawer-status';live.setAttribute('role','status');live.setAttribute('aria-live','polite');body.append(live);footer.replaceChildren(button('Close',()=>drawer.hide()));drawer.show();}
  async function run(fn){
    if(busy)return;busy=true;root.setAttribute('aria-busy','true');
    const controls=[...panel.querySelectorAll('input,select,button:not([data-bs-dismiss])'),document.getElementById('backup-create'),document.getElementById('backup-upload')];
    controls.forEach(n=>{n.dataset.wasDisabled=String(n.disabled);n.disabled=true;});
    try{await fn();}catch(e){setStatus(e.message);status.setAttribute('role','alert');}
    finally{busy=false;root.removeAttribute('aria-busy');controls.forEach(n=>{n.disabled=n.dataset.wasDisabled==='true';delete n.dataset.wasDisabled;});if(panel.classList.contains('show')&&!panel.contains(document.activeElement)){title.tabIndex=-1;title.focus();}}
  }
  async function api(path,data){const r=await fetch('/api/backups'+path,data===undefined?{cache:'no-store'}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const j=await r.json();if(!r.ok||j.ok===false)throw new Error(j.error||j.detail||'Operation failed');return j;}
  function size(n){const units=['B','KB','MB','GB'];let u=0;while(n>=1024&&u<3){n/=1024;u++;}return new Intl.NumberFormat(undefined,{maximumFractionDigits:1}).format(n)+' '+units[u];}
  function scope(r){return r.components.length===Object.keys(components).length?'Everything':r.components.map(k=>components[k]||k).join(', ');}
  async function load(){const j=await api('/list');rows=j.backups;components=j.components;document.getElementById('backup-policy').textContent=j.policy;render();if(j.diagnostics.length)status.textContent=`${j.diagnostics.length} invalid archives excluded. Check library diagnostics before relying on those files.`;}
  function render(){
    const query=document.getElementById('backup-search').value.toLowerCase();list.replaceChildren();
    const selected=rows.filter(r=>`${r.project} ${scope(r)} ${r.comment}`.toLowerCase().includes(query));
    selected.sort((a,b)=>{const x=a[sort],y=b[sort];return (typeof x==='number'?x-y:String(x).localeCompare(String(y)))*(descending?-1:1);});
    for(const r of selected){
      const tr=el('tr');tr.append(el('td',new Date(r.createdAt).toLocaleString()),el('td',scope(r)),el('td',size(r.archiveSize)),el('td',r.comment||'—'));
      const actions=el('div',undefined,'backup-actions');actions.append(actionButton('View','eye',()=>view(r)),actionButton('Restore','rotate-left',()=>restoreForm(r)));
      const link=el('a','Download','btn btn-outline-secondary');link.href='/api/backups/download/'+encodeURIComponent(r.id);const downloadIcon=el('i',undefined,'fa fa-download me-1');downloadIcon.setAttribute('aria-hidden','true');link.prepend(downloadIcon);actions.append(link);
      actions.append(actionButton('Delete','trash',async()=>{if(!window.confirm('Delete this backup archive? Current project content is unchanged.'))return;await api('/delete/'+r.id,{confirmation:'DELETE'});await load();},'btn btn-outline-danger'));
      const cell=el('td');cell.append(actions);tr.append(cell);list.append(tr);
    }
    if(!selected.length){const cell=el('td',rows.length?'No backups match your search.':'No backups yet. Create a snapshot or upload a versioned backup.','text-secondary p-4');cell.colSpan=5;const tr=el('tr');tr.append(cell);list.append(tr);}
  }
  async function poll(ident){
    sessionStorage.setItem('pinballctl.backupJob',ident);
    for(;;){
      const j=(await api('/jobs/'+ident)).job;setStatus(j.message);
      if(j.state==='error'){sessionStorage.removeItem('pinballctl.backupJob');if(j.recoveryId)status.append(el('p','Recovery backup: '+j.recoveryId));throw new Error(j.message);}
      if(j.state==='done'){sessionStorage.removeItem('pinballctl.backupJob');return j.result;}
      await new Promise(resolve=>setTimeout(resolve,750));
    }
  }
  async function job(path,data){const start=await api(path,data);return poll(start.jobId);}
  function checks(parent,allowed,selected,onchange){
    const nodes=[];for(const key of allowed){const wrap=el('div',undefined,'form-check mb-2'),input=el('input',undefined,'form-check-input');input.type='checkbox';input.id='backup-component-'+crypto.randomUUID();input.value=key;input.checked=selected.includes(key);input.onchange=onchange||(()=>{});const label=el('label',components[key]||key,'form-check-label');label.htmlFor=input.id;wrap.append(input,label);parent.append(wrap);nodes.push(input);}return nodes;
  }
  function createForm(){
    show('Create backup');body.append(el('p','Each selected component is a complete snapshot, including its assets. Create backups between games: project updates pause while the snapshot is captured. Active state, caches, credentials and browser profiles are excluded.'));
    const allWrap=el('div',undefined,'form-check mb-3'),all=el('input',undefined,'form-check-input');all.type='checkbox';all.checked=true;all.id='backup-everything';const label=el('label','Everything','form-check-label');label.htmlFor=all.id;allWrap.append(all,label);body.append(allWrap);
    const group=el('fieldset'),legend=el('legend','Components');group.append(legend);body.append(group);
    const selected=checks(group,Object.keys(components),Object.keys(components),()=>{all.checked=selected.every(n=>n.checked);});all.onchange=()=>selected.forEach(n=>n.checked=all.checked);
    const commentLabel=el('label','Comment (optional)','form-label');commentLabel.htmlFor='backup-comment';const comment=el('textarea',undefined,'form-control');comment.id=commentLabel.htmlFor;comment.maxLength=2000;body.append(commentLabel,comment);
    footer.append(button('Create backup',async()=>{const result=await job('/create',{components:selected.filter(n=>n.checked).map(n=>n.value),comment:comment.value});await load();await view(result);status.textContent='Backup saved.';},'btn btn-success'));
  }
  async function view(r){
    const backup=(await api('/view/'+r.id)).backup;show('Backup details');
    const details=el('dl');for(const [label,value] of [['Project',backup.project],['Created',new Date(backup.createdAt).toLocaleString()],['Scope',scope(backup)],['Size',size(backup.archiveSize)],['Comment',backup.comment||'—'],['Format / app',`${backup.formatVersion} / ${backup.appVersion}`],['Compatibility','Supported format and application version'],['Policy',backup.policy]])details.append(el('dt',label),el('dd',value));body.append(details);
    const inventory=el('details');inventory.append(el('summary',`${backup.inventory.length} files with SHA-256 checksums`),el('pre',JSON.stringify(backup.inventory,null,2)));body.append(inventory);
    footer.append(button('Restore',()=>restoreForm(backup),'btn btn-success'));
  }
  function restoreForm(r){restoreSequence=[{id:r.id,components:[...r.components]}];clearOthers=false;renderRestore();}
  function renderRestore(){
    show('Restore components');body.append(el('p','Every selected component is replaced completely. Current files absent from its backup are removed. Unselected components stay unchanged unless you choose the destructive option.'));
    restoreSequence.forEach((step,index)=>{
      const source=rows.find(r=>r.id===step.id);const group=el('fieldset');group.append(el('legend',`Step ${index+1}: ${new Date(source.createdAt).toLocaleString()}`));
      checks(group,source.components,step.components,()=>{step.components=[...group.querySelectorAll('input:checked')].map(n=>n.value);});body.append(group);
    });
    const extra=el('select',undefined,'form-select mb-2');extra.setAttribute('aria-label','Add a later partial backup');for(const r of rows){const o=el('option',`${new Date(r.createdAt).toLocaleString()} · ${scope(r)} · ${r.comment}`);o.value=r.id;extra.append(o);}body.append(extra,button('Add backup step',()=>{const r=rows.find(x=>x.id===extra.value);restoreSequence.push({id:r.id,components:[...r.components]});renderRestore();}));
    body.append(el('p','Optional: apply a full baseline first, then a newer complete Rules/Lighting snapshot. The later snapshot replaces those components.','small text-secondary mt-2'));
    const danger=el('div',undefined,'backup-danger');const remove=el('input',undefined,'form-check-input me-2');remove.type='checkbox';remove.id='backup-remove-others';remove.checked=clearOthers;remove.onchange=()=>{clearOthers=remove.checked;};const label=el('label','Remove all other project content','form-check-label fw-bold');label.htmlFor=remove.id;danger.append(remove,label,el('p','DESTRUCTIVE: deletes every other supported project component in addition to replacing your selection. Backups, protected credentials and host files are preserved.','text-danger mt-2 mb-0'));body.append(danger);
    body.append(el('p','Stop Audio and Media/display playback before restoring. The bridge must also be stopped and will not be restarted or armed automatically.'));
    body.append(button('Pause bridge for maintenance',async()=>{if(window.confirm('Pause the bridge and interrupt gameplay? It will remain stopped after restore.')){await job('/pause-bridge',{confirmation:'PAUSE BRIDGE'});status.textContent='Bridge paused. Stop playback, then preview the restore.';}},'btn btn-outline-warning'));
    footer.append(button('Preview replacements',async()=>{const result=await job('/preview',{sequence:restoreSequence,removeOtherContent:clearOthers});showPreview(result);},'btn btn-success'));
  }
  function showPreview(result){
    show('Confirm replacement restore');const p=result.preview;
    for(const warning of p.warnings)body.append(el('p',warning,p.removeOtherContent?'alert alert-danger':'alert alert-warning'));
    body.append(el('p',`${p.writePaths.length} files replaced or written; ${p.deletePaths.length} files removed. A recovery snapshot is created before live changes.`));
    const inventory=el('details');inventory.append(el('summary','Exact replacements and deletions'),el('pre',JSON.stringify({components:p.components,replace:p.writePaths,remove:p.deletePaths},null,2)));body.append(inventory);
    const required=p.removeOtherContent?'REMOVE OTHER CONTENT':'REPLACE';const label=el('label',`Type ${required} to confirm`,'form-label');label.htmlFor='backup-confirm';const input=el('input',undefined,'form-control');input.id=label.htmlFor;input.autocomplete='off';body.append(label,input);
    footer.append(button('Back',renderRestore),button('Restore',async()=>{
      if(input.value!==required)throw new Error(`Type ${required} exactly to confirm.`);
      const completed=await job('/restore',{token:result.token,confirmation:input.value});await load();show('Restore complete');body.append(el('p','Selected components were replaced. Bridge and playback remain stopped. Review configuration before manually restarting services and syncing.'));
      body.append(el('p','Recovery backup: '+completed.recoveryId));status.textContent='Restore complete. Recovery backup saved. Restart/reload web and runtime services before resuming gameplay.';
    },'btn btn-danger'));
  }
  function upload(file){
    return new Promise((resolve,reject)=>{
      const xhr=new XMLHttpRequest();xhr.open('POST','/api/backups/upload');xhr.responseType='json';
      xhr.upload.onprogress=e=>{setStatus(e.lengthComputable?`Uploading… ${Math.round(e.loaded/e.total*100)}%`:'Uploading…');};xhr.upload.onload=()=>{setStatus('Upload received. Preparing archive validation…');};xhr.onerror=()=>reject(new Error('Upload interrupted'));
      xhr.onload=()=>xhr.status<300&&xhr.response?.ok?resolve(xhr.response):reject(new Error(xhr.response?.error||'Upload failed'));
      const form=new FormData();form.append('file',file);xhr.send(form);
    });
  }
  document.getElementById('backup-create').onclick=()=>run(createForm);
  document.getElementById('backup-upload').onclick=()=>document.getElementById('backup-upload-file').click();
  document.getElementById('backup-upload-file').onchange=event=>run(async()=>{const file=event.target.files[0];if(!file)return;const start=await upload(file);await poll(start.jobId);await load();status.textContent='Backup validated and added to the library. Nothing was restored.';event.target.value='';});
  document.getElementById('backup-search').oninput=render;
  root.querySelectorAll('[data-sort]').forEach(b=>b.onclick=()=>{if(sort===b.dataset.sort)descending=!descending;else{sort=b.dataset.sort;descending=true;}render();});
  panel.addEventListener('hidden.bs.offcanvas',()=>document.getElementById('backup-create').focus());
  run(async()=>{await load();const pending=sessionStorage.getItem('pinballctl.backupJob');if(pending){await poll(pending);await load();}});
})();
