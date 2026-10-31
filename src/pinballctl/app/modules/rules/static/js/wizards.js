/* Declarative authoring only. All validation and output compilation also run on the server. */
(() => {
  'use strict';
  const open = document.getElementById('rules-wizard-open');
  if (!open) return;
  const panel = document.getElementById('rules-wizard');
  const title = document.getElementById('rules-wizard-title');
  const content = document.getElementById('wizard-content');
  const footer = document.getElementById('wizard-footer');
  const message = document.getElementById('wizard-message');
  const drawer = bootstrap.Offcanvas.getOrCreateInstance(panel);
  let library = [], choices = {}, current = null, steps = [], page = 0, preview = null, busy = false;
  const saved = new Map();
  let answers = {}, search = '', category = '', editing = Promise.resolve();
  function el(tag, text, cls) {
    const n = document.createElement(tag);
    if (text !== undefined) n.textContent = text;
    if (cls) n.className = cls;
    return n;
  }
  function button(text, action, cls = 'btn btn-outline-secondary') {
    const b = el('button', text, cls); b.type = 'button'; b.onclick = () => run(async () => { await editing; await action(); }); return b;
  }
  async function api(path, body) {
    const r = await fetch('/api/rules/wizards' + path, body === undefined ? {cache: 'no-store'} : {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body),
    });
    const data = await r.json();
    if (!r.ok || data.ok === false) throw new Error(data.error || 'Could not load wizard');
    return data;
  }
  async function run(fn) {
    if (busy) return;
    busy = true; message.textContent = ''; panel.setAttribute('aria-busy', 'true');
    try { await fn(); }
    catch (e) { message.textContent = e.message; message.className = 'alert alert-warning'; }
    finally { busy = false; panel.removeAttribute('aria-busy'); }
  }
  function heading(text) { const h = el('h3', text, 'h5'); h.tabIndex = -1; content.append(h); h.focus(); }
  function catalogue() {
    current = null; preview = null; title.textContent = 'Rules Wizard'; content.replaceChildren(); footer.replaceChildren();
    heading('Choose a wizard');
    content.append(el('p', 'Create ordinary editable rules. New rules start disabled until you review and enable them.', 'text-secondary'));
    const q = el('input', undefined, 'form-control mb-2'); q.type = 'search'; q.placeholder = 'Search wizards'; q.setAttribute('aria-label','Search wizards'); q.value = search;
    const filter = el('select', undefined, 'form-select mb-3'); filter.setAttribute('aria-label','Wizard category');
    for (const c of ['', ...new Set(library.map(w => w.category))]) { const o = el('option', c || 'All categories'); o.value = c; filter.append(o); }
    filter.value = category;
    const list = el('div', undefined, 'wizard-catalogue');
    function update() {
      search = q.value; category = filter.value; list.replaceChildren();
      const matches = library.filter(w => (!category || w.category === category) && `${w.name} ${w.description} ${w.category}`.toLowerCase().includes(search.toLowerCase()));
      list.append(el('p', `${matches.length} wizards · ${matches.filter(w=>w.availability==='available').length} available`, 'small text-secondary'));
      for (const w of matches) {
        const b = button('', () => select(w), 'btn btn-outline-secondary text-start w-100 mb-2 wizard-tile');
        const icon = el('i', undefined, 'fa fa-' + w.icon + ' me-2'); icon.setAttribute('aria-hidden','true');
        b.append(icon, el('strong', w.name));
        b.append(el('span', `${w.category} · ${w.origin} · ${w.availability === 'available' ? 'Available' : 'Unavailable'}`, 'd-block small mt-1'));
        b.append(el('span', w.description, 'd-block small text-secondary mt-1')); list.append(b);
      }
    }
    q.oninput = update; filter.onchange = update; content.append(q,filter,list); update();
    footer.append(button('Close', () => drawer.hide()));
  }
  async function select(w) {
    current = w; answers = saved.get(w.id) || {}; preview = null; page = 0;
    title.textContent = w.name;
    if (w.availability !== 'available') {
      content.replaceChildren(); footer.replaceChildren(); heading('Unavailable');
      for (const reason of w.prerequisites) content.append(el('p', reason));
      footer.append(button('Catalogue', catalogue)); return;
    }
    await refresh(); showStep();
  }
  async function refresh() {
    const data = await api('/preview', {id: current.id, answers, partial: true});
    answers = data.answers; steps = data.steps; saved.set(current.id, answers);
  }
  function readFields() {
    for (const input of content.querySelectorAll('[data-field]')) {
      const key = input.dataset.field, kind = input.dataset.kind;
      if (kind === 'boolean') answers[key] = input.value === '' ? null : input.value === 'true';
      else if (kind === 'multi-select') answers[key] = Array.from(input.selectedOptions).map(x=>JSON.parse(x.value));
      else if (kind === 'select' || kind === 'radio') answers[key] = input.value === '' ? null : JSON.parse(input.value);
      else if (['number','integer','duration'].includes(kind)) answers[key] = input.value === '' ? null : Number(input.value);
      else answers[key] = input.value;
    }
    saved.set(current.id, answers); preview = null;
  }
  function field(f) {
    const wrapper = el('div', undefined, 'mb-3');
    const label = el('label', f.label, 'form-label'); label.htmlFor = 'wizard-field-' + f.id;
    if(f.icon){const icon=el('i',undefined,'fa fa-'+f.icon+' me-2');icon.setAttribute('aria-hidden','true');label.prepend(icon);}
    let input;
    if (['boolean','radio','select','multi-select','input','switch','output','coil','sound','lighting','media','flag','counter'].includes(f.type)) {
      input = el('select', undefined, 'form-select');
      if (f.type === 'multi-select') input.multiple = true;
      else { const blank = el('option','Choose…'); blank.value=''; input.append(blank); }
      const options = f.type === 'boolean' ? [{value:true,label:'Yes'},{value:false,label:'No'}] :
        ['select','radio','multi-select'].includes(f.type) ? f.options : (choices[f.type] || []).map(x=>({value:x.id,label:x.name || x.friendly || x.id}));
      for (const o of options) {
        const option = el('option',o.label); option.value = ['boolean','radio','select','multi-select'].includes(f.type) ? JSON.stringify(o.value) : o.value;
        if (f.type === 'multi-select') option.selected = (answers[f.id] || []).includes(o.value);
        input.append(option);
      }
      if (f.type !== 'multi-select' && answers[f.id] !== undefined && answers[f.id] !== null) input.value = ['boolean','radio','select'].includes(f.type) ? JSON.stringify(answers[f.id]) : answers[f.id];
    } else {
      input = el('input', undefined, 'form-control'); input.type = ['integer','number','duration'].includes(f.type) ? 'number' : 'text';
      input.value = answers[f.id] ?? ''; if(f.min !== undefined) input.min=f.min; if(f.max !== undefined) input.max=f.max;
      input.step = f.type === 'number' ? 'any' : '1'; input.maxLength = 200;
    }
    input.id = label.htmlFor; input.dataset.field = f.id; input.dataset.kind = f.type; input.required = f.required !== false;
    input.onchange = () => {
      readFields();
      editing = editing.then(async () => {
        const before = JSON.stringify(steps.map(s => [s.title, s.fields.map(x=>x.id)]));
        await refresh();
        if (before !== JSON.stringify(steps.map(s => [s.title, s.fields.map(x=>x.id)]))) {
          showStep(false); document.getElementById('wizard-field-'+f.id)?.focus();
        }
      }).catch(e => { message.textContent=e.message; message.className='alert alert-warning'; });
    };
    wrapper.append(label,input);
    if (f.help) { const help=el('div',f.help,'form-text');help.id=input.id+'-help';input.setAttribute('aria-describedby',help.id);wrapper.append(help); }
    return wrapper;
  }
  function showStep(focus=true) {
    preview = null; page = Math.min(page,Math.max(0,steps.length-1)); content.replaceChildren();footer.replaceChildren();
    const s=steps[page];
    content.append(el('p',`Step ${page+1} of ${steps.length} · ${s.title}`,'small text-secondary'));
    const progress=el('progress');progress.max=steps.length;progress.value=page+1;progress.setAttribute('aria-label','Wizard progress');progress.className='w-100 mb-3';content.append(progress);
    if(focus)heading(s.title);else content.append(el('h3',s.title,'h5'));
    if(s.icon){const icon=el('i',undefined,'fa fa-'+s.icon+' me-2');icon.setAttribute('aria-hidden','true');content.querySelector('h3')?.prepend(icon);}
    if(page===0 && current.illustration){const img=el('img');img.src='/rules/static/images/wizard-rules-flow.svg';img.alt=current.illustration.alt;img.className='w-100 mb-3';content.append(img);}
    if(s.description)content.append(el('p',s.description));
    for(const f of s.fields)content.append(field(f));
    footer.append(button('Catalogue',()=>{readFields();catalogue();}));
    if(page>0)footer.append(button('Back',async()=>{readFields();await refresh();page--;showStep();}));
    footer.append(button(page===steps.length-1?'Preview rules':'Next',async()=>{
      for(const i of content.querySelectorAll('[data-field]'))if(!i.reportValidity())return;
      readFields();await refresh();
      if(page<steps.length-1){page++;showStep();}else await review();
    },'btn btn-success'));
  }
  async function review() {
    preview=await api('/preview',{id:current.id,answers});content.replaceChildren();footer.replaceChildren();heading('Review generated rules');
    for(const warning of preview.warnings)content.append(el('p',warning,'alert alert-warning'));
    content.append(el('p',`${preview.rules.length} independent rules. Optional sound/lighting actions appear only when selected.`));
    const summary=el('dl');for(const [key,value] of Object.entries(preview.answers)){summary.append(el('dt',key),el('dd',Array.isArray(value)?value.join(', '):String(value)));}content.append(summary);
    for(const r of preview.rules){const detail=el('details');detail.append(el('summary',r.name));detail.append(el('pre',JSON.stringify(r,null,2),'wizard-json'));content.append(detail);}
    footer.append(button('Back',()=>showStep()),button('Create rules',async()=>{
      if(window.RulesWizardHost?.isDirty())throw new Error('Save your Rules changes before creating wizard rules.');
      await api('/create',{token:preview.token});preview=null;await window.RulesWizardHost.reload();content.replaceChildren();footer.replaceChildren();heading('Rules created');content.append(el('p','Created disabled rules. Review them in the existing Rules list, enable only after checking, then save and sync when ready.'));
      footer.append(button('Open Rules',()=>drawer.hide(),'btn btn-success'));
    },'btn btn-success'));
  }
  open.onclick=()=>run(async()=>{
    if(window.RulesWizardHost?.isDirty()){window.alert('Save your Rules changes before opening the wizard.');return;}
    drawer.show();content.replaceChildren(el('p','Loading wizards…'));const data=await api('');library=data.wizards.sort((a,b)=>(a.availability==='available'?0:1)-(b.availability==='available'?0:1)||a.name.localeCompare(b.name));choices=data.choices;catalogue();
    if(data.diagnostics.length)message.textContent=`${data.diagnostics.length} invalid definitions were excluded. Check the wizard API diagnostics.`;
  });
  panel.addEventListener('hidden.bs.offcanvas',()=>{if(current){readFields();}open.focus();});
})();
