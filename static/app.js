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
  html += marketSection(d) + splitsSection(d) + rlmSection(d) + movementSection(d);
  if(d.odds && d.odds.src==='espn') html += oddsSection(d);
  if(d.kind==='tennis') html += tennisSections(d); else html += teamSections(d);
  if(d.gaps && d.gaps.length) html += `<div class="note gap"><b>🕳️ Datos no disponibles (${SD}):</b><ul class="t">${d.gaps.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div>`;
  html += `<div class="note">⚖️ <b>Estimación del modelo, no certeza.</b> Sin promesas de rentabilidad. Revisa lesiones/alineaciones de último minuto antes de apostar.</div>`;
  $app.innerHTML = html;
  mvDraw();
}

function candRow(c){
  const e = c.edge;
  return `<div class="cand"><div>${esc(c.label)} ${badgeSt(c.status)}${c.clipped?' <span class="sub" title="Probabilidad del modelo recortada a ±20 pp del mercado">✂️</span>':''}</div>
  <div class="mono" data-l="Precio">${esc(c.price_txt||SD)}</div>
  <div class="mono" data-l="Modelo">${pct(c.p_model)}</div>
  <div class="mono" data-l="Mercado s/vig">${pct(c.p_nv)}</div>
  <div class="mono ${e>0?'pos':e<0?'neg':''}" data-l="Edge">${e==null?SD:sg(e)+' pp'}</div>
  <div class="mono" data-l="Línea justa">${esc(c.fair_txt||SD)}</div>
  <div class="mono" data-l="Precio máx.">${esc(c.max_txt||SD)}</div>${c.signals&&c.signals.verdict&&c.signals.verdict!=='sin_dato'?`<div class="ctags">${tagChips(c.signals)||'<span class="sub">Mercado: sin señal clara</span>'}${c.signals.best?`<span class="sub">🏷️ Mejor precio ${esc(c.signals.best.price_txt)} en ${esc(c.signals.best.book)}${c.signals.best.ev!=null?' · EV '+sg(c.signals.best.ev)+'%':''}</span>`:''}</div>`:''}</div>`;
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
  return `<div class="lean">${lines.join('<br>')}</div>${sigLine(l.signals)}`;
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
  <div class="sub" style="margin-top:6px">Una sola casa (${esc(o.book)}, vía ESPN) · el comparador de arriba tiene más casas · probabilidad sin vig = normalización proporcional. Precios pueden cambiar; verifica en tu casa de apuestas.</div></div>`;
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
    <div class="sub mono">Modelo ${pct(l.p_model)} vs s/vig ${pct(l.p_nv)} · Línea justa ${esc(l.fair_txt||SD)} · Máx. ${esc(l.max_txt||SD)}</div>${l.signals&&l.signals.verdict&&l.signals.verdict!=='sin_dato'?`<div class="sub">${(VERD[l.signals.verdict]||[])[0]||''} ${(VERD[l.signals.verdict]||[])[1]||''}${l.signals.tickets!=null?` · ${l.signals.tickets}% tickets / ${l.signals.money!=null?l.signals.money+'% dinero':'dinero '+SD}`:''}${l.signals.best?` · mejor ${esc(l.signals.best.price_txt)} en ${esc(l.signals.best.book)}`:''}</div>${tagChips(l.signals)}`:''}</div>
    <div class="mono ${l.edge>0?'pos':'mut'}" style="font-size:18px;font-weight:800;text-align:right">${l.edge==null?SD:sg(l.edge)+' pp'}<div class="sub">edge</div></div></a>`; };
  let html=`<h1>🔥 Top picks · todos los deportes</h1>${t}<div class="sub" style="margin-bottom:8px">Ventana: ${d.n_games} juegos próximos analizados · ordenados por estado, edge y confianza. <b>Estimaciones del modelo</b>, no garantías.</div>`;
  if(!d.items.length) html+=`<div class="card mut">No hay juegos pre-juego en esta ventana. Prueba otra pestaña.</div>`;
  if(withOdds.length) html+=`<div class="day">Con ventaja (PICK / LEAN)</div>`+withOdds.slice(0,40).map(card).join('');
  if(pass.length) html+=`<div class="day">⛔ PASS · sin ventaja (se muestra el lean)</div>`+pass.slice(0,15).map(card).join('');
  if(noodds.length) html+=`<div class="day">🔍 Sin línea de mercado (sólo lean del modelo, sin edge)</div>`+noodds.slice(0,20).map(card).join('');
  $app.innerHTML=html;
}


