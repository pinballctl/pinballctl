(() => {
  const root = document.getElementById('performance-root');
  if (!root) return;
  const status = document.getElementById('performance-status');
  const live = document.getElementById('performance-live');
  const range = document.getElementById('performance-range');
  const overload = document.getElementById('performance-overload');
  const reset = document.getElementById('performance-reset');
  let data = null, busy = false;
  function chart(id, keys) {
    const canvas = document.getElementById(id), rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = rect.width * dpr; canvas.height = 210 * dpr;
    const ctx = canvas.getContext('2d'); ctx.scale(dpr, dpr);
    const width = rect.width, left = 55, right = width - 15, top = 15, bottom = 180;
    const rows = data?.history || [], end = rows.at(-1)?.at || Date.now()/1000;
    const start = end - Number(range.value), visible = rows.filter(r => r.at >= start);
    const max = Math.max(1, ...visible.flatMap(r => keys.map(k => Number(r[k]) || 0)));
    ctx.font = '12px system-ui'; ctx.fillStyle = '#94a3b8'; ctx.strokeStyle = '#334155';
    for(let i=0;i<=4;i++){const y=bottom-(bottom-top)*i/4;ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(right,y);ctx.stroke();ctx.fillText((max*i/4).toFixed(1),2,y+4);}
    ctx.fillText(`−${range.value}s`,left,203);ctx.fillText('Now',right-28,203);
    keys.forEach((key,index) => {
      ctx.strokeStyle = ['#60a5fa','#34d399','#fbbf24'][index];ctx.lineWidth=2;ctx.beginPath();let prev=null;
      for(const row of visible){const value=row[key];if(value===null||value===undefined){prev=null;continue;}
        const x=left+(row.at-start)/(end-start)*(right-left), y=bottom-value/max*(bottom-top);
        if(prev===null||row.at-prev>3)ctx.moveTo(x,y);else ctx.lineTo(x,y);prev=row.at;
      }ctx.stroke();
    });
  }
  function render(){chart('chart-rates',['rx_rate','completed_rate','confirmed_rate']);chart('chart-queue',['queued','worker_pending','awaiting']);chart('chart-latency',['latency_p95_ms','delivery_p95_ms']);}
  function unavailable(message){status.textContent=message;root.querySelectorAll('[data-metric]').forEach(el=>el.textContent='—');}
  async function refresh(){
    if(busy||!live.checked||document.hidden)return;
    busy=true;const controller=new AbortController(), timeout=setTimeout(()=>controller.abort(),2500);
    try{const response=await fetch('/api/performance/status',{cache:'no-store',signal:controller.signal});const next=await response.json();
      if(!response.ok||!next.ok)throw new Error(next.error||'Metrics unavailable');data=next;
      overload.hidden=!next.overload;reset.disabled=!next.disabled_confirmed;
      if(next.stale||!next.connected){unavailable(next.stale?'Metrics stale — bridge may be busy':'ESP disconnected');render();return;}
      status.textContent=(next.overload ? 'Overload: '+next.recovery_state+' · ' : 'Live · ')+new Date(next.latest.at*1000).toLocaleTimeString();
      root.querySelectorAll('[data-metric]').forEach(el=>{const value=next.latest[el.dataset.metric];el.textContent=value==null?'—':Number(value).toFixed(el.dataset.metric.includes('rate')||el.dataset.metric.includes('ms')?1:0);});render();
    }catch(error){unavailable('Unavailable — '+error.message);}finally{clearTimeout(timeout);busy=false;}
  }
  reset.addEventListener('click', async () => {
    reset.disabled=true;
    try {
      const response=await fetch('/api/performance/reset-overload',{method:'POST',signal:AbortSignal.timeout(2500)});
      const result=await response.json();
      if(!response.ok||!result.ok)throw new Error(result.error||'Reset failed');
      status.textContent='Safe recovery requested; waiting for cooldown and ESP confirmation';
      refresh();
    } catch(error) {status.textContent=error.message;reset.disabled=false;}
  });
  range.addEventListener('change',render);live.addEventListener('change',()=>{if(live.checked)refresh();else status.textContent='Paused';});window.addEventListener('resize',render);
  document.addEventListener('visibilitychange',refresh);setInterval(refresh,1000);refresh();
})();
