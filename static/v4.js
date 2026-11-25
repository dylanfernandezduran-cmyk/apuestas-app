/* NRNM 4.0 · Intelligence Terminal: Inicio, Partidos, Radar de valor, Parlay Lab y Rendimiento.
   Todo número sale de la API real (Probabilidad oficial NRNM, cuota, EV, candados). Sin dato => «—». */
const V4 = {cache:{}, legs:new Set(), stake:100, sport:'todos', sort:'ev'};
const v4d = v => v==null||isNaN(v) ? '—' : v;
const v4dec = o => o==null ? null : (o>0 ? 1+o/100 : 1+100/(-o));
const v4pc = (p,d=1) => p==null||isNaN(p) ? '—' : (p*100).toFixed(d)+'%';
const v4ev = e => e==null||isNaN(e) ? '—' : (e>0?'+':'')+Number(e).toFixed(1)+'%';
const v4sg = (v,d=1,u='') => v==null||isNaN(v) ? '—' : (v>0?'+':'')+Number(v).toFixed(d)+u;
async function v4get(path, ttl=60000){
  const c=V4.cache[path]; if(c&&Date.now()-c.t<ttl) return c.d;
  const d=await api(path); V4.cache[path]={t:Date.now(),d}; return d;
}
// estado del lado del modelo (de los candados reales): CANDIDATO = pasa TODOS; WAIT = EV>0 pero algún candado lo bloquea; PASS = sin valor o sin cuota
function v4state(it){
  const l=it.lean||{};
  if(it.approved) return {k:'ok', t:'CANDIDATO', why:'Pasa todos los candados'};
  if(l.price!=null && l.ev!=null && l.ev>0) return {k:'wait', t:'WAIT', why:it.block_reason||'Algún candado no pasa'};
  return {k:'no', t:'PASS', why:it.block_reason||(l.price==null?'Sin cuota: no es pick':'EV no positivo')};
}
const V4ICO = {
  crown:'<path d="M3 8l4.5 4L12 5l4.5 7L21 8l-2 10H5z"/>',
  bell:'<path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15z"/><path d="M10 20.5a2 2 0 0 0 4 0"/>',
  user:'<circle cx="12" cy="9" r="3.6"/><path d="M5 20c1.2-3.6 3.8-5.4 7-5.4s5.8 1.8 7 5.4"/>',
  cal:'<rect x="4" y="5.5" width="16" height="14" rx="2"/><path d="M4 10h16M8.5 3.5v4M15.5 3.5v4"/>',
  target:'<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="1.2"/>',
  medal:'<circle cx="12" cy="9" r="5"/><path d="M9 13.5 7.5 21l4.5-2.5 4.5 2.5-1.5-7.5"/>',
  coins:'<ellipse cx="12" cy="6.5" rx="6" ry="2.5"/><path d="M6 6.5v5c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5v-5M6 11.5v5c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5v-5"/>',
  shield:'<path d="M12 3.5 19 6v6c0 4.2-3 7.3-7 8.5-4-1.2-7-4.3-7-8.5V6z"/><path d="m8.8 12 2.2 2.2 4.4-4.4"/>',
  layers:'<path d="M12 4 3.5 8.5 12 13l8.5-4.5z"/><path d="m3.5 12.5 8.5 4.5 8.5-4.5M3.5 16.5 12 21l8.5-4.5"/>',
  warn:'<path d="M12 4 21 19.5H3z"/><path d="M12 10v4.5M12 17.2v.3"/>',
  bars:'<path d="M5 20v-6M10 20V9M15 20v-9M20 20V5"/>',
  arrow:'<path d="M7 17 17 7M9 7h8v8"/>'
};
const v4i = (k,c='') => `<svg class="v4i ${c}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${V4ICO[k]||''}</svg>`;
function v4spark(vals, cls=''){
  const v=(vals||[]).filter(x=>x!=null&&!isNaN(x)); if(v.length<2) return '<svg class="v4sp" viewBox="0 0 100 26"></svg>';
  const lo=Math.min(...v), hi=Math.max(...v), rg=(hi-lo)||1, X=i=>i*100/(v.length-1), Y=x=>23-(x-lo)/rg*20;
  const p=v.map((x,i)=>`${i?'L':'M'}${X(i).toFixed(1)},${Y(x).toFixed(1)}`).join(' ');
  return `<svg class="v4sp ${cls}" viewBox="0 0 100 26" preserveAspectRatio="none" aria-hidden="true"><path d="${p} L100,26 L0,26Z" class="a"/><path d="${p}" class="l"/></svg>`;
}
function v4bars(vals){
  const v=(vals||[]).filter(x=>x!=null); if(!v.length) return '<svg class="v4sp" viewBox="0 0 100 26"></svg>';
  const mx=Math.max(...v,1), w=100/v.length;
  return `<svg class="v4sp" viewBox="0 0 100 26" preserveAspectRatio="none" aria-hidden="true">${v.map((x,i)=>`<rect x="${(i*w+w*.18).toFixed(1)}" y="${(26-x/mx*24).toFixed(1)}" width="${(w*.64).toFixed(1)}" height="${(x/mx*24).toFixed(1)}" rx="1" class="b"/>`).join('')}</svg>`;
}
const v4tile = (ico,lab,val,spark,cls='') => `<div class="v4t glow"><div class="v4th">${v4i(ico)}<span>${lab}</span></div><b class="mono ${cls}">${val}</b>${spark||''}</div>`;
const v4hdr = (kick,title,sub,right='') => `<div class="v4ph"><div>${kick?`<small class="v4k">${kick}</small>`:''}<h1>${title}</h1>${sub?`<p>${sub}</p>`:''}</div>${right}</div>`;
const v4when = iso => { const d=new Date(iso), k=dayKey(iso), t=todayKey(); return (k===t?'Hoy':new Intl.DateTimeFormat('es-MX',{timeZone:TZ,weekday:'short',day:'numeric'}).format(d))+' '+new Intl.DateTimeFormat('es-MX',{timeZone:TZ,hour:'2-digit',minute:'2-digit',hour12:false}).format(d); };
const v4lg = g => esc((g.league_name||g.league||'').toUpperCase());
function v4team(t){ return `<div class="v4tm">${badge(t,40)}<b>${esc(t.abbr||t.short||(t.name||'').split(' ').slice(-1)[0])}</b><small>${esc((t.name||'').split(' ').slice(-1)[0])}</small></div>`; }
const v4nm = t => g4sp(t);
function g4sp(t){ const n=(t&&(t.name||t.short))||''; return /\s/.test(n)&&!/^(FC|CF|Real|Club|Atl)/.test(n)&&n.split(' ').length<=3&&(t.abbr||'').length<=4 ? n.split(' ').slice(-1)[0] : (t.short||n); }
function v4short(l,g){ return typeof shortLbl==='function'?shortLbl(l.label||'',g):(l.label||''); }

