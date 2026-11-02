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

// ------------------------------------------------------------ calificación (ganó / perdió)
const GRADE = {GANADO:['✅','Ganado','g-w'],PERDIDO:['❌','Perdido','g-l'],PUSH:['➖','Push','g-p'],PENDIENTE:['⏳','Pendiente','g-n'],
  MEDIO_GANADO:['✅','Medio ganado','g-w'],MEDIO_PERDIDO:['❌','Medio perdido','g-l'],ANULADO:['⚪','Anulado','g-v']};
const gradeBadge = (r,withScore) => { if(!r) return ''; const x=GRADE[r.status]||GRADE.PENDIENTE;
  return `<span class="gbadge ${x[2]}" title="${esc(r.note||'')}">${x[0]} ${x[1]}</span>${withScore&&r.score_text?` <span class="sub mono">${esc(r.score_text)}</span>`:''}`; };
const typeLbl = t => t==='main' ? '<span class="badge b-pick">PICK PRINCIPAL</span>' : '<span class="badge b-model">SUGERENCIA</span>';
const mktKey = c => ({ML:'ml',Spread:'spread',Total:'total'})[c.market]||c.market;
let REC_MAP = {};
const recFor = (market, side, line) => { const r = REC_MAP[market+'.'+side]; return r && (line==null || r.line==null || Number(r.line)===Number(line)) ? r : null; };   // sólo si es la MISMA línea registrada
const units = u => u==null ? '—' : (u>0?'+':'')+Number(u).toFixed(2)+'u';
const oddsTxt = r => r.odds==null ? 'sin cuota' : am(r.odds)+(r.book?' · '+esc(r.book):'');
const SPORT_EM = {mlb:'⚾',nfl:'🏈',nba:'🏀',nhl:'🏒',tenis:'🎾',futbol:'⚽'};
function setNav(n){ document.querySelectorAll('nav a').forEach(a=>{ const on=a.dataset.n===n; a.classList.toggle('on',on); if(on){ const nv=a.parentElement; nv.scrollLeft=Math.max(0,a.offsetLeft-(nv.clientWidth-a.offsetWidth)/2); } }); }