// ------------------------------------------------------------ mercado: casas, % apuestas, RLM, movimientos
const tsFmt = t => t==null ? SD : new Intl.DateTimeFormat('es-MX',{timeZone:TZ,day:'numeric',month:'short',hour:'2-digit',minute:'2-digit',hour12:true}).format(new Date(t*1000))+' CDMX';
const dec2 = a => a==null ? null : (a>0 ? 1+a/100 : 1+100/Math.abs(a));
const probRaw = a => a==null ? null : (a>0 ? 100/(a+100) : Math.abs(a)/(Math.abs(a)+100));
const fairAm = p => p==null||p<=0||p>=1 ? null : (p>=.5 ? Math.round(-100*p/(1-p)) : Math.round(100*(1-p)/p));
const KIND = {sharp:['SHARP','b-model'],consensus:['CONSENSO','b-conf'],open:['APERTURA','b-pass'],book:['','']};
const TAG_CLS = {rlm_for:'t-pos',sharp_for:'t-pos',rlm_against:'t-neg',sharp_against:'t-neg',move_with:'t-neu'};
const tagChips = c => (c&&c.tags&&c.tags.length) ? `<div class="tags">${c.tags.map(t=>`<span class="tag ${TAG_CLS[t[0]]||'t-neu'}" title="${esc(t[1])}">${esc(t[1])}</span>`).join('')}</div>` : '';
const VERD = {a_favor:['✅','Señales de mercado a favor','pos'],en_contra:['⚠️','Señales de mercado en contra','neg'],mixto:['↔️','Señales mixtas','amb'],neutral:['➖','Sin señal clara de mercado','mut'],sin_dato:['🕳️','Señales de mercado: '+SD,'mut']};
function sigLine(c){
  if(!c||!c.verdict) return '';
  const v=VERD[c.verdict]||VERD.sin_dato;
  const sp = (c.tickets!=null||c.money!=null) ? ` · <span class="mono">${c.tickets!=null?c.tickets+'% tickets':'tickets '+SD} / ${c.money!=null?c.money+'% dinero':'dinero '+SD}</span>` : '';
  const best = c.best ? ` · 🏷️ Mejor precio: <b class="mono">${esc(c.best.price_txt)}</b> en ${esc(c.best.book)}${c.best.ev!=null?` (EV ${sg(c.best.ev)}%)`:''}` : '';
  return `<div class="sig"><span class="${v[2]}">${v[0]} <b>${v[1]}</b></span>${sp}${best}${tagChips(c)}<div class="sub">Indicadores de mercado (RLM, % dinero vs % tickets), no garantías.</div></div>`;
}

