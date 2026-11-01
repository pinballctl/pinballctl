(() => {
  'use strict';
  const root=document.getElementById('backup-root');if(!root)return;
  const list=document.getElementById('backup-list'), status=document.getElementById('backup-status');
  const panel=document.getElementById('backup-drawer'),body=document.getElementById('backup-drawer-body'),footer=document.getElementById('backup-drawer-footer'),title=document.getElementById('backup-drawer-title');
  const drawer=bootstrap.Offcanvas.getOrCreateInstance(panel);
  let rows=[],components={},sort='createdAt',descending=true,busy=false,restoreSequence=[],clearOthers=false;
  function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
  function button(text,action,cls='btn btn-outline-secondary'){const b=el('button',text,cls);b.type='button';b.onclick=()=>run(action);return b;}
  function actionButton(text,icon,action,cls){const b=button('',action,cls||'btn btn-sm btn-outline-secondary');b.title=text;b.setAttribute('aria-label',text);const i=el('i',undefined,'fa fa-'+icon);i.setAttribute('aria-hidden','true');b.prepend(i);return b;}
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
  function date(value){
    const d=new Date(value);if(!value||Number.isNaN(d.getTime()))return '—';
    const parts=new Intl.DateTimeFormat('en-GB',{day:'numeric',month:'long',year:'numeric',hour:'2-digit',minute:'2-digit',hour12:false}).formatToParts(d);
    const get=type=>parts.find(p=>p.type===type)?.value||'';
    return `${get('day')} ${get('month')} ${get('year')} ${get('hour')}:${get('minute')}`;
  }
  function componentLabels(keys){return keys.filter(k=>k!=='combos'||!keys.includes('scoring')).map(k=>k==='scoring'?(keys.includes('combos')?'Scoring':'Scoring (without combos)'):k==='combos'?'Scoring (combos only)':components[k]||k);}
  function size(n){const units=['B','KB','MB','GB'];let u=0;while(n>=1024&&u<3){n/=1024;u++;}return new Intl.NumberFormat(undefined,{maximumFractionDigits:1}).format(n)+' '+units[u];}
  function scope(r){return r.components.length===Object.keys(components).length?'Everything':componentLabels(r.components).join(', ');}
  async function load(){const j=await api('/list');rows=j.backups;components=j.components;document.getElementById('backup-policy').textContent=j.policy;render();if(j.diagnostics.length)status.textContent=`${j.diagnostics.length} invalid archives excluded. Check library diagnostics before relying on those files.`;}
  function render(){
    root.querySelectorAll('[data-sort]').forEach(button=>{
      const active=button.dataset.sort===sort;
      const label=button.dataset.sortLabel||(button.dataset.sortLabel=button.textContent.trim());
      button.replaceChildren(document.createTextNode(label));
      button.closest('th').setAttribute('aria-sort',active?(descending?'descending':'ascending'):'none');
      if(active){const arrow=el('span',descending?' ↓':' ↑');arrow.setAttribute('aria-hidden','true');button.append(arrow);}
    });
    const query=document.getElementById('backup-search').value.toLowerCase();list.replaceChildren();
    const selected=rows.filter(r=>`${r.project} ${scope(r)} ${r.comment}`.toLowerCase().includes(query));
    selected.sort((a,b)=>{const x=a[sort],y=b[sort];return (typeof x==='number'?x-y:String(x).localeCompare(String(y)))*(descending?-1:1);});
    for(const r of selected){
      const tr=el('tr');tr.append(el('td',date(r.createdAt)),el('td',scope(r)),el('td',size(r.archiveSize)),el('td',r.comment||'—'));
      const actions=el('div',undefined,'backup-actions');actions.append(actionButton('View','eye',()=>view(r)),actionButton('Restore','clock-rotate-left',()=>restoreForm(r)));
      const link=el('a',undefined,'btn btn-sm btn-outline-secondary');link.title='Download';link.setAttribute('aria-label','Download');link.href='/api/backups/download/'+encodeURIComponent(r.id);const downloadIcon=el('i',undefined,'fa fa-download');downloadIcon.setAttribute('aria-hidden','true');link.prepend(downloadIcon);actions.append(link);
      actions.append(actionButton('Delete','trash',async()=>{if(!window.confirm('Delete this backup archive? Current project content is unchanged.'))return;await api('/delete/'+r.id,{confirmation:'DELETE'});await load();},'btn btn-sm btn-outline-danger'));
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
    const nodes=[];
    for(const key of allowed){
      if(key==='combos'&&allowed.includes('scoring'))continue;
      const keys=key==='scoring'&&allowed.includes('combos')?['scoring','combos']:[key];
      const wrap=el('div',undefined,'form-check mb-2'),input=el('input',undefined,'form-check-input');
      input.type='checkbox';input.id='backup-component-'+crypto.randomUUID();input.value=key;input.componentKeys=keys;input.checked=keys.every(k=>selected.includes(k));input.onchange=onchange||(()=>{});
      const label=el('label',componentLabels(keys).join(', '),'form-check-label');label.htmlFor=input.id;wrap.append(input,label);parent.append(wrap);nodes.push(input);
    }return nodes;
  }
  function createForm(){
    show('Create backup');body.append(el('p','Each selected component is a complete snapshot, including its assets. Create backups between games: project updates pause while the snapshot is captured. Active state, caches, credentials and browser profiles are excluded.'));
    const allWrap=el('div',undefined,'form-check mb-3'),all=el('input',undefined,'form-check-input');all.type='checkbox';all.checked=true;all.id='backup-everything';const label=el('label','Everything','form-check-label');label.htmlFor=all.id;allWrap.append(all,label);body.append(allWrap);
    const group=el('fieldset'),legend=el('legend','Components');group.append(legend);body.append(group);
    const selected=checks(group,Object.keys(components),Object.keys(components),()=>{all.checked=selected.every(n=>n.checked);});all.onchange=()=>selected.forEach(n=>n.checked=all.checked);
    const commentLabel=el('label','Comment (optional)','form-label');commentLabel.htmlFor='backup-comment';const comment=el('textarea',undefined,'form-control');comment.id=commentLabel.htmlFor;comment.maxLength=2000;body.append(commentLabel,comment);
    footer.append(button('Create backup',async()=>{const result=await job('/create',{components:selected.filter(n=>n.checked).flatMap(n=>n.componentKeys),comment:comment.value});await load();await view(result);status.textContent='Backup saved.';},'btn btn-success'));
  }
  async function view(r){
    const backup=(await api('/view/'+r.id)).backup;show('Backup details');
    const summary=el('section',undefined,'backup-detail-summary');
    summary.append(el('h3',backup.project||'Project backup','h5 mb-1'),el('p',date(backup.createdAt),'text-secondary mb-3'));
    const pills=el('div',undefined,'d-flex flex-wrap gap-2');
    pills.append(el('span',size(backup.archiveSize),'badge rounded-pill text-bg-secondary'),el('span',`${backup.inventory.length} files`,'badge rounded-pill text-bg-secondary'),el('span','Compatible','badge rounded-pill text-bg-success'));summary.append(pills);body.append(summary);
    const details=el('dl',undefined,'backup-detail-meta');
    for(const [label,value] of [['Scope',scope(backup)],['Comment',backup.comment||'No comment'],['App version',backup.appVersion],['Backup format',backup.formatVersion]])details.append(el('dt',label),el('dd',String(value)));
    body.append(details);
    const policy=el('details',undefined,'mb-4');policy.append(el('summary','Backup policy'),el('p',backup.policy,'small text-secondary mt-2'));body.append(policy);
    const section=el('section');section.append(el('h3','Files','h5'));
    const searchLabel=el('label','Search files','visually-hidden');searchLabel.htmlFor='backup-file-search';
    const search=el('input',undefined,'form-control mb-3');search.type='search';search.id=searchLabel.htmlFor;search.placeholder='Search file path or component…';
    const count=el('p',undefined,'small text-secondary');count.setAttribute('role','status');
    const wrap=el('div',undefined,'table-responsive backup-file-table');const table=el('table',undefined,'table table-hover align-middle mb-0');table.setAttribute('aria-label','Backup files');
    const head=el('thead'),heading=el('tr');
    for(const name of ['File / checksum','Component','Size']){const th=el('th',name,name==='Size'?'text-end':'');th.scope='col';heading.append(th);}head.append(heading);
    const files=el('tbody');table.append(head,files);wrap.append(table);section.append(searchLabel,search,count,wrap);body.append(section);
    function renderFiles(){
      const query=search.value.trim().toLowerCase();files.replaceChildren();
      const matching=backup.inventory.filter(file=>`${file.path} ${componentLabels([file.component]).join(' ')}`.toLowerCase().includes(query));
      count.textContent=`${matching.length} of ${backup.inventory.length} files`;
      for(const file of matching){
        const row=el('tr'),path=el('td');path.append(el('span',file.path,'backup-file-path'));
        const checksum=el('details',undefined,'backup-file-checksum');checksum.append(el('summary','SHA-256'),el('code',file.sha256));path.append(checksum);
        row.append(path,el('td',componentLabels([file.component]).join(', '),'small text-secondary'),el('td',size(file.size),'text-end text-nowrap'));files.append(row);
      }
      if(!matching.length){const row=el('tr'),empty=el('td','No files match your search.','text-secondary');empty.colSpan=3;row.append(empty);files.append(row);}
    }
    search.oninput=renderFiles;renderFiles();
    footer.append(button('Restore',()=>restoreForm(backup),'btn btn-success'));
  }
  function restoreForm(r){restoreSequence=[{id:r.id,components:[...r.components]}];clearOthers=false;renderRestore();}
  function renderRestore(){
    show('Restore components');body.append(el('p','Every selected component is replaced completely. Current files absent from its backup are removed. Unselected components stay unchanged unless you choose the destructive option.'));
    restoreSequence.forEach((step,index)=>{
      const source=rows.find(r=>r.id===step.id);const group=el('fieldset');group.append(el('legend',`Backup: ${date(source.createdAt)}`));
      checks(group,source.components,step.components,()=>{step.components=[...group.querySelectorAll('input:checked')].flatMap(n=>n.componentKeys);});body.append(group);
    });
    body.append(el('p','To apply another backup afterwards, complete this restore and select Restore on the next archive.','small text-secondary'));
    const danger=el('div',undefined,'backup-danger');const remove=el('input',undefined,'form-check-input me-2');remove.type='checkbox';remove.id='backup-remove-others';remove.checked=clearOthers;remove.onchange=()=>{clearOthers=remove.checked;};const label=el('label','Remove all other project content','form-check-label fw-bold');label.htmlFor=remove.id;danger.append(remove,label,el('p','DESTRUCTIVE: deletes every other supported project component in addition to replacing your selection. Backups, protected credentials and host files are preserved.','text-danger mt-2 mb-0'));body.append(danger);
    body.append(el('p','Stop Audio and Media/display playback before restoring. On confirmation, a running bridge stops automatically and restarts after a successful restore. An already stopped bridge stays stopped. Restore never arms hardware; failures leave the bridge stopped.'));
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
      const completed=await job('/restore',{token:result.token,confirmation:input.value});await load();show('Restore complete');body.append(el('p',completed.bridgeRestarted ? 'Selected components were replaced and the bridge restarted. Hardware was not armed. Review configuration before syncing.' : 'Selected components were replaced. The bridge was already stopped and remains stopped. Review configuration before starting it and syncing.'));
      body.append(el('p','Recovery backup: '+completed.recoveryId));status.textContent='Restore complete. Recovery backup saved. Review configuration and reload any other running services before resuming gameplay.';
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