// ------------------------------------------------------------ rutas
async function route(){
  Live.stop();
  const h = location.hash.replace(/^#\/?/,'').split('/').map(decodeURIComponent);
  window.scrollTo(0,0);
  try{
    if(!h[0]||h[0]==='') { setNav('home'); return viewHome(); }
    if(h[0]==='deportes'){ setNav('sports'); return viewSports(); }
    if(h[0]==='deporte'){ setNav('sports'); return viewSport(h[1], h[2]); }
    if(h[0]==='juego'){ setNav('sports'); return viewGame(h[1], h[2]); }
    if(h[0]==='picks'){ setNav('picks'); return viewPicks(h[1]||'24h'); }
    if(h[0]==='record'){ setNav('record'); return viewRecord(); }
    if(h[0]==='info'){ setNav('info'); return viewInfo(); }
    viewHome();
  }catch(e){ $app.innerHTML = `<div class="err">⚠️ ${esc(e.message)}</div>`; }
}
window.addEventListener('hashchange', route); route();

// ------------------------------------------------------------ home
async function viewSports(){
  SPORTS = SPORTS || await api('/api/sports');
  $app.innerHTML = `<h1>Elige un deporte</h1>
  <div class="grid g3">${SPORTS.map(s=>`<a class="card sport" href="#/deporte/${s.key}"><span class="em">${s.emoji}</span>${esc(s.name)}<span class="sub">${s.leagues.map(l=>esc(l.name)).join(' · ')}</span></a>`).join('')}</div>
  <div style="height:14px"></div>
  <a class="card sport" href="#/picks" style="border-color:#1b6b4a"><span class="em">🔥</span>Top picks del día (todos los deportes)<span class="sub">Ranking de los mejores spots según el modelo vs. el mercado</span></a>
  <div class="note">Datos reales de ESPN, MLB StatsAPI y Open-Meteo (sin llaves). Si algo no está disponible se muestra <b>${SD}</b>. Todas las probabilidades son <b>estimaciones de un modelo simple</b>, no certezas.</div>`;
}

// ------------------------------------------------------------ deporte
async function viewSport(sport, league){
  SPORTS = SPORTS || await api('/api/sports');
  const sp = SPORTS.find(s=>s.key===sport); if(!sp) return viewSports();
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
    body = Object.keys(groups).sort().map(k=>`<div class="day">${esc(dayLabel(groups[k][0].date))}</div><div class="glist">${groups[k].map(gameCard).join('')}</div>`).join('');
  }
  const anyLive = d.games.some(g=>g.state==='in');
  $app.innerHTML = `<a class="back" href="#/deportes">← Deportes</a><h1>${sp.emoji} ${esc(sp.name)}</h1>${pills}<div class="updline">${updTag(d.now,anyLive)}</div>${body}`;
  if(d.ok&&d.games.some(g=>g.state==='pre')) fillBriefs(league);
  fillWx(league);
  Live.start(()=>tickSport(league), 25000);
}
// ---- auto-actualización de la lista: sólo repinta tarjetas que están en vivo / cambiaron de estado (conserva lo desplegado)
async function tickSport(league){
  const cards=[...document.querySelectorAll('[data-gid]')]; if(!cards.length) return;
  const soon=cards.some(c=>c.dataset.state==='pre'&&c.dataset.ts&&(+c.dataset.ts-Date.now())<10*60e3);
  if(!cards.some(c=>c.dataset.state==='in')&&!soon) return;
  let d; try{ d=await api('/api/games?league='+encodeURIComponent(league)); }catch(e){ return; }
  d.games.forEach(g=>{
    const el=document.querySelector(`[data-gid="${CSS.escape(g.id)}"]`); if(!el) return;
    if(g.state==='pre'&&el.dataset.state==='pre'){ GAMES[g.id]=Object.assign(GAMES[g.id]||{},{inj:g.inj}); return; }
    if(g.state==='post'&&el.dataset.state==='post') return;
    const open=[...el.querySelectorAll('.gp.open')].length>0;
    const tmp=document.createElement('div'); tmp.innerHTML=gameCard(g); const nu=tmp.firstElementChild;
    if(open) nu.querySelectorAll('.gp').forEach(x=>x.classList.add('open'));
    const wx=el.querySelector('.wxc'); if(wx&&nu.querySelector('.wxc')) nu.querySelector('.wxc').innerHTML=wx.innerHTML;
    el.replaceWith(nu);
  });
  const u=document.getElementById('upd'); if(u) u.outerHTML=updTag(d.now,d.games.some(g=>g.state==='in'));
}
async function fillWx(league){
  try{
    const r=await api('/api/league_wx?league='+encodeURIComponent(league));
    document.querySelectorAll('.wxc[data-id]').forEach(el=>{ el.innerHTML=wxChip(r.items[el.dataset.id]); });
  }catch(e){}
}
function stBadge(g){ return g.state==='in'?`<span class="badge b-live">● EN VIVO</span>`:g.state==='post'?`<span class="badge b-fin">FINAL</span>`:`<span class="badge b-pre">PROGRAMADO</span>`; }
// ---- helpers de la vista compacta
const tn = t => (t&&(t.abbr||t.short))||((t&&t.name)||'').split(' ').slice(-1)[0];
const shortLbl = (l,g) => { let x=String(l||''); [g.away,g.home].forEach(t=>{ if(t&&t.name&&t.name.length>3) x=x.split(t.name).join(tn(t)); }); return x.replace(/\s*\((visitante|local)\)/g,'').trim(); };
const MKL = {ml:'ML',spread:'SPR',total:'TOT',sspread:'HÁN',stotal:'TOT',dc:'DC',btts:'BTTS'};
const mkl = b => MKL[b.market]||String(b.title||b.market||'').slice(0,3).toUpperCase();
let GAMES = {};
const gradedBadge = x => (x&&x.status&&x.status!=='PENDIENTE') ? gradeBadge(x,false) : '';
const edgeTxt = e => e==null ? '' : `<span class="ed mono ${e>0?'pos':e<0?'neg':'mut'}">${sg(e)}pp</span>`;
function sgrRow(b,g,rec){
  const rr=rec&&rec.find(x=>x.market===b.market&&x.selection===b.side);
  return `<div class="sgr" title="${esc(b.title||'')}"><span class="mk">${esc(mkl(b))}</span><span class="lb">${esc(shortLbl(b.label,g))}${b.clipped?' <span title="Probabilidad del modelo recortada a ±20 pp del mercado">✂️</span>':''} ${gradedBadge(rr)}</span>${edgeTxt(b.edge)}
    <span class="st mono">Mod ${b.p_model!=null?pct(b.p_model,0):SD} · Mkt ${b.p_nv!=null?pct(b.p_nv,0):SD}${b.best&&b.best.price_txt?' · '+esc(b.best.price_txt):''}</span></div>`;
}
const briefRows = (items,g,rec) => (items||[]).map(b=>sgrRow(b,g,rec)).join('');
function briefBlock(g,items){
  if(!items||!items.length) return `<div class="pickline none">Probabilidades: ${SD}</div>`;
  const rec=g.rec||[], rm=rec.find(x=>x.type==='main');
  let main = rm && items.find(b=>b.market===rm.market&&b.side===rm.selection);
  let line;
  if(!main && rm){
    line=`<div class="pickline"><span class="k">PICK</span><span class="t">${esc(shortLbl(rm.label,g))}</span>${gradedBadge(rm)}</div>`;
  } else {
    if(!main) main=items.slice().sort((a,b)=>(b.edge==null?-99:b.edge)-(a.edge==null?-99:a.edge))[0];
    line=`<div class="pickline" title="${esc(main.title||'')} · ${esc(main.label)}"><span class="k">PICK</span><span class="t">${esc(shortLbl(main.label,g))}</span>${main.p_model!=null?`<span class="m mono">${pct(main.p_model,0)}</span>`:''}${main.edge!=null?`<span class="e mono ${main.edge>0?'pos':'neg'}">edge ${sg(main.edge)}pp</span>`:''}${gradedBadge(rm&&rm.market===main.market&&rm.selection===main.side?rm:null)}</div>`;
  }
  const rest=items.filter(b=>b!==main);
  if(!rest.length) return line;
  return line+`<div class="tg" role="button" tabindex="0">Sugerencias (${rest.length})</div><div class="sg">${briefRows(rest,g,rec)}</div>`;
}
function recBlock(g){
  const r=g.rec||[]; if(!r.length) return '';
  const m=r.find(x=>x.type==='main'), rest=r.filter(x=>x!==m);
  const gb=x=>x.status==='PENDIENTE'&&g.state==='in' ? (provBadge(g.prov,x.market,x.selection)||gradeBadge(x,false)) : gradeBadge(x,false);
  const row=x=>`<div class="sgr"><span class="mk">${esc(MKL[x.market]||String(x.market).slice(0,3).toUpperCase())}</span><span class="lb">${esc(shortLbl(x.label,g))}</span>${gb(x)}</div>`;
  return `<div class="gp">${m?`<div class="pickline"><span class="k">PICK</span><span class="t">${esc(shortLbl(m.label,g))}</span>${gb(m)}</div>`:''}${rest.length?`<div class="tg" role="button" tabindex="0">Sugerencias (${rest.length})</div><div class="sg">${rest.map(row).join('')}</div>`:''}</div>`;
}
function marketRow(g){
  const o=g.odds; if(!o) return g.state==='pre'?`<div class="sub" style="margin-top:8px">Cuotas: ${SD}</div>`:'';
  const c=[];
  if(o.spread&&o.spread.home) c.push(`<div class="mc"><small>Spread</small><span class="mono">${esc(tn(g.home))} ${sg(o.spread.home.line)}</span> <span class="sub mono">${am(o.spread.home.price)}</span></div>`);
  if(o.total&&o.total.over) c.push(`<div class="mc"><small>Total</small><span class="mono">O/U ${o.total.over.line}</span></div>`);
  if(o.ml&&o.ml.draw!=null) c.push(`<div class="mc"><small>Empate</small><span class="mono">${am(o.ml.draw)}</span></div>`);
  return c.length?`<div class="gm">${c.join('')}</div>`:'';
}
function gameCard(g){
  GAMES[g.id]=g;
  const sc = g.state!=='pre', o=g.odds;
  const team=(t,side)=>{ const ml=o&&o.ml?o.ml[side]:null;
    return `<div class="tm">${t.logo?`<img src="${esc(t.logo)}" loading="lazy" alt="">`:'<span style="width:22px;flex:none"></span>'}<span class="nm" title="${esc(t.name)}">${esc(t.name)}</span><span class="rc">${esc(t.record||'')}</span>${sc?`<span class="sc mono ${t.winner?'pos':''}">${esc(g.sport==='tenis'?(t.sets||[]).join(' '):(t.score??''))}</span>`:''}${ml!=null?`<span class="ml mono">${am(ml)}</span>`:''}</div>`; };
  const where=[g.note||g.league_name, g.venue].filter(Boolean).map(esc).join(' · ');
  const live=g.state==='in', chips=[injChip(g), `<span class="wxc" data-id="${esc(g.id)}"></span>`].filter(Boolean).join('');
  const tennisWd = g.wd ? `<div class="sub" style="margin-top:6px">⚠️ ${esc(g.wd)}</div>` : '';
  return `<a class="card game ${live?'is-live':''}" href="#/juego/${encodeURIComponent(g.league)}/${g.id}" data-gid="${esc(g.id)}" data-state="${g.state}" data-ts="${new Date(g.date).getTime()}">
    <div class="gh">${live?`<span class="time mono lv-clock">${esc((g.live&&g.live.text)||g.status||'')}</span>`:`<span class="time mono">${fmtTime(g.date)}</span>`}<span class="gl">${where}</span>${sc?stBadge(g):''}</div>
    ${team(g.away,'away')}${team(g.home,'home')}
    ${liveLine(g)}${tennisWd}
    ${marketRow(g)}
    ${chips?`<div class="cchips">${chips}</div>`:''}
    ${g.state==='pre'?`<div class="gp" data-id="${esc(g.id)}"><span class="sub">⏳ Probabilidades…</span></div>`:recBlock(g)}</a>`;
}

