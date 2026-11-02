const TZ = 'America/Mexico_City';
const $app = document.getElementById('app');
const SD = 'Sin dato';
let SPORTS = null;
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmtTime = iso => new Intl.DateTimeFormat('es-MX',{timeZone:TZ,hour:'2-digit',minute:'2-digit',hour12:true}).format(new Date(iso));
const fmtDay = iso => new Intl.DateTimeFormat('es-MX',{timeZone:TZ,weekday:'long',day:'numeric',month:'long'}).format(new Date(iso));
const fmtShort = iso => new Intl.DateTimeFormat('es-MX',{timeZone:TZ,day:'numeric',month:'short'}).format(new Date(iso));
const dayKey = iso => new Intl.DateTimeFormat('en-CA',{timeZone:TZ}).format(new Date(iso));
const pct = (p, d=1) => (p==null||isNaN(p)) ? SD : (p*100).toFixed(d)+'%';
const am = v => v==null ? SD : (v>0?'+'+v:''+v);
const sg = (v,d=1) => v==null ? SD : (v>0?'+':'')+v.toFixed(d);
const num = (v,d=1) => v==null||isNaN(v) ? SD : Number(v).toFixed(d);

setInterval(()=>{document.getElementById('clock').textContent = new Intl.DateTimeFormat('es-MX',{timeZone:TZ,weekday:'short',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit',hour12:true}).format(new Date())+' · CDMX (UTC-6)'},1000);

async function api(path){ const r = await fetch(path); if(!r.ok) throw new Error((await r.json().catch(()=>({detail:r.statusText}))).detail||r.statusText); return r.json(); }
const loading = t => $app.innerHTML = `<div class="loading">⏳ ${t||'Cargando datos reales…'}</div>`;
const todayKey = () => dayKey(new Date().toISOString());
function dayLabel(iso){ const k=dayKey(iso); const t=todayKey(); const tm=dayKey(new Date(Date.now()+864e5).toISOString());
  const base = fmtDay(iso); return k===t?`Hoy · ${base}`:k===tm?`Mañana · ${base}`:base; }

const STATUS = {PICK:['🔥','PICK','b-pick'],LEAN:['🟡','LEAN LIGERO','b-lean'],PASS:['⛔','PASS','b-pass'],SIN_LINEA:['🔍','SIN LÍNEA','b-sl']};
const badgeSt = s => { const x=STATUS[s]||STATUS.PASS; return `<span class="badge ${x[2]}">${x[0]} ${x[1]}</span>` };
const confBadge = c => c ? `<span class="badge b-conf">${c.emoji} Confianza ${c.level}</span>` : '';

function setNav(n){ document.querySelectorAll('nav a').forEach(a=>a.classList.toggle('on',a.dataset.n===n)); }

// ------------------------------------------------------------ rutas
async function route(){
  const h = location.hash.replace(/^#\/?/,'').split('/').map(decodeURIComponent);
  window.scrollTo(0,0);
  try{
    if(!h[0]||h[0]==='') { setNav('home'); return viewHome(); }
    if(h[0]==='deporte'){ setNav('home'); return viewSport(h[1], h[2]); }
    if(h[0]==='juego'){ setNav('home'); return viewGame(h[1], h[2]); }
    if(h[0]==='picks'){ setNav('picks'); return viewPicks(h[1]||'24h'); }
    if(h[0]==='info'){ setNav('info'); return viewInfo(); }
    viewHome();
  }catch(e){ $app.innerHTML = `<div class="err">⚠️ ${esc(e.message)}</div>`; }
}
window.addEventListener('hashchange', route); route();

// ------------------------------------------------------------ home
async function viewHome(){
  SPORTS = SPORTS || await api('/api/sports');
  $app.innerHTML = `<h1>Elige un deporte</h1>
  <div class="grid g3">${SPORTS.map(s=>`<a class="card sport" href="#/deporte/${s.key}"><span class="em">${s.emoji}</span>${esc(s.name)}<span class="sub">${s.leagues.map(l=>esc(l.name)).join(' · ')}</span></a>`).join('')}</div>
  <div style="height:14px"></div>
  <a class="card sport" href="#/picks" style="border-color:#1b6b4a"><span class="em">🔥</span>Top picks del día (todos los deportes)<span class="sub">Ranking de los mejores spots según el modelo vs. el mercado</span></a>
  <div class="note">Datos reales de ESPN y MLB StatsAPI (sin llaves). Si algo no está disponible se muestra <b>${SD}</b>. Todas las probabilidades son <b>estimaciones de un modelo simple</b>, no certezas.</div>`;
}

// ------------------------------------------------------------ deporte
async function viewSport(sport, league){
  SPORTS = SPORTS || await api('/api/sports');
  const sp = SPORTS.find(s=>s.key===sport); if(!sp) return viewHome();
  league = league || sp.leagues[0].key;
  loading(`Cargando juegos de ${sp.name}…`);
  const d = await api('/api/games?league='+encodeURIComponent(league));
  const pills = sp.leagues.length>1 ? `<div class="pills">${sp.leagues.map(l=>`<a class="pill ${l.key===league?'on':''}" href="#/deporte/${sport}/${encodeURIComponent(l.key)}">${esc(l.name)}</a>`).join('')}</div>`:'';
  let body='';
  if(!d.ok) body = `<div class="note">⚠️ La fuente de datos no respondió. Intenta de nuevo en un momento.</div>`;
  else if(!d.games.length) body = `<div class="card mut">No hay juegos programados en los próximos días para <b>${esc(d.name)}</b>${league==='mlb'?' (la temporada 2026 de MLB ya terminó; vuelve en la próxima temporada)':''}. ${SD}.</div>`;
  else {
    let cur=''; const groups={};
    d.games.forEach(g=>{ const k=dayKey(g.date); (groups[k]=groups[k]||[]).push(g); });
    body = Object.keys(groups).sort().map(k=>`<div class="day">${esc(dayLabel(groups[k][0].date))}</div>`+groups[k].map(gameCard).join('')).join('');
  }
  $app.innerHTML = `<a class="back" href="#/">← Deportes</a><h1>${sp.emoji} ${esc(sp.name)}${sp.leagues.length>1?'':''}</h1>${pills}${body}`;
}
function stBadge(g){ return g.state==='in'?`<span class="badge b-live">● EN VIVO</span>`:g.state==='post'?`<span class="badge b-fin">FINAL</span>`:`<span class="badge b-pre">PROGRAMADO</span>`; }
function oddsChips(g){
  const o=g.odds; if(!o) return g.state==='pre'?`<span class="chip mut">Cuotas: ${SD}</span>`:'';
  const c=[];
  if(o.ml.home!=null||o.ml.away!=null) c.push(`<span class="chip mono">ML ${am(o.ml.away)} / ${am(o.ml.home)}${o.ml.draw!=null?' · E '+am(o.ml.draw):''}</span>`);
  if(o.spread.home) c.push(`<span class="chip mono">SPR ${sg(o.spread.home.line)} (${am(o.spread.home.price)})</span>`);
  if(o.total.over) c.push(`<span class="chip mono">O/U ${o.total.over.line}</span>`);
  return c.join('');
}
function gameCard(g){
  const sc = g.state!=='pre';
  return `<a class="card game" href="#/juego/${encodeURIComponent(g.league)}/${g.id}">
    <div><div class="time mono">${fmtTime(g.date)}</div><div class="sub">${stBadge(g)}</div></div>
    <div>
      <div class="tm">${g.away.logo?`<img src="${esc(g.away.logo)}" loading="lazy" alt="">`:''}<b>${esc(g.away.name)}</b><span class="sub">${esc(g.away.record||'')}</span>${sc?`<span class="sc mono ${g.away.winner?'pos':''}">${esc(g.away.score??'')}</span>`:''}</div>
      <div class="tm">${g.home.logo?`<img src="${esc(g.home.logo)}" loading="lazy" alt="">`:''}<b>${esc(g.home.name)}</b><span class="sub">${esc(g.home.record||'')}</span>${sc?`<span class="sc mono ${g.home.winner?'pos':''}">${esc(g.home.score??'')}</span>`:''}</div>
      <div class="sub">${esc(g.note||g.league_name)}${g.venue?' · '+esc(g.venue):''}</div>
    </div>
    <div class="chips hide-m">${oddsChips(g)}</div></a>`;
}

// ------------------------------------------------------------ juego
async function viewGame(league, id){
  loading('Analizando partido con datos reales…');
  const d = await api(`/api/game/${encodeURIComponent(league)}/${id}`);
  const g = d.game;
  const back = `<a class="back" href="#/deporte/${g.sport}/${encodeURIComponent(league)}">← ${esc(g.league_name)}</a>`;
  const hero = `<div class="card"><div class="sub" style="text-align:center">${esc(g.league_name)} · ${esc(fmtDay(g.date))} · <b>${fmtTime(g.date)}</b> CDMX ${stBadge(g)}${g.neutral&&d.kind!=='tennis'?' · cancha neutral':''}</div>
    <div class="hero" style="margin-top:10px">
      <div>${g.away.logo?`<img src="${esc(g.away.logo)}" alt="">`:''}<div class="n">${esc(g.away.name)}</div><div class="sub">${esc(g.away.record||'')}${d.kind==='tennis'&&g.away.rank?` · #${g.away.rank} ranking · ${g.away.points} pts`:''}</div>${g.state!=='pre'?`<div class="big mono" style="font-size:26px">${esc(g.away.score??'')}</div>`:''}</div>
      <div class="vs">${d.kind==='tennis'?'VS':'@'}</div>
      <div>${g.home.logo?`<img src="${esc(g.home.logo)}" alt="">`:''}<div class="n">${esc(g.home.name)}</div><div class="sub">${esc(g.home.record||'')}${d.kind==='tennis'&&g.home.rank?` · #${g.home.rank} ranking · ${g.home.points} pts`:''}</div>${g.state!=='pre'?`<div class="big mono" style="font-size:26px">${esc(g.home.score??'')}</div>`:''}</div>
    </div>
    <div class="sub" style="text-align:center;margin-top:8px">${esc(g.venue||'')}${g.court?' · '+esc(g.court):''}${g.note?' · '+esc(g.note):''}${g.weather?` · 🌡️ ${g.weather.temp_f}°F`:''}</div></div>`;
  let html = back + hero;
  html += picksSection(d);
  if(d.odds) html += oddsSection(d);
  if(d.kind==='tennis') html += tennisSections(d); else html += teamSections(d);
  if(d.gaps && d.gaps.length) html += `<div class="note gap"><b>🕳️ Datos no disponibles (${SD}):</b><ul class="t">${d.gaps.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div>`;
  html += `<div class="note">⚖️ <b>Estimación del modelo, no certeza.</b> Sin promesas de rentabilidad. Revisa lesiones/alineaciones de último minuto antes de apostar.</div>`;
  $app.innerHTML = html;
}

function candRow(c){
  const e = c.edge;
  return `<div class="cand"><div>${esc(c.label)} ${badgeSt(c.status)}${c.clipped?' <span class="sub" title="Probabilidad del modelo recortada a ±20 pp del mercado">✂️</span>':''}</div>
  <div class="mono" data-l="Precio">${esc(c.price_txt||SD)}</div>
  <div class="mono" data-l="Modelo">${pct(c.p_model)}</div>
  <div class="mono" data-l="Mercado s/vig">${pct(c.p_nv)}</div>
  <div class="mono ${e>0?'pos':e<0?'neg':''}" data-l="Edge">${e==null?SD:sg(e)+' pp'}</div>
  <div class="mono" data-l="Línea justa">${esc(c.fair_txt||SD)}</div>
  <div class="mono" data-l="Precio máx.">${esc(c.max_txt||SD)}</div></div>`;
}
function leanBlock(d){
  const p=d.picks, l=p.lean, c=p.confidence;
  const st=STATUS[p.status];
  const lines = [];
  if(l.price_txt){
    lines.push(`<div class="big">${st[0]} ${st[1]} · ${esc(l.label)} <span class="mono">(${esc(l.price_txt)})</span></div>`);
    lines.push(`📊 Modelo <b class="mono">${pct(l.p_model)}</b> vs implícita s/vig <b class="mono">${pct(l.p_nv)}</b> (con vig ${pct(l.implied_raw)})`);
    lines.push(`🧮 Prob. final (mezcla modelo/mercado) <b class="mono">${pct(l.p_final)}</b> · ⚡ Edge <b class="mono ${l.edge>0?'pos':'neg'}">${sg(l.edge)} pp</b> · EV <b class="mono ${l.ev>0?'pos':'neg'}">${sg(l.ev)}%</b>`);
    lines.push(`🎯 Línea justa <b class="mono">${esc(l.fair_txt)}</b> · 💰 Precio máximo para apostar <b class="mono">${esc(l.max_txt)}</b> <span class="sub">(EV ≥ +2% sobre la prob. final)</span>`);
  } else {
    lines.push(`<div class="big">${st[0]} ${st[1]} · Lean del modelo: ${esc(l.label)}</div>`);
    lines.push(`📊 Modelo <b class="mono">${pct(l.p_model)}</b> · Edge: ${SD} (no hay precio de mercado)`);
    lines.push(`🎯 Línea justa <b class="mono">${esc(l.fair_txt)}</b> · 💰 Precio máximo para apostar <b class="mono">${esc(l.max_txt)}</b> <span class="sub">(sólo valdría la pena apostar a ese momio o mejor)</span>`);
  }
  lines.push(`🧠 ${confBadge(c)} ${c.reasons&&c.reasons.length?`<span class="sub">${esc(c.reasons.join(' · '))}</span>`:''}`);
  if(l.downgraded) lines.push(`<span class="sub">⬇️ Era PICK pero se degradó a LEAN por confianza baja.</span>`);
  if(p.status==='PASS') lines.push(`<span class="sub">Sin ventaja suficiente en ningún mercado; este es el lean menos malo, no una recomendación fuerte.</span>`);
  return `<div class="lean">${lines.join('<br>')}</div>`;
}
function picksSection(d){
  if(!d.picks) return `<div class="card" style="margin-top:10px"><h2>🎯 Mejores picks</h2><div class="mut">${d.game.state!=='pre'?'El juego ya empezó o terminó: los picks pre-juego no aplican.':`Sin modelo para este juego (${SD}).`}</div></div>`;
  const cs = d.picks.candidates||[];
  return `<div class="card hot" style="margin-top:10px"><h2>🎯 Mejores picks <span class="badge b-model">ESTIMACIÓN DEL MODELO</span></h2>${leanBlock(d)}
  ${cs.length?`<div style="margin-top:12px"><div class="cand h"><div>Selección</div><div>Precio</div><div>Modelo</div><div>Mercado s/vig</div><div>Edge</div><div>Línea justa</div><div>Precio máx.</div></div>${cs.map(candRow).join('')}</div>`:''}
  ${d.model&&d.model.w_model!=null?`<div class="sub" style="margin-top:8px">Prob. final = ${Math.round(d.model.w_model*100)}% modelo + ${100-Math.round(d.model.w_model*100)}% mercado s/vig (el peso del modelo crece con la muestra de juegos). Edge = prob. final − prob. s/vig. ✂️ = prob. del modelo recortada a ±20 pp del mercado.</div>`:''}
  </div>`;
}
function oddsSection(d){
  const o=d.odds, nv=o.nv||{}, g=d.game;
  const rows=[];
  const mk=(lbl,price,p,pn)=>`<tr><td>${esc(lbl)}</td><td class="mono">${am(price)}</td><td class="mono">${pct(price==null?null:(price>0?100/(price+100):Math.abs(price)/(Math.abs(price)+100)))}</td><td class="mono"><b>${pct(pn)}</b></td></tr>`;
  const mlh=o.ml.home, mla=o.ml.away;
  if(mlh!=null||mla!=null){
    rows.push(`<tr><td colspan="4" class="mut">Moneyline${nv.ml_vig!=null?` · vig ${(nv.ml_vig*100).toFixed(1)}%`:''}</td></tr>`);
    rows.push(mk(g.away.name,mla,0,(nv.ml||{}).away)); if(o.ml.draw!=null) rows.push(mk('Empate',o.ml.draw,0,(nv.ml||{}).draw)); rows.push(mk(g.home.name,mlh,0,(nv.ml||{}).home));
  }
  if(o.spread.home||o.spread.away){
    rows.push(`<tr><td colspan="4" class="mut">${d.game.sport==='mlb'?'Run line':d.game.sport==='futbol'?'Hándicap':'Spread'}${nv.spread_vig!=null?` · vig ${(nv.spread_vig*100).toFixed(1)}%`:''}</td></tr>`);
    if(o.spread.away) rows.push(mk(`${g.away.name} ${sg(o.spread.away.line)}`,o.spread.away.price,0,(nv.spread||{}).away));
    if(o.spread.home) rows.push(mk(`${g.home.name} ${sg(o.spread.home.line)}`,o.spread.home.price,0,(nv.spread||{}).home));
  }
  if(o.total.over||o.total.under){
    rows.push(`<tr><td colspan="4" class="mut">Total${nv.total_vig!=null?` · vig ${(nv.total_vig*100).toFixed(1)}%`:''}</td></tr>`);
    if(o.total.over) rows.push(mk('Over '+o.total.over.line,o.total.over.price,0,(nv.total||{}).over));
    if(o.total.under) rows.push(mk('Under '+o.total.under.line,o.total.under.price,0,(nv.total||{}).under));
  }
  let mv='';
  if(o.open&&o.open.ml){ const bits=[]; for(const s of ['away','home']){ if(o.open.ml[s]!=null&&o.ml[s]!=null) bits.push(`${esc(g[s].short||g[s].name)}: ${am(o.open.ml[s])} → <b>${am(o.ml[s])}</b>`);} if(bits.length) mv=`<div class="sub" style="margin-top:6px">📈 Movimiento ML (apertura → actual): ${bits.join(' · ')}</div>`; }
  return `<div class="card" style="margin-top:10px"><h2>💵 Cuotas actuales <span class="badge b-ok">CONFIRMADO · ${esc(o.book)} vía ESPN</span></h2>
  <div class="tbl"><table><thead><tr><th>Mercado</th><th>Precio</th><th>Impl. c/vig</th><th>Impl. s/vig</th></tr></thead><tbody>${rows.join('')}</tbody></table></div>${mv}
  <div class="sub" style="margin-top:6px">Una sola casa (DraftKings) · probabilidad sin vig = normalización proporcional. Precios pueden cambiar; verifica en tu casa de apuestas.</div></div>`;
}

function formPills(f){ return `<div class="form">${(f||[]).map(x=>`<span class="f f-${x}">${x==='W'?'G':x==='L'?'P':'E'}</span>`).join('')||SD}</div>`; }
function teamSections(d){
  const g=d.game, H=g.home, A=g.away, th=d.teams[H.id], ta=d.teams[A.id], m=d.model, fam=g.sport;
  const unit = g.league==='mlb'?'Carreras':fam==='futbol'?'Goles':fam==='nhl'?'Goles':'Puntos';
  const row=(lbl,a,b)=>`<tr><td>${lbl}</td><td class="mono">${a}</td><td class="mono">${b}</td></tr>`;
  const sp=(s)=>s&&s.n?`${s.text}`:SD;
  const pfpa=(s)=>s&&s.n?`${num(s.pf)} / ${num(s.pa)}`:SD;
  let html = `<div class="card" style="margin-top:10px"><h2>📊 Comparativa del duelo <span class="badge b-ok">DATOS REALES ESPN</span></h2><div class="tbl"><table>
   <thead><tr><th></th><th>${esc(A.abbr||A.name)} (V)</th><th>${esc(H.abbr||H.name)} (L)</th></tr></thead><tbody>
   ${row('Récord temporada',sp(ta.overall),sp(th.overall))}
   ${row('Como visita / local',`${sp(ta.away)} <span class="mut">V</span>`,`${sp(th.home)} <span class="mut">L</span>`)}
   ${row('Últimos 5',sp(ta.last5),sp(th.last5))}${row('Últimos 10',sp(ta.last10),sp(th.last10))}
   ${row('Racha',ta.streak||SD,th.streak||SD)}
   ${row(`${unit} a favor / en contra (prom.)`,pfpa(ta.overall),pfpa(th.overall))}
   ${row(`… de visita / de local`,pfpa(ta.away),pfpa(th.home))}
   ${row(`… últimos 5`,pfpa(ta.last5),pfpa(th.last5))}
   ${m&&m.rating_home!=null?row('Rating del modelo (SRS ajustado, '+unit.toLowerCase()+')',sg(m.rating_away,2),sg(m.rating_home,2)):''}
   ${m&&m.lam_home!=null?row('Goles esperados (Poisson)',num(m.lam_away,2),num(m.lam_home,2)):''}
   </tbody></table></div>
   <div class="two" style="margin-top:10px"><div><div class="sub">Forma ${esc(A.abbr||A.name)} (más antiguo → reciente)</div>${formPills(ta.form)}</div><div><div class="sub">Forma ${esc(H.abbr||H.name)}</div>${formPills(th.form)}</div></div>
   <div class="sub">G = ganó · P = perdió · E = empate. Calculado con resultados finales de la temporada (n=${ta.n} / ${th.n} juegos).</div></div>`;
  if(d.pitchers){
    const pc = (p,t)=>p?`<div class="kv"><b>${esc(p.name)}</b> ${p.hand?`(${esc(p.hand)})`:''} <span class="badge b-prob">❓ PROBABLE</span><br>ERA ${esc(p.era||SD)} · WHIP ${esc(p.whip||SD)} · ${esc(p.ip||SD)} IP · ${p.w??'?'}-${p.l??'?'} · K ${p.k??SD}<br><span class="sub">Últimas salidas: ${(p.last||[]).map(x=>esc(x.date)+': '+esc(x.summary)).join(' | ')||SD}</span></div>`:`<div class="mut">Abridor: ${SD} (no anunciado)</div>`;
    html += `<div class="card" style="margin-top:10px"><h2>⚾ Lanzadores abridores</h2><div class="two"><div><div class="sub">${esc(A.name)}</div>${pc(d.pitchers.away)}</div><div><div class="sub">${esc(H.name)}</div>${pc(d.pitchers.home)}</div></div><div class="sub" style="margin-top:6px">Probables = anunciados por MLB, sujetos a cambio hasta el primer lanzamiento. Fuente: MLB StatsAPI.${m&&m.pitcher_adj!=null?` Ajuste del modelo por abridores: ${sg(m.pitcher_adj,2)} carreras de margen (local).`:''}</div></div>`;
  }
  html += `<div class="card" style="margin-top:10px"><h2>📈 Tendencias</h2>${d.trends&&d.trends.length?`<ul class="t">${d.trends.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:SD}
    ${(d.ats||[]).length?`<div class="sub" style="margin-top:6px">ATS (ESPN): ${d.ats.map(a=>esc(a.team)+' '+a.records.map(r=>esc(r.displayValue||r.summary)).join(' / ')).join(' · ')}</div>`:`<div class="sub" style="margin-top:6px">Récord ATS / O-U histórico: ${SD}</div>`}
    ${d.espn_predictor?`<div class="sub">🔮 Referencia ESPN (Matchup Predictor, no es de este modelo): ${esc(A.abbr)} ${esc(d.espn_predictor.away)}% · ${esc(H.abbr)} ${esc(d.espn_predictor.home)}%</div>`:''}</div>`;
  // últimos juegos
  const recent=(t,T)=>`<div><div class="sub"><b>${esc(T.name)}</b> · últimos juegos</div><div class="tbl"><table><tbody>${(t.recent||[]).slice(0,8).map(r=>`<tr><td>${fmtShort(r.date)} ${r.home?'vs':'@'} ${esc(r.opp)}</td><td class="mono ${r.res==='W'?'pos':r.res==='L'?'neg':'amb'}">${r.res==='W'?'G':r.res==='L'?'P':'E'} ${r.pf}-${r.pa}</td></tr>`).join('')||`<tr><td>${SD}</td></tr>`}</tbody></table></div></div>`;
  html += `<div class="card" style="margin-top:10px"><h2>🗓️ Resultados recientes</h2><div class="two">${recent(ta,A)}${recent(th,H)}</div></div>`;
  // lesiones y jugadores clave
  const injBlock=(T)=>{ const l=(d.injuries||{})[T.id]; if(l==null) return `<div class="mut">${esc(T.name)}: lesiones ${SD}</div>`;
    if(!l.length) return `<div><b>${esc(T.name)}</b><div class="mut">Sin lesionados reportados por la fuente.</div></div>`;
    return `<div><b>${esc(T.name)}</b>${l.slice(0,14).map(i=>`<div class="row"><span>${esc(i.name)} <span class="sub">${esc(i.pos||'')}</span><br><span class="sub">${esc(i.detail||'')}</span></span><span>${i.kind==='confirmado'?'<span class="badge b-ok">✅ '+esc(i.status)+'</span>':'<span class="badge b-prob">❓ '+esc(i.status)+'</span>'}</span></div>`).join('')}</div>`; };
  html += `<div class="card" style="margin-top:10px"><h2>🩹 Lesiones</h2><div class="two">${injBlock(A)}${injBlock(H)}</div><div class="sub" style="margin-top:6px">✅ confirmado = baja oficial (Out/IR) · ❓ por confirmar = dudoso / día a día / cuestionable. El modelo <b>no</b> ajusta por lesiones; sólo reduce la confianza si un líder del equipo está en la lista.${m&&m.key_injuries&&m.key_injuries.length?` <span class="amb">⚠️ Líder lesionado: ${esc(m.key_injuries.join(', '))}</span>`:''}</div></div>`;
  const leadBlock=(T)=>{ const l=(d.leaders||{})[T.id]; if(!l||!l.length) return `<div class="mut">${esc(T.name)}: ${SD}</div>`;
    return `<div><b>${esc(T.name)}</b>${l.map(x=>`<div class="row"><span class="sub">${esc(x.cat)}</span><span>${esc(x.name)} <span class="mono sub">${esc(x.value)}</span></span></div>`).join('')}</div>`; };
  html += `<div class="card" style="margin-top:10px"><h2>⭐ Jugadores clave (líderes del equipo)</h2><div class="two">${leadBlock(A)}${leadBlock(H)}</div></div>`;
  if(d.h2h&&d.h2h.length){ const s=d.h2h[0];
    html += `<div class="card" style="margin-top:10px"><h2>🤝 Enfrentamientos directos</h2><div class="sub">${esc(s.summary||'')}</div><div class="tbl"><table><tbody>${s.events.map(e=>`<tr><td>${fmtShort(e.date)} ${new Date(e.date).getFullYear()} · ${esc(e.away)} @ ${esc(e.home)}</td><td class="mono">${esc(e.as_)}-${esc(e.hs)}</td></tr>`).join('')}</tbody></table></div></div>`; }
  if(m){
    html += `<div class="card" style="margin-top:10px"><h2>🧠 Detalle del modelo</h2><div class="kv">
    <div class="row"><span>Prob. victoria (modelo)</span><span class="mono">${esc(A.abbr)} ${pct(m.p_away)} · ${m.p_draw!=null?'Empate '+pct(m.p_draw)+' · ':''}${esc(H.abbr)} ${pct(m.p_home)}</span></div>
    ${m.exp_margin!=null?`<div class="row"><span>Margen esperado (local)</span><span class="mono">${sg(m.exp_margin,2)}</span></div>`:''}
    ${m.exp_total!=null?`<div class="row"><span>Total esperado</span><span class="mono">${num(m.exp_total,1)}</span></div>`:''}
    ${m.hfa!=null?`<div class="row"><span>Ventaja de local (liga, observada con prior)</span><span class="mono">${sg(m.hfa,2)}</span></div>`:''}
    <div class="row"><span>Muestra (juegos)</span><span class="mono">${m.n_away} / ${m.n_home}</span></div>
    ${m.top_scores?`<div class="row"><span>Marcadores más probables</span><span class="mono">${m.top_scores.map(s=>`${s[0]}-${s[1]} (${(s[2]*100).toFixed(1)}%)`).join(' · ')}</span></div>`:''}
    </div><div class="sub" style="margin-top:6px">${m.kind==='poisson'?'Poisson con fuerza de ataque/defensa suavizada y ventaja local de la liga.':'Rating SRS (margen ajustado por rival y localía) suavizado + forma reciente; probabilidad con distribución normal.'} Ver pestaña Metodología.</div></div>`;
  }
  return html;
}

function tennisSections(d){
  const g=d.game, A=g.away, H=g.home; // en tenis: home=jugador 1 (orden ESPN), away=jugador 2
  const P=[H,A]; const m=d.model;
  const fm=(p,list)=>`<div><b>${esc(p.name)}</b> <span class="sub">${p.rank?`#${p.rank} · ${p.points} pts`:'Ranking: '+SD}${p.country?` · ${esc(p.country)}`:''}</span><div class="form">${(list||[]).slice(0,10).map(r=>`<span class="f f-${r.res}">${r.res==='W'?'G':'P'}</span>`).join('')||SD}</div>
    <div class="tbl"><table><tbody>${(list||[]).slice(0,6).map(r=>`<tr><td>${fmtShort(r.date)} vs ${esc(r.opp)} <span class="sub">${esc(r.round||'')}</span></td><td class="mono ${r.res==='W'?'pos':'neg'}">${r.res==='W'?'G':'P'} ${esc(r.score)}</td></tr>`).join('')||`<tr><td>${SD}</td></tr>`}</tbody></table></div></div>`;
  return `<div class="card" style="margin-top:10px"><h2>🎾 Jugadores y forma reciente</h2><div class="two">${fm(H,d.form.home)}${fm(A,d.form.away)}</div>
   <div class="sub" style="margin-top:6px">Forma = partidos de singles terminados en los torneos en curso/recientes que publica ESPN (muestra limitada). Superficie, H2H y lesiones: ${SD}.</div></div>
   ${m?`<div class="card" style="margin-top:10px"><h2>🧠 Detalle del modelo</h2><div class="row"><span>Prob. de victoria (heurística de ranking)</span><span class="mono">${esc(H.short)} ${pct(m.p_home)} · ${esc(A.short)} ${pct(m.p_away)}</span></div><div class="sub">${esc(m.label)}. No hay cuotas gratuitas en ESPN para tenis, así que no hay edge: sólo línea justa y el precio máximo sugerido.</div></div>`:''}`;
}

// ------------------------------------------------------------ picks del día
async function viewPicks(scope){
  loading('Calculando picks de todos los deportes (primera vez puede tardar ~20 s)…');
  const d = await api('/api/picks?scope='+scope);
  const tabs=[['24h','Próx. 24 h'],['hoy','Hoy'],['manana','Mañana'],['72h','72 h']];
  const t=`<div class="pills">${tabs.map(([k,l])=>`<a class="pill ${k===scope?'on':''}" href="#/picks/${k}">${l}</a>`).join('')}</div>`;
  const withOdds=d.items.filter(r=>r.has_odds&&r.status!=='PASS'), pass=d.items.filter(r=>r.has_odds&&r.status==='PASS'), noodds=d.items.filter(r=>!r.has_odds);
  const card=r=>{ const l=r.lean, g=r.game, st=STATUS[r.status];
    return `<a class="card pk" href="#/juego/${encodeURIComponent(g.league)}/${g.id}"><div class="ic">${st[0]}</div><div>
    <div><b>${esc(l.label)}</b> <span class="mono">${l.price_txt?'('+esc(l.price_txt)+')':''}</span> ${badgeSt(r.status)} ${confBadge(r.confidence)}</div>
    <div class="sub">${esc(g.league_name)} · ${esc(g.away.name)} @ ${esc(g.home.name)} · ${fmtShort(g.date)} ${fmtTime(g.date)} CDMX</div>
    <div class="sub mono">Modelo ${pct(l.p_model)} vs s/vig ${pct(l.p_nv)} · Línea justa ${esc(l.fair_txt||SD)} · Máx. ${esc(l.max_txt||SD)}</div></div>
    <div class="mono ${l.edge>0?'pos':'mut'}" style="font-size:18px;font-weight:800;text-align:right">${l.edge==null?SD:sg(l.edge)+' pp'}<div class="sub">edge</div></div></a>`; };
  let html=`<h1>🔥 Top picks · todos los deportes</h1>${t}<div class="sub" style="margin-bottom:8px">Ventana: ${d.n_games} juegos próximos analizados · ordenados por estado, edge y confianza. <b>Estimaciones del modelo</b>, no garantías.</div>`;
  if(!d.items.length) html+=`<div class="card mut">No hay juegos pre-juego en esta ventana. Prueba otra pestaña.</div>`;
  if(withOdds.length) html+=`<div class="day">Con ventaja (PICK / LEAN)</div>`+withOdds.slice(0,40).map(card).join('');
  if(pass.length) html+=`<div class="day">⛔ PASS · sin ventaja (se muestra el lean)</div>`+pass.slice(0,15).map(card).join('');
  if(noodds.length) html+=`<div class="day">🔍 Sin línea de mercado (sólo lean del modelo, sin edge)</div>`+noodds.slice(0,20).map(card).join('');
  $app.innerHTML=html;
}

// ------------------------------------------------------------ info
function viewInfo(){
  $app.innerHTML=`<h1>ℹ️ Metodología y fuentes</h1>
  <div class="card kv"><h2>Fuentes (públicas, sin llave)</h2><ul class="t"><li>ESPN site API: marcadores, resúmenes, calendarios y resultados, lesiones, líderes, tablas, rankings de tenis y cuotas de DraftKings (cuando existen).</li><li>MLB StatsAPI: lanzadores abridores probables y sus estadísticas.</li><li>Todo se cachea (marcadores 90 s, resúmenes 150 s, calendarios 1 h). Si un dato no existe se muestra <b>${SD}</b>; nunca se inventa.</li></ul></div>
  <div class="card kv" style="margin-top:10px"><h2>Modelo (transparente y simple)</h2><ul class="t">
  <li><b>NFL / NBA / NHL / MLB:</b> rating SRS (margen promedio ajustado por rival y localía) calculado con todos los resultados reales de la liga, suavizado hacia 0 según juegos jugados, + ajuste por forma (últimos 5). Probabilidad = normal(margen esperado, σ). En MLB se añade un ajuste pequeño por ERA de abridores probables.</li>
  <li><b>Fútbol:</b> Poisson con fuerza de ataque/defensa suavizada y ventaja de local de la liga → 1X2, hándicap y totales.</li>
  <li><b>Tenis:</b> logística sobre ln(puntos de ranking). Sin cuotas gratuitas ⇒ sin edge.</li>
  <li><b>Prob. final</b> = mezcla del modelo y el mercado sin vig; el peso del modelo (máx. 50%) crece con la muestra. El modelo se recorta a ±20 pp del mercado.</li>
  <li><b>Edge</b> = prob. final − prob. implícita sin vig (pp). <b>EV</b> = prob. final × momio decimal − 1. <b>Línea justa</b> = momio de la prob. final. <b>Precio máx.</b> = momio con EV = +2%.</li>
  <li><b>Estados:</b> 🔥 PICK (edge ≥ 3 pp, EV ≥ 0 y confianza Media/Alta) · 🟡 LEAN (edge ≥ 1 pp) · ⛔ PASS (sin edge; igual se muestra el lean) · 🔍 SIN LÍNEA (no hay precio).</li>
  <li><b>Confianza:</b> muestra de juegos, acuerdo con el mercado, líderes lesionados, abridores (MLB).</li></ul></div>
  <div class="note">El modelo no sabe de lesiones de último minuto, descansos, clima ni alineaciones. El mercado suele ser más informado que un modelo simple: trátalo como una segunda opinión. Sin promesas de rentabilidad.</div>`;
}
