/* Pantalla Líneas: STEAM / RLM / REZAGADA del historial real. Sólo movimientos ≥ 3 pp. */
function lnAgo(ts){
  if(!ts) return '';
  const m=Math.max(0, Math.round((Date.now()/1000 - +ts)/60));
  if(m<1) return 'hace menos de 1 min';
  if(m===1) return 'hace 1 min';
  if(m<60) return 'hace '+m+' min';
  const h=Math.floor(m/60); return 'hace '+h+' h';
}
function lnAm(o){ if(o==null||isNaN(o)) return 'Sin dato'; o=+o; return (o>0?'+':'')+o; }
async function viewLineas(filter){
  filter=filter|| (location.hash.split('/')[2]||'todos');
  loading('Cargando movimientos de línea…');
  let d;
  try{ d=await api('/api/lineas?hours=36'); }
  catch(e){ $app.innerHTML=errBox(e.message); const b=document.getElementById('retry'); if(b) b.onclick=()=>route(); return; }
  const all=[];
  (d.items||[]).forEach(it=>{
    (it.alerts||[]).forEach(a=>{
      all.push(Object.assign({league:it.league,eid:it.eid,game:it.game}, a));
    });
  });
  const rows=all.filter(x=>{
    const tags=(x.tags||[]).map(k=>String(k).toUpperCase());
    if(filter==='steam') return tags.includes('STEAM');
    if(filter==='rlm') return tags.includes('RLM');
    if(filter==='rezagada') return tags.includes('REZAGADA')||tags.includes('CASA REZAGADA');
    return true;
  });
  const pills=[['todos','Todos'],['steam','Steam'],['rlm','RLM'],['rezagada','Rezagada']];
  let html=`<h1>Líneas</h1><p class="ago">${esc(agoTxt(d.now))}</p>
    <div class="pills">${pills.map(([k,l])=>`<a class="pill ${k===filter?'on':''}" href="#/lineas/${k}">${l}</a>`).join('')}</div>
    <div class="sub">Solo movimientos de 3 pp o más, del historial real. Si no hay % de tickets, no se etiqueta RLM.</div>`;
  if(!rows.length) html+=`<div class="card mut">No hay movimientos de al menos 3 puntos porcentuales en las últimas ${d.hours||36} h${filter!=='todos'?' con ese filtro':''}.</div>`;
  else html+=`<div class="ln-al">`+rows.map(it=>{
    const g=it.game;
    const away=g&&g.away?(g.away.abbr||g.away.short||g.away.name||''):'';
    const home=g&&g.home?(g.home.abbr||g.home.short||g.home.name||''):'';
    const lg=(g&&g.league_name)||({atp:'ATP',wta:'WTA',mlb:'MLB',nfl:'NFL',nba:'NBA',nhl:'NHL'}[it.league]||String(it.league||'').toUpperCase());
    const named=home||away;
    const name=named?((g.sport==='futbol'||g.sport==='tenis')?`${esc(home)} vs ${esc(away)}`:`${esc(away)} @ ${esc(home)}`):esc(lg);
    const href=g?`#/juego/${encodeURIComponent(it.league)}/${encodeURIComponent(it.eid)}`:'#/lineas';
    const tags=(it.tags||[]).map(a=>{
      const k=String(a).toUpperCase();
      const cls=k.includes('STEAM')?'tag-st':k.includes('RLM')?'tag-rl':'tag-rz';
      return `<span class="${cls}">${esc(a)}</span>`;
    }).join('');
    const isLine=(it.market==='spread'||it.market==='total'||it.market==='Spread'||it.market==='Total') && it.open_line!=null && it.now_line!=null;
    const openTxt=isLine?String(it.open_line):lnAm(it.open_odds);
    const nowTxt=isLine?String(it.now_line):lnAm(it.now_odds);
    const chg=isLine&&it.line_delta!=null?(sg(it.line_delta)+' pts'):(it.pp!=null?sg(it.pp)+' pp':'');
    const pOpen=it.open_odds!=null&&typeof implied==='function'?implied(it.open_odds):null;
    const pNow=it.now_odds!=null&&typeof implied==='function'?implied(it.now_odds):null;
    const bar=(pNow!=null)?`<div class="imp-bar" title="Prob. implícita ${ (pNow*100).toFixed(1) }%">${pOpen!=null?`<i class="open" style="width:${Math.max(2,pOpen*100)}%"></i>`:''}<i style="width:${Math.max(2,pNow*100)}%"></i></div>`:'';
    let value='';
    if(it.laggards&&it.laggards.length){
      const lg=it.laggards[0];
      value=`<div class="sub">aún hay ${esc(lnAm(lg.odds))} en ${esc(lg.book)}</div>`;
    }
    const tix=it.pct_tickets==null?`<span class="sub">% tickets: no disponible</span>`:`<span class="sub">${it.pct_tickets}% tickets</span>`;
    return `<a class="card ln-card" href="${href}"><div class="sub">${esc((it.market||'').toUpperCase())} · ${esc(it.side||'')} · ${name}</div>
      <div class="ln-od mono">${esc(openTxt)} → ${esc(nowTxt)}</div>
      <div class="sub">${esc(chg)}${it.books?` · ${it.books} casas`:''} · ${esc(lnAgo(it.ts))}</div>
      <div class="tags">${tags}</div>${bar}${value}${tix}
      <div class="sub">${esc((g&&g.league_name)||it.league)}</div></a>`;
  }).join('')+`</div>`;
  $app.innerHTML=html;
}
