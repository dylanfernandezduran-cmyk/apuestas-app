/* Props de jugadores (pt84u): sección del detalle de juego + pantalla de un prop (tendencias). Sólo datos reales:
   líneas/cuotas de DraftKings (vía ESPN) y bitácora real de cada jugador. Sin línea => «Sin línea» (y, si hay ≥3 juegos, una REFERENCIA calculada y rotulada). */
const PGR = '#34D17B';                       // verde = cumplió (la línea se superó en el lado elegido); rosa DC.pk = falló
const PST = {};                              // estado por juego: estadística, equipo, «ver más» (sobrevive al refresco en vivo)
const PCACHE = {};                           // /api/props por juego (90 s)
const PDET = {n:10, side:'over', mode:'actual'};   // filtros de la pantalla de un prop
const pAm = v => v==null ? '—' : (v>0?'+'+v:String(v).replace('-','−'));
const pNum = v => v==null ? '—' : (Number.isInteger(v)?String(v):String(Math.round(v*10)/10));
const pHitCls = p => p==null ? 'mut' : p>=.6 ? 'pp-g' : p<=.4 ? 'pp-r' : 'pp-a';
const pDate = iso => { if(!iso) return ''; try{ return new Intl.DateTimeFormat('es-MX',{timeZone:TZ,day:'numeric',month:'short'}).format(new Date(iso)).replace('.','').replace(' de ',' '); }catch(e){ return ''; } };
const pWho = pl => esc([pl.jersey?'#'+pl.jersey:'', pl.pos, pl.team&&pl.team.abbr].filter(Boolean).join(' · '));
const pFace = (pl,s) => badge({logo:pl.img, name:pl.name}, s);
const pSide = (v,line,side) => (v==null||line==null) ? null : v===line ? 'push' : ((side==='over' ? v>line : v<line) ? 'hit' : 'miss');

function pSpark(last, line){
  const v = (last||[]).filter(x=>x!=null).slice(0,10).reverse(); if(!v.length) return '';
  const m = Math.max(...v, line==null?0:line, 1);
  const bars = v.map(x=>{ const c = line==null ? '#4b5563' : x>line ? PGR : x<line ? DC.pk : '#6b7280'; return `<i style="height:${Math.max(8,Math.round(x/m*100))}%;background:${c}"></i>`; }).join('');
  const ln = line==null ? '' : `<u style="bottom:${Math.round(line/m*100)}%"></u>`;
  return `<span class="pp-sp" aria-hidden="true">${bars}${ln}</span>`;
}

