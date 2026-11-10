/* Pantalla Líneas: alertas STEAM / RLM / REZAGADA del historial real. Sólo movimientos ≥ 3 pp. */
async function viewLineas(){
  loading('Cargando movimientos de línea…');
  let d;
  try{ d=await api('/api/lineas?hours=36'); }
  catch(e){ $app.innerHTML=errBox(e.message); const b=document.getElementById('retry'); if(b) b.onclick=()=>route(); return; }
  const items=d.items||[];
  let html=`<h1>Líneas</h1><p class="ago">${esc(agoTxt(d.now))}</p>
    <div class="sub">Movimientos reales del historial (mínimo 3 pp). <b>STEAM</b>: salto de ≥3 pp en ≤60 min. <b>RLM</b>: el público (≥55% tickets) carga un lado y la línea se mueve en contra (≥3 pp). <b>REZAGADA</b>: el consenso se movió ≥3 pp y una casa no lo siguió.</div>`;
  if(!items.length) html+=`<div class="card mut">No hay movimientos de al menos 3 puntos porcentuales en las últimas ${d.hours||36} h.</div>`;
  else html+=`<div class="ln-al">`+items.map(it=>{
    const g=it.game;
    const away=g&&g.away?(g.away.abbr||g.away.name||''):'';
    const home=g&&g.home?(g.home.abbr||g.home.name||''):'';
    const name=g?`${esc(away)} vs ${esc(home)}`:`${esc(it.league)} · ${esc(it.eid)}`;
    const href=g?`#/juego/${encodeURIComponent(it.league)}/${encodeURIComponent(it.eid)}`:'#/lineas';
    const tags=(it.alerts||[]).map(a=>{
      const k=a.kind==='STEAM'?'tag-st':a.kind==='RLM'?'tag-rl':'tag-rz';
      return `<span class="${k}">${esc(a.kind||'')}</span>`;
    }).join('');
    const det=(it.alerts||[]).map(a=>{
      const pp=a.pp!=null?sg(a.pp)+' pp':(a.consensus_pp!=null?'consenso '+sg(a.consensus_pp)+' pp':'');
      const lag=(a.laggards||[]).map(x=>esc(x.book)+' ('+sg(x.lag_pp)+' pp)').join(', ');
      return `<div class="sub">${esc(a.kind||'')} · ${esc(a.market||'')} ${esc(a.side||'')} ${pp}${a.book?' · '+esc(a.book):''}${a.tickets!=null?' · público '+a.tickets+'% tickets':''}${lag?' · rezaga '+lag:''}</div>`;
    }).join('');
    return `<a class="card ln-card" href="${href}"><div class="pkt">${name}</div><div class="sub">${esc((g&&g.league_name)||it.league)}</div><div class="tags">${tags}</div>${det}</a>`;
  }).join('')+`</div>`;
  $app.innerHTML=html;
}