function marketSection(d){
  const mk=d.market, g=d.game;
  if(!mk||!mk.books||!mk.books.length) return `<div class="card" style="margin-top:10px"><h2>📚 Comparador de casas</h2><div class="mut">${SD}: ninguna fuente publica cuotas para este juego${d.odds_note?' · '+esc(d.odds_note):''}.</div></div>`;
  const books=mk.books, nm=s=>s==='home'?g.home.name:s==='away'?g.away.name:s==='draw'?'Empate':s==='over'?'Over':'Under';
  const sh=s=>s==='home'?(g.home.short||g.home.name):s==='away'?(g.away.short||g.away.name):s==='draw'?'Empate':s==='over'?'Over':'Under';
  const tbl=(title,key,sides,cell,extra)=>{
    if(!books.some(b=>b[key]&&sides.some(s=>b[key][s]!=null))) return '';
    const head=`<tr><th>Casa</th>${sides.map(s=>`<th>${esc(sh(s))}</th>`).join('')}</tr>`;
    const rows=books.filter(b=>b[key]&&sides.some(s=>b[key][s]!=null)).map(b=>{
      const k=KIND[b.kind]||KIND.book;
      return `<tr class="k-${b.kind}"><td>${esc(b.name)} ${k[0]?`<span class="badge ${k[1]}">${k[0]}</span>`:''}</td>${sides.map(s=>{
        const fl=(b.flags||{})[key+'.'+s]; const c=cell(b,s);
        return `<td class="mono ${fl==='best'?'best':fl==='line'?'bline':''}" title="${fl==='best'?'Mejor precio en la misma línea':fl==='line'?'Mejor línea (número más favorable)':''}">${c}</td>`}).join('')}</tr>`;}).join('');
    let nvrow='';
    const cn=(mk.consensus_nv||{})[key], sn=(mk.sharp_nv||{})[key];
    const nvr=(lbl,o,cls)=>o?`<tr class="nv ${cls}"><td>${lbl} <span class="sub">(${o.n?o.n+' casas':'1 casa'}${o.line!=null?' · línea '+(key==='spread'?sg(o.line):o.line):''})</span></td>${sides.map(s=>`<td class="mono">${o[s]!=null?`<b>${pct(o[s])}</b> <span class="sub">${am(fairAm(o[s]))}</span>`:SD}</td>`).join('')}</tr>`:'';
    nvrow=nvr('Consenso s/vig',cn,'cons')+nvr('Pinnacle s/vig',sn,'sharp');
    return `<div class="tbl"><div class="sub tt">${title}</div><table class="cmp"><thead>${head}</thead><tbody>${rows}${nvrow}</tbody></table></div>`;
  };
  const sideCell=(key,s)=>b=>b[key]&&b[key][s]!=null?am(b[key][s]):'<span class="mut">—</span>';
  const lp=(key)=>(b,s)=>{const c=(b[key]||{})[s]; return c?`${key==='spread'?sg(c.line):(s==='over'?'O ':'U ')+c.line} <span class="${c.price>0?'pos':''}">${am(c.price)}</span>`:'<span class="mut">—</span>'};
  const mlSides = books.some(b=>b.ml&&b.ml.draw!=null)?['away','draw','home']:['away','home'];
  const ts=(mk.sources||[]).map(s=>`${esc(s.name)} (${s.n_books} ${s.n_books===1?'casa':'casas'}) · ${tsFmt(s.ts)}`).join(' · ');
  const nreal=books.filter(b=>b.kind==='book'||b.kind==='sharp').length;
  return `<div class="card" style="margin-top:10px"><h2>📚 Comparador de casas <span class="badge b-ok">${nreal} CASAS</span></h2>
   ${tbl('Moneyline','ml',mlSides,(b,s)=>sideCell('ml',s)(b))}
   ${tbl(d.game.sport==='mlb'?'Run line':d.game.sport==='futbol'?'Hándicap':d.game.sport==='tenis'?'Hándicap de sets':'Spread','spread',['away','home'],(b,s)=>lp('spread')(b,s))}
   ${tbl(d.game.sport==='tenis'?'Total de sets':'Total','total',['over','under'],(b,s)=>lp('total')(b,s))}
   <div class="legend"><span class="best mono">verde</span> = mejor precio en la misma línea · <span class="bline mono">subrayado</span> = mejor línea (número más favorable) · filas “s/vig” = probabilidad sin comisión (normalización proporcional) y su momio justo. Consenso = promedio de las casas en la línea de referencia.</div>
   <div class="sub" style="margin-top:6px">Fuentes: ${ts||SD}. Los precios cambian; confirma en tu casa antes de apostar.</div></div>`;
}