// ---------------- sección del detalle
function dProps(d){
  if(d.kind==='tennis' || !d.game) return '';
  const g=d.game;
  return ds('props','Props de jugadores',`<div class="pp-host" data-l="${esc(g.league||'')}" data-e="${esc(g.id||'')}"><div class="pp-ld">Cargando props reales…</div></div>`,{right:tag2('DRAFTKINGS','mod'), info:'Líneas y cuotas de DraftKings publicadas vía ESPN (suelen salir el mismo día del juego). Tendencia = veces que el jugador superó la línea en sus últimos 10 juegos (bitácora real de ESPN). Si DraftKings aún no publica, se muestran los líderes de cada equipo contra una REFERENCIA calculada (promedio de sus últimos 10 juegos llevado a x.5): no es una línea de casa. Tenis: ninguna fuente pública publica props de jugador.'});
}
function propsInit(){
  document.querySelectorAll('.pp-host').forEach(async h=>{
    const l=h.dataset.l, e=h.dataset.e; if(!l||!e) return;
    const c=PCACHE[l+'/'+e];
    if(c) pRender(h,c.d,l,e);
    if(c && Date.now()-c.t<90000) return;
    try{
      const d = await api(`/api/props/${encodeURIComponent(l)}/${encodeURIComponent(e)}`, 40000);
      PCACHE[l+'/'+e] = {t:Date.now(), d};
      const host = document.querySelector(`.pp-host[data-l="${CSS.escape(l)}"][data-e="${CSS.escape(e)}"]`);
      if(host) pRender(host,d,l,e);
    }catch(err){ const host=document.querySelector('.pp-host'); if(host && !PCACHE[l+'/'+e]) host.innerHTML=`<div class="pp-ld">No se pudieron cargar los props (${esc(err.message)}). <button type="button" class="pp-retry">Reintentar</button></div>`; }
  });
}
function pRender(host,d,l,e){
  const sec = host.closest('.ds');
  if(!d || d.mode==='none' || !(d.players||[]).length){
    host.innerHTML = `<div class="pp-ld">${esc((d&&d.note)||'Sin props disponibles para este juego.')}</div>`; return;
  }
  const key = l+'/'+e, S = PST[key] = PST[key] || {};
  const stats = d.stats||[];
  if(!stats.some(s=>s.key===S.stat)) S.stat = (stats[0]||{}).key;
  const teams = d.teams||[];
  if(S.team && !teams.some(t=>t.id===S.team)) S.team = null;
  let rows = [];
  for(const pl of d.players){
    if(S.team && pl.team.id!==S.team) continue;
    const pr = (pl.props||[]).find(p=>p.key===S.stat); if(pr) rows.push([pl,pr]);
  }
  rows.sort((a,b)=>(b[1].line||0)-(a[1].line||0) || a[0].name.localeCompare(b[0].name));
  const chips = stats.length>1 ? `<div class="pp-chips">${stats.map(s=>`<button type="button" data-st="${s.key}" class="${s.key===S.stat?'on':''}">${esc(s.label)}</button>`).join('')}</div>` : '';
  const seg = teams.length===2 ? `<div class="pp-seg"><button type="button" data-tm="" class="${!S.team?'on':''}">Todos</button>${teams.map(t=>`<button type="button" data-tm="${esc(t.id)}" class="${S.team===t.id?'on':''}">${esc(t.abbr||t.name)}</button>`).join('')}</div>` : '';
  const LIM=8, shown = S.more ? rows : rows.slice(0,LIM);
  const row = ([pl,pr])=>{
    const sideTxt = pr.kind==='ou' ? 'Más' : 'Más';
    const hit = pr.l10 && pr.l10.n ? `<em class="pp-hit ${pHitCls(pr.l10.pct)}">${pr.l10.hit}/${pr.l10.n}${pr.l10.pct!=null?' · '+Math.round(pr.l10.pct*100)+'%':''}</em>` : `<em class="pp-hit mut">Sin historial</em>`;
    const price = pr.ref ? '<small class="pp-rf">REF</small>' : `<small class="mono">${pAm(pr.over)}</small>`;
    return `<a class="pp-row" href="#/prop/${encodeURIComponent(l)}/${encodeURIComponent(e)}/${pl.id}/${pr.key}">${pFace(pl,38)}<span class="pp-who"><b>${esc(pl.name)}</b><small>${pWho(pl)}</small>${pSpark(pr.last,pr.line)}</span>
      <span class="pp-ln"><i>${sideTxt}</i><b class="mono">${pr.line==null?'Sin línea':pNum(pr.line)}</b>${price}${hit}</span></a>`;
  };
  const note = d.mode==='referencia' ? `<div class="pp-note"><b>Referencia</b> · ${esc(d.note||'')}</div>` : `<div class="pp-note">${esc(d.src||'')} · tendencia = últimos 10 juegos del jugador (bitácora ESPN). Toca un jugador para ver el detalle.</div>`;
  host.innerHTML = `${chips}${seg}<div class="pp-list">${shown.map(row).join('') || '<div class="pp-ld">Sin jugadores con esta estadística.</div>'}</div>${rows.length>LIM?`<button type="button" class="pp-more">${S.more?'Ver menos':`Ver ${rows.length-LIM} más`}</button>`:''}${note}`;
  host.dataset.k = key;
}
document.addEventListener('click',e=>{
  const host = e.target.closest('.pp-host'); if(!host) return;
  const key = host.dataset.k || (host.dataset.l+'/'+host.dataset.e), S = PST[key] = PST[key] || {};
  const c = PCACHE[host.dataset.l+'/'+host.dataset.e];
  const st=e.target.closest('.pp-chips button'), tm=e.target.closest('.pp-seg button'), mo=e.target.closest('.pp-more');
  if(e.target.closest('.pp-retry')){ delete PCACHE[host.dataset.l+'/'+host.dataset.e]; host.innerHTML='<div class="pp-ld">Cargando props reales…</div>'; propsInit(); return; }
  if(!c) return;
  if(st){ S.stat=st.dataset.st; S.more=false; }
  else if(tm){ S.team=tm.dataset.tm||null; S.more=false; }
  else if(mo){ S.more=!S.more; }
  else return;
  pRender(host,c.d,host.dataset.l,host.dataset.e);
});