// ---- tarjeta de juego (Radar / Cartelera)
function v4card(it, compact){
  const g=it.game, l=it.lean||{}, st=v4state(it), [s0,s1]=sides(g), sc=(it.pred||{}).score;
  const href=`#/juego/${encodeURIComponent(g.league)}/${encodeURIComponent(g.id)}`;
  const dec=v4dec(l.price);
  const proj=sc&&sc[s0]!=null?`${sc[s0]} - ${sc[s1]}`:'—';
  const ttl=it.approved?'Pick principal':'Lado del modelo';
  return `<article class="v4g glow ${compact?'cmp':''}"><div class="v4gh"><span>${v4lg(g)} · ${esc(v4when(g.date))}</span><span class="v4b v4b-${st.k}" title="${esc(st.why)}">${st.k==='ok'?v4i('crown'):''}${st.t}</span></div>
    <div class="v4gm">${v4team(g[s0])}<div class="v4pj"><small>Proyección</small><b class="mono">${proj}</b></div>${v4team(g[s1])}</div>
    <div class="v4pk"><div class="v4pl"><small class="${it.approved?'v4pkc':''}">${ttl}</small><b>${esc(v4short(l,g)||'—')}</b></div>
      <div class="v4c"><small>Probabilidad</small><b class="mono">${v4pc(l.p_final)}</b></div>
      <div class="v4c"><small>Cuota</small><b class="mono">${dec?dec.toFixed(2):'—'}</b><em class="mono">${l.price_txt?esc(l.price_txt):''}</em></div>
      <div class="v4c"><small>EV</small><b class="mono ${l.ev>0?'pos':l.ev<0?'neg':''}">${v4ev(l.price!=null?l.ev:null)}</b></div></div>
    <div class="v4bar"><i style="width:${l.p_final!=null?Math.round(l.p_final*100):0}%"></i></div>
    <div class="v4gf"><span class="v4why">${it.approved?'✓ Pasa todos los candados':'🔒 '+esc(st.why)}</span><a class="v4btn" href="${href}">Análisis ${v4i('arrow')}</a></div></article>`;
}
async function v4items(scope='hoy'){ const d=await v4get('/api/picks?scope='+scope); return (d.items||[]).filter(it=>it.game&&it.game.state==='pre'&&it.lean); }
async function v4nrnm(){ try{ return await v4get('/api/nrnm',120000); }catch(e){ return null; } }
function v4kpis(items, nr){
  const r=(nr&&nr.record)||{}, mn=r.main||{}, D=r.daily||[];
  let cu=0; const cum=D.map(x=>(cu+=x.units||0)); const hits=D.map(x=>x.hit);
  const appr=items.filter(x=>x.approved).length;
  const bySp={}; items.forEach(x=>{ bySp[x.game.league]=(bySp[x.game.league]||0)+1; });
  return [v4tile('cal','Eventos hoy',String(items.length),v4bars(Object.values(bySp))),
    v4tile('target','Picks validados',String(appr),v4bars(items.map(x=>x.approved?1:0.08))),
    v4tile('medal','Precisión histórica',mn.n?mn.hit_pct.toFixed(1)+'%':'—',v4spark(hits),mn.hit_pct>=52.4?'pos':''),
    v4tile('coins','ROI verificado',mn.n?v4sg(mn.roi,1,'%'):'—',v4spark(cum),mn.roi>0?'pos':mn.roi<0?'neg':'')].join('');
}