function splitsSection(d){
  const mk=d.market, g=d.game; if(!mk) return '';
  const sp=mk.splits||{}, has=Object.keys(sp).length>0;
  const names={ml:'Moneyline',spread:d.game.sport==='futbol'?'Hándicap':'Spread',total:'Total'};
  const lab=(m,s)=>s==='home'?g.home.name:s==='away'?g.away.name:s==='draw'?'Empate':s==='over'?'Over':'Under';
  const ordr={ml:['away','draw','home'],spread:['away','home'],total:['over','under']};
  let body='';
  if(has){
    body=['ml','spread','total'].filter(m=>sp[m]).map(m=>{
      const sg_=(mk.signals||{})[m]||{};
      const rows=ordr[m].filter(s=>sp[m][s]).map(s=>{ const t=sp[m][s].t, mo=sp[m][s].m; const df=(t!=null&&mo!=null)?mo-t:null;
        return `<div class="bars"><div class="bl">${esc(lab(m,s))}${df!=null&&df>=10?' <span class="tag t-pos" title="Dinero% supera tickets% por ≥10 pp">$ dinero &gt; tickets</span>':''}</div>
         <div class="bw"><div class="bar t" style="width:${t||0}%"></div><span class="mono">${t!=null?t+'%':SD}</span></div>
         <div class="bw"><div class="bar m" style="width:${mo||0}%"></div><span class="mono">${mo!=null?mo+'%':SD}</span></div></div>`; }).join('');
      return `<div class="mk"><div class="sub tt">${names[m]}</div><div class="bars hd"><div></div><div>% Tickets (apuestas)</div><div>% Dinero</div></div>${rows}</div>`;}).join('');
  } else body=`<div class="mut">${SD}: la fuente de % apuestas / % dinero no cubre este juego${d.kind==='tennis'||mk.matched&&!mk.matched.an?' (sólo Action Network publica splits y no cubre esta liga o este juego aún)':''}. No se estima ni se inventa.</div>`;
  return `<div class="card" style="margin-top:10px"><h2>🧾 % Apuestas y % Dinero ${has?'<span class="badge b-ok">CONFIRMADO</span>':'<span class="badge b-pass">SIN DATO</span>'}</h2>${body}
   <div class="sub" style="margin-top:6px">Fuente: ${has?esc(mk.splits_src||'Action Network')+' · '+tsFmt(mk.splits_ts):SD}. % tickets = proporción de apuestas; % dinero = proporción del monto apostado. Cubre las casas de EE. UU. que reporta la fuente, no el mercado total.</div></div>`;
}

function rlmSection(d){
  const mk=d.market, g=d.game; if(!mk) return '';
  const sg_=mk.signals||{}; const names={ml:'Moneyline',spread:'Spread',total:'Total'};
  const lab=(m,s)=>s==='home'?g.home.name:s==='away'?g.away.name:s==='draw'?'Empate':s==='over'?'Over':'Under';
  const items=['ml','spread','total'].filter(m=>sg_[m]&&sg_[m].tickets).map(m=>{
    const s=sg_[m]; const pub=s.public_side;
    const flags=[];
    if(s.rlm) flags.push(`<span class="tag t-pos">🔄 RLM → ${esc(lab(m,s.rlm_side))}</span>`);
    else if(s.move_dir==='con') flags.push(`<span class="tag t-neu">La línea se mueve con el público</span>`);
    else if(!pub) flags.push(`<span class="tag t-neu">Sin lado público claro</span>`);
    else flags.push(`<span class="tag t-neu">Sin movimiento significativo</span>`);
    if(s.sharp_side) flags.push(`<span class="tag t-pos">$ Dinero &gt; tickets (+${s.sharp_diff} pp) → ${esc(lab(m,s.sharp_side))}</span>`);
    return `<div class="row2"><div><b>${names[m]}</b> · lado público: <b>${pub?esc(lab(m,pub)):SD}</b> <span class="mono sub">(${pub?s.tickets[pub]+'% tickets':''})</span></div><div>${flags.join(' ')}</div><div class="sub">${esc(s.move_text||'')}</div></div>`;}).join('');
  const body = items || `<div class="mut">${SD}: sin % apuestas y/o sin apertura para este juego, no se puede evaluar RLM ni dinero inteligente.</div>`;
  return `<div class="card" style="margin-top:10px"><h2>🔄 RLM y dinero inteligente <span class="badge b-prob">INDICADOR · NO GARANTÍA</span></h2>${body}
   <div class="note" style="margin-bottom:0">RLM (movimiento inverso de línea): el público (≥55% de tickets; ≥45% y mayoría en 3 vías) está de un lado, pero la línea o el precio se mueve en su contra (≥0.25 pts o ≥1.5 pp en prob. s/vig entre apertura y actual de Action Network). “Dinero &gt; tickets” = % dinero supera % tickets por ≥10 pp en un lado. Son <b>indicadores</b> que a veces fallan; no garantizan resultado.</div></div>`;
}