// ------------------------------------------------------------ juego
async function viewGame(league, id, silent){
  if(!silent) loading('Analizando partido con datos reales…');
  const d = await api(`/api/game/${encodeURIComponent(league)}/${id}`);
  const g = d.game;
  const back = `<a class="back" href="#/deporte/${g.sport}/${encodeURIComponent(league)}">← ${esc(g.league_name)}</a>`;
  const live = g.state==='in';
  const stTxt = g.state!=='pre' && d.live && d.live.text ? ` · <b class="${live?'lv-clock':''}">${esc(d.live.text)}</b>` : '';
  const hero = `<div class="card"><div class="sub" style="text-align:center">${esc(g.league_name)} · ${esc(fmtDay(g.date))} · <b>${fmtTime(g.date)}</b> CDMX ${stBadge(g)}${stTxt}${g.neutral&&d.kind!=='tennis'?' · cancha neutral':''}</div>
    <div class="hero" style="margin-top:10px">
      <div>${g.away.logo?`<img src="${esc(g.away.logo)}" alt="">`:''}<div class="n">${esc(g.away.name)}</div><div class="sub">${esc(g.away.record||'')}${d.kind==='tennis'&&g.away.rank?` · #${g.away.rank} ranking · ${g.away.points} pts`:''}</div>${g.state!=='pre'?`<div class="big mono" style="font-size:26px">${esc(d.kind==='tennis'?(g.away.sets||[]).join(' '):(g.away.score??''))}</div>`:''}</div>
      <div class="vs">${d.kind==='tennis'?'VS':'@'}</div>
      <div>${g.home.logo?`<img src="${esc(g.home.logo)}" alt="">`:''}<div class="n">${esc(g.home.name)}</div><div class="sub">${esc(g.home.record||'')}${d.kind==='tennis'&&g.home.rank?` · #${g.home.rank} ranking · ${g.home.points} pts`:''}</div>${g.state!=='pre'?`<div class="big mono" style="font-size:26px">${esc(d.kind==='tennis'?(g.home.sets||[]).join(' '):(g.home.score??''))}</div>`:''}</div>
    </div>
    <div class="sub" style="text-align:center;margin-top:8px">${esc(g.venue||'')}${g.court?' · '+esc(g.court):''}${g.note?' · '+esc(g.note):''}${g.weather&&!d.weather?` · 🌡️ ${g.weather.temp_f}°F`:''}</div>
    ${g.wd?`<div class="sub" style="text-align:center;margin-top:4px">⚠️ ${esc(g.wd)}</div>`:''}
    ${restTags(d)?`<div style="text-align:center;margin-top:8px">${restTags(d)}</div>`:''}
    <div style="text-align:center;margin-top:8px">${updTag(d.updated,live)}</div></div>`;
  REC_MAP = {}; (d.record||[]).forEach(r=>{ REC_MAP[r.market+'.'+r.selection]=r; }); PROV = d.prov||{};
  let html = back + hero;
  html += liveSection(d) + recordCard(d) + picksSection(d) + probSection(d);
  html += marketSection(d) + splitsSection(d) + rlmSection(d) + movementSection(d);
  if(d.odds && d.odds.src==='espn') html += oddsSection(d);
  if(d.kind==='tennis') html += tennisSections(d); else html += teamSections(d);
  if(d.gaps && d.gaps.length) html += `<div class="note gap"><b>🕳️ Datos no disponibles (${SD}):</b><ul class="t">${d.gaps.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div>`;
  html += `<div class="note">⚖️ <b>Estimación del modelo, no certeza.</b> Sin promesas de rentabilidad. Revisa lesiones/alineaciones de último minuto antes de apostar.</div>`;
  // conserva scroll y tarjetas plegadas/abiertas al refrescar en vivo
  const st = silent ? {y:window.scrollY, open:[...document.querySelectorAll('#app > .fold')].map(c=>[c.querySelector(':scope > h2').textContent.trim().slice(0,24), !c.classList.contains('closed')]), tg:[...document.querySelectorAll('#app .gp.open, #app .open')].length} : null;
  $app.innerHTML = html;
  mvDraw(); foldCards();
  if(st){ const m=new Map(st.open); document.querySelectorAll('#app > .fold').forEach(c=>{ const k=c.querySelector(':scope > h2').textContent.trim().slice(0,24); if(m.has(k)) c.classList.toggle('closed',!m.get(k)); }); window.scrollTo(0,st.y); }
  Live.start(async()=>{ if(!location.hash.startsWith('#/juego/')) return; try{ await viewGame(league,id,true); }catch(e){} }, 25000);
  if(!live) Live.stop();
  return d;
}
let PROV = {};

function candRow(c){
  const e = c.edge;
  const rr = recFor(mktKey(c), c.side, c.line);
  return `<div class="cand"><div>${esc(c.label)} ${badgeSt(c.status)}${rr?' '+gradeBadge(rr,false):''}${c.clipped?' <span class="sub" title="Probabilidad del modelo recortada a ±20 pp del mercado">✂️</span>':''}</div>
  <div class="mono" data-l="Precio">${esc(c.price_txt||SD)}</div>
  <div class="mono" data-l="Modelo">${pct(c.p_model)}</div>
  <div class="mono" data-l="Mercado s/vig">${pct(c.p_nv)}</div>
  <div class="mono ${e>0?'pos':e<0?'neg':''}" data-l="Edge">${e==null?SD:sg(e)+' pp'}</div>
  <div class="mono" data-l="Línea justa">${esc(c.fair_txt||SD)}</div>
  <div class="mono" data-l="Precio máx.">${esc(c.max_txt||SD)}</div>${c.signals&&c.signals.verdict&&c.signals.verdict!=='sin_dato'?`<div class="ctags">${tagChips(c.signals)||'<span class="sub">Mercado: sin señal clara</span>'}${c.signals.best?`<span class="sub">🏷️ Mejor precio ${esc(c.signals.best.price_txt)} en ${esc(c.signals.best.book)}${c.signals.best.ev!=null?' · EV '+sg(c.signals.best.ev)+'%':''}</span>`:''}</div>`:''}</div>`;
}
function leanBlock(d){
  const p=d.picks, l=p.lean, c=p.confidence, st=STATUS[p.status];
  const gb = gradeBadge(recFor(mktKey(l),l.side,l.line),true)||'<span class="gbadge g-n">⏳ Pendiente</span>';
  const cell=(k,v,cls='')=>`<div><small>${k}</small><b class="mono ${cls}">${v}</b></div>`;
  let head, cells, note;
  if(l.price_txt){
    head=`${st[0]} ${st[1]} · ${esc(l.label)} <span class="mono">(${esc(l.price_txt)})</span> ${gb}`;
    cells=[cell('Modelo',pct(l.p_model)),cell('Mercado s/vig',pct(l.p_nv)),cell('Con vig',pct(l.implied_raw)),cell('Prob. final',pct(l.p_final)),
      cell('Edge',sg(l.edge)+' pp',l.edge>0?'pos':'neg'),cell('EV',sg(l.ev)+'%',l.ev>0?'pos':'neg'),cell('Línea justa',esc(l.fair_txt)),cell('Precio máx.',esc(l.max_txt))];
    note='Prob. final = mezcla modelo/mercado. Precio máximo = el que deja EV ≥ +2% sobre la prob. final.';
  } else {
    head=`${st[0]} ${st[1]} · Lean del modelo: ${esc(l.label)} ${gb}`;
    cells=[cell('Modelo',pct(l.p_model)),cell('Edge',SD),cell('Línea justa',esc(l.fair_txt)),cell('Precio máx.',esc(l.max_txt))];
    note='Sin precio de mercado: sólo valdría la pena apostar a ese momio o mejor.';
  }
  const lines=[`<div class="lh">${head}</div><div class="stats">${cells.join('')}</div><div class="sub">${note}</div>`];
  lines.push(`<div style="margin-top:8px">🧠 ${confBadge(c)} ${c.reasons&&c.reasons.length?`<span class="sub">${esc(c.reasons.join(' · '))}</span>`:''}</div>`);
  if(l.downgraded) lines.push(`<div class="sub">⬇️ Era PICK pero se degradó a LEAN por confianza baja.</div>`);
  if(p.status==='PASS') lines.push(`<div class="sub">Sin ventaja suficiente en ningún mercado; este es el lean menos malo, no una recomendación fuerte.</div>`);
  return `<div class="lean">${lines.join('')}</div>${sigLine(l.signals)}`;
}
function picksSection(d){
  if(!d.picks) return `<div class="card" style="margin-top:10px"><h2>🎯 Mejores picks</h2><div class="mut">${d.game.state!=='pre'?'El juego ya empezó o terminó: los picks pre-juego no aplican.':`Sin modelo para este juego (${SD}).`}</div></div>`;
  const cs = d.picks.candidates||[];
  return `<div class="card hot" style="margin-top:10px"><h2>🎯 Mejores picks <span class="badge b-model">ESTIMACIÓN DEL MODELO</span></h2>${leanBlock(d)}
  ${cs.length?`<details class="cands" ${matchMedia('(min-width:641px)').matches?'open':''} style="margin-top:8px"><summary>Todas las selecciones (${cs.length})</summary><div class="cand h"><div>Selección</div><div>Precio</div><div>Modelo</div><div>Mercado s/vig</div><div>Edge</div><div>Línea justa</div><div>Precio máx.</div></div>${cs.map(candRow).join('')}</details>`:''}
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
   ${restRows(d)}
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
  // lesiones (detalle nuevo: extras.js), alineaciones y clima
  html += lineupsSection(d) + injSection(d) + weatherSection(d);
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
  const extra=injSection(d);
  const g=d.game, A=g.away, H=g.home; // en tenis: home=jugador 1 (orden ESPN), away=jugador 2
  const P=[H,A]; const m=d.model;
  const fm=(p,list)=>`<div><b>${esc(p.name)}</b> <span class="sub">${p.rank?`#${p.rank} · ${p.points} pts`:'Ranking: '+SD}${p.country?` · ${esc(p.country)}`:''}</span><div class="form">${(list||[]).slice(0,10).map(r=>`<span class="f f-${r.res}">${r.res==='W'?'G':'P'}</span>`).join('')||SD}</div>
    <div class="tbl"><table><tbody>${(list||[]).slice(0,6).map(r=>`<tr><td>${fmtShort(r.date)} vs ${esc(r.opp)} <span class="sub">${esc(r.round||'')}</span></td><td class="mono ${r.res==='W'?'pos':'neg'}">${r.res==='W'?'G':'P'} ${esc(r.score)}</td></tr>`).join('')||`<tr><td>${SD}</td></tr>`}</tbody></table></div></div>`;
  return `<div class="card" style="margin-top:10px"><h2>🎾 Jugadores y forma reciente</h2><div class="two">${fm(H,d.form.home)}${fm(A,d.form.away)}</div>
   <div class="sub" style="margin-top:6px">Forma = partidos de singles terminados en los torneos en curso/recientes que publica ESPN (muestra limitada). Superficie, H2H y lesiones: ${SD}.</div></div>
   ${extra}
   ${m?`<div class="card" style="margin-top:10px"><h2>🧠 Detalle del modelo</h2><div class="row"><span>Prob. de victoria (heurística de ranking)</span><span class="mono">${esc(H.short)} ${pct(m.p_home)} · ${esc(A.short)} ${pct(m.p_away)}</span></div><div class="sub">${esc(m.label)}. No hay cuotas gratuitas en ESPN para tenis, así que no hay edge: sólo línea justa y el precio máximo sugerido.</div></div>`:''}`;
}

function recordCard(d){
  const rows=d.record||[]; const g=d.game;
  if(!rows.length) return g.state!=='pre' ? `<div class="card" style="margin-top:10px"><h2>🧾 Picks registrados</h2><div class="mut">No se registró ningún pick para este juego antes de que empezara (el historial empieza cuando el servidor lo vio pre-juego). Nunca se reconstruye después.</div></div>` : '';
  const fin = rows.find(r=>r.score_text);
  const items = rows.map(r=>`<div class="rrow"><div>${typeLbl(r.type)} <b>${esc(r.label)}</b>${r.basis==='mercado'?' <span class="sub" title="Sin probabilidad del modelo para este mercado: se eligió el lado con mayor probabilidad de mercado">(sólo mercado)</span>':''}
     <div class="sub mono">Cuota registrada ${oddsTxt(r)}${r.line!=null?' · línea '+(/spread$/.test(r.market)?sg(r.line):r.line):''}${r.p_model!=null?' · modelo '+pct(r.p_model,0):''}</div>
     ${r.note?`<div class="sub">ℹ️ ${esc(r.note)}</div>`:''}</div>
     <div class="rr">${r.status==='PENDIENTE'&&g.state==='in'?(provBadge(PROV,r.market,r.selection)||gradeBadge(r,false)):gradeBadge(r,false)}${r.units!=null?`<div class="mono ${r.units>0?'pos':r.units<0?'neg':'mut'}">${units(r.units)}</div>`:''}</div></div>`).join('');
  return `<div class="card hot" style="margin-top:10px"><h2>🧾 Picks registrados · ¿se ganaron? ${fin?'<span class="badge b-fin">FINAL</span>':g.state==='in'?'<span class="badge b-live">● EN VIVO</span>':'<span class="badge b-pre">PRE-JUEGO</span>'}</h2>
    ${fin?`<div class="mono" style="margin-bottom:8px">Marcador final: <b>${esc(fin.score_text)}</b></div>`:''}${items}
    <div class="sub" style="margin-top:8px">Línea y cuota = las primeras registradas (no se actualizan). Se califican solos con el marcador final de ESPN (cada ~10 min); mientras no haya final confirmado, quedan ⏳ Pendiente. Unidades a 1u plano.</div></div>`;
}

// ------------------------------------------------------------ récord / historial
let RECF = {sport:'', type:'', basis:'', days:''};
async function viewRecord(){
  SPORTS = SPORTS || await api('/api/sports');
  loading('Cargando récord…');
  const q = Object.entries(RECF).filter(([k,v])=>v).map(([k,v])=>k+'='+encodeURIComponent(v)).join('&');
  const d = await api('/api/record?limit=80'+(q?'&'+q:''));
  const S=d.summary;
  const pills=(key,opts)=>`<div class="pills">${opts.map(([v,l])=>`<span class="pill ${RECF[key]===v?'on':''}" onclick="setRecF('${key}','${v}')">${l}</span>`).join('')}</div>`;
  const f=n=>Number.isInteger(n)?n:n.toFixed(1);
  const since = S.since ? tsFmt(S.since) : SD;
  const kpi=(l,v,c='')=>`<div class="kpi"><div class="sub">${l}</div><div class="v mono ${c}">${v}</div></div>`;
  let html=`<h1>📒 Historial / Récord</h1>
   <div class="sub" style="margin-bottom:8px">¿Se ganaron el pick principal y las sugerencias? Se registran al generarse (antes del juego) y se califican con el marcador final real. Historial desde <b>${since}</b> (no hay datos anteriores: nunca se reconstruyen picks de juegos pasados).</div>
   ${S.backfilled?`<div class="card" style="border-color:var(--amb);margin-bottom:8px">⚠️ Incluye <b>${S.backfilled}</b> picks que NO son del modelo en vivo (source ≠ live: demostración/retroactivos). Los picks reales sólo se registran antes del juego.</div>`:''}
   ${pills('sport',[['','Todos'],...SPORTS.map(s=>[s.key,s.emoji+' '+s.name])])}
   ${pills('type',[['','Principal + sugerencias'],['main','Sólo pick principal'],['suggestion','Sólo sugerencias']])}
   ${pills('basis',[['','Toda base'],['modelo','Con modelo'],['mercado','Sólo mercado']])}
   ${pills('days',[['','Todo'],['7','7 días'],['30','30 días']])}
   <div class="kpis">${kpi('Récord G-P-E',`${f(S.W)}-${f(S.L)}-${f(S.P)}`)}${kpi('% acierto',S.win_pct==null?SD:S.win_pct.toFixed(1)+'%',S.win_pct>=52.4?'pos':'')}
    ${kpi('Unidades (1u plano)',S.n_priced?units(S.units):SD,S.units>0?'pos':S.units<0?'neg':'')}${kpi('ROI',S.roi==null?SD:sg(S.roi)+'%',S.roi>0?'pos':S.roi<0?'neg':'')}
    </div><div class="kpis s">${kpi('Calificados',S.graded)}${kpi('⏳ Pendientes',S.pending)}${kpi('⚪ Anulados',S.void)}</div>
   <div class="sub">G = ganado · P = perdido · E = push (devolución). % acierto = G/(G+P) sin pushes. Medio ganado/perdido (líneas de cuarto) cuenta 0.5 en G o P y 0.5 en E. Unidades = ganancia/pérdida de apostar 1u a la cuota registrada${S.n_unpriced?` (${S.n_unpriced} calificados sin cuota registrada no entran en unidades/ROI)`:''}.
   <button class="btn" onclick="gradeNow(this)">🔄 Calificar ahora</button> <span class="sub">Automático cada ${d.grading.every_min} min${d.grading.last?' · última '+tsFmt(d.grading.last):''}</span></div>`;
  if(!d.recent.length) html+=`<div class="card mut" style="margin-top:10px">Aún no hay picks calificados con esos filtros. ${S.pending?`Hay <b>${S.pending}</b> picks registrados esperando el final de sus juegos.`:'Cuando el servidor genere picks y sus juegos terminen, aparecerán aquí.'}</div>`;
  else html+=`<div class="day">Últimos picks calificados</div><div class="rec-list">`+d.recent.map(r=>`<div class="rec-r"><div class="rl"><span class="mono sub">${fmtShort(new Date(r.start_ts*1000).toISOString())} · ${SPORT_EM[r.sport]||''} ${esc(r.league.toUpperCase())}</span> ${typeLbl(r.type)}${r.basis==='mercado'?' <span class="sub">(sólo mercado)</span>':''}
     <div><b>${esc(r.label)}</b> <span class="mono sub">${oddsTxt(r)}</span></div><div class="sub mono">${esc(r.score_text||'')}</div>${r.note?`<div class="sub">ℹ️ ${esc(r.note)}</div>`:''}</div>
     <div class="rr">${r.status==='PENDIENTE'&&g.state==='in'?(provBadge(PROV,r.market,r.selection)||gradeBadge(r,false)):gradeBadge(r,false)}<div class="mono ${r.units>0?'pos':r.units<0?'neg':'mut'}">${units(r.units)}</div></div></div>`).join('')+`</div>`;
  $app.innerHTML=html;
}
function setRecF(k,v){ RECF[k]=v; viewRecord(); }
async function gradeNow(btn){ btn.disabled=true; btn.textContent='Calificando…'; try{ await fetch('/api/grade',{method:'POST'}); }catch(e){} viewRecord(); }

// ------------------------------------------------------------ picks del día
async function viewPicks(scope){
  loading('Calculando picks de todos los deportes (primera vez puede tardar ~20 s)…');
  const d = await api('/api/picks?scope='+scope);
  const tabs=[['24h','Próx. 24 h'],['hoy','Hoy'],['manana','Mañana'],['72h','72 h']];
  const t=`<div class="pills">${tabs.map(([k,l])=>`<a class="pill ${k===scope?'on':''}" href="#/picks/${k}">${l}</a>`).join('')}</div>`;
  const withOdds=d.items.filter(r=>r.has_odds&&r.status!=='PASS'), pass=d.items.filter(r=>r.has_odds&&r.status==='PASS'), noodds=d.items.filter(r=>!r.has_odds);
  const card=r=>{ const l=r.lean, g=r.game, st=STATUS[r.status];
    const sg_=l.signals&&l.signals.verdict&&l.signals.verdict!=='sin_dato';
    const sigH=sg_?`<div class="sub" style="margin:8px 0 4px">${(VERD[l.signals.verdict]||[])[0]||''} ${(VERD[l.signals.verdict]||[])[1]||''}${l.signals.tickets!=null?` · ${l.signals.tickets}% tickets / ${l.signals.money!=null?l.signals.money+'% dinero':'dinero '+SD}`:''}${l.signals.best?` · mejor ${esc(l.signals.best.price_txt)} en ${esc(l.signals.best.book)}`:''}</div>${tagChips(l.signals)}`:'';
    const nb=(r.brief||[]).length;
    const det=(sg_||nb)?`<div class="gp"><div class="tg" role="button" tabindex="0">Señales y mercados${nb?` (${nb})`:''}</div><div class="sg">${sigH}${nb?briefRows(r.brief,g,[]):''}</div></div>`:'';
    return `<a class="card pk" href="#/juego/${encodeURIComponent(g.league)}/${g.id}"><div class="pk1"><div class="pkt">${st[0]} ${esc(l.label)} <span class="mono">${l.price_txt?'('+esc(l.price_txt)+')':''}</span></div>
    <div class="pke mono ${l.edge>0?'pos':'mut'}">${l.edge==null?SD:sg(l.edge)+'pp'}<small>edge</small></div></div>
    <div class="meta">${badgeSt(r.status)} ${confBadge(r.confidence)}<span class="sub">${esc(g.league_name)} · ${esc(g.away.name)} @ ${esc(g.home.name)} · ${fmtShort(g.date)} ${fmtTime(g.date)} CDMX</span></div>
    <div class="stat mono">Modelo ${pct(l.p_model)} · s/vig ${pct(l.p_nv)} · Justa ${esc(l.fair_txt||SD)} · Máx. ${esc(l.max_txt||SD)}</div>${det}</a>`; };
  let html=`<h1>🔥 Top picks · todos los deportes</h1>${t}<div class="sub" style="margin-bottom:8px">Ventana: ${d.n_games} juegos próximos analizados · ordenados por estado, edge y confianza. <b>Estimaciones del modelo</b>, no garantías.</div>`;
  if(!d.items.length) html+=`<div class="card mut">No hay juegos pre-juego en esta ventana. Prueba otra pestaña.</div>`;
  if(withOdds.length) html+=`<div class="day">Con ventaja (PICK / LEAN)</div>`+withOdds.slice(0,40).map(card).join('');
  if(pass.length) html+=`<div class="day">⛔ PASS · sin ventaja (se muestra el lean)</div>`+pass.slice(0,15).map(card).join('');
  if(noodds.length) html+=`<div class="day">🔍 Sin línea de mercado (sólo lean del modelo, sin edge)</div>`+noodds.slice(0,20).map(card).join('');
  $app.innerHTML=html;
}



// ------------------------------------------------------------ probabilidades de todos los resultados
function probSection(d){
  const P=d.probs, g=d.game;
  if(!P||!P.markets||!P.markets.length) return d.game.state==='pre' ? `<div class="card" style="margin-top:10px"><h2>🎲 Probabilidades</h2><div class="mut">${SD}: no hay modelo ni línea de mercado para este juego.</div></div>` : '';
  const cell=(v,cls='')=>v==null?`<span class="mut">${SD}</span>`:`<span class="mono ${cls}">${pct(v)}</span>`;
  const tbl=m=>{
    const rows=m.outcomes.map(o=>{
      const e=o.edge, hi=e!=null&&e>=3;
      const pinTxt = o.p_pin==null ? `<span class="mut">${SD}</span>` : `<span class="mono">${pct(o.p_pin)}</span>${o.pin_line!=null&&o.line!=null&&o.pin_line!==o.line?` <span class="sub" title="Pinnacle ofrece otra línea; no es comparable directamente">(línea ${m.key==='total'?o.pin_line:sg(o.pin_line)})</span>`:''}`;
      const consTxt = o.p_nv==null ? `<span class="mut">${SD}</span>` : (o.nv_src&&o.nv_src.startsWith('Pinnacle') ? `<span class="sub">= Pinnacle</span>` : `<span class="mono">${pct(o.p_nv)}</span> <span class="sub">${esc(am(o.fair_nv_txt?parseInt(o.fair_nv_txt):null))}</span>`);
      const mod = o.p_model_raw==null ? `<span class="mut" title="${esc(o.model_note||'Modelo: Sin dato')}">Modelo: ${SD}</span>` : `<span class="mono"><b>${pct(o.p_model)}</b></span>${o.clipped?' <span title="Recortada a ±20 pp del mercado">✂️</span>':''}${o.p_push?` <span class="sub" title="Probabilidad aprox. de push (devolución); excluida del cálculo">push ${(o.p_push*100).toFixed(0)}%</span>`:''}`;
      const rr=recFor(o.market,o.side,o.line);
      return `<tr class="${hi?'hi':''}"><td class="lb"><b>${esc(o.label)}</b>${rr?' '+gradeBadge(rr,false)+' <span class="sub">'+(rr.type==='main'?'principal':'sugerencia')+'</span>':''}${o.model_note&&o.p_model_raw==null&&m.key!=='dc'?`<div class="sub">${esc(o.model_note)}</div>`:''}</td>
       <td data-l="Modelo">${mod}</td><td data-l="Mercado s/vig">${consTxt}</td><td data-l="Pinnacle">${pinTxt}</td>
       <td class="mono" data-l="Prob. final">${o.p_final==null?`<span class="mut">${SD}</span>`:pct(o.p_final)}</td>
       <td class="mono" data-l="Línea justa">${o.fair_txt?esc(o.fair_txt):`<span class="mut">${SD}</span>`}</td>
       <td class="mono" data-l="Mejor precio">${o.best?`<b>${esc(o.best.price_txt)}</b> <span class="sub">${esc(o.best.book||'')}${o.best.n_books>1?' · '+o.best.n_books+' casas':''}</span>`:`<span class="mut">${m.derived?'sin precio directo':SD}</span>`}</td>
       <td class="mono ${e>0?'pos':e<0?'neg':''}" data-l="Edge">${e==null?`<span class="mut">${SD}</span>`:sg(e)+' pp'}</td></tr>`;
    }).join('');
    const src=[...new Set(m.outcomes.map(o=>o.nv_src).filter(Boolean))].join(' · ');
    return `<div class="tbl"><div class="sub tt">${esc(m.title)}${m.outcomes[0]&&m.outcomes[0].line!=null&&m.key!=='ml'?` · línea actual ${/spread$/.test(m.key)?sg(m.outcomes[0].line):m.outcomes[0].line}${m.unit?' '+m.unit:''}`:''}${m.derived?' · derivado del 1X2':''}${src?` · mercado: ${esc(src)}`:''}</div>
      <table class="prob"><thead><tr><th>Resultado</th><th>Modelo</th><th>Mercado s/vig</th><th>Pinnacle s/vig</th><th title="Probabilidad final = mezcla modelo/mercado">Prob. final</th><th>Línea justa</th><th>Mejor precio</th><th>Edge</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  };
  return `<div class="card" style="margin-top:10px"><h2>🎲 Probabilidades <span class="badge b-model">ESTIMACIÓN DEL MODELO</span></h2>
   ${P.markets.map(tbl).join('')}
   <div class="legend"><b>Modelo</b> = probabilidad del modelo (estimación). <b>Mercado s/vig</b> = consenso de casas sin comisión (a la derecha, su momio justo). <b>Pinnacle s/vig</b> = referencia sharp; si su línea es distinta se indica. <b>Prob. final</b> = mezcla modelo/mercado${P.w_model!=null?` (${Math.round(P.w_model*100)}% modelo)`:''}; <b>Línea justa</b> sale de ella. <b>Edge</b> = prob. final − mercado s/vig (pp). <b>Mejor precio</b> = el momio más alto a esa misma línea entre las casas disponibles. Filas con edge ≥ +3 pp resaltadas.</div>
   ${(P.notes||[]).map(n=>`<div class="sub" style="margin-top:4px">ℹ️ ${esc(n)}</div>`).join('')}
   ${g.neutral&&d.kind!=='tennis'?`<div class="sub" style="margin-top:4px">Cancha neutral: “local” es sólo la designación del calendario; el modelo no aplica ventaja de local.</div>`:''}
   <div class="note" style="margin-bottom:0">Son estimaciones de un modelo simple, no certezas ni recomendaciones de apuesta.</div></div>`;
}
const briefChips = (items,g) => !items||!items.length ? `<span class="sub">Probabilidades: ${SD}</span>` : briefRows(items,g||{away:{},home:{}},[]);
async function fillBriefs(league){
  try{
    const r=await api('/api/league_brief?league='+encodeURIComponent(league));
    document.querySelectorAll('.gp[data-id]').forEach(el=>{ const it=r.items[el.dataset.id]; el.innerHTML = it===undefined ? '' : briefBlock(GAMES[el.dataset.id]||{away:{},home:{}},it); });
  }catch(e){ document.querySelectorAll('.gp[data-id]').forEach(el=>el.innerHTML=`<span class="sub">Probabilidades: ${SD}</span>`); }
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
    const nvr=(lbl,o,cls)=>o?`<tr class="nv ${cls}"><td>${lbl} <span class="sub">(${o.n?o.n+' casas':'1 casa'}${o.line!=null?' · línea '+(/spread$/.test(key)?sg(o.line):o.line):''})</span></td>${sides.map(s=>`<td class="mono">${o[s]!=null?`<b>${pct(o[s])}</b> <span class="sub">${am(fairAm(o[s]))}</span>`:SD}</td>`).join('')}</tr>`:'';
    nvrow=nvr('Consenso s/vig',cn,'cons')+nvr('Pinnacle s/vig',sn,'sharp');
    return `<div class="tbl"><div class="sub tt">${title}</div><table class="cmp"><thead>${head}</thead><tbody>${rows}${nvrow}</tbody></table></div>`;
  };
  const sideCell=(key,s)=>b=>b[key]&&b[key][s]!=null?am(b[key][s]):'<span class="mut">—</span>';
  const lp=(key)=>(b,s)=>{const c=(b[key]||{})[s]; return c?`${/spread$/.test(key)?sg(c.line):(s==='over'?'O ':'U ')+c.line} <span class="${c.price>0?'pos':''}">${am(c.price)}</span>`:'<span class="mut">—</span>'};
  const mlSides = books.some(b=>b.ml&&b.ml.draw!=null)?['away','draw','home']:['away','home'];
  const ts=(mk.sources||[]).map(s=>`${esc(s.name)} (${s.n_books} ${s.n_books===1?'casa':'casas'}) · ${tsFmt(s.ts)}`).join(' · ');
  const nreal=books.filter(b=>b.kind==='book'||b.kind==='sharp').length;
  return `<div class="card" style="margin-top:10px"><h2>📚 Comparador de casas <span class="badge b-ok">${nreal} CASAS</span></h2>
   ${tbl('Moneyline','ml',mlSides,(b,s)=>sideCell('ml',s)(b))}
   ${tbl(d.game.sport==='mlb'?'Run line':d.game.sport==='futbol'?'Hándicap':d.game.sport==='tenis'?'Hándicap de juegos':d.game.sport==='nhl'?'Puck line':'Spread','spread',['away','home'],(b,s)=>lp('spread')(b,s))}
   ${tbl(d.game.sport==='tenis'?'Total de juegos':'Total','total',['over','under'],(b,s)=>lp('total')(b,s))}
   ${d.game.sport==='tenis'?tbl('Hándicap de sets','sspread',['away','home'],(b,s)=>lp('sspread')(b,s))+tbl('Total de sets','stotal',['over','under'],(b,s)=>lp('stotal')(b,s)):''}
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
  <li><b>Tenis:</b> logística sobre ln(puntos de ranking) sólo para el ganador. Hándicap y total son de <b>JUEGOS</b> (p. ej. Sinner -3.5 juegos, Over 22.5 juegos) y además hay hándicap/total de <b>SETS</b>, todos sólo mercado (Pinnacle). No hay empate ni 1X2 en tenis.</li><li><b>Récord (¿se ganó?):</b> cada pick principal y sugerencia se guarda al generarse (antes del juego) con la primera línea y cuota; se califica con el marcador final real de ESPN (tenis: juegos y sets del marcador por sets). Ganado / Perdido / Push / medio ganado-perdido (líneas de cuarto) / Anulado; pendiente hasta que haya final confirmado. Unidades a 1u plano con la cuota registrada. El historial empieza cuando el servidor empezó a registrar.</li>
  <li><b>Prob. final</b> = mezcla del modelo y el mercado sin vig; el peso del modelo (máx. 50%) crece con la muestra. El modelo se recorta a ±20 pp del mercado.</li>
  <li><b>Edge</b> = prob. final − prob. implícita sin vig (pp). <b>EV</b> = prob. final × momio decimal − 1. <b>Línea justa</b> = momio de la prob. final. <b>Precio máx.</b> = momio con EV = +2%.</li>
  <li><b>Estados:</b> 🔥 PICK (edge ≥ 3 pp, EV ≥ 0 y confianza Media/Alta) · 🟡 LEAN (edge ≥ 1 pp) · ⛔ PASS (sin edge; igual se muestra el lean) · 🔍 SIN LÍNEA (no hay precio).</li>
  <li><b>Probabilidades por resultado:</b> en cada juego se listan ganador/1X2, doble oportunidad (fútbol), hándicap y over/under con el nombre real del equipo o jugador. Hándicap y totales del modelo salen de la normal del margen/total esperado (NBA, NFL, NHL, MLB) o de la matriz Poisson de goles (fútbol); en tenis el modelo sólo cubre al ganador (el resto: “Modelo: Sin dato”). Líneas de cuarto (asiáticas, p. ej. -0.75 o 2.75) sólo muestran mercado.</li>
  <li><b>Casas y consenso:</b> mejor precio = el momio más alto en la misma línea; consenso s/vig = promedio de las probabilidades sin vig de las casas en la línea de referencia.</li>
  <li><b>RLM:</b> lado público (≥55% de tickets) y la línea/precio se mueve en su contra entre la apertura y ahora. <b>Dinero &gt; tickets:</b> % dinero − % tickets ≥ 10 pp. Se muestran junto al pick como etiquetas (a favor / en contra / mixto) <b>sin cambiar la probabilidad del modelo</b>: son indicadores, no garantías. Sin % de apuestas ⇒ “Sin dato”.</li>
  <li><b>Confianza:</b> muestra de juegos, acuerdo con el mercado, líderes lesionados, abridores (MLB).</li></ul></div>
  <div class="note">El modelo no sabe de lesiones de último minuto, descansos, clima ni alineaciones. El mercado suele ser más informado que un modelo simple: trátalo como una segunda opinión. Sin promesas de rentabilidad.</div>`;
}


// ------------------------------------------------------------ interacción (móvil): sugerencias y tarjetas plegables
function foldCards(){
  if(!matchMedia('(max-width:640px)').matches) return;
  const keep=/Picks registrados|Mejores picks|Probabilidades|Comparador|Movimientos de l|En vivo|Marcador y estad/i;
  document.querySelectorAll('#app > .card').forEach(c=>{
    const h=c.querySelector(':scope > h2'); if(!h) return;
    c.classList.add('fold'); if(!keep.test(h.textContent)) c.classList.add('closed');
  });
}
document.addEventListener('click',e=>{
  const t=e.target.closest('.tg');
  if(t){ e.preventDefault(); e.stopPropagation(); t.parentElement.classList.toggle('open'); return; }
  const h=e.target.closest('.fold > h2'); if(h) h.parentElement.classList.toggle('closed');
},true);
document.addEventListener('keydown',e=>{ if((e.key==='Enter'||e.key===' ')&&e.target.classList&&e.target.classList.contains('tg')){ e.preventDefault(); e.target.parentElement.classList.toggle('open'); } });