// ---- Inicio
if(typeof viewHome==='function' && !window.__v4home){
  window.__v4home=viewHome;
  viewHome = async function(){
    await window.__v4home();
    const h=document.querySelector('#app .hm-h'); if(h) h.remove();
    const top=document.createElement('div'); top.id='v4home';
    top.innerHTML=`<section class="v4hero glow"><span class="v4mode">● PAPER TRADING</span><div class="v4hx"><h1>Inteligencia<br>deportiva.</h1><p>El dato antes que la intuición.</p><small>MODELO · MERCADO · RIESGO · CALIBRACIÓN</small><a class="v4cta" href="#/partidos">${v4i('bars')} Explorar partidos ›</a></div></section>
      <div class="v4tiles" id="v4k">${v4tile('cal','Eventos hoy','…')}${v4tile('target','Picks validados','…')}${v4tile('medal','Precisión histórica','…')}${v4tile('coins','ROI verificado','…')}</div>
      <div class="v4sh"><div><h2>Radar NBA</h2><p>Partidos de hoy con análisis NRNM</p></div><a href="#/partidos/nba">Ver todo ›</a></div><div class="v4car" id="v4car"><div class="skel">Cargando…</div></div>`;
    $app.prepend(top);
    try{
      const [items,nr]=await Promise.all([v4items('hoy'),v4nrnm()]);
      const k=document.getElementById('v4k'); if(k) k.innerHTML=v4kpis(items,nr);
      let nba=items.filter(x=>x.game.league==='nba'); const c=document.getElementById('v4car');
      if(c) c.innerHTML=nba.length?nba.map(x=>v4card(x,true)).join(''):`<div class="card mut">Sin juegos de NBA pendientes hoy.</div>`;
    }catch(e){ const c=document.getElementById('v4car'); if(c) c.innerHTML=`<div class="card mut">—: ${esc(e.message)}</div>`; }
  };
}

