/* Chat IA de NRNM (pt90u): botón flotante + panel. Responde con datos REALES de la app (picks, probabilidades, líneas, predicción, lesiones, props).
   Si el servidor tiene un LLM configurado (llave en variable de entorno) lo usa; si no (o en la versión de GitHub Pages), responde el motor local con reglas
   sobre los mismos datos. Nunca inventa cifras: si un dato no está, lo dice. */
const CH = {open:false, msgs:[], busy:false, llm:null, picks:null, picksT:0};
const chNorm = s => String(s||'').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'');
const chPct = p => p==null ? '—' : Math.round(p*100)+'%';
const chEdge = e => e==null ? '' : ` · edge ${e>0?'+':''}${e.toFixed(1)} pp`;
const chWhen = iso => { try{ return new Intl.DateTimeFormat('es-MX',{timeZone:TZ,weekday:'short',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit',hour12:true}).format(new Date(iso)); }catch(e){ return ''; } };
const chVs = g => (g.sport==='futbol'||g.sport==='tenis') ? `${g.home.name} vs ${g.away.name}` : `${g.away.name} @ ${g.home.name}`;   // fútbol/tenis: local primero
const chGame = it => chVs(it.game);
const chLink = g => `#/juego/${encodeURIComponent(g.league)}/${encodeURIComponent(g.id)}`;

async function chPicks(){
  if(CH.picks && Date.now()-CH.picksT<120000) return CH.picks;
  const d = await api('/api/picks?scope=72h', 60000); CH.picks = d.items||[]; CH.picksT = Date.now(); return CH.picks;
}
function chCurGame(){ const m=location.hash.match(/^#\/(?:juego|prop)\/([^/]+)\/([^/]+)/); return m?{league:decodeURIComponent(m[1]), eid:decodeURIComponent(m[2])}:null; }
function chFindGame(items, qn){
  // coincidencia por nombre/abreviatura de equipo o jugador (palabras de ≥4 letras o abreviatura exacta)
  const words = qn.split(/[^a-z0-9]+/).filter(w=>w.length>=3);
  let best=null, bs=0;
  for(const it of items){
    const g=it.game; let sc=0;
    for(const t of [g.home,g.away]){
      const nm=chNorm(t.name), ab=chNorm(t.abbr||'');
      for(const w of words){ if(w.length>=4 && nm.split(/\s+/).some(x=>x===w||(x.length>=5&&x.startsWith(w)))) sc+=2; else if(ab && w===ab) sc+=1; }
    }
    if(sc>bs){ bs=sc; best=it; }
  }
  return bs>=2?best:null;
}
function chPickLine(it){
  const l=it.lean||{}; if(!l.label) return `${chGame(it)}: sin pick (sin línea de mercado).`;
  return `• <a href="${chLink(it.game)}">${esc(chGame(it))}</a> (${esc(chWhen(it.game.date))})<br>&nbsp;&nbsp;<b>${esc(l.label)}</b> ${esc(l.price_txt||'')} · prob. ${chPct(l.p_final)}${chEdge(l.edge)} · ${esc(it.status)}${it.confidence?' · confianza '+esc(it.confidence.level):''}`;
}
async function chGameAnswer(league, eid, qn){
  const d = await api(`/api/game/${encodeURIComponent(league)}/${encodeURIComponent(eid)}`, 60000);
  const g=d.game, out=[`<b>${esc(chVs(g))}</b> · ${esc(g.league_name||'')} · ${esc(chWhen(g.date))}`];
  if(/lesion|baja|injur|lastim/.test(qn)){
    const inj=d.injuries||{}; const rows=[];
    for(const t of [g.away,g.home]){ const L=(inj[t.id]||[]); rows.push(`<b>${esc(t.name)}</b>: ${L.length?L.slice(0,8).map(i=>`${esc(i.name)} (${esc(i.status||'?')})`).join(', '):'sin bajas reportadas por ESPN'}`); }
    return out.concat(rows).join('<br>');
  }
  if(/prop|jugador|puntos|rebotes|asist|tiros|goles de|yardas|ponches|hits/.test(qn) && d.kind!=='tennis'){
    const P = await api(`/api/props/${encodeURIComponent(league)}/${encodeURIComponent(eid)}`, 60000);
    if(!P.players||!P.players.length) return out.concat([esc(P.note||'Sin props disponibles para este juego.')]).join('<br>');
    const rows=[]; for(const pl of P.players){ for(const pr of pl.props.slice(0,1)){ if(pr.line!=null) rows.push({pl,pr}); } }
    rows.sort((a,b)=>((b.pr.l10&&b.pr.l10.pct)||0)-((a.pr.l10&&a.pr.l10.pct)||0));
    out.push(P.mode==='referencia'?'<i>DraftKings aún no publica props: líneas de REFERENCIA (promedio últimos 10).</i>':'Props de DraftKings (vía ESPN), ordenados por % de acierto en sus últimos 10:');
    rows.slice(0,6).forEach(({pl,pr})=>out.push(`• ${esc(pl.name)} — ${esc(pr.label)} Más de ${pr.line}${pr.over!=null?' ('+esc(String(pr.over>0?'+'+pr.over:pr.over))+')':''} · cumplió ${pr.l10?pr.l10.hit+'/'+pr.l10.n:'—'}`));
    return out.join('<br>');
  }
  const p=d.pred, pk=d.picks;
  if(/ambos|btts/.test(qn)){
    const m=((d.probs||{}).markets||[]).find(x=>x.key==='btts');
    if(m) m.outcomes.forEach(o=>out.push(`${esc(o.label)}: modelo ${chPct(o.p_model)} · mercado ${chPct(o.p_nv)}${o.best?' · DraftKings '+esc(o.best.price_txt):''}${chEdge(o.edge)}`));
    else if(p&&p.btts) out.push(`${esc(p.btts.label)} · modelo ${chPct(p.btts.p)}`);
    else out.push('Sin datos de «Ambos anotan» para este juego (sólo fútbol, antes del inicio).');
  }
  if(pk&&pk.lean) out.push(`Pick: <b>${esc(pk.lean.label)}</b> ${esc(pk.lean.price_txt||'')} · prob. ${chPct(pk.lean.p_final)}${chEdge(pk.lean.edge)} · ${esc(pk.status)}`);
  if(p&&p.score){ const sc=d.kind==='tennis'?(p.score.sets||[]).map(x=>x.join('-')).join(' '):`${p.score.home}-${p.score.away} (local-visita)`;
    out.push(`Predicción NRNM: ${esc(sc)} · ganador ${esc(p.winner.side==='draw'?'empate':g[p.winner.side].name)} ${chPct(p.winner.p)}${p.total?` · ${esc(p.total.label)}`:''}${p.btts?` · ${esc(p.btts.label)} ${chPct(p.btts.p)}`:''}`); }
  const rec=(d.record||[]).filter(r=>r.open_line!=null&&r.line!=null&&r.open_line!==r.line);
  rec.slice(0,3).forEach(r=>out.push(`Línea movida: ${esc(r.label)} · abrió ${r.open_line} → ${g.state==='pre'?'actual':'cierre'} ${r.line}${r.state&&r.status==='ANULADO'?' ('+esc(r.state.toLowerCase())+')':''}`));
  if(!pk&&!p) out.push('Sin pick ni predicción (el juego ya empezó o no hay modelo/línea).');
  out.push(`<a href="${chLink(g)}">Abrir el juego →</a>`);
  return out.join('<br>');
}
const CH_NUM={dos:2,tres:3,cuatro:4,cinco:5,seis:6};
async function chParlay(qn){
  const n=Math.min(6,Math.max(2,+((qn.match(/\b([2-6])\b/)||[])[1]||CH_NUM[(qn.match(/\b(dos|tres|cuatro|cinco|seis)\b/)||[])[1]]||3)));
  const sp={nba:/nba|basket/,nfl:/nfl|americano/,nhl:/nhl|hockey/,futbol:/futbol|soccer|liga mx|premier/,tenis:/tenis|atp|wta/,mlb:/mlb|beis/};
  const spk=Object.keys(sp).find(k=>sp[k].test(qn));
  let scope=/manana/.test(qn)?'manana':'hoy', d=await api('/api/picks?scope='+scope);
  const off=x=>(x.official||[]).filter(c=>c.price!=null&&['ML','Spread','Total','BTTS'].includes(c.market));
  let pool=d.items.filter(it=>off(it).length&&(!spk||it.game.sport===spk));
  if(scope==='hoy'&&pool.length<n){ const d2=await api('/api/picks?scope=24h'); const have=new Set(pool.map(it=>it.game.league+it.game.id)); pool=pool.concat(d2.items.filter(it=>off(it).length&&(!spk||it.game.sport===spk)&&!have.has(it.game.league+it.game.id))); scope='24h'; }
  pool.sort((a,b)=>(off(b)[0].score||0)-(off(a)[0].score||0));
  const pick=pool.slice(0,n);
  if(!pick.length) return `No hay picks oficiales${spk?' de '+spk.toUpperCase():''} ${scope==='manana'?'mañana':'en las próximas 24 h'}: hoy ningún juego pasa el filtro estricto, así que no armo un parlay con relleno.`;
  const legs=pick.map(it=>tkLegFromCand(it.game,Object.assign({official:true},off(it)[0])));
  const dd=legs.reduce((a,l)=>a*tkDec(l.odds),1), pm=legs.every(l=>l.p!=null)?legs.reduce((a,l)=>a*l.p,1):null;
  CH.parlay=legs;
  const lines=pick.map((it,i)=>{ const c=off(it)[0], v=(c.signals||{}).verdict; return `${i+1}. <b>${esc(c.label)}</b> ${esc(c.price_txt||'')} — ${esc(chGame(it))} (${esc(chWhen(it.game.date))})<br>&nbsp;&nbsp;puntaje ${c.score}/100 · prob. ${chPct(c.p_final)}${chEdge(c.edge)}${v&&v!=='sin_dato'?' · señales '+esc(v.replace('_',' ')):''}`; });
  return `Parlay de ${legs.length}${legs.length<n?` (sólo hay ${legs.length} picks oficiales; no relleno con picks débiles)`:''} con los picks oficiales de mayor puntaje, 1 por juego (sin correlación):<br>${lines.join('<br>')}
    <br>Momio combinado <b>${tkAm(dd)}</b> · prob. del modelo <b>${pm==null?'—':(pm*100).toFixed(1)+'%'}</b> (asume independencia) · implícita ${(100/dd).toFixed(1)}%.
    <br><button type="button" class="btn pri ch-mk" onclick="tkLoad(CH.parlay)">🎟️ Crear ticket con estas piernas</button><br><span class="ch-mut">Paper trading. Más piernas = mucho menos probable; ningún parlay es «seguro».</span>`;
}
async function chLocal(q){
  const qn=chNorm(q);
  if(/parlay|parley|combinad|ticket|arma/.test(qn)) return chParlay(qn);
  if(/^(hola|buenas|hey|que tal|ayuda|help)\b/.test(qn)) return 'Hola 👋 Pregúntame por <b>los mejores picks de hoy</b>, un equipo (ej. «Chiefs»), sus <b>lesiones</b>, <b>props</b> de jugadores o el <b>récord</b>. Respondo sólo con los datos de la app.';
  if(/record|historial|cuanto (llevamos|vamos)|acierto/.test(qn)){
    const rel={antier:-2,anteayer:-2,ayer:-1,hoy:0,manana:1}, k=Object.keys(rel).find(w=>new RegExp('\\b'+w+'\\b').test(qn));
    if(k){ const d0=await api('/api/record/day'), dt=new Date(Date.parse(d0.today+'T12:00:00Z')+rel[k]*864e5).toISOString().slice(0,10);
      const d=rel[k]?await api('/api/record/day?date='+dt):d0, a=d.summary;
      return `Récord de <b>${k==='manana'?'mañana':k}</b> (${dt}): <b>${a.W}-${a.L}-${a.P}</b>${a.win_pct!=null?` · ${a.win_pct.toFixed(1)}%`:''}${a.n_priced?` · ${a.units>0?'+':''}${a.units.toFixed(2)} u`:''} · ${a.pending} pendientes de ${a.n} picks. <a href="#/record/dia/${dt}">Ver el día →</a>`; }
    const r=await api('/api/record?limit=80'); const s=r.summary||{};
    return `Récord de picks (paper trading): <b>${s.W??'—'}-${s.L??'—'}-${s.P??'—'}</b>${s.win_pct!=null?` · ${s.win_pct.toFixed(1)}% de acierto`:''}${s.units!=null?` · ${s.units>0?'+':''}${(+s.units).toFixed(2)} u a 1u plano`:''}${s.roi!=null?` (ROI ${s.roi.toFixed(1)}%)`:''} · ${s.pending??0} pendientes. <a href="#/record/total">Ver récord →</a>`;
  }
  const cur=chCurGame(), items=await chPicks();
  const named=chFindGame(items,qn);
  if(named) return chGameAnswer(named.game.league, named.game.id, qn);
  if(cur && (/(este|esta|del|el) (juego|partido)|aqui/.test(qn) || (/lesion|baja|prop|jugador|marcador|prediccion/.test(qn) && !/mejores|hoy|manana|todos/.test(qn)))) return chGameAnswer(cur.league, cur.eid, qn);
  let pool=items.filter(it=>it.lean&&it.lean.edge!=null&&it.status==='PICK');
  const sp={nba:/nba|basket/,nfl:/nfl|americano/,mlb:/mlb|beis/,nhl:/nhl|hockey/,futbol:/futbol|soccer|liga mx|premier|champions/,tenis:/tenis|atp|wta/};
  for(const [k,re] of Object.entries(sp)) if(re.test(qn)) pool=pool.filter(it=>it.game.sport===k);
  if(/ambos anotan|btts/.test(qn)) pool=pool.filter(it=>(it.lean.market||'')==='BTTS'||(it.top||[]).some(t=>t.market==='BTTS'));
  if(/hoy/.test(qn)){ const today=new Intl.DateTimeFormat('en-CA',{timeZone:TZ}).format(new Date()); pool=pool.filter(it=>new Intl.DateTimeFormat('en-CA',{timeZone:TZ}).format(new Date(it.game.date))===today); }
  if(/pick|recomien|apost|mejor|valor|hoy|manana|parlay|btts|ambos/.test(qn) || pool.length!==items.length){
    pool.sort((a,b)=>(b.status==='PICK')-(a.status==='PICK')||(b.lean.edge||0)-(a.lean.edge||0));
    if(!pool.length) return 'No hay picks oficiales para eso en las próximas 72 h (ningún juego pasa el filtro estricto).';
    pool.sort((a,b)=>(b.lean.score||0)-(a.lean.score||0));
    return `Picks oficiales (por puntaje, próximas 72 h${/hoy/.test(qn)?', hoy':''}):<br>`+pool.slice(0,5).map(chPickLine).join('<br>')+'<br><span class="ch-mut">Estimaciones del modelo, no garantías. Paper trading.</span>';
  }
  return 'No encontré ese equipo/juego en los próximos 3 días. Prueba con el nombre del equipo (ej. «Real Madrid», «Lakers»), «mejores picks hoy», «props» o «lesiones» desde un juego abierto.';
}
async function chAsk(q){
  if(CH.llm==null && !STATIC){ try{ CH.llm=(await api('/api/chat/status',8000)).llm; }catch(e){ CH.llm=false; } }
  if(CH.llm && !STATIC && !/parlay|parley|combinad|ticket|arma/.test(chNorm(q))){
    try{
      const c=chCurGame();
      const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({q, league:c&&c.league, eid:c&&c.eid})});
      const d=await r.json();
      if(d.llm&&d.text) return {html:esc(d.text).replace(/\*\*(.+?)\*\*/g,'<b>$1</b>').replace(/\n/g,'<br>'), src:'IA ('+esc(d.model||'LLM')+') con datos de la app'};
    }catch(e){}
  }
  return {html: await chLocal(q), src: 'Respuesta con datos de la app (motor local'+(STATIC?', versión en línea':'')+')'};
}
function chRender(){
  let p=document.getElementById('chp');
  if(!p){ p=document.createElement('div'); p.id='chp'; p.setAttribute('role','dialog'); p.setAttribute('aria-label','Chat IA'); document.body.appendChild(p); }
  p.hidden=!CH.open; document.getElementById('chb').classList.toggle('on',CH.open);
  if(!CH.open) return;
  const sug=['Arma un parlay de 3 con lo más seguro de hoy','Mejores picks de hoy','Picks NBA','Ambos anotan','¿Cómo vamos en el récord?'].concat(chCurGame()?['Lesiones de este juego','Props de este juego']:[]);
  p.innerHTML=`<div class="ch-h"><b>Chat NRNM</b><span>IA con datos reales</span><button type="button" class="ch-x" aria-label="Cerrar">✕</button></div>
    <div class="ch-m" id="chm">${CH.msgs.length?CH.msgs.map(m=>`<div class="ch-${m.r}">${m.h}${m.s?`<small>${m.s}</small>`:''}</div>`).join(''):'<div class="ch-a">Hola, pregúntame por picks, un equipo, lesiones, props o el récord. Uso sólo los datos de la app.</div>'}${CH.busy?'<div class="ch-a ch-dots"><i></i><i></i><i></i></div>':''}</div>
    <div class="ch-s">${sug.map(s=>`<button type="button" class="ch-sg">${esc(s)}</button>`).join('')}</div>
    <form class="ch-f"><input id="chi" type="text" autocomplete="off" placeholder="Escribe tu pregunta…" maxlength="400"><button type="submit" aria-label="Enviar">➤</button></form>`;
  const m=document.getElementById('chm'); m.scrollTop=m.scrollHeight;
}
async function chSend(q){
  q=String(q||'').trim(); if(!q||CH.busy) return;
  CH.msgs.push({r:'u',h:esc(q)}); CH.busy=true; chRender();
  try{ const a=await chAsk(q); CH.msgs.push({r:'a',h:a.html,s:a.src}); }
  catch(e){ CH.msgs.push({r:'a',h:'No pude consultar los datos: '+esc(e.message)}); }
  CH.busy=false; chRender(); const i=document.getElementById('chi'); if(i) i.focus();
}
(function(){
  const b=document.createElement('button'); b.id='chb'; b.type='button'; b.setAttribute('aria-label','Abrir chat IA'); b.innerHTML='<span>IA</span>';
  document.body.appendChild(b);
  b.addEventListener('click',()=>{ CH.open=!CH.open; chRender(); if(CH.open){ const i=document.getElementById('chi'); if(i) i.focus(); } });
  document.addEventListener('click',e=>{
    if(e.target.closest('#chp .ch-x')){ CH.open=false; chRender(); }
    const s=e.target.closest('#chp .ch-sg'); if(s) chSend(s.textContent);
    if(e.target.closest('#chp .ch-m a')){ CH.open=false; chRender(); }
  });
  document.addEventListener('submit',e=>{ if(e.target.closest('#chp .ch-f')){ e.preventDefault(); const i=document.getElementById('chi'); const v=i.value; i.value=''; chSend(v); } });
})();
