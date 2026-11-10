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

const BK_KEY='nrnm_bankroll', BK_UNIT_KEY='nrnm_unit_pct', BK_DAILY_KEY='nrnm_daily_used';
function todayISO(){ return new Intl.DateTimeFormat('en-CA',{timeZone:TZ}).format(new Date()); }
function BK(){
  const bankroll=Math.max(0, parseFloat(localStorage.getItem(BK_KEY)||'')||0);
  const unit_pct=Math.max(0.1, Math.min(5, parseFloat(localStorage.getItem(BK_UNIT_KEY)||'')||1));
  let daily=0; try{ const d=JSON.parse(localStorage.getItem(BK_DAILY_KEY)||'{}'); if(d.day===todayISO()) daily=+d.used||0; }catch(e){}
  return {bankroll, unit_pct, daily_used_frac:daily};
}
function BKSet(bankroll, unit_pct){
  if(bankroll!=null && bankroll!=='') localStorage.setItem(BK_KEY, String(Math.max(0,+bankroll||0)));
  if(unit_pct!=null && unit_pct!=='') localStorage.setItem(BK_UNIT_KEY, String(Math.max(0.1, Math.min(5,+unit_pct||1))));
}
function BKAddDaily(frac){
  const used=(BK().daily_used_frac||0)+Math.max(0,+frac||0);
  localStorage.setItem(BK_DAILY_KEY, JSON.stringify({day:todayISO(), used}));
}
function agoTxt(ts){
  if(!ts) return '';
  const m=Math.max(0, Math.round((Date.now()/1000 - +ts)/60));
  if(m<1) return 'Actualizado hace menos de 1 min';
  if(m===1) return 'Actualizado hace 1 min';
  if(m<60) return 'Actualizado hace '+m+' min';
  const h=Math.floor(m/60), r=m%60;
  return 'Actualizado hace '+h+' h'+(r?(' '+r+' min'):'');
}
function toDecPrice(x){
  x=+x; if(!isFinite(x)) return null;
  if(x<=-100 || x>=100) return x>0?1+x/100:1+100/Math.abs(x);
  if(x>1) return x;
  return null;
}
function quarterKelly(p, price, bankroll, unit_pct, daily_used_frac){
  const dec=toDecPrice(price);
  if(!(p>0&&p<1) || !dec || dec<=1 || !(bankroll>0)) return null;
  unit_pct=unit_pct==null?1:+unit_pct;
  daily_used_frac=+daily_used_frac||0;
  const b=dec-1, q=1-p, fFull=(b*p-q)/b, fQ=fFull*0.25;
  const remaining=Math.max(0, 0.08-daily_used_frac);
  if(fQ<=0) return {frac:0,stake:0,units:0,capped:false,kelly_full:fFull,kelly_quarter:fQ,reason:'EV no positivo: no se sugiere stake'};
  let f=fQ; const reasons=[];
  if(f>0.02){ f=0.02; reasons.push('tope 2% por pick'); }
  if(f>remaining){ f=remaining; reasons.push('tope 8% de exposición diaria'); }
  const unit_size=bankroll*(unit_pct/100), stake=bankroll*f, units=unit_size?stake/unit_size:0;
  return {frac:f,stake:stake,units:units,unit_size:unit_size,capped:!!reasons.length,kelly_full:fFull,kelly_quarter:fQ,remaining_daily:remaining,reason:reasons.join('; ')||null};
}
function fmtStake(s){
  if(!s||s.frac==null) return '';
  const u=s.units!=null?s.units.toFixed(2)+'u':'';
  const mon=s.stake!=null?'$'+Number(s.stake).toFixed(2):'';
  return [u,mon].filter(Boolean).join(' · ')+(s.capped?' (tope)':'');
}
function bkBox(){
  const b=BK();
  return `<div class="card bk-box" id="bkbox"><label>Bankroll <input type="number" id="bk-amt" min="0" step="1" value="${b.bankroll||''}" placeholder="0" inputmode="decimal"></label>
    <label>1u = <input type="number" id="bk-u" min="0.1" max="5" step="0.1" value="${b.unit_pct}"> %</label>
    <button type="button" class="btn" id="bk-save">Guardar</button>
    <span class="sub">Stake paper trading: 1/4 Kelly, tope 2% por pick y 8% de exposición diaria.</span></div>`;
}
document.addEventListener('click',e=>{
  if(!e.target.closest('#bk-save')) return;
  const amt=document.getElementById('bk-amt'), u=document.getElementById('bk-u');
  BKSet(amt&&amt.value, u&&u.value);
  if(typeof route==='function') route();
});