// ---- Partidos (Cartelera deportiva)
const V4SP=[['todos','Todos'],['nba','NBA'],['nfl','NFL'],['futbol','Fútbol'],['tenis','Tenis'],['mlb','MLB'],['nhl','NHL']];
const v4chips = (cur, base) => `<div class="v4chips">${V4SP.map(([k,n])=>`<a class="v4chip ${cur===k?'on':''}" href="${base}/${k}">${k!=='todos'&&typeof spIcon==='function'?spIcon(k):''}${n}</a>`).join('')}</div>`;
const v4spOf = it => it.game.sport==='futbol'||it.game.sport==='tenis' ? it.game.sport : it.game.league;
async function viewPartidos(sp, scope){
  sp=sp||'todos'; scope=scope||'hoy';
  const dayTxt=new Intl.DateTimeFormat('es-MX',{timeZone:TZ,day:'numeric',month:'short',year:'numeric'}).format(scope==='manana'?new Date(Date.now()+864e5):new Date());
  $app.innerHTML=`${v4hdr('','Cartelera deportiva','Análisis, probabilidades y valor por partido.',`<label class="v4date">${v4i('cal')}<select id="v4day"><option value="hoy" ${scope==='hoy'?'selected':''}>Hoy, ${esc(dayTxt)}</option><option value="manana" ${scope==='manana'?'selected':''}>Mañana</option></select></label>`)}
    <span class="v4mode" style="margin-bottom:10px">● PAPER TRADING</span>${v4chips(sp,'#/partidos')}<div class="v4tiles" id="v4k"></div><div id="v4list"><div class="skel">Cargando partidos…</div></div>`;
  document.getElementById('v4day').onchange=e=>{ location.hash=`#/partidos/${sp}/${e.target.value}`; };
  const [items,nr]=await Promise.all([v4items(scope),v4nrnm()]);
  if(!location.hash.startsWith('#/partidos')) return;
  const f=items.filter(x=>sp==='todos'||v4spOf(x)===sp).sort((a,b)=>Date.parse(a.game.date)-Date.parse(b.game.date));
  document.getElementById('v4k').innerHTML=v4kpis(f,nr);
  document.getElementById('v4list').innerHTML=f.length?f.map(x=>v4card(x)).join(''):`<div class="card mut">No hay partidos pendientes con análisis para este filtro.</div>`;
}

// ---- Picks (Radar de valor)
async function viewRadar(sp, sort){
  sp=sp||'todos'; sort=sort||V4.sort; V4.sort=sort;
  $app.innerHTML=`${v4hdr('PICK ENGINE','Radar de valor','Selecciones ordenadas por valor esperado (EV).','<span class="v4mode">● PAPER TRADING</span>')}
    <div class="v4strict glow">${v4i('shield','big')}<div><b>Validación estricta</b><span>Ningún pick se aprueba sin pasar todos los candados (prob. ≥ 50%, EV &gt; 0, datos frescos, calibración, coincide con la predicción).</span></div><em>ACTIVA</em></div>
    ${v4chips(sp,'#/picks/radar')}<div class="v4sort"><label>Ordenar por: <select id="v4sort"><option value="ev" ${sort==='ev'?'selected':''}>EV (mayor a menor)</option><option value="p" ${sort==='p'?'selected':''}>Probabilidad</option><option value="t" ${sort==='t'?'selected':''}>Hora</option></select></label><a class="v4lnk" href="#/picks/clasica">Vista detallada ›</a></div>
    <div id="v4list"><div class="skel">Cargando…</div></div>`;
  document.getElementById('v4sort').onchange=e=>{ V4.sort=e.target.value; location.hash=`#/picks/radar/${sp}/${e.target.value}`; };
  const items=await v4items('24h'); if(!location.hash.startsWith('#/picks')) return;
  const ord={ok:0,wait:1,no:2};
  const f=items.filter(x=>x.lean.price!=null&&(sp==='todos'||v4spOf(x)===sp)).sort((a,b)=> sort==='p'?(b.lean.p_final-a.lean.p_final): sort==='t'?(Date.parse(a.game.date)-Date.parse(b.game.date)) : ((b.lean.ev??-999)-(a.lean.ev??-999)));
  const row=(it,i)=>{ const g=it.game,l=it.lean,st=v4state(it),[s0,s1]=sides(g),dec=v4dec(l.price);
    return `<a class="v4r glow" href="#/juego/${encodeURIComponent(g.league)}/${encodeURIComponent(g.id)}"><span class="v4n">${st.k==='ok'&&i===0?v4i('crown'):''}${i+1}</span>
      <div class="v4rg"><small>${v4lg(g)} · ${esc(v4when(g.date))}</small><div class="v4rl">${badge(g[s0],24)}<i>vs</i>${badge(g[s1],24)}</div><small class="mono">${esc(g[s0].abbr||'')} vs ${esc(g[s1].abbr||'')}</small></div>
      <div class="v4rm"><b>${esc(v4short(l,g))}</b><small>${it.approved?'Pick':'Lado del modelo'} · Probabilidad</small><span class="mono v4rp">${v4pc(l.p_final)}</span><div class="v4bar"><i style="width:${Math.round(l.p_final*100)}%"></i></div></div>
      <div class="v4rc"><small>Cuota</small><b class="mono">${dec?dec.toFixed(2):'—'}</b><small>EV</small><b class="mono ${l.ev>0?'pos':'neg'}">${v4ev(l.ev)}</b></div>
      <span class="v4b v4b-${st.k}" title="${esc(st.why)}">${st.t}</span></a>`; };
  document.getElementById('v4list').innerHTML=(f.length?f.map(row).join(''):`<div class="card mut">Sin selecciones con cuota para este filtro.</div>`)+
    `<p class="nb-foot">CANDIDATO = pasa todos los candados · WAIT = EV positivo pero algún candado lo bloquea (toca para ver cuál) · PASS = sin valor (EV ≤ 0) o sin cuota. Probabilidad = Probabilidad oficial NRNM. Cuota en decimal (momio americano en el detalle).</p>`;
}