// ---------------- pantalla de un prop (modelo: tendencias de Action Network)
async function viewProp(league,eid,aid,key){
  loading('Cargando tendencias del jugador…');
  const d = await api(`/api/prop/${encodeURIComponent(league)}/${encodeURIComponent(eid)}/${encodeURIComponent(aid)}/${encodeURIComponent(key)}?hist=${PDET.n}`, 50000);
  if(!location.hash.startsWith('#/prop/')) return d;
  PDET.cur = {d, league, eid, aid, key};
  $app.classList.add('gd');
  pDraw();
  return d;
}
function pDraw(){
  const C = PDET.cur; if(!C) return;
  const d=C.d, I=d.info, L=d.line, ln=L.value;
  const hasHist = d.games.some(g=>g.line_hist!=null);
  if(PDET.mode==='hist' && !hasHist) PDET.mode='actual';
  const N = PDET.n, side = PDET.side;
  const gm = d.games.slice(0,N).slice().reverse();                       // cronológico: más reciente a la derecha
  const lineOf = g => PDET.mode==='hist' ? (g.line_hist!=null?g.line_hist:null) : ln;
  const res = gm.map(g=>pSide(g.value, lineOf(g), side));
  const hit = res.filter(x=>x==='hit').length, push = res.filter(x=>x==='push').length, valid = res.filter(x=>x!=null).length;
  const pctv = (valid-push)>0 ? hit/(valid-push) : null;
  const avg = gm.length ? gm.reduce((a,g)=>a+g.value,0)/gm.length : null;
  const refTxt = L.ref && ln!=null ? `<span class="tg2 mod">REFERENCIA</span>` : '';
  const hist = d.games.slice(0,N);
  const mx = Math.max(1, ...gm.map(g=>g.value), ...(PDET.mode==='hist' ? gm.map(g=>g.line_hist||0) : [ln||0])) * 1.12;
  const col = (g,i)=>{
    const r=res[i], lg=lineOf(g), c = r==='hit'?PGR : r==='miss'?DC.pk : r==='push'?'#6b7280':'#3a3f47';
    const h = Math.max(6, Math.round(g.value/mx*100));
    const tick = (PDET.mode==='hist' && lg!=null) ? `<u class="pp-t" style="bottom:${Math.round(lg/mx*100)}%"></u>` : '';
    return `<div class="pp-cc"><i class="pp-bar" style="height:${h}%;background:${c}"><b class="mono">${pNum(g.value)}</b><span>${esc(g.opp||'')}</span></i>${tick}</div>`;
  };
  const lineEl = (PDET.mode!=='hist' && ln!=null) ? `<div class="pp-line" style="bottom:${Math.round(ln/mx*100)}%"><span class="mono">${pNum(ln)}</span></div>` : '';
  const chart = gm.length ? `<div class="pp-sc"><div class="pp-in" style="min-width:${N>10?gm.length*32:0}px"><div class="pp-plot">${gm.map(col).join('')}${lineEl}</div><div class="pp-lbs">${gm.map(g=>`<div class="pp-lc"><b class="mono">${lineOf(g)==null?'—':pNum(lineOf(g))}</b><small>${esc(pDate(g.date))}</small></div>`).join('')}</div></div></div>` : `<div class="pp-ld">Sin juegos recientes con este dato.</div>`;
  const seg = (items,cur,attr)=>`<div class="pp-seg">${items.map(([v,t])=>`<button type="button" data-${attr}="${v}" class="${String(cur)===String(v)?'on':''}">${t}</button>`).join('')}</div>`;
  const mk = (d.markets||[]);
  const mkchips = mk.length>1 ? `<div class="pp-chips">${mk.map(m=>`<button type="button" data-mk="${m.key}" class="${m.key===C.key?'on':''}">${esc(m.label)}</button>`).join('')}</div>` : '';
  const rowsL = hist.map(g=>{ const lg=lineOf(g), r=pSide(g.value,lg,side);
    const bd = r==='hit'?`<span class="pp-bd pp-ok">Cumplió</span>`: r==='miss'?`<span class="pp-bd pp-no">Falló</span>`: r==='push'?`<span class="pp-bd pp-pu">Push</span>`:`<span class="pp-bd pp-nl">Sin línea</span>`;
    return `<div class="pp-gr"><span class="pp-gd"><b>${esc(pDate(g.date))}</b><small>${g.home?'vs':'@'} ${esc(g.opp||'')}${g.result?` · ${g.result==='W'?'G':g.result==='L'?'P':'E'} ${esc(g.score||'')}`:''}</small></span><span class="pp-gv mono">${pNum(g.value)}</span><span class="pp-gl mono">${lg==null?'—':(side==='over'?'M ':'m ')+pNum(lg)}</span>${bd}</div>`; }).join('');
  const sideLbl = side==='over' ? 'Más' : 'Menos';
  const price = side==='over' ? L.over : L.under;
  const head = `<div class="card pp-head">${pFace({img:I.img,name:I.name},56)}<div class="pp-hn"><b>${esc(I.name)}</b><small>${esc([I.jersey?'#'+I.jersey:'', I.pos_name||I.pos].filter(Boolean).join(' · '))}</small><span class="pp-tm">${I.team&&I.team.logo?badge({logo:I.team.logo,name:I.team.name},16):''}<span>${esc((I.team&&I.team.name)||'')}</span></span></div></div>`;
  const lcard = ln==null
    ? `<div class="pp-lc2"><div><small>Línea</small><b class="mono pp-sl">Sin línea</b></div></div><div class="pp-note">DraftKings no publicó línea para este prop y no hay juegos suficientes (mín. 3) para una referencia. Se muestran los valores reales sin umbral.</div>`
    : `<div class="pp-lc2"><div><small>${L.ref?'Referencia':'Línea'} ${refTxt}</small><b class="mono">${sideLbl} ${pNum(ln)}</b></div><div><small>Cuota ${sideLbl.toLowerCase()}</small><b class="mono">${L.ref?'—':pAm(price)}</b></div><div><small>Cumplió</small><b class="mono ${pHitCls(pctv)}">${valid?hit+'/'+valid:'—'}${pctv!=null?' · '+Math.round(pctv*100)+'%':''}</b></div><div><small>Promedio</small><b class="mono">${avg==null?'—':pNum(Math.round(avg*10)/10)}</b></div></div>
      ${L.ref?`<div class="pp-note"><b>Referencia calculada</b>, no es una línea de casa: promedio de los últimos ${L.ref_n} juegos (${pNum(Math.round(L.ref_avg*10)/10)}) llevado a x.5.</div>`:`<div class="pp-note">${esc(L.src||'')}${L.open!=null&&L.open!==ln?` · apertura ${pNum(L.open)} → ahora ${pNum(ln)}`:''}${L.kind!=='ou'?' · mercado «N+»: sólo precio del Más':''}</div>`}`;
  const modeSeg = hasHist ? seg([['actual','Línea de hoy'],['hist','Línea de cada juego']],PDET.mode,'md') : '';
  $app.innerHTML = `<a class="back" href="#/juego/${encodeURIComponent(C.league)}/${encodeURIComponent(C.eid)}">← Volver al juego</a>${head}
    <section class="ds pp-fil"><div class="pp-cap">Últimos juegos</div>${seg([[5,'5'],[10,'10'],[20,'20']],N,'n')}${mkchips}<div class="pp-cap">Lado</div>${seg([['over','Más'],['under','Menos']],side,'sd')}${modeSeg?`<div class="pp-cap">Línea del gráfico</div>${modeSeg}`:''}</section>
    <section class="ds pp-main"><h3 class="dh"><span class="ttl2">${esc(d.label)}</span><span class="dr">${L.ref?tag2('REFERENCIA','mod'):L.value==null?tag2('SIN LÍNEA'):tag2('DRAFTKINGS','mod')}</span></h3><div class="db">${lcard}${chart}
      <div class="pp-leg"><span><i style="background:${PGR}"></i>Cumplió</span><span><i style="background:${DC.pk}"></i>Falló</span>${PDET.mode==='hist'?'<span><i class="pp-lt"></i>Línea del juego</span>':'<span><i class="pp-ld2"></i>Línea</span>'}</div></div></section>
    <section class="ds"><h3 class="dh"><span class="ttl2">Juegos recientes</span></h3><div class="db"><div class="pp-gh"><span>Juego</span><span>Real</span><span>Línea</span><span></span></div>${rowsL||'<div class="pp-ld">Sin juegos.</div>'}${hasHist?'':'<div class="pp-note">La línea mostrada por juego es la de hoy: las líneas históricas de DraftKings no están disponibles para este prop.</div>'}</div></section>
    <div class="fine ctr">Datos de DraftKings vía ESPN y bitácora real del jugador. Estimaciones informativas, no recomendaciones de apuesta.</div>`;
}
document.addEventListener('click',async e=>{
  const C = PDET.cur; if(!C || !location.hash.startsWith('#/prop/')) return;
  const n=e.target.closest('.pp-fil [data-n]'), sd=e.target.closest('.pp-fil [data-sd]'), md=e.target.closest('.pp-fil [data-md]'), mk=e.target.closest('.pp-fil [data-mk]');
  if(n){ PDET.n=+n.dataset.n; if(PDET.n>(C.d.hist_n||0) && C.d.line.kind==='ou' && C.d.line.ref===false){ try{ PDET.cur.d=await api(`/api/prop/${encodeURIComponent(C.league)}/${encodeURIComponent(C.eid)}/${encodeURIComponent(C.aid)}/${encodeURIComponent(C.key)}?hist=${PDET.n}`,50000); }catch(err){} } pDraw(); }
  else if(sd){ PDET.side=sd.dataset.sd; pDraw(); }
  else if(md){ PDET.mode=md.dataset.md; pDraw(); }
  else if(mk){ location.hash=`#/prop/${encodeURIComponent(C.league)}/${encodeURIComponent(C.eid)}/${encodeURIComponent(C.aid)}/${mk.dataset.mk}`; }
});
