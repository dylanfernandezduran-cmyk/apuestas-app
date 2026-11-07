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

// fetch con tope de tiempo: nunca se queda girando; el error sube a route() que muestra el mensaje + «Reintentar»
const API_TIMEOUT_MS = 45000;
// Modo GitHub Pages (pt90u): sin servidor; las respuestas de /api vienen de JSON estáticos que un GitHub Action regenera cada ~10-15 min
const STATIC = typeof window!=='undefined' && !!window.NRNM_STATIC;
const LOCAL_URL = 'http://192.168.100.11:8765';
const NOSTATIC = [/^\/api\/tickets/, /^\/api\/prop\//, /^\/api\/search/, /^\/api\/grade/, /^\/api\/history\//];
function staticUrl(path){
  if(/^\/api\/record(\?|$)/.test(path)) path='/api/record?limit=80';            // filtros del récord: se aplican sobre el último récord publicado
  let [p,q]=path.split('?'); p=p.replace(/^\/api\//,'');
  if(q){ q=q.split('&').filter(Boolean).sort().join('&').replace(/[^A-Za-z0-9._-]/g,'_'); p+='@'+q; }
  return 'data/'+p+'.json';
}
async function api(path, ms){
  const ac = new AbortController(), t = setTimeout(()=>ac.abort(), ms||API_TIMEOUT_MS);
  try{
    if(STATIC && NOSTATIC.some(r=>r.test(path))) throw new Error('Esto necesita el servidor: no está disponible en la versión en línea (GitHub). Ábrelo en el link local '+LOCAL_URL+' con la PC encendida.');
    const r = await fetch(STATIC ? staticUrl(path) : path, {signal: ac.signal, cache: STATIC ? 'no-cache' : 'default'});
    if(STATIC && r.status===404) throw new Error('Sin datos publicados para esto todavía en la versión en línea (se actualiza cada ~10-15 min). Para datos al momento usa el link local '+LOCAL_URL+'.');
    if(!r.ok) throw new Error((await r.json().catch(()=>({detail:r.statusText}))).detail||r.statusText);
    return await r.json();
  }catch(e){
    if(e&&e.name==='AbortError') throw new Error('La consulta tardó demasiado (más de '+Math.round((ms||API_TIMEOUT_MS)/1000)+' s). Revisa tu conexión o que el servidor esté encendido.');
    if(e instanceof TypeError) throw new Error('No se pudo conectar con el servidor. Revisa tu conexión.');
    throw e;
  }finally{ clearTimeout(t); }
}
const errBox = (msg) => `<div class="err">⚠️ ${esc(msg)}<div style="margin-top:10px"><button class="btn" id="retry" type="button">↻ Reintentar</button></div></div>`;
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
const mktKey = c => ({ML:'ml',Spread:'spread',Total:'total',BTTS:'btts'})[c.market]||c.market;
let REC_MAP = {};
const recFor = (market, side, line) => { const r = REC_MAP[market+'.'+side]; return r && (line==null || r.line==null || Number(r.line)===Number(line)) ? r : null; };   // sólo si es la MISMA línea registrada
const units = u => u==null ? '—' : (u>0?'+':'')+Number(u).toFixed(2)+'u';
const oddsTxt = r => r.odds==null ? 'sin cuota' : am(r.odds)+(r.book?' · '+esc(r.book):'');
const SPORT_EM = {mlb:'⚾',nfl:'🏈',nba:'🏀',nhl:'🏒',tenis:'🎾',futbol:'⚽'};
function setNav(n){ document.querySelectorAll('nav a').forEach(a=>{ const on=a.dataset.n===n; a.classList.toggle('on',on); if(on){ const nv=a.parentElement; nv.scrollLeft=Math.max(0,a.offsetLeft-(nv.clientWidth-a.offsetWidth)/2); } }); }

// ------------------------------------------------------------ rutas
let ROUTE_SEQ = 0;
async function route(){
  const seq = ++ROUTE_SEQ;
  Live.stop();
  const h = location.hash.replace(/^#\/?/,'').split('/').map(decodeURIComponent);
  window.scrollTo(0,0); $app.classList.remove('gd');
  try{
    if(!h[0]||h[0]==='') { setNav('home'); return await viewHome(); }
    if(h[0]==='deportes'){ setNav('sports'); return await viewSports(); }
    if(h[0]==='deporte'){ setNav('sports'); return await viewSport(h[1], h[2]); }
    if(h[0]==='juego'){ setNav('sports'); return await viewGame(h[1], h[2]); }
    if(h[0]==='prop'){ setNav('sports'); return await viewProp(h[1], h[2], h[3], h[4]); }
    if(h[0]==='picks'){ setNav('picks'); return await viewPicks(h[1]||'24h'); }
    if(h[0]==='record'){ setNav('record');
      if(h[1]==='total') return await viewRecord();
      if(h[1]==='cal') return await viewRecordCal(h[2]);
      return await viewRecordDay(h[1]==='dia'?h[2]:null); }
    if(h[0]==='tickets'){ setNav('record'); return await viewTickets(h[1]||null); }
    if(h[0]==='info'){ setNav('info'); return await viewInfo(); }
    await viewHome();
  }catch(e){ if(seq!==ROUTE_SEQ) return; $app.innerHTML = errBox(e.message); const b=document.getElementById('retry'); if(b) b.onclick=()=>route(); }
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
  if(!location.hash.startsWith('#/deporte/')) return;   // el usuario ya se fue a otra pantalla: no pisarla
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
// fútbol: el primer equipo es el LOCAL (home - away); resto de deportes: visitante @ local
const isSoc = g => !!g && g.sport==='futbol';
// fútbol y tenis: el primer lado es el LOCAL / jugador 1 (home), después el visitante / jugador 2
const homeFirst = g => !!g && (g.sport==='futbol'||g.sport==='tenis');
const sides = g => homeFirst(g) ? ['home','away'] : ['away','home'];
const vsMark = g => homeFirst(g) ? 'vs' : '@';
// ---- logos de equipo / foto de jugador (ESPN, vía /api/img: reducidas + caché). Sin imagen o si falla -> círculo con iniciales, mismo tamaño (sin saltos de layout)
const imgSrc = (u,w) => (typeof window!=='undefined'&&window.NRNM_STATIC) ? u : `/api/img?w=${w||64}&u=${encodeURIComponent(u)}`;
const initials = n => { const w=String(n||'').replace(/\(.*?\)/g,' ').split(/[\s.\-]+/).filter(Boolean); if(!w.length) return '?'; return (w.length>1 ? w[0][0]+w[w.length-1][0] : w[0].slice(0,2)).toUpperCase(); };
const badge = (t,s) => { s=s||22; t=t||{}; const u=t.logo, ini=initials(t.name||t.short), ph=u&&/\/headshots\//.test(u);
  return `<span class="tl${u?'':' ini'}${ph?' ph':''}" style="--s:${s}px" data-i="${esc(ini)}">${u?`<img src="${esc(imgSrc(u,s*2))}" width="${s}" height="${s}" loading="lazy" decoding="async" alt="" onerror="this.parentNode.classList.add('ini');this.remove()">`:''}</span>`; };
const matchup = (g,short) => sides(g).map(sd=>`<span class="mu">${badge(g[sd],16)}<span>${esc(short?(g[sd].short||g[sd].name):g[sd].name)}</span></span>`).join(` <span class="vs">${vsMark(g)}</span> `);
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
    return `<div class="tm">${badge(t,22)}<span class="nm" title="${esc(t.name)}">${esc(t.name)}</span><span class="rc">${esc(t.record||'')}</span>${sc?`<span class="sc mono ${t.winner?'pos':''}">${esc(g.sport==='tenis'?(t.sets||[]).join(' '):(t.score??''))}</span>`:''}${ml!=null?`<span class="ml mono">${am(ml)}</span>`:''}</div>`; };
  const where=[g.note||g.league_name, g.venue].filter(Boolean).map(esc).join(' · ');
  const live=g.state==='in', chips=[injChip(g), `<span class="wxc" data-id="${esc(g.id)}"></span>`].filter(Boolean).join('');
  const tennisWd = g.wd ? `<div class="sub" style="margin-top:6px">⚠️ ${esc(g.wd)}</div>` : '';
  return `<a class="card game ${live?'is-live':''}" href="#/juego/${encodeURIComponent(g.league)}/${g.id}" data-gid="${esc(g.id)}" data-state="${g.state}" data-ts="${new Date(g.date).getTime()}">
    <div class="gh">${live?`<span class="time mono lv-clock">${esc((g.live&&g.live.text)||g.status||'')}</span>`:`<span class="time mono">${fmtTime(g.date)}</span>`}<span class="gl">${where}</span>${sc?stBadge(g):''}</div>
    ${sides(g).map(sd=>team(g[sd],sd)).join('')}
    ${liveLine(g)}${tennisWd}
    ${marketRow(g)}
    ${chips?`<div class="cchips">${chips}</div>`:''}
    ${g.state==='pre'?`<div class="gp" data-id="${esc(g.id)}"><span class="sub">⏳ Probabilidades…</span></div>`:recBlock(g)}</a>`;
}

// ------------------------------------------------------------ juego
// ---- detalle limpio: encabezado, pick principal, mercados en bloques y todo lo técnico en acordeones cerrados
function heroSide(g,d,sd){ const t=g[sd], ten=d.kind==='tennis';
  return `<div class="hs">${badge(t,56)}<div class="n">${esc(t.name)}</div><div class="sub">${esc(t.record||'')}${ten&&t.rank&&!t.record?`#${t.rank} ranking`:''}</div>${ten&&g.state!=='pre'?`<div class="big mono hsets">${esc((t.sets||[]).join(' '))}</div>`:''}</div>`; }
function heroMid(g,d){
  const live=g.state==='in', ten=d.kind==='tennis', sd=sides(g);
  if(g.state==='pre') return `<div class="hm-d">${esc(fmtShort(g.date))}</div><div class="hm-t mono">${esc(fmtTime(g.date))}</div><div class="sub">CDMX</div>`;
  const clock = d.live&&d.live.text ? d.live.text : (live?(g.status||''):'Final');
  if(ten) return `<div class="hm-s ${live?'lv-clock':''}">${live?'● EN VIVO':'FINAL'}</div><div class="sub">${esc(clock)}</div>`;
  return `<div class="hm-sc mono">${esc(g[sd[0]].score??'')} <span class="mut">–</span> ${esc(g[sd[1]].score??'')}</div><div class="hm-s ${live?'lv-clock':''}">${live?'● '+esc(clock):'FINAL'}</div>`;
}
const MK_ORDER={ml:0,total:1,spread:2,dc:3};
function mkTitle(m,g){
  const sp=g.sport, k=m.key;
  if(k==='ml') return isSoc(g)?'Resultado final':sp==='tenis'?'Ganador del partido':'Ganador';
  if(k==='total') return sp==='tenis'?'Total':'Total de '+(sp==='futbol'?'goles':sp==='mlb'||sp==='nhl'?'carreras/goles':'puntos');
  if(k==='spread') return sp==='mlb'?'Run line':sp==='futbol'?'Hándicap asiático':sp==='tenis'?'Hándicap de juegos':'Hándicap (spread)';
  if(k==='dc') return 'Doble oportunidad';
  return (m.title||k).replace(/\s*\(.*\)\s*$/,'');
}
const obLabel = (o,g) => String(o.label||'').replace(/\s*\((local|visitante)\)/i,'').replace(/^Over\b/,'Más de').replace(/^Under\b/,'Menos de').replace(/\s*\(sin empate\)/i,'');
function mkFromOdds(d){
  const o=d.odds, g=d.game; if(!o) return [];
  const out=[], bt=(label,price,market,side,line)=>({label,market,side,line,p_final:null,best:price!=null?{price_txt:am(price)}:null});
  if(o.ml){ const th=o.ml.draw!=null; out.push({key:'ml',outcomes:mlSides(g,th).filter(sd=>o.ml[sd]!=null).map(sd=>bt(sd==='draw'?'Empate':g[sd].name,o.ml[sd],'ml',sd))}); }
  const T=o.total; if(T&&T.over&&T.under) out.push({key:'total',outcomes:[bt('Más de '+T.over.line,T.over.price,'total','over',T.over.line),bt('Menos de '+T.under.line,T.under.price,'total','under',T.under.line)]});
  const S=o.spread; if(S&&S.home&&S.away) out.push({key:'spread',outcomes:sides(g).map(sd=>bt(g[sd].name+' '+(S[sd].line>0?'+':'')+S[sd].line,S[sd].price,'spread',sd,S[sd].line))});
  return out.filter(m=>m.outcomes.length);
}
function marketBlocks(d){
  const g=d.game, P=d.probs, l=d.picks&&d.picks.lean;
  let mk=(P&&P.markets||[]).filter(m=>m.outcomes&&m.outcomes.length);
  let fb=false; if(!mk.length){ mk=mkFromOdds(d); fb=mk.length>0; }
  if(!mk.length) return '';
  mk=mk.slice().sort((a,b)=>(MK_ORDER[a.key]??9)-(MK_ORDER[b.key]??9));
  const isPick=o=>l&&String(o.market||'').toLowerCase()===String(mktKey(l)).toLowerCase()&&o.side===l.side&&(l.line==null||o.line==null||Number(o.line)===Number(l.line));
  const order = (m)=>{ if(m.key==='ml'||m.key==='spread'){ const th=m.outcomes.length===3; const ord=mlSides(g,th); return m.outcomes.slice().sort((a,b)=>ord.indexOf(a.side)-ord.indexOf(b.side)); } if(m.key==='total') return m.outcomes.slice().sort((a,b)=>(a.side==='over'?0:1)-(b.side==='over'?0:1)); return m.outcomes; };
  const btn=o=>{ const pk=isPick(o), v=o.edge!=null&&o.edge>=3, rr=recFor(String(o.market||'').toLowerCase(),o.side,o.line);
    const pr=o.best&&(o.best.price_txt||(o.best.price!=null?am(o.best.price):null));
    return `<div class="ob ${pk?'pick':''} ${v?'val':''}"><span class="ol">${esc(obLabel(o,g))}</span><span class="oq mono">${esc(pr||'—')}</span><span class="op">${o.p_final!=null?pct(o.p_final,0)+(pk&&o.edge!=null?` · <b class="${o.edge>0?'pos':'neg'}">${sg(o.edge)}pp</b>`:''):'&nbsp;'}</span>${rr&&rr.status!=='PENDIENTE'?`<span class="og">${gradeBadge(rr,false)}</span>`:''}</div>`; };
  const blocks=mk.map(m=>{ const os=order(m); return `<div class="mkb"><div class="mkb-h">${esc(mkTitle(m,g))}</div><div class="ob-g n${Math.min(os.length,3)}">${os.map(btn).join('')}</div></div>`; }).join('');
  return `<div class="card mkc"><h2>Mercados</h2>${blocks}<div class="sub mkn">${fb?'Cuotas de ESPN. ':''}Cuota = mejor precio disponible · % = probabilidad final${P&&P.markets&&P.markets.length?' (modelo + mercado)':''}.</div></div>`;
}
async function viewGame(league, id, silent){
  if(!silent) loading('Analizando partido con datos reales…');
  const d = await api(`/api/game/${encodeURIComponent(league)}/${id}`);
  if(!location.hash.startsWith('#/juego/')) return d;
  const g = d.game;
  const back = `<a class="back" href="#/deporte/${g.sport}/${encodeURIComponent(league)}">← ${esc(g.league_name)}</a>`;
  const live = g.state==='in';
  const sub=[g.note&&g.note!==g.league_name?g.note:'', g.venue, g.court, g.neutral&&d.kind!=='tennis'?'cancha neutral':'', g.weather&&!d.weather?`🌡️ ${g.weather.temp_f}°F`:''].filter(Boolean).map(esc).join(' · ');
  const hero = `<div class="card gh2"><div class="gh2-t"><span>${esc(g.league_name)}</span>${stBadge(g)}</div>
    <div class="hero">${heroSide(g,d,sides(g)[0])}<div class="hmid">${heroMid(g,d)}</div>${heroSide(g,d,sides(g)[1])}</div>
    ${sub?`<div class="sub hsub">${sub}</div>`:''}${g.wd?`<div class="sub hsub">⚠️ ${esc(g.wd)}</div>`:''}
    ${restTags(d)?`<div class="hsub">${restTags(d)}</div>`:''}<div class="hsub">${updTag(d.updated,live)}</div></div>`;
  REC_MAP = {}; (d.record||[]).forEach(r=>{ REC_MAP[r.market+'.'+r.selection]=r; }); PROV = d.prov||{};
  let html = back + hero + courtLive(d) + liveSection(d) + marketBlocks(d) + detailSections(d);
  // conserva scroll y acordeón de «En vivo» al refrescar en vivo; el estado de secciones/ⓘ/pestañas vive en DST
  const keyOf=c=>c.querySelector(':scope > h2').textContent.trim().slice(0,24);
  const st = silent ? {y:window.scrollY, open:[...document.querySelectorAll('#app > .fold')].map(c=>[keyOf(c), !c.classList.contains('closed')])} : null;
  $app.classList.add('gd');
  $app.innerHTML = html;
  mvDraw(); foldCards(); if(typeof propsInit==='function') propsInit();
  if(st){ const m=new Map(st.open); document.querySelectorAll('#app > .fold').forEach(c=>{ const k=keyOf(c); if(m.has(k)) c.classList.toggle('closed',!m.get(k)); }); window.scrollTo(0,st.y); }
  Live.start(async()=>{ if(!location.hash.startsWith('#/juego/')) return; try{ await viewGame(league,id,true); }catch(e){} }, 25000);
  if(!live) Live.stop();
  return d;
}
let PROV = {};

const mlSides = (g,three) => three ? (isSoc(g)?['home','draw','away']:['away','draw','home']) : sides(g);
function oddsSection(d){
  const o=d.odds, nv=o.nv||{}, g=d.game;
  const rows=[];
  const mk=(lbl,price,p,pn)=>`<tr><td>${esc(lbl)}</td><td class="mono">${am(price)}</td><td class="mono">${pct(price==null?null:(price>0?100/(price+100):Math.abs(price)/(Math.abs(price)+100)))}</td><td class="mono"><b>${pct(pn)}</b></td></tr>`;
  const mlh=o.ml.home, mla=o.ml.away;
  if(mlh!=null||mla!=null){
    rows.push(`<tr><td colspan="4" class="mut">Moneyline${nv.ml_vig!=null?` · vig ${(nv.ml_vig*100).toFixed(1)}%`:''}</td></tr>`);
    const mlr={away:()=>mk(g.away.name,mla,0,(nv.ml||{}).away), home:()=>mk(g.home.name,mlh,0,(nv.ml||{}).home), draw:()=>mk('Empate',o.ml.draw,0,(nv.ml||{}).draw)};
    for(const sd of mlSides(g,o.ml.draw!=null)){ if(sd!=='draw'||o.ml.draw!=null) rows.push(mlr[sd]()); }
  }
  if(o.spread.home||o.spread.away){
    rows.push(`<tr><td colspan="4" class="mut">${d.game.sport==='mlb'?'Run line':d.game.sport==='futbol'?'Hándicap':'Spread'}${nv.spread_vig!=null?` · vig ${(nv.spread_vig*100).toFixed(1)}%`:''}</td></tr>`);
    for(const sd of sides(g)) if(o.spread[sd]) rows.push(mk(`${g[sd].name} ${sg(o.spread[sd].line)}`,o.spread[sd].price,0,(nv.spread||{})[sd]));
  }
  if(o.total.over||o.total.under){
    rows.push(`<tr><td colspan="4" class="mut">Total${nv.total_vig!=null?` · vig ${(nv.total_vig*100).toFixed(1)}%`:''}</td></tr>`);
    if(o.total.over) rows.push(mk('Over '+o.total.over.line,o.total.over.price,0,(nv.total||{}).over));
    if(o.total.under) rows.push(mk('Under '+o.total.under.line,o.total.under.price,0,(nv.total||{}).under));
  }
  let mv='';
  if(o.open&&o.open.ml){ const bits=[]; for(const s of sides(g)){ if(o.open.ml[s]!=null&&o.ml[s]!=null) bits.push(`${esc(g[s].short||g[s].name)}: ${am(o.open.ml[s])} → <b>${am(o.ml[s])}</b>`);} if(bits.length) mv=`<div class="sub" style="margin-top:6px">📈 Movimiento ML (apertura → actual): ${bits.join(' · ')}</div>`; }
  return ds('odds','Cuotas actuales',`<div class="tbl"><table><thead><tr><th>Mercado</th><th>Precio</th><th>c/vig</th><th>s/vig</th></tr></thead><tbody>${rows.join('')}</tbody></table></div>${mv}`,{right:`<span class="tg2">${esc(o.book)} · ESPN</span>`,info:`Una sola casa (${esc(o.book)}, vía ESPN). Probabilidad sin vig = normalización proporcional. Los precios cambian; verifica en tu casa de apuestas.`});
}

// ------------------------------------------------------------ récord / historial
let RECF = {sport:'', type:'', basis:'', days:''};
const recMatch = r => { const H={name:r.home,logo:r.home_logo}, A={name:r.away,logo:r.away_logo}, soc=r.sport==='futbol'||r.sport==='tenis';
  const m=(t)=>`<span class="mu">${badge(t,16)}<span>${esc(t.name)}</span></span>`;
  return (soc?[H,A]:[A,H]).map(m).join(` <span class="vs">${soc?'vs':'@'}</span> `); };
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
  let html=`<h1>📒 Récord</h1>${rdTabs('total')}<div class="day" style="margin-top:4px">Total de la temporada (todo el historial)</div>
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
   ${STATIC?'':'<button class="btn" onclick="gradeNow(this)">🔄 Calificar ahora</button>'} <span class="sub">Automático cada ${d.grading.every_min} min${d.grading.last?' · última '+tsFmt(d.grading.last):''}</span></div>`;
  html+=predRecord(d.pred);
  if(!d.recent.length) html+=`<div class="card mut" style="margin-top:10px">Aún no hay picks calificados con esos filtros. ${S.pending?`Hay <b>${S.pending}</b> picks registrados esperando el final de sus juegos.`:'Cuando el servidor genere picks y sus juegos terminen, aparecerán aquí.'}</div>`;
  else html+=`<div class="day">Últimos picks calificados</div><div class="rec-list">`+d.recent.map(r=>`<div class="rec-r"><div class="rl"><span class="mono sub">${fmtShort(new Date(r.start_ts*1000).toISOString())} · ${SPORT_EM[r.sport]||''} ${esc(r.league.toUpperCase())}</span> ${typeLbl(r.type)}${r.basis==='mercado'?' <span class="sub">(sólo mercado)</span>':''}
     <div class="rl-m">${recMatch(r)}</div><div><b>${esc(r.label)}</b> <span class="mono sub">${oddsTxt(r)}</span></div>${lineMove(r,{state:'post'})}<div class="sub mono">${esc(r.score_text||'')}</div>${r.note?`<div class="sub">ℹ️ ${esc(r.note)}</div>`:''}</div>
     <div class="rr">${gradeBadge(r,false)}<div class="mono ${r.units>0?'pos':r.units<0?'neg':'mut'}">${units(r.units)}</div></div></div>`).join('')+`</div>`;
  $app.innerHTML=html;
}
function setRecF(k,v){ RECF[k]=v; viewRecord(); }
async function gradeNow(btn){ btn.disabled=true; btn.textContent='Calificando…'; try{ await fetch('/api/grade',{method:'POST'}); }catch(e){} viewRecord(); }

// ------------------------------------------------------------ picks del día
const PICK_GROUPS = ['mlb','nfl','futbol','nba','nhl','tenis'];
async function viewPicks(scope){
  SPORTS = SPORTS || await api('/api/sports');
  loading('Calculando picks de todos los deportes (primera vez puede tardar ~20 s)…');
  const d = await api('/api/picks?scope='+scope);
  d.items.forEach(r=>{ if(!r.lean) r.lean={label:'Sin pick oficial',edge:null,p_model:null,p_nv:null}; });
  const tabs=[['24h','Próx. 24 h'],['hoy','Hoy'],['manana','Mañana'],['72h','72 h']];
  const t=`<div class="pills">${tabs.map(([k,l])=>`<a class="pill ${k===scope?'on':''}" href="#/picks/${k}">${l}</a>`).join('')}</div>`;
  const withOdds=d.items.filter(r=>r.has_odds&&r.status==='PICK'), pass=d.items.filter(r=>r.has_odds&&r.status==='PASS'), noodds=d.items.filter(r=>!r.has_odds);
  const card=r=>{ const l=r.lean, g=r.game, st=STATUS[r.status];
    const sg_=l.signals&&l.signals.verdict&&l.signals.verdict!=='sin_dato';
    const sigH=sg_?`<div class="sub" style="margin:8px 0 4px">${(VERD[l.signals.verdict]||[])[0]||''} ${(VERD[l.signals.verdict]||[])[1]||''}${l.signals.tickets!=null?` · ${l.signals.tickets}% tickets / ${l.signals.money!=null?l.signals.money+'% dinero':'dinero '+SD}`:''}${l.signals.best?` · mejor ${esc(l.signals.best.price_txt)} en ${esc(l.signals.best.book)}`:''}</div>${tagChips(l.signals)}`:'';
    const nb=(r.brief||[]).length;
    const det=(sg_||nb)?`<div class="gp"><div class="tg" role="button" tabindex="0">Señales y mercados${nb?` (${nb})`:''}</div><div class="sg">${sigH}${nb?briefRows(r.brief,g,[]):''}</div></div>`:'';
    return `<a class="card pk" href="#/juego/${encodeURIComponent(g.league)}/${g.id}"><div class="pk1"><div class="pkt">${st[0]} ${esc(l.label)} <span class="mono">${l.price_txt?'('+esc(l.price_txt)+')':''}</span></div>
    <div class="pke mono ${l.edge>0?'pos':'mut'}">${l.edge==null?SD:sg(l.edge)+'pp'}<small>edge</small></div></div>
    <div class="meta">${badgeSt(r.status)} ${confBadge(r.confidence)}<span class="sub">${esc(g.league_name)} · ${matchup(g)} · ${fmtShort(g.date)} ${fmtTime(g.date)} CDMX</span></div>
    <div class="stat mono">${r.status==='PICK'?`Puntaje <b>${l.score}/100</b> · `:''}Modelo ${pct(l.p_model)} · s/vig ${pct(l.p_nv)} · Justa ${esc(l.fair_txt||SD)} · Máx. ${esc(l.max_txt||SD)}</div>
    ${r.status!=='PICK'&&l.why_not&&l.why_not.length?`<div class="sub">No es pick oficial: ${esc(l.why_not.join(' · '))}</div>`:''}
    ${(r.official||[]).length>1?`<div class="sub">2.º pick oficial: <b>${esc(r.official[1].label)}</b> ${esc(r.official[1].price_txt||'')}</div>`:''}
    ${r.status==='PICK'?`<div class="tkrow">${(r.official||[]).map(c=>tkBtn(tkLegFromCand(g,Object.assign({official:true},c)),'+ Ticket · '+shortLbl(c.label,g))).join('')}</div>`:''}${det}</a>`; };
  let html=`<h1>🔥 Picks oficiales · todos los deportes</h1>${t}<div class="sub" style="margin-bottom:8px">Ventana: ${d.n_games} juegos analizados · <b>${d.items.filter(r=>r.status==='PICK').length} picks oficiales</b> (filtro estricto: edge ≥ 2 pp, prob. ≥ 55 %, señales no en contra, sin lesión clave en duda, puntaje ≥ 60, coherente con la Predicción NRNM; máx. 1 por juego) · ordenados por puntaje. <b>Estimaciones del modelo</b>, no garantías.</div>`;
  if(!d.items.length) html+=`<div class="card mut">No hay juegos pre-juego en esta ventana. Prueba otra pestaña.</div>`;
  // agrupado por deporte (orden: MLB, NFL, Fútbol, NBA, NHL, Tenis; grupos vacíos ocultos). Dentro de cada grupo: con ventaja, PASS y sin línea (orden del servidor)
  const rank=r=>r.has_odds?(r.status==='PICK'?0:1):2;
  PICK_GROUPS.slice().sort((a,b)=>(d.items.some(r=>r.game.sport===b&&r.status==='PICK'))-(d.items.some(r=>r.game.sport===a&&r.status==='PICK'))).forEach(k=>{
    const its=d.items.filter(r=>r.game.sport===k).map((r,i)=>[r,i]).sort((a,b)=>rank(a[0])-rank(b[0])||a[1]-b[1]).map(x=>x[0]);
    if(!its.length) return;
    const sp=(SPORTS||[]).find(x=>x.key===k)||{name:k,emoji:''}, nPick=its.filter(r=>r.status==='PICK').length;
    const offs=its.filter(r=>r.status==='PICK'), rest=its.filter(r=>r.status!=='PICK').slice(0,30);
    html+=`<h2 class="pgrp" data-sport="${k}"><span class="em">${sp.emoji}</span> ${esc(sp.name)} <span class="n mono">${its.length} juegos${nPick?` · ${nPick} pick${nPick>1?'s':''} oficial${nPick>1?'es':''}`:' · sin pick oficial'}</span></h2>`+offs.map(card).join('')
      +(rest.length?`<div class="gp"><div class="tg" role="button" tabindex="0">${rest.length} juego${rest.length>1?'s':''} sin pick oficial (no recomendado)</div><div class="sg">${rest.map(card).join('')}</div></div>`:'');
  });
  $app.innerHTML=html;
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
  if(!mk||!mk.books||!mk.books.length) return '';
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
  const mlSd = mlSides(g, books.some(b=>b.ml&&b.ml.draw!=null));
  const ts=(mk.sources||[]).map(s=>`${esc(s.name)} (${s.n_books} ${s.n_books===1?'casa':'casas'}) · ${tsFmt(s.ts)}`).join(' · ');
  const nreal=books.filter(b=>b.kind==='book'||b.kind==='sharp').length;
  return ds('odds','Cuotas actuales',`
   ${tbl(isSoc(g)?'1X2 (local · empate · visita)':'Moneyline','ml',mlSd,(b,s)=>sideCell('ml',s)(b))}
   ${tbl(d.game.sport==='mlb'?'Run line':d.game.sport==='futbol'?'Hándicap':d.game.sport==='tenis'?'Hándicap de juegos':d.game.sport==='nhl'?'Puck line':'Spread','spread',sides(g),(b,s)=>lp('spread')(b,s))}
   ${tbl(d.game.sport==='tenis'?'Total de juegos':'Total','total',['over','under'],(b,s)=>lp('total')(b,s))}
   ${d.game.sport==='tenis'?tbl('Hándicap de sets','sspread',sides(g),(b,s)=>lp('sspread')(b,s))+tbl('Total de sets','stotal',['over','under'],(b,s)=>lp('stotal')(b,s)):''}`,{right:`<span class="tg2">${nreal} casas</span>`,info:`<b>Verde</b> = mejor precio en la misma línea · <b>subrayado</b> = mejor línea · filas “s/vig” = probabilidad sin comisión y su momio justo. Consenso = promedio de las casas en la línea de referencia. Fuentes: ${ts||SD}. Los precios cambian; confirma en tu casa antes de apostar.`});
}

let MV=null;
function movementSection(d){
  const mk=d.market, g=d.game; if(!mk) return '';
  const mv=mk.movement||{}, rows=[];
  const sh=s=>s==='home'?tn(g.home):s==='away'?tn(g.away):s==='draw'?'Empate':s==='over'?'Más':'Menos';
  if(mv.ml) for(const s of mlSides(g,true)){ const x=mv.ml[s]; if(x) rows.push(`<tr><td>ML · ${esc(sh(s))}</td><td class="mono">${am(x.open)}</td><td class="mono"><b>${am(x.cur)}</b></td><td class="mono ${x.d_nv_pp>0?'pos':x.d_nv_pp<0?'neg':''}">${x.d_nv_pp!=null?sg(x.d_nv_pp)+' pp':SD}</td></tr>`); }
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
  if(!rows.length && !h.n_points) return '';
  const body=`${rows.length?`<div class="tbl"><table><thead><tr><th>Mercado</th><th>Apertura</th><th>Actual</th><th>Cambio</th></tr></thead><tbody>${rows.join('')}</tbody></table></div>`:''}
   ${h.n_points?`<div class="pills" id="mvtabs">${[['ml','ML'],['spread','Spread'],['total','Total'],['pct','% Apuestas']].map(t=>`<span class="pill ${t[0]==='ml'?'on':''}" data-t="${t[0]}" onclick="mvTab('${t[0]}')">${t[1]}</span>`).join('')}</div><div id="mvchart"></div>`:''}
   ${byBook.length?`<details class="dd"><summary>Por casa</summary><div class="tbl"><table><thead><tr><th>Casa</th><th>ML local</th><th>Spread</th><th>Total</th></tr></thead><tbody>${byBook.join('')}</tbody></table></div></details>`:''}`;
  return ds('move','Movimiento de líneas',body,{right:`<span class="tg2">${mk.movement_src?'Apertura real':'Sin apertura'}</span>`,info:`Apertura vs consenso actual${mk.movement_src?' · fuente: '+esc(mk.movement_src):''}. El cambio de ML se mide en prob. sin vig; spread/total en puntos. Las casas no publican aperturas individuales: por casa usamos nuestro propio historial. ${note}`});
}
const PAL=['#3C85F7','#06AAC4','#FF1179','#F5B942','#a78bfa','#2dd4bf','#f472b6','#fb923c','#94a3b8','#e879f9','#84cc16'];
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
  for(let i=0;i<=4;i++){ const y=y0+(y1-y0)*i/4; svg+=`<line x1="${L}" x2="${W-R}" y1="${Y(y)}" y2="${Y(y)}" stroke="#1a1a1a"/><text x="${L-6}" y="${Y(y)+4}" text-anchor="end" fill="#7d8ba1" font-size="10">${fmt(y)}</text>`; }
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
  <li><b>Tenis:</b> logística sobre ln(puntos de ranking) sólo para el ganador. Hándicap y total son de <b>JUEGOS</b> (p. ej. Sinner -3.5 juegos, Over 22.5 juegos) y además hay hándicap/total de <b>SETS</b>, todos sólo mercado (Pinnacle). No hay empate ni 1X2 en tenis.</li><li><b>Pick oficial (filtro estricto):</b> máx. 1 por juego (2 sólo si son de otro mercado y ambos ≥ 75/100). Debe tener edge ≥ 2 pp, prob. final ≥ 55 %, señales de mercado (RLM / dinero vs tickets) que no vayan en contra, ningún jugador clave en duda, abridores MLB confirmados, puntaje ≥ 60, y coincidir con la Predicción NRNM. Puntaje 0-100 = edge 35 + prob. 25 + señales 15 + confianza 15 + contexto 10 (clima/datos críticos). Umbrales elegidos con el récord real calificado (backtest: 694 picks 369-317, −51.6u → 33 picks 26-7, +9.3u; muestra chica, no es garantía). Lo demás sólo aparece como «También considerado».</li><li><b>Tickets / parlays (papel):</b> agrega piernas con «+ Ticket»; momio combinado = producto de momios decimales, prob. combinada = producto de probabilidades del modelo (asume independencia; se avisa si hay piernas del mismo juego). Se califican solos pierna por pierna; push/anulada se quita del momio.</li><li><b>Récord (¿se ganó?):</b> cada pick principal y sugerencia se guarda al generarse (antes del juego) con la primera línea y cuota; se califica con el marcador final real de ESPN (tenis: juegos y sets del marcador por sets). Ganado / Perdido / Push / medio ganado-perdido (líneas de cuarto) / Anulado; pendiente hasta que haya final confirmado. Unidades a 1u plano con la cuota registrada. El historial empieza cuando el servidor empezó a registrar.</li>
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
  const keep=/En vivo/i;   // sólo el marcador en vivo arranca abierto; todo lo demás va en acordeones cerrados
  document.querySelectorAll('#app > .card').forEach(c=>{
    const h=c.querySelector(':scope > h2'); if(!h||c.classList.contains('mkc')) return;
    c.classList.add('fold'); if(!keep.test(h.textContent)) c.classList.add('closed');
  });
}
document.addEventListener('click',e=>{
  const t=e.target.closest('.tg');
  if(t){ e.preventDefault(); e.stopPropagation(); t.parentElement.classList.toggle('open'); return; }
  const h=e.target.closest('.fold > h2'); if(h) h.parentElement.classList.toggle('closed');
},true);
document.addEventListener('keydown',e=>{ if((e.key==='Enter'||e.key===' ')&&e.target.classList&&e.target.classList.contains('tg')){ e.preventDefault(); e.target.parentElement.classList.toggle('open'); } });

// barra de la versión en línea: hora de los datos + link local
if(STATIC){ try{ const b=document.createElement('div'); b.className='stbar';
  const dt=new Intl.DateTimeFormat('es-MX',{timeZone:TZ,day:'numeric',month:'short',hour:'2-digit',minute:'2-digit',hour12:true}).format(new Date(window.NRNM_STATIC.built));
  b.innerHTML=`🌐 Versión en línea · datos de ${esc(dt)} (CDMX) · se actualizan cada ~10-15 min · <a href="${LOCAL_URL}">link local (en vivo)</a>`;
  document.querySelector('header').after(b); }catch(e){} }