// ---- Parlay Lab (Simulador de riesgo)
async function viewParlayLab(sp){
  sp=sp||'todos';
  $app.innerHTML=`${v4hdr(`${v4i('layers')} PARLAY LAB`,'Simulador de riesgo','Ejercicio hipotético bajo independencia. Una selección por juego (las del mismo juego están correlacionadas y se bloquean).','<span class="v4ev" id="v4evh">EV —</span>')}
    ${v4chips(sp,'#/parlays')}<div class="v4legs glow" id="v4legs"><div class="skel">Cargando selecciones…</div></div><div id="v4sim"></div>`;
  const items=(await v4items('24h')).filter(x=>x.lean.price!=null&&x.lean.p_final!=null); if(!location.hash.startsWith('#/parlays')) return;
  const f=items.filter(x=>sp==='todos'||v4spOf(x)===sp).sort((a,b)=>(b.lean.ev??-99)-(a.lean.ev??-99));
  const key=it=>it.game.league+'/'+it.game.id;
  const draw=()=>{
    const L=items.filter(x=>V4.legs.has(key(x)));
    const n=L.length, dec=L.reduce((a,x)=>a*v4dec(x.lean.price),1), p=L.reduce((a,x)=>a*x.lean.p_final,1);
    const ev=n?(p*dec-1)*100:null, ret=n?V4.stake*dec:null, evm=n?V4.stake*(p*dec-1):null;
    const okAll=n>0&&L.every(x=>x.approved)&&ev>0;
    const why=[]; if(n&&!L.every(x=>x.approved)) why.push(`${L.filter(x=>!x.approved).length} de ${n} selecciones no pasan los candados`); if(n&&ev<=0) why.push('EV conjunto ≤ 0');
    document.getElementById('v4evh').innerHTML=`EV <b class="mono ${ev>0?'pos':ev<0?'neg':''}">${n?v4ev(ev):'—'}</b>`;
    document.getElementById('v4sim').innerHTML=`<div class="v4tiles">${v4tile('layers','Selecciones',String(n))}${v4tile('coins','Cuota combinada',n?dec.toFixed(2):'—')}${v4tile('target','Prob. conjunta',n?v4pc(p):'—','','v4pkc')}${v4tile('warn','Prob. de fallar',n?v4pc(1-p):'—')}</div>
      <div class="v4stake glow"><div><small>Monto hipotético MXN</small><div class="v4st"><button type="button" data-st="-">−</button><input id="v4amt" inputmode="numeric" value="${V4.stake}" aria-label="Monto hipotético en MXN"><button type="button" data-st="+">+</button></div></div>
        <div><small>Retorno potencial</small><b class="mono v4pkc">${ret==null?'—':'$'+ret.toLocaleString('es-MX',{minimumFractionDigits:2,maximumFractionDigits:2})}</b></div>
        <div><small>EV hipotético</small><b class="mono ${ev>0?'pos':ev<0?'neg':''}">${n?v4ev(ev):'—'}</b><em class="mono">${evm==null?'':(evm>=0?'+':'−')+'$'+Math.abs(evm).toFixed(2)}</em></div>
        <div class="v4fair"><small>Momio justo (decimal)</small><b class="mono">${n&&p>0?(1/p).toFixed(2):'—'}</b></div></div>
      ${n?(okAll?`<div class="v4ok">✓ VALIDADO · todas las selecciones pasan los candados · paper trading, no es una apuesta real</div>`:`<div class="v4warn">${v4i('warn')} NO VALIDADO · NO ES UNA APUESTA REAL<small>${esc(why.join(' · '))}</small></div>`):`<div class="v4warn">${v4i('warn')} Elige selecciones para simular · NO ES UNA APUESTA REAL</div>`}
      <p class="nb-foot">Prob. conjunta = producto de las Probabilidades oficiales NRNM (supone independencia; por eso sólo una selección por juego). Cuota combinada = producto de cuotas decimales. EV = prob. conjunta × cuota combinada − 1. Retorno = monto × cuota combinada.</p>`;
    const amt=document.getElementById('v4amt'); amt.onchange=()=>{ V4.stake=Math.max(0,Math.round(+amt.value.replace(/[^0-9.]/g,'')||0)); draw(); };
    document.querySelectorAll('[data-st]').forEach(b=>b.onclick=()=>{ V4.stake=Math.max(0,V4.stake+(b.dataset.st==='+'?50:-50)); draw(); });
  };
  const leg=it=>{ const g=it.game,l=it.lean,on=V4.legs.has(key(it)),st=v4state(it);
    return `<label class="v4leg ${on?'on':''}"><input type="checkbox" data-k="${esc(key(it))}" ${on?'checked':''}><span class="v4cb"></span>${badge(g[sides(g)[0]],26)}<div class="v4lt"><b>${esc(v4nm(g[sides(g)[0]]))} vs ${esc(v4nm(g[sides(g)[1]]))}</b><small>${esc(v4short(l,g))} · <span class="v4b v4b-${st.k} sm">${st.t}</span></small></div><span class="mono v4pkc v4lp">${v4pc(l.p_final)}</span><span class="mono v4lo">${esc(l.price_txt)}</span></label>`; };
  document.getElementById('v4legs').innerHTML=f.length?f.map(leg).join(''):`<div class="mut">Sin selecciones con cuota para este filtro.</div>`;
  document.getElementById('v4legs').onchange=e=>{ const k=e.target.dataset.k; if(!k) return; e.target.checked?V4.legs.add(k):V4.legs.delete(k); e.target.closest('.v4leg').classList.toggle('on',e.target.checked); draw(); };
  draw();
}

// ---- Rendimiento
async function viewRendimiento(){
  $app.innerHTML=`${v4hdr('PERFORMANCE LAB','Rendimiento','Récord real calificado con el marcador final. Paper trading.')}<div class="v4tiles" id="v4k"></div><div id="v4perf"><div class="skel">Cargando…</div></div>`;
  const [items,nr]=await Promise.all([v4items('hoy').catch(()=>[]),v4nrnm()]); if(!location.hash.startsWith('#/rendimiento')) return;
  document.getElementById('v4k').innerHTML=v4kpis(items,nr);
  document.getElementById('v4perf').innerHTML=(nr&&typeof nbRec==='function'?nbRec(nr.record):'<div class="card mut">—</div>')+`<p><a class="v4lnk" href="#/record/total">Récord completo ›</a> · <a class="v4lnk" href="#/tickets">Tickets ›</a></p>`;
}
