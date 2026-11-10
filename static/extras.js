/* Piezas nuevas: en vivo, lesiones, clima, alineaciones, resumen del día y auto-actualización.
   Se carga antes que app.js; usa sus ayudantes (esc, fmtTime, pct…) sólo cuando se llaman. Todo dato viene del servidor (ESPN / Open-Meteo): si falta algo se muestra "Sin dato". */
const fmtHMS = t => new Intl.DateTimeFormat('es-MX',{timeZone:'America/Mexico_City',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:true}).format(new Date(t*1000));
const fmtDM = t => new Intl.DateTimeFormat('es-MX',{timeZone:'America/Mexico_City',day:'numeric',month:'short'}).format(new Date(typeof t==='number'?t*1000:t));
const fmtDMH = t => new Intl.DateTimeFormat('es-MX',{timeZone:'America/Mexico_City',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit',hour12:true}).format(new Date(typeof t==='number'?t*1000:t));
const updTag = (ts,live) => ts ? `<span class="upd sub mono" id="upd" title="Hora de la última consulta a las fuentes">${live?'<i class="dot"></i>':''}${esc(typeof agoTxt==='function'?agoTxt(ts):('Actualizado '+fmtHMS(ts)+' CDMX'))}${live?' · auto cada 25 s':''}</span>` : '';

// ---------- auto-actualización (pausa si la pestaña está oculta)
const Live = {t:null, fn:null,
  start(fn, ms){ this.stop(); this.fn=fn; this.t=setInterval(()=>{ if(!document.hidden) fn(); }, ms||25000); },
  stop(){ if(this.t) clearInterval(this.t); this.t=null; this.fn=null; } };
document.addEventListener('visibilitychange', ()=>{ if(!document.hidden && Live.fn) Live.fn(); });

// ---------- piezas de la tarjeta de lista
const provBadge = (prov, market, sel) => {
  const p = prov && prov[market+'.'+sel]; if(!p) return '';
  const t = p.state==='ganando' ? ['p-w','▲ Ganando ahora'] : p.state==='perdiendo' ? ['p-l','▼ Perdiendo ahora'] : ['p-p','＝ Empatando ahora'];
  return `<span class="pbadge ${t[0]}" title="PROVISIONAL: con el marcador actual (${esc(p.score)}). ${p.locked?'Ya no puede cambiar por marcador, pero ':''}No es el resultado final.">${t[1]}${p.locked?' 🔒':''}</span>`;
};
const injChip = g => { const i=g.inj; if(!i||g.state==='post') return '';
  const out=(i.home.out||0)+(i.away.out||0), dbt=(i.home.doubt||0)+(i.away.doubt||0), dtd=(i.home.dtd||0)+(i.away.dtd||0);
  if(!out&&!dbt&&!dtd) return '';
  const parts=[]; if(out) parts.push(`${out} baja${out>1?'s':''}`); if(dbt) parts.push(`${dbt} dud.`); if(!out&&!dbt&&dtd) parts.push(`${dtd} en duda leve`);
  return `<span class="cchip ${out?'c-out':'c-dtd'}" title="Lesionados reportados por ESPN (ambos equipos): ${out} baja(s), ${dbt} dudoso(s), ${dtd} día a día/cuestionable">🩹 ${parts.join(' · ')}</span>`; };
const wxChip = w => { if(!w) return '';
  if(w.status==='techado') return `<span class="cchip">🏟️ Techado</span>`;
  if(w.status!=='ok'&&w.status!=='retractil') return '';
  const wind = w.wind_kmh!=null ? ` · 💨 ${Math.round(w.wind_kmh)} km/h${w.wind_from?' '+esc(w.wind_from):''}` : '';
  const rain = w.precip_prob!=null && w.precip_prob>=30 ? ` · 🌧️ ${Math.round(w.precip_prob)}%` : '';
  return `<span class="cchip ${w.warn?'c-warn':''}" title="Clima en el estadio a la hora del juego (Open-Meteo)${w.roof==='retractil'?' · techo retráctil':''}">${w.icon||''} ${w.temp_c!=null?Math.round(w.temp_c)+'°C':''}${wind}${rain}${w.roof==='retractil'?' · retráctil':''}</span>`; };
const liveLine = g => { if(g.state!=='in') return '';
  const l=g.live||{}; return l.situation&&l.situation.text?`<div class="lvl"><span class="lv-sit">${esc(l.situation.text)}</span></div>`:''; };

// ---------- detalle: en vivo / estadísticas
const PLAY_ICON = {goal:'⚽','yellow-card':'🟨','red-card':'🟥','penalty-goal':'⚽'};
function periodLabels(g, n){
  const s=g.sport, out=[];
  for(let i=1;i<=n;i++){
    if(s==='nba'||s==='nfl') out.push(i<=4?'Q'+i:(i===5?'TE':'TE'+(i-4)));
    else if(s==='nhl') out.push(i<=3?'P'+i:(i===4?'TE':'SO'));
    else if(s==='futbol') out.push(i===1?'1T':i===2?'2T':'TE'+(i-2));
    else out.push(String(i));
  }
  return out;
}
function lineTable(d){
  const g=d.game, L=d.live; let A=null,H=null;
  if(d.kind==='tennis'){ A=g.away.sets; H=g.home.sets; }
  else if(L.linescores){ A=L.linescores.away; H=L.linescores.home; }
  if(!A||!H||!A.length) return '';
  const n=Math.max(A.length,H.length), lab=d.kind==='tennis'?Array.from({length:n},(_,i)=>'S'+(i+1)):periodLabels(g,n);
  const cell=(a,i)=>`<td class="mono">${a[i]==null?'':esc(a[i])}</td>`;
  const row=(t,a,tot)=>`<tr><td>${esc(t.abbr||t.short||t.name)}</td>${Array.from({length:n},(_,i)=>cell(a,i)).join('')}${tot==null?'':`<td class="mono tot">${esc(tot)}</td>`}</tr>`;
  const T=d.kind==='tennis'?false:true;
  return `<div class="tbl"><table class="ls"><thead><tr><th></th>${lab.map(x=>`<th>${x}</th>`).join('')}${T?'<th>T</th>':''}</tr></thead><tbody>${sides(g).map(sd=>sd==='away'?row(g.away,A,T?g.away.score:null):row(g.home,H,T?g.home.score:null)).join('')}</tbody></table></div>`;
}
function statRows(d){
  const g=d.game, S=(d.live&&d.live.stats)||[]; if(!S.length) return ''; const [f1,f2]=sides(g);
  const nv=x=>{ const v=parseFloat(String(x).replace(/[^0-9.\-]/g,'')); return isNaN(v)?null:v; };
  return `<div class="cmpst"><div class="cmph"><span>${esc(g[f1].abbr||g[f1].short)}</span><span></span><span>${esc(g[f2].abbr||g[f2].short)}</span></div>${S.map(r=>{
    const a=nv(r[f1]), h=nv(r[f2]), tot=(a!=null&&h!=null&&a+h>0)?a+h:null, pa=tot?Math.round(a/tot*100):50;
    return `<div class="cmpr"><span class="v mono ${tot&&a>h?'lead':''}">${esc(r[f1]??SD)}</span><span class="l">${esc(r.label)}</span><span class="v mono ${tot&&h>a?'lead':''}">${esc(r[f2]??SD)}</span>${tot?`<div class="cb"><i style="width:${pa}%"></i></div>`:''}</div>`; }).join('')}</div>`;
}
function topRows(d){
  const T=d.live&&d.live.top; if(!T) return '';
  const g=d.game, one=(t)=>{ const rows=T[t.id]||[]; if(!rows.length) return '';
    return `<div><div class="sub"><b>${esc(t.name)}</b> · mejores del juego</div>${rows.map(r=>`<div class="row"><span>${esc(r.name)}</span><span class="mono">${r.pts} pts${r.reb!=null?` · ${esc(r.reb)} reb`:''}${r.ast!=null?` · ${esc(r.ast)} ast`:''}</span></div>`).join('')}</div>`; };
  const x=sides(g).map(sd=>one(g[sd])).join(''); return x?`<div class="two" style="margin-top:12px">${x}</div>`:'';
}
function liveSection(d){
  const L=d.live, g=d.game; if(!L) return '';
  const live=g.state==='in';
  const sit=L.situation;
  const plays=(L.plays||[]).slice(0,6);
  const body = `<div class="lv-st"><span class="lv-clock mono">${esc(L.text||g.status||'')}</span>${sit?`<span class="lv-sit">${esc(sit.text)}</span>`:''}</div>
    ${lineTable(d)}${statRows(d)}${topRows(d)}
    ${plays.length?`<div class="tt sub" style="margin-top:12px">${g.state==='in'?'Últimas jugadas':'Jugadas clave / finales'}</div><ul class="plays">${plays.map(p=>`<li class="${p.scoring?'sc':''}"><span class="mono ck">${esc(p.clock||'')}${p.period?` · ${esc(p.period)}`:''}</span><span>${PLAY_ICON[p.kind]||(p.scoring?'🔹':'')} ${esc(p.text.length>190?p.text.slice(0,187)+'…':p.text)}${p.score?` <span class="mono sub">(${esc(p.score)})</span>`:''}</span></li>`).join('')}</ul><div class="sub">Texto de las jugadas tal como lo publica ESPN (en inglés).</div>`:''}
    ${!(L.stats||[]).length&&!lineTable(d)&&!plays.length?`<div class="mut">ESPN aún no publica estadísticas de este juego (${SD}).</div>`:''}`;
  return `<div class="card ${live?'hot':''}" style="margin-top:10px"><h2>📡 ${live?'En vivo':'Marcador y estadísticas'} ${live?'<span class="badge b-live">● EN VIVO</span>':'<span class="badge b-fin">FINAL</span>'}</h2>${body}</div>`;
}

// ---------- detalle: alineaciones
const LS_BADGE = {confirmado:['b-ok','✅ CONFIRMADA'], proyectado:['b-prob','❓ PROYECTADA'], sin_publicar:['b-fin','Sin publicar'], profundidad:['b-prob','Depth chart']};
function lineupSide(T, S, d, side){
  if(!S) return `<div class="mut">${esc(T.name)}: ${SD}</div>`;
  const b=LS_BADGE[S.status]||LS_BADGE.sin_publicar;
  const retIds=new Set(((d.injuries_full&&d.injuries_full.sides&&d.injuries_full.sides[side]&&d.injuries_full.sides[side].returning)||[]).map(r=>r.id));
  const tag=p=>`${p.inj?` <span class="cchip c-out" title="Aparece en el reporte de lesiones de ESPN">⚠️ ${esc(p.inj)}</span>`:''}${retIds.has(p.id)?' <span class="cchip c-ret">🔁 regresa</span>':''}`;
  let h=`<div><div class="ih"><b>${esc(T.name)}</b><span class="badge ${b[0]}">${b[1]}</span>${S.formation?`<span class="cchip">${esc(S.formation)}</span>`:''}</div>`;
  if(S.status==='proyectado') h+=`<div class="sub" style="margin-bottom:4px">Proyección: titulares del último juego terminado (${esc(fmtDM(S.from_date))}). No es la alineación oficial.</div>`;
  if(S.status==='sin_publicar') h+=`<div class="mut">ESPN aún no publica la alineación (${SD}).</div>`;
  if(S.status==='profundidad'){
    const blocks=(S.depth||[]); if(!blocks.length) h+=`<div class="mut">${SD}</div>`;
    blocks.forEach((bk,i)=>{ const rows=bk.players.map(p=>`<div class="row"><span><span class="mono pos-t">${esc(p.pos)}</span> ${esc(p.name)}${tag(p)}</span>${p.backup?`<span class="sub">suplente: ${esc(p.backup)}</span>`:''}</div>`).join('');
      h+= i===0 ? `<div class="sub" style="margin-top:6px">${bk.side}</div>${rows}` : `<div class="gp"><div class="tg" role="button" tabindex="0">${bk.side==='DEFENSA'?'Ver defensa':'Ver '+esc(bk.side)}</div><div class="sg">${rows}</div></div>`; });
  }
  if(S.pitcher&&!d.pitchers) h+=`<div class="row"><span>⚾ Abridor <b>${esc(S.pitcher.name)}</b> <span class="badge b-prob">PROBABLE</span></span><span class="sub">${esc(S.pitcher.line||'')}</span></div>`;
  if(S.goalie) h+=`<div class="row"><span>🥅 Portero <b>${esc(S.goalie.name)}</b>${tag(S.goalie)}</span><span class="sub">${S.status==='confirmado'?'titular':'abrió el último juego'}</span></div>`;
  if(S.players&&S.players.length) h+=S.players.map(p=>`<div class="row"><span>${p.order?`<span class="mono sub">${p.order}.</span> `:(p.jersey?`<span class="mono sub">#${esc(p.jersey)}</span> `:'')}${esc(p.name)}${tag(p)}</span><span class="sub">${esc(p.pos||'')}</span></div>`).join('');
  if(S.changes&&S.changes.length) h+=`<div class="chg"><b>🔄 Cambios${S.changes[0].vs==='proyectado'?' vs la proyección':' vs la foto anterior'}</b>${S.changes.map(c=>`<div>${c.enters?`<span class="pos">Entra ${esc(c.enters)}</span>${c.leaves?` por <span class="neg">${esc(c.leaves)}</span>`:''}`:`<span class="neg">Sale ${esc(c.leaves)}</span> (baja de último momento)`}${c.pos?` <span class="sub">${esc(c.pos)}</span>`:''}</div>`).join('')}${S.changes_since?`<div class="sub">Foto anterior: ${fmtDMH(S.changes_since)} CDMX</div>`:''}</div>`;
  return h+'</div>';
}
function lineupsSection(d){
  const L=d.lineups; if(!L||!L.sides) return '';
  const g=d.game, ttl = g.sport==='nhl'?'Porteros':g.sport==='mlb'?'Alineaciones y abridores':g.sport==='nfl'?'Profundidad de plantilla':'Alineaciones';
  const body=`<div class="two">${sides(g).map(sd=>lineupSide(g[sd],L.sides[sd],d,sd)).join('')}</div>${L.note?`<div class="fine">${esc(L.note)}</div>`:''}`;
  return ds('lin',ttl,body,{info:'Confirmada = publicada por ESPN · proyectada = deducida del último juego real, puede cambiar. Los cambios se comparan contra la foto anterior guardada por el servidor.'});
}

// ---------- descanso (filas para la tabla comparativa)
function restRows(d){
  const R=d.rest; if(!R||(!R.home&&!R.away)) return '';
  const fmt=r=>!r?SD:r.b2b?'<b class="neg">Back-to-back</b>':`${r.days} día${r.days===1?'':'s'}`;
  return `<tr><td>Descanso (días sin jugar)</td><td class="mono">${fmt(R.away)}</td><td class="mono">${fmt(R.home)}</td></tr><tr><td>Juegos en los últimos 7 días</td><td class="mono">${R.away?R.away.n7:SD}</td><td class="mono">${R.home?R.home.n7:SD}</td></tr>`;
}
const restTags = d => { const R=d.rest||{}, g=d.game; return ['away','home'].filter(s=>R[s]&&R[s].b2b).map(s=>`<span class="cchip c-warn">${esc(g[s].abbr||g[s].short)}: back-to-back</span>`).join(' '); };

// ---------- carrusel de juegos en vivo (inicio): UNA tarjeta a la vez, deslizable (scroll-snap). Se actualiza EN SITIO por data-gid para no perder la diapositiva actual
const carIdx = tr => Math.max(0, Math.min(tr.children.length-1, Math.round(tr.scrollLeft / (tr.clientWidth||1))));
function carSync(root){
  const tr=root.querySelector('.car-track'); if(!tr) return;
  const n=tr.children.length, i=carIdx(tr);
  root.querySelectorAll('.car-dots button').forEach((b,k)=>{ b.classList.toggle('on',k===i); b.setAttribute('aria-current',k===i?'true':'false'); });
  const c=root.querySelector('.car-n'); if(c) c.textContent=`${i+1}/${n}`;
}
function carGo(root,i){ const tr=root.querySelector('.car-track'); if(tr) tr.scrollTo({left:i*tr.clientWidth,behavior:'smooth'}); }
/* Parchea el carrusel con la lista nueva de juegos. Devuelve el gid visible. Si el conjunto de juegos no cambió sólo se reemplaza el contenido de cada tarjeta: el scroll no se toca. */
function carPatch(root, games){
  let car=root.querySelector('.car');
  if(!car){
    root.insertAdjacentHTML('beforeend','<div class="car"><div class="car-track" tabindex="0" aria-label="Juegos en vivo"></div></div><div class="car-nav"><div class="car-dots"></div><span class="car-n mono"></span></div>');
    car=root.querySelector('.car');
    const tr=car.querySelector('.car-track'); let raf=0;
    tr.addEventListener('scroll',()=>{ if(raf) return; raf=requestAnimationFrame(()=>{ raf=0; carSync(root); }); },{passive:true});
    root.querySelector('.car-dots').addEventListener('click',e=>{ const b=e.target.closest('button'); if(b) carGo(root,+b.dataset.i); });
  }
  const tr=car.querySelector('.car-track');
  const cur=tr.children[carIdx(tr)], curId=cur?cur.dataset.gid:null;
  const have=[...tr.children].map(x=>x.dataset.gid), want=games.map(g=>String(g.id));
  if(have.join()===want.join()){
    games.forEach((g,k)=>{ tr.children[k].innerHTML=liveRowHtml(g); });
  }else{
    const old={}; [...tr.children].forEach(x=>old[x.dataset.gid]=x);
    tr.innerHTML=games.map(g=>`<div class="car-slide" data-gid="${esc(g.id)}">${liveRowHtml(g)}</div>`).join('');
    const k=Math.max(0,want.indexOf(curId));
    tr.scrollLeft=k*tr.clientWidth;
    root.querySelector('.car-dots').innerHTML=games.map((g,j)=>`<button type="button" data-i="${j}" aria-label="Juego ${j+1} de ${games.length}"></button>`).join('');
    root.querySelector('.car-nav').classList.toggle('one',games.length<2);
  }
  carSync(root);
  const v=tr.children[carIdx(tr)]; return v?v.dataset.gid:null;
}

// ---------- buscador del inicio: juegos, equipos, jugadores (tenis), ligas y torneos (GET /api/search, con debounce y cancelación)
const srchWhen = x => x.state==='in' ? '<b class="srl">● En vivo</b>' : x.state==='post' ? 'Final' : `${esc(fmtShort(x.date))} ${esc(fmtTime(x.date))}`;
function srchHtml(r){
  const gl = x => `#/juego/${encodeURIComponent(x.league)}/${encodeURIComponent(x.id)}`;
  const parts = [];
  if(r.leagues.length) parts.push(`<div class="sr-h">Ligas y torneos</div>`+r.leagues.map(l=>`<a class="sr" href="#/deporte/${encodeURIComponent(l.sport)}/${encodeURIComponent(l.key)}"><span class="sr-em">${l.emoji}</span><div class="sr-t"><b>${esc(l.name)}</b><div class="sub">${esc(l.sub||'Liga')} · ${l.n} juego${l.n===1?'':'s'} cargado${l.n===1?'':'s'}</div></div><span class="sr-r sub">›</span></a>`).join(''));
  if(r.teams.length) parts.push(`<div class="sr-h">Equipos y jugadores</div>`+r.teams.map(t=>`<a class="sr" href="#/juego/${encodeURIComponent(t.league)}/${encodeURIComponent(t.game_id)}">${badge(t,30)}<div class="sr-t"><b>${esc(t.name)}</b><div class="sub">${esc(t.league_name||'')} · vs ${esc(t.opp||SD)}</div></div><span class="sr-r sub">${srchWhen(t)}</span></a>`).join(''));
  if(r.games.length) parts.push(`<div class="sr-h">Juegos</div>`+r.games.map(x=>{ const sd=sides({sport:x.sport});
    return `<a class="sr" href="${gl(x)}"><span class="sr-pair">${badge(x[sd[0]],24)}${badge(x[sd[1]],24)}</span><div class="sr-t"><b>${esc(x[sd[0]].name)}</b> <span class="vs">${x.sport==='futbol'?'vs':x.sport==='tenis'?'vs':'@'}</span> <b>${esc(x[sd[1]].name)}</b><div class="sub">${esc(x.league_name||'')}</div></div><span class="sr-r sub">${srchWhen(x)}</span></a>`; }).join(''));
  return parts.join('') || `<div class="sr-none">Sin resultados para «${esc(r.q)}».</div>`;
}
function srchInit(root){
  const inp=root.querySelector('input'), box=root.querySelector('.srch-r'); let tm=0, seq=0, ac=null;
  const run = async q=>{
    const me=++seq; if(ac) ac.abort(); ac=new AbortController();
    box.hidden=false; box.innerHTML='<div class="sr-none">Buscando…</div>';
    if(window.NRNM_STATIC){ box.innerHTML='<div class="sr-none">La búsqueda necesita el servidor: en la versión en línea entra por Deportes o usa el link local.</div>'; return; }
    try{
      const r = await fetch('/api/search?q='+encodeURIComponent(q),{signal:ac.signal}); if(!r.ok) throw new Error(r.statusText);
      const d = await r.json(); if(me!==seq) return;
      box.innerHTML = srchHtml(d);
    }catch(e){ if(me===seq && e.name!=='AbortError') box.innerHTML=`<div class="sr-none">${SD}: no se pudo buscar. Reintenta.</div>`; }
  };
  inp.addEventListener('input',()=>{ clearTimeout(tm); const q=inp.value.trim();
    if(q.length<2){ seq++; if(ac) ac.abort(); box.hidden=true; box.innerHTML=''; return; }
    tm=setTimeout(()=>run(q),250); });
  box.addEventListener('click',e=>{ if(e.target.closest('a')){ inp.blur(); } });
}

// ---------- navegación minimalista de deportes (inicio): emoji arriba, nombre abajo, sin cajas
const SNAV_ORDER = ['mlb','nfl','nba','nhl','futbol','tenis'];
const sportNavItem = s => `<a href="#/deporte/${s.key}" data-sp="${s.key}"><span class="em">${s.emoji}</span><span class="nm">${esc(s.name)}</span></a>`;

// ---------- resumen del día (inicio)
const liveRowHtml = g => {
  const pv = Object.values(g.prov||{}); const main=(g.rec||[]).find(r=>r.type==='main');
  const mp = main && provBadge(g.prov, main.market, main.selection);
  const t=(x)=>`<div class="lr-t">${badge(x,30)}<span class="nm">${esc(x.short||x.name)}</span><span class="sc mono">${x.score!=null&&x.score!==''?esc(x.score):(x.sets&&x.sets.length?esc(x.sets.join(' ')):'')}</span></div>`;
  return `<a class="card lrow" href="#/juego/${encodeURIComponent(g.league)}/${g.id}"><div class="lr-h"><span class="badge b-live">● ${esc((g.live&&g.live.text)||g.status||'EN VIVO')}</span><span class="sub">${esc(g.league_name)}</span></div>${sides(g).map(sd=>t(g[sd])).join('')}${g.live&&g.live.situation?`<div class="sub">${esc(g.live.situation.text)}</div>`:''}${mp?`<div style="margin-top:6px"><span class="sub">${esc(shortLbl(main.label,g))}</span> ${mp}</div>`:''}</a>`; };

async function viewHome(){
  SPORTS = SPORTS || await api('/api/sports');
  const today = new Intl.DateTimeFormat('es-MX',{timeZone:TZ,weekday:'long',day:'numeric',month:'long'}).format(new Date());
  $app.innerHTML = `<div class="hm-h"><div class="sub">${esc(today)} · CDMX</div><h1>Resumen del día</h1></div>
   <section class="hm" id="hm-live"><h3>En vivo ahora</h3><div class="skel">Buscando juegos en vivo…</div></section>
   <section class="hm" id="hm-search"><label class="srch"><span class="ico" aria-hidden="true">🔍</span><input type="search" inputmode="search" enterkeyhint="search" autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="Buscar juego, equipo o torneo" aria-label="Buscar juego, equipo, jugador o torneo"></label><div class="srch-r" hidden></div></section>
   <div class="hm snav" id="hm-sp" role="navigation" aria-label="Deportes">${SNAV_ORDER.map(k=>SPORTS.find(x=>x.key===k)).filter(Boolean).concat(SPORTS.filter(x=>!SNAV_ORDER.includes(x.key))).map(sportNavItem).join('')}</div>
   <section class="hm" id="hm-rec"><h3>Récord acumulado <a href="#/record" class="more">Ver día →</a></h3><div class="skel">Cargando récord…</div></section>
   <div class="note">Datos reales de ESPN, MLB StatsAPI y Open-Meteo. Si algo no está disponible se muestra <b>${SD}</b>. Las probabilidades son <b>estimaciones de un modelo simple</b>, no certezas.</div>`;
  srchInit(document.getElementById('hm-search'));
  let timer=null;
  const fillHome = async (first)=>{
    try{
      const h = await api('/api/home');
      const rec = h.record_main || h.record_all || h.record;
      const elr=document.getElementById('hm-rec');
      if(elr && rec){
        const kpi=(l,v,c='',ti='')=>`<div class="kpi"${ti}><div class="sub">${l}</div><div class="v mono ${c}">${v}</div></div>`;
        elr.innerHTML = `<h3>Récord acumulado · pick principal <a href="#/record" class="more">Ver día →</a></h3>
          <div class="kpis">${kpi('Muestra', rec.graded==null?SD:(rec.graded+' calificados'+(rec.total!=null?` / ${rec.total}`:'')))}${kpi('G-P-E', (rec.W||rec.L||rec.P)?`${rec.W}-${rec.L}${rec.P?'-'+rec.P:''}`:SD)}
          ${kpi('ROI', rec.roi==null?SD:((rec.roi>0?'+':'')+rec.roi.toFixed(1)+'%'), rec.roi>0?'pos':rec.roi<0?'neg':'')}
          ${kpi('CLV promedio', rec.clv_avg==null?SD:((rec.clv_avg>0?'+':'')+rec.clv_avg.toFixed(1)+'%'+(rec.clv_n?` · n=${rec.clv_n}`:'')), rec.clv_avg>0?'pos':rec.clv_avg<0?'neg':'', typeof tip==='function'?tip('CLV'):'')}</div>`;
      }
      const el=document.getElementById('hm-live'); if(!el) return;
      if(!el.querySelector('.hm-lh')) el.innerHTML='<h3 class="hm-lh"></h3><div class="hm-lb"></div>';
      el.querySelector('.hm-lh').innerHTML=`En vivo ahora${h.live.length?` <span class="badge b-live">${h.live.length}</span>`:''} ${updTag(h.now,h.live.length>0)}`;
      const lb=el.querySelector('.hm-lb');
      if(h.live.length){ const nc=lb.querySelector('.hm-none'); if(nc) nc.remove(); carPatch(lb,h.live.slice(0,12)); }
      else lb.innerHTML=`<div class="card mut hm-none">No hay juegos en vivo en este momento.</div>`;
      h.sports.forEach(x=>{ const a=document.querySelector(`.snav a[data-sp="${x.key}"]`); if(a){ a.classList.toggle('lv',!!x.live); a.title = x.live?`${x.live} en vivo`:(x.today?`${x.today} juego${x.today===1?'':'s'} hoy`:'Sin juegos hoy'); } });
      if(typeof setNavDot==='function') setNavDot('sports', !!(h.live&&h.live.length));
      if(h.live.length && !timer) { Live.start(()=>fillHome(false),25000); timer=1; }
      if(!h.live.length && timer){ Live.stop(); timer=null; }
    }catch(e){ const l=document.getElementById('hm-live'); if(l&&first) l.innerHTML=`<h3>En vivo ahora</h3><div class="card mut">${SD}: ${esc(e.message)}</div>`; }
  };
  fillHome(true);
}
