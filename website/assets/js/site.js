(() => {
  const $ = s => document.querySelector(s);
  const nav = $('#site-nav'), toggle = $('.menu-toggle');
  const mobileMenu = matchMedia('(max-width: 760px)'), backdrop = $('.menu-backdrop');
  const featureDropdown=$('.features-dropdown'), featureTrigger=featureDropdown?.querySelector('summary');
  const primary=$('.nav-primary'), featureMenu=$('.feature-menu'), featureBack=$('.features-back');
  function setFeatures(open, focus=false) {
    open = open && mobileMenu.matches && nav.classList.contains('open');
    nav.classList.toggle('features-active',open);
    primary.inert=open;
    featureMenu.inert=mobileMenu.matches && !open;
    featureTrigger.setAttribute('aria-expanded',String(open));
    if(open)featureMenu.scrollTop=0;
    if(focus)setTimeout(()=>{
      if(nav.classList.contains('open') && nav.classList.contains('features-active')===open)
        (open?featureBack:featureTrigger).focus({preventScroll:true});
    },matchMedia('(prefers-reduced-motion: reduce)').matches?20:240);
  }
  function syncFeatureView() {
    featureDropdown.open=false;
    if(mobileMenu.matches)nav.append(featureMenu);
    else featureDropdown.append(featureMenu);
    setFeatures(false);
  }
  syncFeatureView();
  featureTrigger?.addEventListener('click',e=>{
    if(mobileMenu.matches){e.preventDefault();setFeatures(true,true);}
  });
  featureBack?.addEventListener('click',()=>setFeatures(false,true));
  featureDropdown?.addEventListener('toggle',()=>{
    if(!mobileMenu.matches)featureTrigger.setAttribute('aria-expanded',String(featureDropdown.open));
  });
  let menuScroll = 0;
  const inertBefore = new Map();
  function setMenu(open, returnFocus=false) {
    open = open && mobileMenu.matches;
    if (open === nav.classList.contains('open')) return;
    nav.classList.toggle('open',open);
    toggle.setAttribute('aria-expanded',String(open));
    toggle.textContent=open?'Close ✕':'Menu ☰';
    backdrop.hidden=!open;
    if(open) {
      menuScroll=window.scrollY;
      document.body.style.top=`-${menuScroll}px`;
      document.body.classList.add('mobile-menu-open');
      document.querySelectorAll('main, body > footer, .consent, .development-ribbon').forEach(el=>{inertBefore.set(el,el.inert);el.inert=true;});
    } else {
      setFeatures(false);
      document.body.classList.remove('mobile-menu-open');
      document.body.style.top='';
      window.scrollTo({top:menuScroll,behavior:'instant'});
      inertBefore.forEach((value,el)=>el.inert=value);inertBefore.clear();
      if(returnFocus)toggle.focus();
    }
  }
  toggle?.addEventListener('click',()=>setMenu(!nav.classList.contains('open')));
  backdrop?.addEventListener('click',()=>setMenu(false,true));
  nav?.addEventListener('click',e=>{if(e.target.closest('a'))setMenu(false);});
  mobileMenu.addEventListener('change',()=>{
    const hadMenu=nav.classList.contains('open');
    const hadFocus=nav.contains(document.activeElement);
    if(hadMenu)setMenu(false);
    syncFeatureView();
    if(hadMenu || hadFocus)(mobileMenu.matches?toggle:featureTrigger).focus();
  });
  document.addEventListener('keydown',e=>{
    if(!nav.classList.contains('open'))return;
    if(e.key==='Escape'){
      e.preventDefault();
      if(nav.classList.contains('features-active'))setFeatures(false,true);
      else setMenu(false,true);
    }
    if(e.key==='Tab'){
      const controls=[...$('.site-header').querySelectorAll('a,button,summary')].filter(el=>el.getClientRects().length && !el.closest('[inert]') && getComputedStyle(el).visibility!=='hidden');
      const first=controls[0],last=controls.at(-1);
      if(e.shiftKey && document.activeElement===first){e.preventDefault();last.focus();}
      else if(!e.shiftKey && document.activeElement===last){e.preventDefault();first.focus();}
    }
  });
  $('.doc-mobile')?.addEventListener('click', e => {const open=$('#docs-nav').classList.toggle('open');e.currentTarget.setAttribute('aria-expanded',String(open));});
  document.addEventListener('click', e => {document.querySelectorAll('.nav details[open]').forEach(d=>{if(!d.contains(e.target))d.open=false;});});
  document.addEventListener('keydown',e=>{
    if(!mobileMenu.matches && e.key==='Escape' && featureDropdown?.open){featureDropdown.open=false;featureTrigger.focus();}
  });
  featureDropdown?.addEventListener('focusout',e=>{
    if(!mobileMenu.matches && e.relatedTarget && !featureDropdown.contains(e.relatedTarget))featureDropdown.open=false;
  });
  const consent = $('.consent');
  let choice=null, analyticsStarted=false;
  try {choice=localStorage.getItem('pinballctl.analytics');} catch (_) {}
  const hasPreference=choice==='yes' || choice==='no';
  if(!hasPreference)choice='yes';
  window['ga-disable-G-V8YD2KZZ9W']=choice==='no';
  function startAnalytics(){
    window['ga-disable-G-V8YD2KZZ9W']=false;
    if(analyticsStarted || location.hostname!=='www.pinballctl.com')return;
    analyticsStarted=true;window['ga-disable-G-V8YD2KZZ9W']=false;
    window.dataLayer=window.dataLayer||[];window.gtag=function(){dataLayer.push(arguments);};
    gtag('js',new Date());
    // One automatic page view per real HTML page. Do not add manual page views.
    gtag('config','G-V8YD2KZZ9W',{page_location:location.origin+location.pathname,content_group:document.body.dataset.section});
    const script=document.createElement('script');script.async=true;script.src='https://www.googletagmanager.com/gtag/js?id=G-V8YD2KZZ9W';document.head.append(script);
  }
  function track(name,params={}){if(choice==='yes' && analyticsStarted)window.gtag('event',name,params);}
  if(choice==='yes')startAnalytics();
  if(!hasPreference && consent)consent.hidden=false;
  document.querySelectorAll('[data-consent]').forEach(b=>b.addEventListener('click',()=>{
    choice=b.dataset.consent;try{localStorage.setItem('pinballctl.analytics',choice);}catch(_){}
    consent.hidden=true;
    if(choice==='yes')startAnalytics();
    else {
      window['ga-disable-G-V8YD2KZZ9W']=true;
      document.cookie.split(';').forEach(item=>{const name=item.split('=')[0].trim();if(name.startsWith('_ga'))for(const domain of ['', ';domain=.pinballctl.com',';domain=www.pinballctl.com'])document.cookie=`${name}=;max-age=0;path=/${domain}`;});
    }
  }));
  document.querySelectorAll('[data-cookie-settings]').forEach(button=>button.addEventListener('click',()=>{consent.hidden=false;consent.querySelector('button').focus();}));
  document.querySelectorAll('[data-track]').forEach(a=>a.addEventListener('click',()=>track(a.dataset.track,{link_path:new URL(a.href).pathname})));
  const dialog=$('.search-dialog'),input=$('#site-search'),results=$('.search-results'),status=$('[data-search-status]');
  const docsOnly=$('#search-docs-only');
  let searchData=null,loading=null;
  async function loadIndex(){
    if(searchData)return searchData;
    if(!loading)loading=fetch('/search-index.json').then(r=>{if(!r.ok)throw Error('Search unavailable');return r.json();}).then(data=>searchData=data).catch(e=>{loading=null;throw e;});
    return loading;
  }
  async function search(){
    const query=input.value.trim().toLowerCase();results.replaceChildren();
    if(!query){status.textContent=docsOnly.checked?'Search documentation and setup guides only.':'Search features, setup guides and technical documentation.';return;}
    status.textContent='Searching…';
    try{
      const data=await loadIndex();if(query!==input.value.trim().toLowerCase())return;
      const words=query.split(/\s+/).filter(Boolean);
      const found=data.filter(row=>!docsOnly.checked || row.url.startsWith('/docs/')).map(row=>{const title=row.title.toLowerCase(),text=(title+' '+row.text).toLowerCase();return {...row,score:words.every(w=>text.includes(w))?words.reduce((n,w)=>n+(title.includes(w)?10:1),0):0};}).filter(r=>r.score).sort((a,b)=>b.score-a.score).slice(0,20);
      status.textContent=found.length?`${found.length} result${found.length===1?'':'s'}`:'No matches. Try a broader term such as “lighting” or “hardware”.';
      for(const row of found){const li=document.createElement('li'),a=document.createElement('a'),title=document.createElement('strong'),detail=document.createElement('small');a.href=row.url;title.textContent=row.title;detail.textContent=row.section+' · '+row.description; a.append(title,detail);a.addEventListener('click',()=>track('search_result_click',{result_path:row.url,content_group:row.section}));li.append(a);results.append(li);}
    }catch(_){status.textContent='Search could not load. Check your connection and try again.';}
  }
  $('[data-search-open]')?.addEventListener('click',()=>{setMenu(false);dialog.showModal();input.focus();search();track('site_search_open');});
  $('[data-search-close]')?.addEventListener('click',()=>dialog.close());
  input?.addEventListener('input',search);
  docsOnly?.addEventListener('change',search);
  dialog?.addEventListener('click',e=>{if(e.target===dialog)dialog.close();});
  document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key==='k'){e.preventDefault();setMenu(false);if(!dialog.open)dialog.showModal();input.focus();}});
  const imageDialog=$('.image-dialog');
  const imageScroll=$('.image-scroll'), preview=imageScroll.querySelector('img');
  const zoomIn=$('[data-image-zoom-in]'), zoomOut=$('[data-image-zoom-out]');
  const zoomLevel=$('[data-image-zoom-level]');
  const imageScales=[1, 2, 4];
  let imageScale=1;
  const imageTouches=new Map();

  function layoutImage() {
    if(!imageDialog.open) return;
    const ready=preview.naturalWidth>0;
    zoomIn.disabled=!ready || imageScale===imageScales.at(-1);
    zoomOut.disabled=imageScale===1;
    zoomLevel.value=imageScale===1?'Fit':`${Number(imageScale.toFixed(2))}×`;
    imageScroll.classList.toggle('is-zoomed',imageScale>1);
    if(!ready) return;
    const bounds=imageScroll.getBoundingClientRect();
    const fitWidth=Math.min(bounds.width, bounds.height*preview.naturalWidth/preview.naturalHeight, preview.naturalWidth);
    preview.style.width=`${fitWidth*imageScale}px`;
  }

  function zoomImage(scale, from, to=from) {
    const before=preview.getBoundingClientRect();
    const x=(from.x-before.left)/before.width;
    const y=(from.y-before.top)/before.height;
    imageScale=Math.max(1,Math.min(scale,imageScales.at(-1)));
    layoutImage();
    const after=preview.getBoundingClientRect();
    imageScroll.scrollBy(after.left+x*after.width-to.x,after.top+y*after.height-to.y);
  }

  function stepImageZoom(scale) {
    const image=preview.getBoundingClientRect();
    const viewport=imageScroll.getBoundingClientRect();
    zoomImage(scale,{
      x:(Math.max(image.left,viewport.left)+Math.min(image.right,viewport.right))/2,
      y:(Math.max(image.top,viewport.top)+Math.min(image.bottom,viewport.bottom))/2
    });
  }

  function imageGesture() {
    const [first,second]=imageTouches.values();
    if(!second) return first;
    return {
      x:(first.x+second.x)/2,
      y:(first.y+second.y)/2,
      distance:Math.hypot(first.x-second.x,first.y-second.y)
    };
  }

  imageScroll.addEventListener('pointerdown',event=>{
    if(event.pointerType!=='touch' || !preview.naturalWidth) return;
    imageScroll.setPointerCapture(event.pointerId);
    imageTouches.set(event.pointerId,{x:event.clientX,y:event.clientY});
  });
  imageScroll.addEventListener('pointermove',event=>{
    if(!imageTouches.has(event.pointerId)) return;
    const before=imageGesture();
    imageTouches.set(event.pointerId,{x:event.clientX,y:event.clientY});
    const after=imageGesture();
    if(before.distance && after.distance) {
      zoomImage(imageScale*after.distance/before.distance,before,after);
    } else if(imageTouches.size===1) {
      imageScroll.scrollBy(before.x-after.x,before.y-after.y);
    }
  });
  imageScroll.addEventListener('lostpointercapture',event=>imageTouches.delete(event.pointerId));
  imageDialog.addEventListener('close',()=>imageTouches.clear());

  function showImage(img, opener=img) {
    imageScale=1;
    preview.style.width='';
    preview.alt=img.alt;
    preview.src=img.dataset.fullSrc||img.currentSrc||img.src;
    opener.focus({preventScroll:true});
    imageDialog.showModal();
    imageScroll.scrollTo(0,0);
    layoutImage();
    track('screenshot_open');
  }

  preview.addEventListener('load',layoutImage);
  new ResizeObserver(layoutImage).observe(imageScroll);
  zoomIn.addEventListener('click',()=>stepImageZoom(imageScales.find(scale=>scale>imageScale)));
  zoomOut.addEventListener('click',()=>stepImageZoom(imageScales.findLast(scale=>scale<imageScale)));
  document.querySelectorAll('[data-image-open]').forEach(b=>b.addEventListener('click',()=>showImage(b.querySelector('img'),b)));
  document.querySelectorAll('.doc-body img').forEach(img=>{img.tabIndex=0;img.setAttribute('role','button');img.setAttribute('aria-label','Enlarge '+img.alt);img.addEventListener('click',()=>showImage(img));img.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();showImage(img);}});});
  $('[data-image-close]')?.addEventListener('click',()=>imageDialog.close());
  imageDialog?.addEventListener('click',e=>{if(e.target===imageDialog)imageDialog.close();});

  const partsChecklist = $('[data-parts-checklist]');
  if (partsChecklist) {
    const storageKey = `pinballctl.parts.${partsChecklist.dataset.partsChecklist}`;
    let owned = new Set(), storageAvailable = true;
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || '[]');
      if (Array.isArray(saved)) owned = new Set(saved.filter(value => typeof value === 'string'));
    } catch (_) { storageAvailable = false; }

    const groups = [];
    partsChecklist.closest('.doc-body').querySelectorAll('table').forEach(table => {
      const rows = [...(table.tBodies[0]?.rows || [])];
      if (!rows.length || !table.querySelector('.part-thumbnail')) return;
      const items = rows.map((row, order) => {
        if (row.cells.length !== 6) return null;
        const id = row.cells[0].textContent.match(/^([PF]\d{2})\s*·/)?.[1];
        const product = row.cells[1].querySelector('a[href*="amazon.co.uk/"]');
        const asin = product?.href.match(/\/(?:dp|gp\/product)\/([A-Z0-9]{10})(?:[/?]|$)/)?.[1];
        const price = row.cells[3].textContent.match(/£([\d,]+)\.(\d{2})/);
        if (!id || !asin || !price) return null;
        // A replacement product must not inherit the previous product's ownership.
        return {row, order, id, key:`${id}:${asin}`, name:product.textContent.trim(),
          pence:Number(price[1].replaceAll(',', '')) * 100 + Number(price[2])};
      });
      if (items.some(item => !item)) return;
      table.classList.add('parts-checklist-table');
      const heading = document.createElement('th');
      heading.scope = 'col';
      heading.textContent = 'Have';
      table.tHead.rows[0].prepend(heading);
      items.forEach(item => {
        const cell = document.createElement('td'), label = document.createElement('label');
        const input = document.createElement('input'), state = document.createElement('span');
        input.type = 'checkbox';
        input.checked = owned.has(item.key);
        input.setAttribute('aria-label', `Have ${item.id}: ${item.name}`);
        label.className = 'part-have';
        label.append(input, state);
        cell.append(label);
        item.row.prepend(cell);
        Object.assign(item, {input, state});
        input.addEventListener('change', () => {
          if (input.checked) owned.add(item.key);
          else owned.delete(item.key);
          try {
            localStorage.setItem(storageKey, JSON.stringify([...owned]));
            storageAvailable = true;
          } catch (_) { storageAvailable = false; }
          updateParts();
          input.focus({preventScroll:true});
        });
      });
      groups.push({body:table.tBodies[0], items});
    });

    const summary = document.createElement('p'), storageNote = document.createElement('p');
    summary.className = 'parts-checklist-summary';
    summary.setAttribute('role', 'status');
    summary.setAttribute('aria-atomic', 'true');
    storageNote.className = 'parts-checklist-storage';
    storageNote.setAttribute('aria-live', 'polite');
    partsChecklist.append(summary, storageNote);
    const currency = new Intl.NumberFormat('en-GB', {style:'currency', currency:'GBP'});
    function updateParts() {
      let have = 0, need = 0, remaining = 0;
      groups.forEach(({body, items}) => {
        items.forEach(item => {
          const checked = item.input.checked;
          item.row.classList.toggle('part-owned', checked);
          item.state.textContent = checked ? 'Have' : 'Need';
          if (checked) have++;
          else { need++; remaining += item.pence; }
        });
        [...items].sort((a, b) => Number(b.input.checked) - Number(a.input.checked) || a.order - b.order)
          .forEach(item => body.append(item.row));
      });
      summary.textContent = `Have ${have} of ${have + need} listed items · Need ${need} · Still to buy: ${currency.format(remaining / 100)}`;
      storageNote.textContent = storageAvailable
        ? 'Saved in this browser only. The remaining estimate uses whole packs; the exclusions below still apply.'
        : 'Browser storage is unavailable. These selections will be lost on reload. The estimate uses whole packs; the exclusions below still apply.';
    }
    if (groups.length) {
      partsChecklist.hidden = false;
      updateParts();
    }
  }

  document.querySelectorAll('.doc-table-scroll').forEach(scroller => {
    const frame = scroller.parentElement;
    const update = () => {
      const remaining = scroller.scrollWidth - scroller.clientWidth;
      frame.classList.toggle('has-more-columns', remaining - scroller.scrollLeft > 1);
      if (remaining > 1) {
        scroller.tabIndex = 0;
        scroller.setAttribute('role', 'region');
        scroller.setAttribute('aria-label', 'Scrollable table');
      } else {
        scroller.removeAttribute('tabindex');
        scroller.removeAttribute('role');
        scroller.removeAttribute('aria-label');
      }
    };
    scroller.addEventListener('scroll', update, {passive:true});
    const observer = new ResizeObserver(update);
    observer.observe(scroller);
    observer.observe(scroller.firstElementChild);
    update();
  });
  // Preserve old documentation bookmarks that used #doc= rather than real URLs.
  if(location.pathname==='/docs/' && location.hash.startsWith('#doc=')){
    const slug=new URLSearchParams(location.hash.slice(1)).get('doc');
    fetch('/docs/legacy-links.json').then(r=>r.json()).then(m=>{if(m[slug] && m[slug]!=='/docs/')location.replace(m[slug]);}).catch(()=>{});
  }
})();
