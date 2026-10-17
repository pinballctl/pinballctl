(() => {
  const $ = s => document.querySelector(s);
  const nav = $('#site-nav'), toggle = $('.menu-toggle');
  const mobileMenu = matchMedia('(max-width: 760px)'), backdrop = $('.menu-backdrop');
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
      document.querySelectorAll('main, body > footer, .consent').forEach(el=>{inertBefore.set(el,el.inert);el.inert=true;});
    } else {
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
  mobileMenu.addEventListener('change',()=>{if(!mobileMenu.matches)setMenu(false);});
  document.addEventListener('keydown',e=>{
    if(!nav.classList.contains('open'))return;
    if(e.key==='Escape'){e.preventDefault();setMenu(false,true);}
    if(e.key==='Tab'){
      const controls=[...$('.site-header').querySelectorAll('a,button,summary')].filter(el=>el.getClientRects().length);
      const first=controls[0],last=controls.at(-1);
      if(e.shiftKey && document.activeElement===first){e.preventDefault();last.focus();}
      else if(!e.shiftKey && document.activeElement===last){e.preventDefault();first.focus();}
    }
  });
  $('.doc-mobile')?.addEventListener('click', e => {const open=$('#docs-nav').classList.toggle('open');e.currentTarget.setAttribute('aria-expanded',String(open));});
  document.addEventListener('click', e => {document.querySelectorAll('.nav details[open]').forEach(d=>{if(!d.contains(e.target))d.open=false;});});
  const featureDropdown=$('.features-dropdown');
  document.addEventListener('keydown',e=>{
    if(e.key==='Escape' && featureDropdown?.open){featureDropdown.open=false;featureDropdown.querySelector('summary').focus();}
  });
  featureDropdown?.addEventListener('focusout',e=>{
    if(e.relatedTarget && !featureDropdown.contains(e.relatedTarget))featureDropdown.open=false;
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
  function showImage(img){const preview=imageDialog.querySelector('img');preview.src=img.dataset.fullSrc||img.currentSrc||img.src;preview.alt=img.alt;imageDialog.showModal();track('screenshot_open');}
  document.querySelectorAll('[data-image-open]').forEach(b=>b.addEventListener('click',()=>showImage(b.querySelector('img'))));
  document.querySelectorAll('.doc-body img').forEach(img=>{img.tabIndex=0;img.setAttribute('role','button');img.setAttribute('aria-label','Enlarge '+img.alt);img.addEventListener('click',()=>showImage(img));img.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();showImage(img);}});});
  $('[data-image-close]')?.addEventListener('click',()=>imageDialog.close());
  imageDialog?.addEventListener('click',e=>{if(e.target===imageDialog)imageDialog.close();});
  // Preserve old documentation bookmarks that used #doc= rather than real URLs.
  if(location.pathname==='/docs/' && location.hash.startsWith('#doc=')){
    const slug=new URLSearchParams(location.hash.slice(1)).get('doc');
    fetch('/docs/legacy-links.json').then(r=>r.json()).then(m=>{if(m[slug] && m[slug]!=='/docs/')location.replace(m[slug]);}).catch(()=>{});
  }
})();