setInterval(()=>{document.getElementById('clock').textContent = new Intl.DateTimeFormat('es-MX',{timeZone:TZ,weekday:'short',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit',hour12:true}).format(new Date())+' · CDMX (UTC-6)'},1000);

// fetch con tope de tiempo: nunca se queda girando; el error sube a route() que muestra el mensaje + «Reintentar»
const API_TIMEOUT_MS = 45000;
// Modo GitHub Pages (pt90u): sin servidor; las respuestas de /api vienen de JSON estáticos que un GitHub Action regenera cada ~10-15 min
const STATIC = typeof window!=='undefined' && !!window.NRNM_STATIC;
let LOCAL_URL = 'http://DESKTOP-NOG66RU.local:8765'; // estable ante DHCP (mDNS); IP se refresca abajo
const NOSTATIC = [/^\/api\/prop\//, /^\/api\/search/, /^\/api\/grade/, /^\/api\/history\//];
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
const TIP = {
  pp: 'Puntos porcentuales: diferencia de probabilidad en puntos (1 pp = 1%).',
  RLM: 'Reverse Line Movement: el lado público (≥55% tickets) y la línea se mueve en su contra.',
  's/vig': 'Probabilidad implícita del mercado sin el margen (vig) de la casa.',
  SRS: 'Simple Rating System: margen promedio ajustado por rival y localía.',
  EV: 'Valor esperado al precio pagado: prob. final × momio decimal − 1.',
  CLV: 'Closing Line Value: (momio decimal de apertura / momio de cierre − 1) × 100. Positivo si el cierre se acortó (el mercado se movió a favor).',
  edge: 'Diferencia (pp) entre la prob. final del modelo y la prob. del mercado sin vig.'
};
const tip = k => ` title="${String(TIP[k]||'').replace(/"/g,'&quot;')}"`;
const tipAbbr = (k, label) => `<abbr${tip(k)}>${label||k}</abbr>`;
const gameSkel = () => `<div class="skel-game" aria-busy="true" aria-live="polite">
  <div class="skel-line" style="width:36%"></div>
  <div class="card skel-hero"><div class="skel-circ"></div><div class="skel-mid"></div><div class="skel-circ"></div></div>
  <div class="card skel-block"><div class="skel-line"></div><div class="skel-line" style="width:74%"></div><div class="skel-line" style="width:52%"></div></div>
  <div class="sub">Cargando análisis con datos reales…</div></div>`;
const todayKey = () => dayKey(new Date().toISOString());
function dayLabel(iso){ const k=dayKey(iso); const t=todayKey(); const tm=dayKey(new Date(Date.now()+864e5).toISOString());
  const base = fmtDay(iso); return k===t?`Hoy · ${base}`:k===tm?`Mañana · ${base}`:base; }

const STATUS = {PICK:['🔥','PICK','b-pick'],LEAN:['🟡','LEAN LIGERO','b-lean'],REVISAR:['⚠️','REVISAR','b-rev'],PASS:['⛔','PASS','b-pass'],SIN_LINEA:['🔍','SIN LÍNEA','b-sl']};
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

function setNavDot(name, on){
  const a=document.querySelector('#bnav [data-n="'+name+'"]'); if(!a) return;
  let d=a.querySelector('.nav-dot'); if(!d){ d=document.createElement('i'); d.className='nav-dot'; a.appendChild(d); }
  d.hidden=!on;
}
let _navDotsT=0;
async function refreshNavDots(){
  if(Date.now()-_navDotsT<20000) return; _navDotsT=Date.now();
  try{
    const h=await api('/api/home');
    setNavDot('sports', !!(h&&h.live&&h.live.length));
  }catch(e){}
}

function setNav(n){ document.querySelectorAll('#bnav a, #bnav button, header nav a').forEach(a=>{ const on=a.dataset.n===n; a.classList.toggle('on',on); if(on && a.parentElement){ const nv=a.parentElement; nv.scrollLeft=Math.max(0,a.offsetLeft-(nv.clientWidth-a.offsetWidth)/2); } }); }

// ------------------------------------------------------------ rutas
let ROUTE_SEQ = 0;
async function route(){
  const seq = ++ROUTE_SEQ;
  Live.stop();
  const h = location.hash.replace(/^#\/?/,'').split('/').map(decodeURIComponent);
  window.scrollTo(0,0); $app.classList.remove('gd');
  try{
    if(!h[0]||h[0]===''||h[0]==='inicio'){ setNav('inicio'); refreshNavDots(); return await viewHome(); }
    if(h[0]==='picks'){ setNav('picks'); return await viewPicks(h[1]||'hoy'); }
    if(h[0]==='lineas'){ setNav('lineas'); return await viewLineas(h[1]||'todos'); }
    if(h[0]==='ia'){ /* ruta #/ia: abre el chat del FAB */ if(typeof chOpen==='function') chOpen(true); setNav('inicio'); refreshNavDots(); return await viewHome(); }
    if(h[0]==='deportes'){ setNav('sports'); return await viewSports(); }
    if(h[0]==='deporte'){ setNav('sports'); return await viewSport(h[1], h[2]); }
    if(h[0]==='juego'){ setNav('sports'); return await viewGame(h[1], h[2]); }
    if(h[0]==='prop'){ setNav('sports'); return await viewProp(h[1], h[2], h[3], h[4]); }
    if(h[0]==='record'){ setNav('record');
      if(h[1]==='total') return await viewRecord();
      if(h[1]==='cal') return await viewRecordCal(h[2]);
      return await viewRecordDay(h[1]==='dia'?h[2]:null); }
    if(h[0]==='tickets'){ setNav('record'); return await viewTickets(h[1]||null); }
    if(h[0]==='info'||h[0]==='metodo'){ setNav('record'); return await viewInfo(); }
    setNav('inicio'); await viewHome();
  }catch(e){ if(seq!==ROUTE_SEQ) return; $app.innerHTML = errBox(e.message); const b=document.getElementById('retry'); if(b) b.onclick=()=>route(); }
}
window.addEventListener('hashchange', route);
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', ()=>route()); else route();   // esperar a recdia.js / ticket.js (se cargan después)

// ------------------------------------------------------------ home
async function viewSports(){
  const seq=ROUTE_SEQ;
  SPORTS = SPORTS || await api('/api/sports');
  loading('Cargando deportes…');
  let home=null;
  try{ home=await api('/api/home'); }catch(e){ $app.innerHTML=errBox(e.message); const b=document.getElementById('retry'); if(b) b.onclick=()=>route(); return; }
  if(seq!==ROUTE_SEQ) return;
  const chips=`<div class="pills">${(SPORTS||[]).map(s=>`<a class="pill" href="#/deporte/${s.key}"><span class="em">${s.emoji||''}</span> ${esc(s.name)}</a>`).join('')}</div>`;
  const search=`<section class="hm" id="sp-search"><label class="srch"><span class="ico" aria-hidden="true">🔍</span><input type="search" inputmode="search" enterkeyhint="search" autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="Buscar juego, equipo, jugador o torneo" aria-label="Buscar"></label><div class="srch-r" hidden></div></section>`;
  const live=(home.live&&home.live.length)?`<div class="card" id="sp-live"><h2>En vivo ahora <span class="badge b-live">${home.live.length}</span></h2>${home.live.slice(0,8).map(g=>{
    const href=`#/juego/${encodeURIComponent(g.league)}/${encodeURIComponent(g.id||g.eid)}`;
    return typeof liveRowHtml==='function'?liveRowHtml(g):`<a class="card" href="${href}">${esc((g.away&&(g.away.abbr||g.away.name))||'')} vs ${esc((g.home&&(g.home.abbr||g.home.name))||'')}</a>`;
  }).join('')}</div>`:'';
  const games=home.today||[];
  const list=games.length?`<h2>Juegos de hoy</h2><div id="sp-today">${games.map(g=>{
    const href=`#/juego/${encodeURIComponent(g.league)}/${encodeURIComponent(g.id)}`;
    return `<a class="card" data-gid="${esc(g.league+'/'+g.id)}" href="${href}"><div class="sub mono">${fmtTime(g.date)} · ${esc(g.league_name||g.league)}</div><div class="pkt">${esc((g.away&&(g.away.short||g.away.name))||'')} vs ${esc((g.home&&(g.home.short||g.home.name))||'')}</div><div class="pick-tag sub"></div></a>`;
  }).join('')}</div>`:`<div class="card mut">No hay juegos programados hoy.</div>`;
  $app.innerHTML=`<h1>Deportes</h1><p class="ago">${esc(agoTxt(home.now))}</p>${search}${chips}${live}${list}`;
  if(typeof srchInit==='function'){ const s=document.getElementById('sp-search'); if(s) srchInit(s); }
  api('/api/picks?scope=hoy').then(pk=>{
    const map={};
    (pk.items||[]).forEach(r=>{ map[r.game.league+'/'+r.game.id]=r; });
    document.querySelectorAll('#sp-today [data-gid]').forEach(el=>{
      const r=map[el.dataset.gid]; if(!r) return;
      const tag=el.querySelector('.pick-tag'); if(!tag) return;
      if(r.status==='REVISAR'||(r.lean&&r.lean.divergence_high)) tag.innerHTML='<span class="divf">Divergencia alta</span>';
      else if(r.status==='PICK'||r.status==='LEAN') tag.innerHTML=badgeSt(r.status)+' '+esc((r.lean&&r.lean.label)||'');
    });
  }).catch(()=>{});
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
  const rec=g.rec||[], _mains=(rec||[]).filter(x=>x.type==='main'), rm=[..._mains].reverse().find(x=>x.status!=='ANULADO')||_mains[_mains.length-1];
  let main = rm && items.find(b=>b.market===rm.market&&b.side===rm.selection);
  let line;
  if(!main && rm){
    const inv=rec.find(x=>x.market===rm.market&&x.status==='ANULADO'&&x.state==='INVERTIDO');
    line=`<div class="pickline"><span class="k">PICK</span><span class="t">${esc(shortLbl(rm.label,g))}</span>${gradedBadge(rm)}</div>`+(inv?`<div class="sub">antes: ${esc(shortLbl(inv.label,g))} · invertido</div>`:'');
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
  const _ms=r.filter(x=>x.type==='main'), m=[..._ms].reverse().find(x=>x.status!=='ANULADO')||_ms[_ms.length-1], rest=r.filter(x=>x!==m);
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
const MK_ORDER={ml:0,total:1,spread:2,dc:3,btts:4,corners:5};
function mkTitle(m,g){
  const sp=g.sport, k=m.key;
  if(k==='ml') return isSoc(g)?'Resultado final':sp==='tenis'?'Ganador del partido':'Ganador';
  if(k==='total') return sp==='tenis'?'Total':'Total de '+(sp==='futbol'?'goles':sp==='mlb'||sp==='nhl'?'carreras/goles':'puntos');
  if(k==='spread') return sp==='mlb'?'Run line':sp==='futbol'?'Hándicap asiático':sp==='tenis'?'Hándicap de juegos':'Hándicap (spread)';
  if(k==='dc') return 'Doble oportunidad';
  if(k==='btts') return 'Ambos anotan';
  if(k==='corners'||k==='corner') return 'Córners';
  return (m.title||k).replace(/\s*\(.*\)\s*$/,'');
}
const obLabel = (o,g) => String(o.label||'').replace(/\s*\((local|visitante)\)/i,'').replace(/^Over\b/,'Más de').replace(/^Under\b/,'Menos de').replace(/^Yes\b/i,'Sí').replace(/^No\b/i,'No').replace(/\s*\(sin empate\)/i,'');
function mkFromOdds(d){
  const o=d.odds, g=d.game; if(!o) return [];
  const out=[], bt=(label,price,market,side,line)=>({label,market,side,line,p_final:null,best:price!=null?{price,price_txt:am(price)}:null});
  if(o.ml){ const th=o.ml.draw!=null; out.push({key:'ml',outcomes:mlSides(g,th).filter(sd=>o.ml[sd]!=null).map(sd=>bt(sd==='draw'?'Empate':g[sd].name,o.ml[sd],'ml',sd))}); }
  const T=o.total; if(T&&T.over&&T.under) out.push({key:'total',outcomes:[bt('Más de '+T.over.line,T.over.price,'total','over',T.over.line),bt('Menos de '+T.under.line,T.under.price,'total','under',T.under.line)]});
  const S=o.spread; if(S&&S.home&&S.away) out.push({key:'spread',outcomes:sides(g).map(sd=>bt(g[sd].name+' '+(S[sd].line>0?'+':'')+S[sd].line,S[sd].price,'spread',sd,S[sd].line))});
  const B=o.btts; if(B&&(B.yes!=null||B.no!=null)) out.push({key:'btts',outcomes:[bt('Sí',B.yes,'btts','yes'),bt('No',B.no,'btts','no')].filter(x=>x.best)});
  return out.filter(m=>m.outcomes.length);
}
function mkDec(a){ return a==null?null:(a>0?1+a/100:1+100/(-a)); }
function mkAltLines(d, key){
  const books=(d.market&&d.market.books)||[];
  const map=new Map();
  const put=(line,side,price,book,label)=>{
    if(line==null||price==null||side==null) return;
    const k=Number(line); if(!Number.isFinite(k)) return;
    const rec=map.get(k)||{line:k, by:{}};
    const cur=rec.by[side];
    if(!cur||price>cur.price) rec.by[side]={price, book, label};
    map.set(k, rec);
  };
  const sidePrice=(blk,sd)=>{
    if(!blk) return null;
    if(typeof blk[sd]==='number') return {price:blk[sd], line:blk.line};
    const o=blk[sd]; if(!o) return null;
    return {price:o.price, line:o.line!=null?o.line:blk.line};
  };
  for(const b of books){
    const blk=b[key]||(b.odds&&b.odds[key]); if(!blk) continue;
    const name=b.name||b.book||'';
    if(key==='total'||key==='corners'||key==='stotal'){
      for(const sd of ['over','under']){ const x=sidePrice(blk,sd); if(x) put(x.line,sd,x.price,name,(sd==='over'?'Más de ':'Menos de ')+x.line); }
    } else if(key==='spread'||key==='sspread'){
      for(const sd of sides(d.game)){ const x=sidePrice(blk,sd); if(x) put(x.line,sd,x.price,name,d.game[sd].name+' '+(x.line>0?'+':'')+x.line); }
    }
  }
  return [...map.values()].sort((a,b)=>a.line-b.line);
}
function mkLeg(g,o,official){
  const pr=o.best&&o.best.price!=null?o.best.price:o.price;
  if(pr==null) return null;
  return {kind:'game', league:g.league, eid:String(g.id), sport:g.sport, start_ts:Math.round(Date.parse(g.date)/1000),
    home:g.home.name, away:g.away.name, home_id:String(g.home.id||''), away_id:String(g.away.id||''),
    market:String(o.market||'').toLowerCase(), selection:o.side, line:o.line??null, odds:pr,
    label:obLabel(o,g), p:o.p_final??null, official:!!official};
}
function marketBlocks(d){
  const g=d.game, P=d.probs, l=d.picks&&d.picks.lean;
  let mk=(P&&P.markets||[]).filter(m=>m.outcomes&&m.outcomes.length);
  let fb=false; if(!mk.length){ mk=mkFromOdds(d); fb=mk.length>0; }
  if(!mk.length) return '';
  mk=mk.slice().sort((a,b)=>(MK_ORDER[a.key]??9)-(MK_ORDER[b.key]??9));
  const isPick=o=>l&&String(o.market||'').toLowerCase()===String(mktKey(l)).toLowerCase()&&o.side===l.side&&(l.line==null||o.line==null||Number(o.line)===Number(l.line));
  const order = (arr, key)=>{
    if(key==='ml'||key==='spread'||key==='sspread'){ const th=arr.length===3; const ord=mlSides(g,th); return arr.slice().sort((a,b)=>ord.indexOf(a.side)-ord.indexOf(b.side)); }
    if(key==='total'||key==='corners'||key==='stotal') return arr.slice().sort((a,b)=>(a.side==='over'?0:1)-(b.side==='over'?0:1));
    if(key==='btts') return arr.slice().sort((a,b)=>(a.side==='yes'||a.side==='si'?0:1)-(b.side==='yes'||b.side==='si'?0:1));
    return arr;
  };
  const evOf=o=>{
    if(o.ev!=null) return o.ev;
    const pr=o.best&&o.best.price!=null?o.best.price:o.price, dec=mkDec(pr);
    return (o.p_final!=null&&dec)?(o.p_final*dec-1):null;
  };
  const btn=o=>{
    const pk=isPick(o), v=o.edge!=null&&o.edge>=3, rr=recFor(String(o.market||'').toLowerCase(),o.side,o.line);
    const pr=o.best&&(o.best.price_txt||(o.best.price!=null?am(o.best.price):null));
    const ev=evOf(o);
    const bits=[];
    if(o.p_final!=null) bits.push(pct(o.p_final,0));
    if(ev!=null) bits.push((ev>=0?'+':'')+(ev*100).toFixed(0)+'% EV');
    else if(pk&&o.edge!=null) bits.push(sg(o.edge)+' pp');
    const book=o.best&&(o.best.book||'');
    const title=[pr?('Mejor cuota '+pr):'', book?('en '+book):'', o.best&&o.best.n_books>1?(o.best.n_books+' casas'):''].filter(Boolean).join(' · ');
    const leg=mkLeg(g,o,pk);
    let id='';
    if(leg&&typeof tkBtn==='function'){ id='t'+(++TK.n); TK.reg[id]=leg; }
    const on=leg&&TK.legs&&TK.legs.some(x=>tkKey(x)===tkKey(leg));
    const aria=`${obLabel(o,g)}${pr?' '+pr:''}${pk?' (pick NRNM)':''}${book?' · '+book:''}`;
    return `<button type="button" class="ob ${pk?'pick':''} ${v?'val':''} ${on?'on':''}" ${id?`data-tk="${id}"`:''} ${id?'':'disabled'} aria-label="${esc(aria)}" aria-pressed="${on?'true':'false'}" ${title?`title="${esc(title)}"`:''}><span class="ol">${esc(obLabel(o,g))}</span>${pk?'<span class="ob-pk">PICK</span>':''}<span class="or"><span class="oq mono">${esc(pr||'—')}</span>${bits.length?`<span class="op">${bits.join(' · ')}</span>`:''}</span></button>`;
  };
  const grid=(os,key)=>{
    const n = key==='ml'&&os.length===3 ? 3 : (os.length===1?1:2);
    return `<div class="ob-g n${n}">${os.map(btn).join('')}</div>`;
  };
  const lineKey=o=>o.line==null?'':String(o.line);
  const blocks=mk.map(m=>{
    let os=order(m.outcomes, m.key);
    const alts=(m.key==='total'||m.key==='spread'||m.key==='corners')?mkAltLines(d,m.key):[];
    const groups=new Map();
    os.forEach(o=>{ const k=lineKey(o); if(!groups.has(k)) groups.set(k,[]); groups.get(k).push(o); });
    if(alts.length>1){
      alts.forEach(al=>{
        const k=String(al.line);
        if(groups.has(k)) return;
        const outs=Object.keys(al.by).map(sd=>{
          const x=al.by[sd];
          return {label:x.label, market:m.key, side:sd, line:al.line, p_final:null, best:{price:x.price, price_txt:am(x.price), book:x.book}};
        });
        groups.set(k, order(outs, m.key));
      });
    }
    const keys=[...groups.keys()];
    const stacked = m.key==='corners' || m.key==='corner' || (keys.length>1 && m.key!=='total');
    const slider = m.key==='total' && keys.filter(k=>k!=='').length>1;
    let body='';
    if(slider){
      const lines=keys.filter(k=>k!=='').sort((a,b)=>Number(a)-Number(b));
      const main=os[0]&&os[0].line!=null?String(os[0].line):lines[0];
      body=`<div class="mk-sl" data-lines="${esc(lines.join(','))}"><button type="button" data-dir="-1" aria-label="Línea anterior">‹</button><span class="mk-sl-val">${esc(main)}</span><button type="button" data-dir="1" aria-label="Línea siguiente">›</button></div>`+
        lines.map(k=>`<div class="ob-g n2" data-line="${esc(k)}" ${k===main?'':'hidden'}>${groups.get(k).map(btn).join('')}</div>`).join('');
    } else if(stacked && keys.length>1){
      body=keys.sort((a,b)=>Number(a)-Number(b)).map(k=>grid(groups.get(k), m.key)).join('');
    } else {
      body=grid(os, m.key);
    }
    const sid='mk-'+m.key;
    return `<div class="mkb" data-k="${esc(m.key)}"><div class="mkb-h"><button type="button" class="mkb-tog" aria-expanded="true" aria-controls="${sid}"><span class="mkb-t">${esc(mkTitle(m,g))}</span><i class="mkb-ch" aria-hidden="true"></i></button><button type="button" class="mkb-star" aria-label="Marcar mercado favorito" aria-pressed="false">★</button></div><div class="mkb-b" id="${sid}">${body}</div></div>`;
  }).join('');
  return `<div class="card mkc"><h2>Mercados</h2>${blocks}<div class="sub mkn">${fb?'Cuotas de ESPN. ':''}Cuota = mejor precio disponible (toca una casilla para ver la casa y agregar al ticket). % = probabilidad final${P&&P.markets&&P.markets.length?' (modelo + mercado)':''}; EV cuando hay precio y prob.</div></div>`;
}
function mkBind(){
  const root=document.getElementById('app'); if(!root) return;
  root.querySelectorAll('.mkb-tog').forEach(b=>{
    b.onclick=()=>{ const box=b.closest('.mkb'); const off=box.classList.toggle('off'); b.setAttribute('aria-expanded', off?'false':'true'); };
  });
  root.querySelectorAll('.mkb-star').forEach(b=>{
    const key=(b.closest('.mkb')||{}).dataset&&b.closest('.mkb').dataset.k;
    let favs=[]; try{ favs=JSON.parse(localStorage.getItem('nrnm_mk_star')||'[]'); }catch(e){}
    if(key&&favs.includes(key)) b.setAttribute('aria-pressed','true');
    b.onclick=e=>{
      e.stopPropagation();
      const on=b.getAttribute('aria-pressed')!=='true';
      b.setAttribute('aria-pressed', on?'true':'false');
      try{
        let s=JSON.parse(localStorage.getItem('nrnm_mk_star')||'[]');
        if(on){ if(key&&!s.includes(key)) s.push(key); } else s=s.filter(x=>x!==key);
        localStorage.setItem('nrnm_mk_star', JSON.stringify(s));
      }catch(err){}
    };
  });
  root.querySelectorAll('.mk-sl').forEach(sl=>{
    const rows=[...sl.parentElement.querySelectorAll('.ob-g[data-line]')];
    if(!rows.length) return;
    let i=rows.findIndex(r=>!r.hidden); if(i<0) i=0;
    const val=sl.querySelector('.mk-sl-val');
    const show=()=>{ rows.forEach((r,j)=>r.hidden=j!==i); if(val) val.textContent=rows[i].dataset.line; };
    sl.querySelectorAll('button[data-dir]').forEach(btn=>{
      btn.onclick=()=>{ i=(i+Number(btn.dataset.dir)+rows.length)%rows.length; show(); };
    });
    show();
  });
}

function injHeroTags(d){
  const f=d.injuries_full, g=d.game; if(!f||f.tennis||!f.sides) return '';
  const tags=[];
  for(const s of ['away','home']){
    const entries=(f.sides[s]&&f.sides[s].entries)||[];
    const outs=entries.filter(e=>e.bucket==='out'||e.key);
    const n=outs.length, T=g[s]||{};
    if(n) tags.push(`<span class="cchip c-warn">${esc(T.abbr||T.short||T.name||s)}: ${n} baja${n>1?'s':''}${outs[0]&&outs[0].name?' · '+esc(outs[0].name):''}</span>`);
  }
  return tags.join(' ');
}
async function viewGame(league, id, silent){
  if(!silent) $app.innerHTML = gameSkel();
  let d;
  try{ d = await api(`/api/game/${encodeURIComponent(league)}/${id}`); }
  catch(e){
    if(!silent && location.hash.startsWith('#/juego/')){
      $app.innerHTML = errBox(e.message||'No se pudo analizar el partido.');
      const b=document.getElementById('retry'); if(b) b.onclick=()=>viewGame(league,id);
      return;
    }
    throw e;
  }
  if(!location.hash.startsWith('#/juego/')) return d;
  const g = d.game;
  const back = `<a class="back" href="#/deporte/${g.sport}/${encodeURIComponent(league)}">← ${esc(g.league_name)}</a>`;
  const live = g.state==='in';
  const sub=[g.note&&g.note!==g.league_name?g.note:'', g.venue, g.court, g.neutral&&d.kind!=='tennis'?'cancha neutral':'', g.weather&&!d.weather?`🌡️ ${g.weather.temp_f}°F`:''].filter(Boolean).map(esc).join(' · ');
  const hero = `<div class="card gh2"><div class="gh2-t"><span>${esc(g.league_name)}</span>${stBadge(g)}</div>
    <div class="hero">${heroSide(g,d,sides(g)[0])}<div class="hmid">${heroMid(g,d)}</div>${heroSide(g,d,sides(g)[1])}</div>
    ${sub?`<div class="sub hsub">${sub}</div>`:''}${g.wd?`<div class="sub hsub">⚠️ ${esc(g.wd)}</div>`:''}
    ${(restTags(d)||injHeroTags(d))?`<div class="hsub">${restTags(d)||''} ${injHeroTags(d)||''}</div>`:''}<div class="hsub">${updTag(d.updated,live)}</div></div>`;
  REC_MAP = {}; (d.record||[]).forEach(r=>{ const k=r.market+'.'+r.selection; if(!REC_MAP[k]||REC_MAP[k].status==='ANULADO') REC_MAP[k]=r; }); PROV = d.prov||{};
  let html = back + hero + courtLive(d) + liveSection(d) + marketBlocks(d) + detailSections(d);
  // conserva scroll y acordeón de «En vivo» al refrescar en vivo; el estado de secciones/ⓘ/pestañas vive en DST
  const keyOf=c=>c.querySelector(':scope > h2').textContent.trim().slice(0,24);
  const st = silent ? {y:window.scrollY, open:[...document.querySelectorAll('#app > .fold')].map(c=>[keyOf(c), !c.classList.contains('closed')])} : null;
  $app.classList.add('gd');
  $app.innerHTML = html;
  mvDraw(); foldCards(); if(typeof mkBind==='function') mkBind(); if(typeof propsInit==='function') propsInit();
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
  let html=`<h1>📒 Récord</h1>${rdTabs('total')}${bkBox()}<div class="day" style="margin-top:4px">Total de la temporada (todo el historial)</div>
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

function capasOf(r){
  const l=r.lean||{}, conf=(r.confidence&&r.confidence.level)||l.conf_level||r.conf_level;
  const p=l.p_final!=null?l.p_final:(l.p||l.p_model);
  let evOk=false;
  if(p!=null && l.price!=null && typeof ev==='function') evOk = ev(p,l.price)>0;
  else if(l.ev!=null) evOk = l.ev>0;
  const confOk = conf==='Alta'||conf==='Media';
  let stab=null;
  const sig=l.signals||{};
  if(sig.verdict && sig.verdict!=='sin_dato'){
    stab = sig.verdict!=='en_contra';
  } else if(l.line_stable!=null) stab=!!l.line_stable;
  const items=[
    {ok:evOk, label:'EV'},
    {ok:confOk, label:conf?('Confianza '+conf):'Confianza'},
    {ok:stab, label: stab==null?'Estabilidad de línea: sin dato':'Estabilidad de línea'}
  ];
  const n=items.filter(i=>i.ok===true).length;
  return {n, of:3, items, txt:n+'/3'};
}
function evPct(l){
  const p=l.p_final!=null?l.p_final:(l.p||l.p_model);
  if(p!=null && l.price!=null && typeof ev==='function') return ev(p, l.price)*100;
  return l.ev;
}
function stakeLabel(l, bank){
  const p=l.p_final!=null?l.p_final:(l.p||l.p_model);
  const evv=evPct(l);
  if(evv==null) return 'Stake: sin dato';
  if(evv<=0) return 'no apostar';
  if(!bank||!bank.bankroll) return 'Stake: 1/4 Kelly';
  if(typeof stakePct==='function' && p!=null && l.price!=null){
    const remaining=Math.max(0, 0.08-(bank.daily_used_frac||0));
    const frac=Math.min(stakePct(p,l.price), remaining);
    if(frac<=0) return 'no apostar';
    const unit_size=bank.bankroll*((bank.unit_pct||1)/100);
    const units=unit_size? (bank.bankroll*frac)/unit_size : 0;
    return units.toFixed(2)+'u';
  }
  return 'Stake: 1/4 Kelly';
}
function capasChips(c){
  return `<div class="capas"><span class="capa on">${c.txt}</span>${c.items.map(i=>`<span class="capa ${i.ok===true?'on':''}">${esc(i.label)}</span>`).join('')}</div>`;
}

async function viewPicks(scope){
  const seq=ROUTE_SEQ;
  SPORTS = SPORTS || await api('/api/sports');
  if(seq!==ROUTE_SEQ) return;
  const alta=scope==='alta';
  const apiScope=alta?'72h':(scope||'hoy');
  loading('Calculando picks de todos los deportes (primera vez puede tardar ~20 s)…');
  const d = await api('/api/picks?scope='+apiScope);
  if(seq!==ROUTE_SEQ) return;
  if(alta) d.items=(d.items||[]).filter(r=>(r.confidence&&r.confidence.level)==='Alta'||r.conf_level==='Alta'||(r.lean&&r.lean.conf_level==='Alta'));
  const allItems=d.items||[];
  const published=allItems.filter(r=>r.published===true||r.published==null);
  const discarded=allItems.filter(r=>r.published===false);
  const tabs=[['hoy','Hoy'],['manana','Mañana'],['72h','72 h'],['alta','Alta confianza']];
  const t=`<div class="pills">${tabs.map(([k,l])=>`<a class="pill ${k===scope?'on':''}" href="#/picks/${k}">${l}</a>`).join('')}</div>`;
  const withOdds=published.filter(r=>r.has_odds&&r.status!=='PASS'&&r.status!=='REVISAR');
  const card=r=>{ const l=r.lean||{}, g=r.game, rev=r.status==='REVISAR'||l.divergence_high;
    const cap=capasOf(r), evv=evPct(l), stak=stakeLabel(l,BK());
    const conf=(r.confidence&&r.confidence.level)||l.conf_level;
    const href=`#/juego/${encodeURIComponent(g.league)}/${g.id}`;
    if(rev){
      const xm=l.p_model_raw!=null?l.p_model_raw:l.p_model, ym=l.p_nv;
      const note=(xm!=null&&ym!=null)?`Divergencia alta: modelo ${pct(xm)} vs mercado ${pct(ym)}`:'Divergencia alta: modelo vs mercado';
      return `<a class="card pk pk-card revisar" href="${href}"><div class="pk-l"><div class="pkt">Revisar · ${esc(l.label||'')}</div>
        <div class="sub">${esc(g.league_name||'')} · ${matchup(g)} · ${fmtShort(g.date)} ${fmtTime(g.date)} CDMX</div>
        ${capasChips(cap)}<div class="div-note">${esc(note)}</div></div></a>`;
    }
    const evTxt=evv==null?SD:((evv>0?'+':'')+evv.toFixed(1)+'%');
    return `<a class="card pk pk-card" href="${href}"><div class="pk-l"><div class="pkt">${esc(l.label||'')} <span class="mono">${l.price_txt?esc(l.price_txt):''}</span></div>
      <div class="sub">${esc(g.league_name||'')} · ${matchup(g)} · ${fmtShort(g.date)} ${fmtTime(g.date)} CDMX</div>
      ${capasChips(cap)}<div class="sub">${esc(conf?('Confianza '+conf):'')} · ${esc(stak)}</div>
      ${l.price!=null&&r.has_odds?`<div class="tkrow">${tkBtn(tkLegFromCand(g,Object.assign({official:r.status==='PICK'},l)),'Agregar al ticket')}</div>`:''}</div>
      <div class="pk-ev ${evv>0?'pos':evv<0?'neg':'mut'}">${evTxt}</div></a>`; };
  const featOf=()=>{
    const pool=published.filter(r=>r.has_odds&&r.status!=='REVISAR'&&r.status!=='PASS'&&r.status!=='SIN_LINEA'&&!(r.lean&&r.lean.divergence_high));
    if(!pool.length) return '';
    const r=pool[0]; // ya vienen ordenados por EV y confianza
    const l=r.lean||{}, g=r.game, cap=capasOf(r), evv=evPct(l), stak=stakeLabel(l,BK());
    const conf=(r.confidence&&r.confidence.level)||l.conf_level;
    const title=(scope==='hoy'||!scope)?'Mejor pick de hoy':'Mejor pick';
    const evTxt=evv==null?SD:((evv>0?'+':'')+evv.toFixed(1)+'%');
    const edgeTxt=l.edge==null?SD:(sg(l.edge)+' pp');
    return `<div class="card pk-feat"><div class="feat-k">${title}</div>
      <p class="feat-title">${esc(l.label||'')} <span class="mono">${l.price_txt?esc(l.price_txt):''}</span></p>
      <div class="sub">${esc(g.league_name||'')} · ${matchup(g)} · ${fmtShort(g.date)} ${fmtTime(g.date)} CDMX</div>
      <div class="pk-nums"><div class="pc"><small>Edge pp</small><b class="mono">${esc(edgeTxt)}</b></div>
        <div class="pc"><small>EV %</small><b class="mono ${evv>0?'pos':evv<0?'neg':''}">${evTxt}</b></div>
        <div class="pc"><small>Stake u</small><b class="mono">${esc(stak)}</b></div></div>
      ${capasChips(cap)}<div class="sub">${esc(conf?('Confianza '+conf):'Confianza: sin dato')} · ${cap.items[2].ok==null?'Estabilidad de línea: sin dato':(cap.items[2].ok?'Línea estable':'Línea inestable')}</div>
      ${l.price!=null?`<div class="tkrow">${tkBtn(tkLegFromCand(g,Object.assign({official:r.status==='PICK'},l)),'Agregar al ticket')}</div>`:''}
      <div class="sub"><a href="#/juego/${encodeURIComponent(g.league)}/${g.id}">Ver juego →</a></div></div>`;
  };
  const compact=`<section class="hm" id="pk-search"><label class="srch"><span class="ico" aria-hidden="true">🔍</span><input type="search" inputmode="search" enterkeyhint="search" autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="Buscar juego, equipo, jugador o torneo" aria-label="Buscar"></label><div class="srch-r" hidden></div></section>`;
  let html=`${compact}<h1>Picks</h1>${t}<p class="ago">${esc(agoTxt(d.generated||d.ts||d.now))}</p>`;
  html+=featOf();
  if(!published.length) html+=`<div class="card mut">${scope==='hoy'?'Hoy no hay pick principal (el filtro pidió al menos 4 señales a favor, EV&gt;0 y confianza Media/Alta).':'No hay pick principal en esta ventana.'}</div>`;
  else if(!withOdds.length && !published.some(r=>r.status==='REVISAR')) html+=`<div class="card mut">${scope==='hoy'?'Hoy no hay pick':'No hay pick en esta ventana.'}</div>`;
  const rank=r=>r.has_odds?(r.status==='PASS'?1:0):2;
  PICK_GROUPS.forEach(k=>{
    const its=published.filter(r=>r.game.sport===k).map((r,i)=>[r,i]).sort((a,b)=>rank(a[0])-rank(b[0])||a[1]-b[1]).map(x=>x[0]);
    if(!its.length) return;
    const sp=(SPORTS||[]).find(x=>x.key===k)||{name:k,emoji:''}, nPick=its.filter(r=>r.has_odds&&r.status!=='PASS').length;
    html+=`<h2 class="pgrp" data-sport="${k}"><span class="em">${sp.emoji}</span> ${esc(sp.name)} <span class="n mono">${its.length}${nPick?` · ${nPick} con ventaja`:''}</span></h2>`+its.slice(0,30).map(card).join('');
  });
  if(discarded.length){
    const dcard=r=>{ const l=r.lean||{}, g=r.game;
      return `<a class="card pk pk-card mut" href="#/juego/${encodeURIComponent(g.league)}/${g.id}"><div class="pk-l"><div class="pkt">${esc(l.label||matchup(g))}</div>
        <div class="sub">${esc(g.league_name||'')} · ${matchup(g)} · ${fmtShort(g.date)} ${fmtTime(g.date)} CDMX</div>
        <div class="sub">${esc(r.discard_reason||'No publicado')}</div></div></a>`; };
    html+=`<details class="disc" id="pk-descartados"><summary>Ver todos / descartados <span class="disc-n mono">${discarded.length}</span></summary>${discarded.slice(0,80).map(dcard).join('')}</details>`;
  }
  if(seq!==ROUTE_SEQ) return;
  $app.innerHTML=html;
  if(typeof srchInit==='function'){ const s=document.getElementById('pk-search'); if(s) srchInit(s); }
  api('/api/home').then(h=>{
    const el=document.getElementById('pk-live'); if(!el||!h||!h.live||!h.live.length) return;
    el.hidden=false;
    const row=g=>{
      if(typeof liveRowHtml==='function') return liveRowHtml(g);
      const href=`#/juego/${encodeURIComponent(g.league)}/${encodeURIComponent(g.id||g.eid)}`;
      return `<a class="card" href="${href}">${esc((g.away&&(g.away.abbr||g.away.name))||'')} vs ${esc((g.home&&(g.home.abbr||g.home.name))||'')}</a>`;
    };
    el.innerHTML=`<h3>En vivo ahora <span class="badge b-live">${h.live.length}</span> <a class="more" href="#/inicio">Ver resumen →</a></h3>`+h.live.slice(0,8).map(row).join('');
  }).catch(()=>{});
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
const PAL=['#3C85F7','#06AAC4','#FF1179','#F5B942','#7f8b9c','#06AAC4','#e6ebf2','#FF1179','#94a3b8','#3C85F7','#34d399'];
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
  $app.innerHTML=`<h1>Método</h1>
  <div class="card"><p>NRNM mezcla el modelo con el mercado sin vig (peso del modelo hasta 50%, recorte ±20 pp). El edge es la diferencia en puntos porcentuales; el EV se calcula con el precio real y es lo que se muestra. Si un dato no está, se indica «Sin dato»: nunca se inventa.</p></div>
  <details class="card kv" open><summary>Probabilidad final</summary>
    <p>pFinal = w · modelo recortado + (1−w) · mercado s/vig. El peso w crece con los juegos de muestra (n0 = 100) y no supera el 50%. El modelo se recorta a ±20 pp del mercado. Se publica el pick con alineación confirmada, 60 a 90 minutos antes, y se guarda la cuota de publicación y la de cierre para el CLV.</p></details>
  <details class="card kv"><summary>Edge y EV</summary>
    <p>Edge = probabilidad final − probabilidad sin vig, en pp. El EV se calcula con el precio real (p · momio decimal − 1) y es lo que aparece en las tarjetas. Los picks se ordenan por EV y confianza, no por edge. Estados: PICK (edge ≥ 3 pp, EV ≥ 0, confianza media o alta), LEAN (edge ≥ 1 pp), PASS, REVISAR (divergencia de más de 10 pp entre modelo y mercado).</p></details>
  <details class="card kv"><summary>Casas y consenso</summary>
    <p>Se muestra el mejor precio disponible y el EV en cada casa («compra el mejor»). Fuentes públicas: ESPN, Action Network, Pinnacle, MLB StatsAPI y Open-Meteo, más el historial propio de líneas. Sin llave de API de pago. Si una casa no cotiza, se indica que no hay dato.</p></details>
  <details class="card kv"><summary>RLM y dinero</summary>
    <p>STEAM: el consenso se mueve ≥ 3 pp, al menos 3 casas en la misma dirección (≥ 2 pp) en una ventana de 180 min. RLM: el consenso de ese lado sube ≥ 3 pp y el % de tickets de ese lado es ≤ 45% (el público está del otro lado). Si no hay % de tickets, no se etiqueta RLM. CASA REZAGADA: una casa queda ≥ 2 pp de implícita peor/mejor que la mediana (precio mejor que el consenso). Solo se listan movimientos de 3 pp o más.</p></details>
  <details class="card kv"><summary>Confianza</summary>
    <p>La confianza (Alta / Media / Baja) combina tamaño de muestra, divergencia frente al mercado, lesiones clave y si hay abridores confirmados. Stake: ¼ Kelly, tope 2% del bankroll por pick y 8% de exposición diaria; si EV ≤ 0, «no apostar». 1u = 1% del bankroll (configurable). Evitar piernas correlacionadas del mismo juego. Los tickets se califican solos con el marcador final.</p></details>
  <div class="card" style="border-color:var(--amb);margin-top:12px"><b>Límite del modelo.</b> El modelo no ve lesiones de último minuto ni descansos. Un pick en REVISAR no se promociona: hay que esperar o no apostar.</div>
  <p class="fine ctr metodo-note">Paper trading / estimaciones, no garantía.</p>`;
}


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

// barra de la versión en línea: hora de los datos + link local (.local estable; IP de lan.json /api/lan)
async function refreshLocalUrl(){
  // Preferir siempre .local (estable). lan.json /api/lan solo aportan la IP de respaldo.
  try{
    const embedded = (window.NRNM_STATIC && window.NRNM_STATIC.lan) || null;
    if(embedded) window.__NRNM_LAN = embedded;
    if(STATIC){
      const r = await fetch('data/lan.json', {cache:'no-cache'});
      if(r.ok){ const j = await r.json(); window.__NRNM_LAN = Object.assign({}, window.__NRNM_LAN||{}, j); }
    }
  }catch(e){}
  if(window.__NRNM_LAN && window.__NRNM_LAN.url_local) LOCAL_URL = window.__NRNM_LAN.url_local;
  // Si el iPhone/PC está en la misma Wi‑Fi, confirmar que el servidor vive (http desde Pages puede fallar por mixed content; no pasa nada)
  try{
    const probe = (window.__NRNM_LAN && window.__NRNM_LAN.url_ip) || LOCAL_URL;
    const ac = new AbortController(); const t = setTimeout(()=>ac.abort(), 2500);
    const r = await fetch(probe + '/api/lan', {signal:ac.signal}); clearTimeout(t);
    if(r.ok){ const j = await r.json(); window.__NRNM_LAN = j; if(j.url_local) LOCAL_URL = j.url_local; }
  }catch(e){}
}
if(STATIC){ try{ const b=document.createElement('div'); b.className='stbar';
  const dt=new Intl.DateTimeFormat('es-MX',{timeZone:TZ,day:'numeric',month:'short',hour:'2-digit',minute:'2-digit',hour12:true}).format(new Date(window.NRNM_STATIC.built));
  const paint = ()=>{
    const lan = window.__NRNM_LAN || (window.NRNM_STATIC && window.NRNM_STATIC.lan) || {};
    const ip = lan.url_ip ? ` · <a href="${esc(lan.url_ip)}">${esc((lan.ip||'')+':8765')}</a>` : '';
    b.innerHTML=`🌐 Versión en línea · datos de ${esc(dt)} (CDMX) · se actualizan cada ~10-15 min · <a href="${LOCAL_URL}">link local (en vivo)</a>${ip}`;
  };
  paint();
  document.querySelector('header').after(b);
  refreshLocalUrl().then(paint).catch(()=>{});
}catch(e){} }
