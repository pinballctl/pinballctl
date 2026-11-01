(() => {
  const target=document.getElementById('manager-observation-summary');if(!target)return;
  async function refresh(){if(document.hidden)return;try{const r=await fetch('/api/ball/status'),view=await r.json();if(!r.ok)return;const g=view.game,b=view.ball;target.textContent=`Game: ${g.status.replaceAll('_',' ')} · Player ${g.currentPlayer||'—'} · Ball ${g.ballNumber||'—'} · In-play estimate: ${b.inPlay??'Unknown'} (${b.confidence}) · Pending movements: ${b.pending.length}`;}catch(_){target.textContent='Manager state unavailable';}}
  refresh();setInterval(refresh,1500);
})();
