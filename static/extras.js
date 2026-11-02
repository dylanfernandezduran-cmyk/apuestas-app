/* Piezas nuevas: en vivo, lesiones, clima, alineaciones, resumen del día y auto-actualización.
   Se carga antes que app.js; usa sus ayudantes (esc, fmtTime, pct…) sólo cuando se llaman. Todo dato viene del servidor (ESPN / Open-Meteo): si falta algo se muestra "Sin dato". */
const fmtHMS = t => new Intl.DateTimeFormat('es-MX',{timeZone:'America/Mexico_City',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:true}).format(new Date(t*1000));
const fmtDM = t => new Intl.DateTimeFormat('es-MX',{timeZone:'America/Mexico_City',day:'numeric',month:'short'}).format(new Date(typeof t==='number'?t*1000:t));
const fmtDMH = t => new Intl.DateTimeFormat('es-MX',{timeZone:'America/Mexico_City',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit',hour12:true}).format(new Date(typeof t==='number'?t*1000:t));
const updTag = (ts,live) => ts ? `<span class="upd sub mono" id="upd" title="Hora de la última consulta a las fuentes">${live?'<i class="dot"></i>':''}Actualizado ${fmtHMS(ts)} CDMX${live?' · auto cada 25 s':''}</span>` : '';

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

// ---------- detalle: lesiones
const BK = {out:['b-out','Baja'], doubt:['b-dbt','Dudoso'], dtd:['b-dtd','Duda leve']};
function injSide(T, side, f, retIds){
  const S=f.sides[side]; if(!S) return `<div class="mut">${esc(T.name)}: ${SD}</div>`;
  const c=S.counts||{}, es=S.entries||[];
  const chips=[c.out?`<span class="cchip c-out">${c.out} baja${c.out>1?'s':''}</span>`:'', c.doubt?`<span class="cchip c-dtd">${c.doubt} dudoso${c.doubt>1?'s':''}</span>`:'', c.dtd?`<span class="cchip">${c.dtd} duda leve</span>`:'', (S.returning||[]).length?`<span class="cchip c-ret">🔁 ${S.returning.length} regresa${S.returning.length>1?'n':''}</span>`:''].join('');
  const row=e=>{ const b=BK[e.bucket]||BK.dtd; const note=e.note&&e.note.length>3?e.note:null;
    return `<div class="irow"><div class="il"><b>${esc(e.name)}</b> <span class="sub">${esc(e.pos||'')}</span>${e.key?' <span class="cchip c-key" title="Líder de su equipo en una categoría estadística (ESPN)">⭐ clave</span>':''}<div class="sub">${esc(e.detail||e.status)}${e.location&&!(e.detail||'').includes(e.location)?' · '+esc(e.location):''}</div>
      ${e.ret?`<div class="sub">Regreso estimado: <b>${esc(fmtDM(e.ret))}</b></div>`:''}${note?`<div class="sub inote" title="${esc(note)}">ESPN: ${esc(note.length>150?note.slice(0,147)+'…':note)}</div>`:''}</div>
      <div class="ir"><span class="badge ${b[0]}">${esc(e.status_es||b[1])}</span>${e.date?`<div class="sub mono">${fmtDM(e.date)}</div>`:''}</div></div>`; };
  const first=es.slice(0,8), rest=es.slice(8);
  const ret=(S.returning||[]).map(r=>`<div class="irow ret"><div class="il"><b>${esc(r.name)}</b> <span class="sub">${esc(r.pos||'')}</span><div class="sub">${r.kind==='salio'?`Salió del reporte (antes: ${esc(r.old||'—')})`:`Mejoró: ${esc(r.old||'—')} → ${esc(r.new||'—')}`}</div></div><div class="ir"><span class="badge b-ret">🔁 Regresa</span><div class="sub mono">${fmtDM(r.ts)}</div></div></div>`).join('');
  return `<div><div class="ih"><b>${esc(T.name)}</b><span class="chips">${chips||'<span class="sub">Sin lesionados reportados</span>'}</span></div>
    ${first.map(row).join('')}${rest.length?`<div class="gp"><div class="tg" role="button" tabindex="0">Ver ${rest.length} más</div><div class="sg">${rest.map(row).join('')}</div></div>`:''}
    ${ret?`<div class="sub rh">🔁 Regresan de lesión (según nuestro seguimiento)</div>${ret}`:''}</div>`;
}
function injSection(d){
  const f=d.injuries_full, g=d.game;
  if(f&&f.tennis) return `<div class="card" style="margin-top:10px"><h2>🩹 Lesiones y retiros</h2><div class="mut">ESPN no publica lesiones de tenis (${SD}). Los retiros o W.O. aparecen en el partido terminado${g.wd?`: <b>${esc(g.wd)}</b>`:''}.</div></div>`;
  if(!f) return `<div class="card" style="margin-top:10px"><h2>🩹 Lesiones</h2><div class="mut">${SD}</div></div>`;
  const any=['home','away'].some(s=>f.sides[s]&&(f.sides[s].entries||[]).length);
  if(!f.supported&&!any) return `<div class="card" style="margin-top:10px"><h2>🩹 Lesiones y suspensiones</h2><div class="mut">ESPN no publica lesiones ni suspensiones para esta liga (${SD}). Revisa las noticias del equipo antes del partido.</div></div>`;
  const since = f.tracking_since ? `Seguimiento propio desde ${fmtDMH(f.tracking_since)} CDMX: «Regresa» = el jugador salió del reporte de ESPN o mejoró de estado en los últimos 10 días (puede ser alta médica, o que fue cortado/traspasado; no es una confirmación de que jugará).` : '';
  return `<div class="card" style="margin-top:10px"><h2>🩹 Lesiones ${f.fetched?`<span class="badge b-fin">ESPN · ${fmtHMS(f.fetched)}</span>`:''}</h2><div class="two">${sides(d.game).map(sd=>injSide(d.game[sd],sd,f)).join('')}</div>
    <div class="sub" style="margin-top:8px">Baja = Out / reserva de lesionados / suspendido · Dudoso · Duda leve = cuestionable / día a día. ⭐ clave = líder estadístico del equipo.</div>${since?`<div class="sub" style="margin-top:4px">${since}</div>`:''}</div>`;
}

// ---------- detalle: clima
function wxWindArrow(deg){ return deg==null?'':`<span class="warr" style="transform:rotate(${Math.round(deg+180)}deg)">↑</span>`; }
function weatherSection(d){
  const w=d.weather, g=d.game; if(!w||w.status==='no_aplica') return '';
  const head=`<h2>🌤️ Clima del estadio ${w.status==='ok'||w.status==='retractil'?'<span class="badge b-fin">Open-Meteo</span>':''}</h2>`;
  if(w.status==='techado') return `<div class="card" style="margin-top:10px">${head}<div><span class="cchip">🏟️ Techado</span> <span class="sub">${esc(w.venue||'')}: recinto cubierto, el clima exterior no influye.</span></div></div>`;
  if(w.status==='sin_dato'){
    const e=w.espn; return `<div class="card" style="margin-top:10px">${head}<div class="mut">${SD}: ${esc(w.reason||'')}</div>${e?`<div class="sub">ESPN: ${e.temp_f}°F${e.gust?` · ráfagas ${e.gust} mph`:''}${e.precip?` · lluvia ${e.precip}%`:''}</div>`:''}</div>`; }
  const cell=(k,v,s='')=>`<div><small>${k}</small><b class="mono">${v}</b>${s?`<div class="sub">${s}</div>`:''}</div>`;
  return `<div class="card" style="margin-top:10px">${head}
    <div class="stats wx">${cell('Cielo',`${w.icon||''} ${esc(w.text||SD)}`)}${cell('Temperatura',w.temp_c!=null?Math.round(w.temp_c)+' °C':SD, w.feels_c!=null?'sensación '+Math.round(w.feels_c)+' °C':'')}
      ${cell('Viento',w.wind_kmh!=null?`${wxWindArrow(w.wind_dir)} ${Math.round(w.wind_kmh)} km/h`:SD, w.wind_from?`del ${esc(w.wind_from)}${w.gust_kmh?` · ráfagas ${Math.round(w.gust_kmh)}`:''}`:'')}
      ${cell('Prob. de lluvia',w.precip_prob!=null?Math.round(w.precip_prob)+'%':SD, w.precip_mm?w.precip_mm.toFixed(1)+' mm':'')}${cell('Humedad',w.humidity!=null?Math.round(w.humidity)+'%':SD)}${w.elevation_m!=null&&w.elevation_m>=800?cell('Altitud',Math.round(w.elevation_m)+' m'):''}</div>
    ${(w.notes||[]).length?`<ul class="t wxn">${w.notes.map(n=>`<li>${esc(n)}</li>`).join('')}</ul>`:''}
    ${w.roof==='retractil'?`<div class="sub">🏟️ Estadio con techo retráctil: si lo cierran, el clima exterior pesa menos.</div>`:''}
    <div class="sub" style="margin-top:6px">Pronóstico para ${esc(fmtDMH(w.at))} CDMX (hora del juego) en ${esc(w.venue||'el estadio')}${w.city?', '+esc(w.city):''}. Es contexto: <b>no modifica</b> las probabilidades del modelo.</div></div>`;
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
  return `<div class="card" style="margin-top:10px"><h2>🧑‍🤝‍🧑 ${ttl}</h2><div class="two">${sides(g).map(sd=>lineupSide(g[sd],L.sides[sd],d,sd)).join('')}</div>${L.note?`<div class="sub" style="margin-top:8px">${esc(L.note)}</div>`:''}
    <div class="sub" style="margin-top:6px">✅ confirmada = publicada por ESPN · ❓ proyectada = deducida del último juego real, puede cambiar. Los cambios se comparan contra la foto anterior guardada por el servidor.</div></div>`;
}

// ---------- descanso (filas para la tabla comparativa)
function restRows(d){
  const R=d.rest; if(!R||(!R.home&&!R.away)) return '';
  const fmt=r=>!r?SD:r.b2b?'<b class="neg">Back-to-back</b>':`${r.days} día${r.days===1?'':'s'}`;
  return `<tr><td>Descanso (días sin jugar)</td><td class="mono">${fmt(R.away)}</td><td class="mono">${fmt(R.home)}</td></tr><tr><td>Juegos en los últimos 7 días</td><td class="mono">${R.away?R.away.n7:SD}</td><td class="mono">${R.home?R.home.n7:SD}</td></tr>`;
}
const restTags = d => { const R=d.rest||{}, g=d.game; return ['away','home'].filter(s=>R[s]&&R[s].b2b).map(s=>`<span class="cchip c-warn">${esc(g[s].abbr||g[s].short)}: back-to-back</span>`).join(' '); };

// ---------- resumen del día (inicio)
const liveRowHtml = g => {
  const pv = Object.values(g.prov||{}); const main=(g.rec||[]).find(r=>r.type==='main');
  const mp = main && provBadge(g.prov, main.market, main.selection);
  const t=(x)=>`<div class="lr-t"><span class="nm">${esc(x.short||x.name)}</span><span class="sc mono">${x.score!=null&&x.score!==''?esc(x.score):(x.sets&&x.sets.length?esc(x.sets.join(' ')):'')}</span></div>`;
  return `<a class="card lrow" href="#/juego/${encodeURIComponent(g.league)}/${g.id}"><div class="lr-h"><span class="badge b-live">● ${esc((g.live&&g.live.text)||g.status||'EN VIVO')}</span><span class="sub">${esc(g.league_name)}</span></div>${sides(g).map(sd=>t(g[sd])).join('')}${g.live&&g.live.situation?`<div class="sub">${esc(g.live.situation.text)}</div>`:''}${mp?`<div style="margin-top:6px"><span class="sub">${esc(shortLbl(main.label,g))}</span> ${mp}</div>`:''}</a>`; };

async function viewHome(){
  SPORTS = SPORTS || await api('/api/sports');
  const today = new Intl.DateTimeFormat('es-MX',{timeZone:TZ,weekday:'long',day:'numeric',month:'long'}).format(new Date());
  $app.innerHTML = `<div class="hm-h"><div class="sub">${esc(today)} · CDMX</div><h1>Resumen del día</h1></div>
   <section class="hm" id="hm-live"><h3>En vivo ahora</h3><div class="skel">Buscando juegos en vivo…</div></section>
   <section class="hm" id="hm-picks"><h3>Mejores picks de hoy <a href="#/picks/hoy" class="more">Ver todos →</a></h3><div class="skel">Calculando con el modelo…</div></section>
   <section class="hm" id="hm-rec"><h3>Récord · últimos 30 días <a href="#/record" class="more">Detalle →</a></h3><div class="skel">…</div></section>
   <section class="hm" id="hm-inj"><h3>Bajas confirmadas en juegos de hoy</h3><div class="skel">…</div></section>
   <section class="hm" id="hm-sp"><h3>Deportes</h3><div class="grid g3">${SPORTS.map(s=>`<a class="card sport" href="#/deporte/${s.key}"><span class="em">${s.emoji}</span>${esc(s.name)}<span class="sub" data-sp="${s.key}">${s.leagues.map(l=>esc(l.name)).join(' · ')}</span></a>`).join('')}</div></section>
   <div class="note">Datos reales de ESPN, MLB StatsAPI y Open-Meteo. Si algo no está disponible se muestra <b>${SD}</b>. Las probabilidades son <b>estimaciones de un modelo simple</b>, no certezas.</div>`;
  let timer=null;
  const fillHome = async (first)=>{
    try{
      const h = await api('/api/home');
      const el=document.getElementById('hm-live'); if(!el) return;
      el.querySelector('div,a')&&0;
      el.innerHTML = `<h3>En vivo ahora${h.live.length?` <span class="badge b-live">${h.live.length}</span>`:''} ${updTag(h.now,h.live.length>0)}</h3>` + (h.live.length ? `<div class="glist">${h.live.slice(0,12).map(liveRowHtml).join('')}</div>` : `<div class="card mut">No hay juegos en vivo en este momento.</div>`);
      h.sports.forEach(s=>{ const x=document.querySelector(`[data-sp="${s.key}"]`); if(x) x.innerHTML = s.today||s.live ? `${s.live?`<b class="pos">● ${s.live} en vivo</b> · `:''}${s.today} juego${s.today===1?'':'s'} hoy` : 'Sin juegos hoy'; });
      if(first){
        const r=h.record, ra=h.record_all;
        document.getElementById('hm-rec').innerHTML = `<h3>Récord · últimos 30 días <a href="#/record" class="more">Detalle →</a></h3>` + (r.graded ? `<div class="kpis s"><div class="kpi"><small class="sub">G-P-E</small><div class="v mono">${r.W%1?r.W.toFixed(1):r.W}-${r.L%1?r.L.toFixed(1):r.L}-${r.P%1?r.P.toFixed(1):r.P}</div></div><div class="kpi"><small class="sub">% acierto</small><div class="v mono">${r.win_pct==null?'—':r.win_pct.toFixed(1)+'%'}</div></div><div class="kpi"><small class="sub">Unidades</small><div class="v mono ${r.units>0?'pos':r.units<0?'neg':''}">${units(r.units)}</div></div></div><div class="rec-note">${r.graded} picks calificados · ${r.pending} pendientes. Unidades a 1u plano con la cuota registrada.</div>` : `<div class="card mut">Aún no hay picks calificados en 30 días (${r.pending} pendientes).</div>`);
        document.getElementById('hm-inj').innerHTML = `<h3>Bajas confirmadas en juegos de hoy</h3>` + (h.injuries.length ? `<div class="card">${h.injuries.map(i=>`<a class="irow" href="#/juego/${encodeURIComponent(i.league)}/${i.id}"><div class="il"><b>${esc(i.name)}</b> <span class="sub">${esc(i.pos||'')} · ${esc(i.team)}</span><div class="sub">${esc(i.detail||'')}${i.n_out>1?` · ${i.n_out} bajas en el equipo`:''}</div></div><div class="ir"><span class="badge b-out">${esc(i.status)}</span></div></a>`).join('')}</div><div class="sub" style="margin-top:4px">Una baja destacada por equipo (QB primero en NFL). Fuente: ESPN.</div>` : `<div class="card mut">Sin dato de bajas para los juegos de hoy (ESPN no publica fútbol/tenis, o no hay juegos).</div>`);
        loadHomePicks();
      }
      if(h.live.length && !timer) { Live.start(()=>fillHome(false),25000); timer=1; }
      if(!h.live.length && timer){ Live.stop(); timer=null; }
    }catch(e){ const l=document.getElementById('hm-live'); if(l&&first) l.innerHTML=`<h3>En vivo ahora</h3><div class="card mut">${SD}: ${esc(e.message)}</div>`; }
  };
  const loadHomePicks = async ()=>{
    try{
      const p = await api('/api/picks?scope=hoy');
      const it = (p.items||[]).filter(x=>x.status==='PICK'||x.status==='LEAN').slice(0,3);
      const el=document.getElementById('hm-picks'); if(!el) return;
      el.innerHTML = `<h3>Mejores picks de hoy <a href="#/picks/hoy" class="more">Ver todos →</a></h3>` + (it.length ? it.map(x=>{ const g=x.game, l=x.lean;
        return `<a class="card pk" href="#/juego/${encodeURIComponent(g.league)}/${g.id}"><div class="pk1"><div><div class="pkt">${esc(shortLbl(l.label,g))} <span class="mono">${esc(l.price_txt||'')}</span></div><div class="sub">${sides(g).map(sd=>esc(g[sd].short||g[sd].name)).join(' '+vsMark(g)+' ')} · ${esc(g.league_name)} · ${fmtTime(g.date)}</div></div><div class="pke ${l.edge>0?'pos':''}">${l.edge==null?'':sg(l.edge)+'pp'}<small>edge</small></div></div><div class="meta">${badgeSt(x.status)} ${confBadge(x.confidence)}</div></a>`; }).join('') : `<div class="card mut">Sin picks con ventaja suficiente hoy (o los juegos de hoy ya empezaron). Revisa «Top picks» para las próximas 24 h.</div>`);
    }catch(e){ const el=document.getElementById('hm-picks'); if(el) el.innerHTML=`<h3>Mejores picks de hoy</h3><div class="card mut">${SD}</div>`; }
  };
  fillHome(true);
}