let MV=null;
function movementSection(d){
  const mk=d.market, g=d.game; if(!mk) return '';
  const mv=mk.movement||{}, rows=[];
  const sh=s=>s==='home'?(g.home.short||g.home.name):s==='away'?(g.away.short||g.away.name):s==='draw'?'Empate':s==='over'?'Over':'Under';
  if(mv.ml) for(const s of ['away','draw','home']){ const x=mv.ml[s]; if(x) rows.push(`<tr><td>Moneyline · ${esc(sh(s))}</td><td class="mono">${am(x.open)}</td><td class="mono"><b>${am(x.cur)}</b></td><td class="mono ${x.d_nv_pp>0?'pos':x.d_nv_pp<0?'neg':''}">${x.d_nv_pp!=null?sg(x.d_nv_pp)+' pp':SD}</td></tr>`); }
  if(mv.spread) rows.push(`<tr><td>${g.sport==='futbol'?'Hándicap':'Spread'} · ${esc(sh('home'))}</td><td class="mono">${sg(mv.spread.open_line)} <span class="sub">${am((mv.spread.open_price||{}).home)}</span></td><td class="mono"><b>${sg(mv.spread.cur_line)}</b> <span class="sub">${am((mv.spread.cur_price||{}).home)}</span></td><td class="mono ${mv.spread.d_line_home>0?'pos':mv.spread.d_line_home<0?'neg':''}">${sg(mv.spread.d_line_home)} pts</td></tr>`);
  if(mv.total) rows.push(`<tr><td>Total</td><td class="mono">${mv.total.open_line} <span class="sub">${am((mv.total.open_price||{}).over)}/${am((mv.total.open_price||{}).under)}</span></td><td class="mono"><b>${mv.total.cur_line}</b> <span class="sub">${am((mv.total.cur_price||{}).over)}/${am((mv.total.cur_price||{}).under)}</span></td><td class="mono ${mv.total.d_line>0?'pos':mv.total.d_line<0?'neg':''}">${sg(mv.total.d_line)} pts</td></tr>`);
  const h=mk.history||{lines:{},splits:{},n_points:0};
  // por casa: primer vs último registro propio
  const byBook=[]; const nameOf=Object.fromEntries((mk.books||[]).map(b=>[b.id,b.name]));
  const first=(arr)=>arr&&arr.length?arr[0]:null, last=(arr)=>arr&&arr.length?arr[arr.length-1]:null;
  const ids=new Set(); for(const m of ['ml','spread','total']) for(const b of Object.keys((h.lines||{})[m]||{})) ids.add(b);
  for(const id of ids){
    const cell=(m,s,fmt)=>{ const a=((h.lines[m]||{})[id]||{})[s]; if(!a||!a.length) return '<td class="mut">—</td>'; const f=a[0],l=a[a.length-1]; const same=a.length===1; return `<td class="mono">${same?fmt(l):fmt(f)+' → <b>'+fmt(l)+'</b>'}${same?'':' <span class="sub">('+a.length+')</span>'}</td>`; };
    byBook.push(`<tr><td>${esc(nameOf[id]||id)}</td>${cell('ml','home',p=>am(p[2]))}${cell('spread','home',p=>sg(p[1]))}${cell('total','over',p=>p[1])}</tr>`);
  }
  const t0=h.first_ts;
  const note = h.n_points? `Historial propio desde ${tsFmt(t0)} · ${h.n_points} registros (se guarda sólo cuando cambia algo; el servidor toma un snapshot cada ~10 min, configurable).` : `Historial propio: ${SD} (aún no hay snapshots de este juego).`;
  MV = {mk, g, tab:'ml'};
  return `<div class="card" style="margin-top:10px"><h2>📈 Movimientos de línea <span class="badge b-ok">${mk.movement_src?'APERTURA REAL':'SIN APERTURA'}</span></h2>
   ${rows.length?`<div class="tbl"><table><thead><tr><th>Mercado</th><th>Apertura</th><th>Actual</th><th>Cambio</th></tr></thead><tbody>${rows.join('')}</tbody></table></div><div class="sub" style="margin-top:4px">Apertura vs consenso actual · fuente: ${esc(mk.movement_src||'')}. El cambio de ML se mide en prob. sin vig; spread/total en puntos (positivo = el local recibe más puntos / el total sube). Las casas no publican aperturas individuales: por casa usamos nuestro propio historial.</div>`:`<div class="mut">Apertura vs actual: ${SD} (ninguna fuente gratuita publica la apertura de este juego).</div>`}
   <div class="pills" style="margin-top:12px" id="mvtabs">${[['ml','Moneyline'],['spread','Spread'],['total','Total'],['pct','% Apuestas']].map(t=>`<span class="pill ${t[0]==='ml'?'on':''}" data-t="${t[0]}" onclick="mvTab('${t[0]}')">${t[1]}</span>`).join('')}</div>
   <div id="mvchart"></div>
   ${byBook.length?`<div class="tbl" style="margin-top:8px"><div class="sub tt">Por casa · primer registro propio → actual (local / over)</div><table><thead><tr><th>Casa</th><th>ML local</th><th>Spread local</th><th>Total</th></tr></thead><tbody>${byBook.join('')}</tbody></table></div>`:''}
   <div class="sub" style="margin-top:6px">${note}</div></div>`;
}
const PAL=['#22e08a','#4da3ff','#ffc247','#ff5c6c','#a78bfa','#2dd4bf','#f472b6','#fb923c','#94a3b8','#e879f9','#84cc16'];
function mvTab(t){ if(!MV) return; MV.tab=t; document.querySelectorAll('#mvtabs .pill').forEach(p=>p.classList.toggle('on',p.dataset.t===t)); mvDraw(); }
function mvDraw(){
  const el=document.getElementById('mvchart'); if(!el||!MV) return;
  const {mk,g,tab}=MV, h=mk.history||{lines:{},splits:{}}, now=mk.now||Date.now()/1000;
  const nameOf=Object.fromEntries((mk.books||[]).map(b=>[b.id,b.name]));
  let series=[], ylab='', fmt=v=>v;
  if(tab==='pct'){
    const sp=h.splits||{}; const pick=[['ml','home'],['spread','home'],['total','over']];
    for(const [m,s] of pick){ const a=(sp[m]||{})[s]; if(!a||!a.length) continue; const nmx=m==='ml'?'ML':m==='spread'?'Spread':'Total'; const sd=s==='home'?(g.home.short||g.home.name):s==='over'?'Over':s;
      series.push({n:`${nmx} ${sd} · tickets`,pts:a.filter(p=>p[1]!=null).map(p=>[p[0],p[1]]),dash:false}); series.push({n:`${nmx} ${sd} · dinero`,pts:a.filter(p=>p[2]!=null).map(p=>[p[0],p[2]]),dash:true}); }
    ylab='% (tickets sólido · dinero punteado)'; fmt=v=>v.toFixed(0)+'%';
  } else {
    const L=(h.lines||{})[tab]||{}; const side=tab==='total'?'over':'home';
    for(const id of Object.keys(L)){ if(id==='an30') continue; /* apertura AN: no tiene hora real de captura */ const a=L[id][side]; if(!a||!a.length) continue;
      const pts=a.map(p=>[p[0], tab==='ml'?probRaw(p[2])*100:p[1]]).filter(p=>p[1]!=null);
      series.push({n:nameOf[id]||id,pts,dash:false}); }
    ylab=tab==='ml'?`Prob. implícita c/vig de ${g.home.name} (%)`:tab==='spread'?`Línea de ${g.home.name}`:'Línea del total'; fmt=v=>tab==='ml'?v.toFixed(1)+'%':(tab==='spread'?sg(v):v.toFixed(1));
  }
  series=series.filter(s=>s.pts.length);
  if(!series.length){ el.innerHTML=`<div class="mut" style="padding:10px">${SD}: aún no hay historial propio para este mercado.</div>`; return; }
  const all=series.flatMap(s=>s.pts); const x0=Math.min(...all.map(p=>p[0])), x1=Math.max(now,...all.map(p=>p[0]));
  let y0=Math.min(...all.map(p=>p[1])), y1=Math.max(...all.map(p=>p[1])); if(y1-y0<(tab==='ml'||tab==='pct'?2:0.5)){ const c=(y0+y1)/2, w=(tab==='ml'||tab==='pct'?1:0.5); y0=c-w; y1=c+w; } const pad=(y1-y0)*.12; y0-=pad; y1+=pad;
  const W=720,H=250,L=52,R=10,T=10,B=28; const X=x=>L+(x1===x0?0:(x-x0)/(x1-x0))*(W-L-R), Y=y=>T+(1-(y-y0)/(y1-y0))*(H-T-B);
  let svg=`<svg viewBox="0 0 ${W} ${H}" class="chart" role="img" aria-label="Historial de líneas">`;
  for(let i=0;i<=4;i++){ const y=y0+(y1-y0)*i/4; svg+=`<line x1="${L}" x2="${W-R}" y1="${Y(y)}" y2="${Y(y)}" stroke="#1f2b3d"/><text x="${L-6}" y="${Y(y)+4}" text-anchor="end" fill="#7d8ba1" font-size="10">${fmt(y)}</text>`; }
  const tl=t=>new Intl.DateTimeFormat('es-MX',{timeZone:TZ,day:'numeric',month:'short',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(t*1000));
  svg+=`<text x="${L}" y="${H-8}" fill="#7d8ba1" font-size="10">${tl(x0)}</text><text x="${W-R}" y="${H-8}" text-anchor="end" fill="#7d8ba1" font-size="10">${tl(x1)} (CDMX)</text>`;
  series.forEach((s,i)=>{ const c=PAL[i%PAL.length]; let d=''; const pts=s.pts.slice(); const lastp=pts[pts.length-1]; const ext=pts.concat([[x1,lastp[1]]]);
    ext.forEach((p,j)=>{ d+=(j?`H${X(p[0]).toFixed(1)}V${Y(p[1]).toFixed(1)}`:`M${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`); });
    svg+=`<path d="${d}" fill="none" stroke="${c}" stroke-width="1.8" ${s.dash?'stroke-dasharray="5 4"':''} opacity=".9"/>`;
    pts.forEach(p=>{ svg+=`<circle cx="${X(p[0]).toFixed(1)}" cy="${Y(p[1]).toFixed(1)}" r="3" fill="${c}"><title>${esc(s.n)}: ${fmt(p[1])} · ${tl(p[0])}</title></circle>`; }); });
  svg+='</svg>';
  const npts=Math.max(...series.map(s=>s.pts.length));
  el.innerHTML=`<div class="sub tt">${esc(ylab)}</div>${svg}<div class="legend2">${series.map((s,i)=>`<span><i style="background:${PAL[i%PAL.length]}"></i>${esc(s.n)}</span>`).join('')}</div>${npts<2?`<div class="sub">Sólo hay ${npts} registro por serie: el gráfico se irá llenando con cada snapshot; la línea se extiende hasta “ahora”.</div>`:''}`;
}

// ------------------------------------------------------------ info
function viewInfo(){
  $app.innerHTML=`<h1>ℹ️ Metodología y fuentes</h1>
  <div class="card kv"><h2>Fuentes (públicas, sin llave)</h2><ul class="t"><li>ESPN site API: marcadores, resúmenes, calendarios y resultados, lesiones, líderes, tablas, rankings de tenis y cuotas de DraftKings (cuando existen).</li><li><b>Action Network</b> (API pública sin llave): cuotas de DraftKings, FanDuel, BetMGM, Caesars, BetRivers, bet365, Fanatics y Unibet, consenso, apertura y <b>% tickets / % dinero</b>. Cubre NBA, NFL, NHL, MLB, NCAA y fútbol de las grandes ligas; no cubre Liga MX ni tenis.</li><li><b>Pinnacle</b> (API de invitado, línea “sharp”): cuotas de todos los deportes incluidos Liga MX y tenis, sin % apuestas.</li><li><b>Historial propio</b>: el servidor guarda en SQLite un snapshot de líneas y % cada ~10 min (sólo cuando algo cambia) para construir nuestra propia curva de movimiento.</li><li>MLB StatsAPI: lanzadores abridores probables y sus estadísticas.</li><li>Todo se cachea (marcadores 90 s, resúmenes 150 s, calendarios 1 h). Si un dato no existe se muestra <b>${SD}</b>; nunca se inventa.</li></ul></div>
  <div class="card kv" style="margin-top:10px"><h2>Modelo (transparente y simple)</h2><ul class="t">
  <li><b>NFL / NBA / NHL / MLB:</b> rating SRS (margen promedio ajustado por rival y localía) calculado con todos los resultados reales de la liga, suavizado hacia 0 según juegos jugados, + ajuste por forma (últimos 5). Probabilidad = normal(margen esperado, σ). En MLB se añade un ajuste pequeño por ERA de abridores probables.</li>
  <li><b>Fútbol:</b> Poisson con fuerza de ataque/defensa suavizada y ventaja de local de la liga → 1X2, hándicap y totales.</li>
  <li><b>Tenis:</b> logística sobre ln(puntos de ranking). Sin cuotas gratuitas ⇒ sin edge.</li>
  <li><b>Prob. final</b> = mezcla del modelo y el mercado sin vig; el peso del modelo (máx. 50%) crece con la muestra. El modelo se recorta a ±20 pp del mercado.</li>
  <li><b>Edge</b> = prob. final − prob. implícita sin vig (pp). <b>EV</b> = prob. final × momio decimal − 1. <b>Línea justa</b> = momio de la prob. final. <b>Precio máx.</b> = momio con EV = +2%.</li>
  <li><b>Estados:</b> 🔥 PICK (edge ≥ 3 pp, EV ≥ 0 y confianza Media/Alta) · 🟡 LEAN (edge ≥ 1 pp) · ⛔ PASS (sin edge; igual se muestra el lean) · 🔍 SIN LÍNEA (no hay precio).</li>
  <li><b>Casas y consenso:</b> mejor precio = el momio más alto en la misma línea; consenso s/vig = promedio de las probabilidades sin vig de las casas en la línea de referencia.</li>
  <li><b>RLM:</b> lado público (≥55% de tickets) y la línea/precio se mueve en su contra entre la apertura y ahora. <b>Dinero &gt; tickets:</b> % dinero − % tickets ≥ 10 pp. Se muestran junto al pick como etiquetas (a favor / en contra / mixto) <b>sin cambiar la probabilidad del modelo</b>: son indicadores, no garantías. Sin % de apuestas ⇒ “Sin dato”.</li>
  <li><b>Confianza:</b> muestra de juegos, acuerdo con el mercado, líderes lesionados, abridores (MLB).</li></ul></div>
  <div class="note">El modelo no sabe de lesiones de último minuto, descansos, clima ni alineaciones. El mercado suele ser más informado que un modelo simple: trátalo como una segunda opinión. Sin promesas de rentabilidad.</div>`;
}
