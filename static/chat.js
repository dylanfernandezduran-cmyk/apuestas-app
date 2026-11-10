/* Chat IA de NRNM (pt90u): botón flotante + panel. Responde con datos REALES de la app (picks, probabilidades, líneas, predicción, lesiones, props).
   Si el servidor tiene un LLM configurado (llave en variable de entorno) lo usa; si no (o en la versión de GitHub Pages), responde el motor local con reglas
   sobre los mismos datos. Nunca inventa cifras: si un dato no está, lo dice. */
const CH = {open:false, msgs:[], busy:false, llm:null, picks:null, picksT:0};
const CH_DISC='Estimación del modelo, no garantía de ganancia.';
const CH_CHASE='No persigas las pérdidas: subir la apuesta para recuperar no mejora el valor esperado y aumenta el riesgo de ruina.';
const CH_BAN=/\b(seguro|segura|seguros|seguras|garantizado|garantizada|garantizados|garantizadas)\b/gi;
const CH_CHASE_RE=/recuper(ar|o|ando)|perdid|cazar|perseguir|aument(ar|o|ando) la apuesta|doblar (la )?apuesta|all-?in/i;
const CH_SECTIONS=['Mi pick','Cuánto meterle','Análisis a detalle','Lesiones y alineaciones','Localía y props'];
function chPolish(html, q){
  html=String(html||'').replace(CH_BAN,'estimado');
  if(CH_CHASE_RE.test(q||'') && !/no persigas las pérdidas/i.test(html)) html+='<p>'+CH_CHASE+'</p>';
  if(!/no una garantía|no es una garantía/i.test(html)) html+='<p class="ch-disc">'+CH_DISC+'</p>';
  return html;
}
function chOpen(on){
  CH.open = on==null?true:!!on;
  chRender();
  if(CH.open){ const i=document.getElementById('chi'); if(i) i.focus(); }
}
function chSyncNav(){
  if(CH.open) return; // el FAB lleva el estado; no se marca una pestaña IA
  if(typeof setNav==='function'){
    const h=location.hash.replace(/^#\/?/,'').split('/')[0];
    const map={'':'inicio',picks:'picks',inicio:'inicio',lineas:'lineas',deportes:'sports',deporte:'sports',juego:'sports',prop:'sports',record:'record',tickets:'record',info:'record',metodo:'record',ia:'inicio'};
    setNav(map[h]||'inicio');
  }
}

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
const CH_STOP=new Set('para que como cual cuál esta este estos estas mejor pick picks meter individual sencillo apuesta apostar juego juegos partido partidos sets set linea momio cuota parlay ticket favor contra gana ganar ganador over under mas menos hoy manana tirar'.split(' '));
function chLev(a,b){ if(Math.abs(a.length-b.length)>2) return 9; const d=[...Array(b.length+1).keys()]; for(let i=1;i<=a.length;i++){ let pv=d[0]; d[0]=i; for(let j=1;j<=b.length;j++){ const t=d[j]; d[j]=Math.min(d[j]+1,d[j-1]+1,pv+(a[i-1]===b[j-1]?0:1)); pv=t; } } return d[b.length]; }
// busca equipo/jugador (con tolerancia a errores de dedo) en juegos en vivo y próximos (72 h) de todas las ligas
async function chSearchGames(qn){
  const words=qn.split(/[^a-z0-9]+/).filter(w=>w.length>=4&&!CH_STOP.has(w)); if(!words.length) return {hit:null,near:[]};
  SPORTS = SPORTS || await api('/api/sports');
  const lgs=[].concat(...SPORTS.map(s=>s.leagues.map(l=>l.key)));
  const res=await Promise.all(lgs.map(l=>api('/api/games?league='+encodeURIComponent(l),60000).catch(()=>null)));
  const now=Date.now(), cand=[];
  res.forEach(d=>{ for(const g of ((d&&d.games)||[])){ const t=Date.parse(g.date); if(g.state==='post'||!(t>now-6*36e5&&t<now+72*36e5)) continue;
    for(const side of ['home','away']){ const nm=chNorm(g[side].name), parts=nm.split(/\s+/); let sc=0;
      for(const w of words) for(const x of parts){ if(x.length<3) continue; const dd=x===w?0:chLev(w,x); const v=dd===0?3:(dd===1&&w.length>=5?2:(dd===2&&w.length>=7?1:0)); if(v>sc) sc=v; }
      if(sc) cand.push({g,side,sc,name:g[side].name}); } } });
  cand.sort((a,b)=>b.sc-a.sc||(a.g.state==='in'?-1:1));
  const hit=cand.length&&cand[0].sc>=2?cand[0]:null;
  return {hit, near:cand.slice(0,4)};
}
// pregunta por un mercado/línea concreto: «tirante +2.5 juegos», «over 22.5», «Chiefs -3», «Munar ML»
function chParseMarket(qn){
  const num=(qn.match(/([+-]?\d+(?:[.,]\d+)?)/)||[])[1]; const n=num!=null?parseFloat(num.replace(',','.')):null;
  const tot=/\b(over|under|mas de|menos de|alta|baja|total)\b/.test(qn);
  if(tot) return {mk:/\bsets?\b/.test(qn)?'stotal':'total', ou:/under|menos de|baja/.test(qn)?'under':'over', line:n==null?null:Math.abs(n)};
  if(n!=null&&/[+-]\s*\d/.test(qn)) return {mk:/\bsets?\b/.test(qn)?'sspread':'spread', line:n};
  if(/\b(ml|gana|ganar|ganador|moneyline|directo)\b/.test(qn)) return {mk:'ml'};
  return null;
}
async function chMarketAnswer(hit, m, qn){
  const g0=hit.g, side=hit.side, other=side==='home'?'away':'home';
  const d=await api(`/api/game/${encodeURIComponent(g0.league)}/${encodeURIComponent(g0.id)}`, 60000);
  const g=d.game, p=d.pred||{}, pk=d.picks, nm=g[side].name, ten=d.kind==='tennis'||g.sport==='tenis';
  const unit=ten?((m.mk==='sspread'||m.mk==='stotal')?' sets':' juegos'):'';
  const live=g.state==='in', out=[`<b>${esc(chVs(g))}</b> · ${esc(g.league_name||g.league)} · ${live?'<b>EN VIVO</b>':esc(chWhen(g.date))}`];
  const MK={ml:'ML',spread:'Spread',total:'Total',sspread:'Spread sets',stotal:'Total sets'};
  const want=m.mk==='total'||m.mk==='stotal'?(m.ou):side;
  const ask=m.mk==='ml'?`${nm} ML`:m.mk.endsWith('total')?`${m.ou==='over'?'Over':'Under'} ${m.line??''}${unit}`:`${nm} ${m.line>0?'+':''}${m.line}${unit}`;
  out.push(`Preguntas por: <b>${esc(ask)}</b>`);
  // línea y momio actuales + prob. del modelo (antes del inicio)
  const cands=(pk&&pk.candidates)||[];
  const c=cands.find(x=>(x.market===MK[m.mk]||x.market.toLowerCase()===m.mk)&&x.side===want);
  let verdict=null;
  if(c){
    out.push(`Mercado actual: <b>${esc(c.label)}</b> ${esc(c.price_txt||'')} · modelo ${chPct(c.p_final)} vs mercado ${chPct(c.p_nv)}${chEdge(c.edge)} · ${esc(c.status||'')}`);
    if(m.line!=null&&c.line!=null&&Math.abs(Math.abs(c.line)-Math.abs(m.line))>1e-9) out.push(`<span class="ch-mut">Ojo: la línea disponible es ${c.line>0?'+':''}${c.line}, no ${m.line>0?'+':''}${m.line}.</span>`);
    verdict=c.edge>0&&(c.status==='PICK'||c.status==='LEAN')?'si':(c.edge<=0?'no':'debil');
  } else if(!live) out.push('No hay momio de ese mercado publicado ahora mismo en la app.');
  // predicción NRNM para ese mercado
  let pa=null;
  if((m.mk==='spread'||m.mk==='sspread')&&p.spread&&m.mk==='spread'){
    const ph=p.spread.p_home, mg=p.spread.proj; const mine=side==='home'?mg:-mg;
    out.push(`Predicción NRNM: ${esc(nm)} por ${mine>0?'+':''}${mine.toFixed(1)}${unit} (proyección). ${m.line!=null?`Con ${m.line>0?'+':''}${m.line} cubre en la proyección: <b>${mine+m.line>0?'sí':'no'}</b>.`:''}${p.spread.line!=null?` A la línea del mercado (${esc(g.home.name)} ${p.spread.line>0?'+':''}${p.spread.line}) el modelo da ${esc(nm)} ${chPct(side==='home'?ph:p.spread.p_away)}.`:''}`);
    if(m.line!=null) pa=mine+m.line>0;
  } else if(m.mk==='total'&&p.total){
    out.push(`Predicción NRNM: total proyectado ${p.total.proj!=null?(+p.total.proj).toFixed(1):'—'}${unit} · ${esc(p.total.label||'')} ${chPct(p.total.p)}`);
    if(m.line!=null&&p.total.proj!=null) pa=m.ou==='over'?p.total.proj>m.line:p.total.proj<m.line;
  } else if(p.winner&&p.winner.probs){
    out.push(`Predicción NRNM: ${esc(nm)} gana ${chPct(p.winner.probs[side])}.`);
    if(m.mk==='ml') pa=p.winner.probs[side]>0.5;
  }
  // pick registrado del mismo mercado
  const rr=(d.record||[]).filter(r=>r.market===m.mk&&r.status!=='ANULADO');
  rr.forEach(r=>{ const same=m.mk.endsWith('total')?r.selection===m.ou:r.selection===side;
    out.push(`Pick registrado: <b>${esc(r.label)}</b> ${r.odds!=null?esc(String(r.odds>0?'+'+r.odds:r.odds)):''} · ${esc(r.status.toLowerCase())} ${same?'(mismo lado)':'(<b>lado contrario</b>)'}`);
    if(!same) verdict='contra'; if(pa!=null&&same!==pa) out.push('<span class="ch-mut">Aviso: en este mercado el pick registrado (basado en el mercado) y la proyección de NRNM no coinciden; manda el pick registrado.</span>'); });
  const lines={si:'✅ Sí tiene valor según el modelo', no:'⛔ Sin valor: el modelo no le ve ventaja a ese precio', debil:'➖ Ventaja mínima; no es pick', contra:'⛔ No: el pick de la app en ese mercado es el lado contrario'};
  let v=verdict?lines[verdict]:(pa==null?'Sin datos suficientes para un veredicto':(pa?'➖ La proyección de NRNM lo cubre, pero no hay momio/edge publicado para confirmarlo':'⛔ La proyección de NRNM no lo cubre'));
  if(verdict==='si'&&pa===false) v='➖ El mercado da ventaja pero la proyección de NRNM no lo cubre: no lo recomiendo';
  out.push(`<b>Veredicto:</b> ${v}.${live?' <span class="ch-mut">El juego ya empezó: las probabilidades son de antes del inicio.</span>':''}`);
  out.push(`<a href="${chLink(g)}">Abrir el juego →</a>`);
  return out.join('<br>');
}

function chAnalisis(d){
  const an=d.analysis||(d.picks&&d.picks.analysis); if(!an||!an.signals) return '';
  const lab={a_favor:'a favor',en_contra:'en contra',mixto:'mixto',neutral:'neutral',sin_dato:'sin dato'};
  const rows=an.signals.map(s=>`• ${esc(s.label)}: <b>${esc(lab[s.verdict]||s.verdict)}</b> — ${esc(s.detail||'sin dato')}`);
  const pk=d.picks||{};
  const head=pk.published?'Pick principal publicado':(pk.discard_reason||'Sin pick principal');
  return `<b>Análisis a detalle</b> (${esc(head)} · ${an.n_agree||0} a favor / ${an.n_present||0} con dato)<br>`+rows.join('<br>');
}
function chAgree(pr,l){ if(!pr||!l) return null;
  if(l.market==='Total'&&pr.total&&pr.total.side) return pr.total.side===l.side;
  if(l.market==='Spread'&&pr.spread&&pr.spread.side) return pr.spread.side===l.side;
  if(l.market==='ML'&&pr.winner&&pr.winner.side) return pr.winner.side===l.side;
  if(l.market==='BTTS'&&pr.btts&&pr.btts.side) return pr.btts.side===l.side;
  return null; }
async function chBestSingle(qn){
  const items=(await chPicks()).filter(it=>it.published&&it.lean&&it.lean.edge!=null&&it.lean.edge>0&&(it.status==='PICK'||it.status==='LEAN')&&Date.parse(it.game.date)>Date.now());
  const rk=it=>(it.status==='PICK'?1e3:0)+(chAgree(it.pred,it.lean)===false?-500:0)+(it.lean.score!=null?it.lean.score:(it.lean.edge||0)*(it.lean.p_final||0));
  items.sort((a,b)=>rk(b)-rk(a));
  const it=items[0]; if(!it) return 'No hay ningún pick con ventaja en las próximas 72 h.';
  const l=it.lean, pr=it.pred||{}, sg=(l.signals||{}).verdict;
  const why=[`prob. del modelo ${chPct(l.p_final)} vs ${chPct(l.p_nv)} del mercado (edge ${l.edge>0?'+':''}${l.edge.toFixed(1)} pp)`];
  if(it.confidence&&it.confidence.level) why.push('confianza '+esc(it.confidence.level));
  if(sg&&sg!=='sin_dato') why.push('señales de mercado '+esc(sg.replace('_',' ')));
  const ag=chAgree(pr,l); if(ag!=null) why.push(ag?'coincide con la Predicción NRNM':'<b>no</b> coincide con la Predicción NRNM');
  return `Mejor pick individual (${esc(it.status)}, próximas 72 h):<br><b>${esc(l.label)}</b> ${esc(l.price_txt||'')} — <a href="${chLink(it.game)}">${esc(chGame(it))}</a> (${esc(chWhen(it.game.date))})<br>Por qué: ${why.filter(Boolean).join(' · ')}.<br><span class="ch-mut">Siguientes: ${items.slice(1,3).map(x=>esc(x.lean.label)+' '+esc(x.lean.price_txt||'')).join(' · ')||'—'}. Estimaciones, no garantías. Paper trading.</span>`;
}
function chPickLine(it){
  const l=it.lean||{}; if(!l.label) return `${chGame(it)}: sin pick (sin línea de mercado).`;
  return `• <a href="${chLink(it.game)}">${esc(chGame(it))}</a> (${esc(chWhen(it.game.date))})<br>&nbsp;&nbsp;<b>${esc(l.label)}</b> ${esc(l.price_txt||'')} · prob. ${chPct(l.p_final)}${chEdge(l.edge)} · ${esc(it.status)}${it.confidence?' · confianza '+esc(it.confidence.level):''}`;
}
async function chGameAnswer(league, eid, qn){
  const d = await api(`/api/game/${encodeURIComponent(league)}/${encodeURIComponent(eid)}`, 60000);
  const g=d.game, out=[`<b>${esc(chVs(g))}</b> · ${esc(g.league_name||g.league||'')} · ${g.state==='in'?'<b>EN VIVO</b> '+(esc((d.live&&d.live.text)||g.status||'')):g.state==='post'?'FINAL':esc(chWhen(g.date))}`];
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
  // ranking / forma
  const rk=[]; for(const side of ['home','away']){ const t=g[side]; if(t&&t.rank) rk.push(`${esc(t.name)} #${t.rank}`); else if(t) rk.push(`${esc(t.name)} sin ranking ESPN`); }
  if(rk.length) out.push('Ranking: '+rk.join(' · '));
  // mercados disponibles (línea + momio)
  const o=d.odds; if(o){
    const mk=[]; if(o.ml) mk.push(`ML ${esc(g.home.name)} ${esc(String(o.ml.home>0?'+'+o.ml.home:o.ml.home))} / ${esc(g.away.name)} ${esc(String(o.ml.away>0?'+'+o.ml.away:o.ml.away))}`);
    if(o.spread&&o.spread.home) mk.push(`Hándicap ${esc(g.home.name)} ${o.spread.home.line>0?'+':''}${o.spread.home.line} (${esc(String(o.spread.home.price>0?'+'+o.spread.home.price:o.spread.home.price))})`);
    if(o.total&&o.total.over) mk.push(`Total ${o.total.over.line} (O ${esc(String(o.total.over.price>0?'+'+o.total.over.price:o.total.over.price))} / U ${esc(String((o.total.under&&o.total.under.price)>0?'+'+o.total.under.price:o.total.under&&o.total.under.price))})`);
    if(mk.length) out.push('Mercados: '+mk.join(' · '));
  } else out.push('Mercados: sin cuotas publicadas ahora mismo en la app.');
  // probs modelo vs mercado
  const mkts=((d.probs||{}).markets)||[];
  if(mkts.length){
    const bits=[];
    mkts.slice(0,4).forEach(m=>m.outcomes.slice(0,2).forEach(x=>{
      if(x.p_nv!=null||x.p_final!=null||x.p_model!=null)
        bits.push(`${esc(x.label||x.name)}: modelo ${chPct(x.p_final!=null?x.p_final:x.p_model)} · mercado ${chPct(x.p_nv)}${chEdge(x.edge)}`);
    }));
    if(bits.length) out.push(bits.slice(0,6).join('<br>'));
  }
  const p=d.pred, pk=d.picks;
  if(p&&p.score){ const sc=d.kind==='tennis'?(p.score.sets||[]).map(x=>x.join('-')).join(' '):`${p.score.home}-${p.score.away} (local-visita)`;
    out.push(`Predicción NRNM: ${esc(sc)} · ganador ${esc(p.winner.side==='draw'?'empate':g[p.winner.side].name)} ${chPct(p.winner.p)}${p.total?` · ${esc(p.total.label)}`:''}${p.spread&&p.spread.line!=null?` · hándicap proy. ${p.spread.side==='home'?g.home.name:g.away.name} ${p.spread.line>0?'+':''}${p.spread.line}`:''}`); }
  const anTxt=chAnalisis(d); if(anTxt) out.push(anTxt);
  else if(g.state==='pre'&&!p) out.push('Predicción NRNM: aún no hay (faltan datos del modelo).');
  else if(g.state!=='pre') out.push('Predicción NRNM: no aplica — el juego ya no está en pre-partido.');
  if(g.state==='pre'){
    const lean=pk&&pk.lean, predSide=p&&p.winner&&p.winner.side;
    const agrees=!lean||!predSide||lean.side===predSide||(lean.market==='ML'&&lean.side===predSide);
    if(pk.published && lean && (lean.edge>0.5 || (pk.status==='PICK') || (agrees && lean.edge!=null && lean.edge>=0))){
      out.push(`${pk.status==='PICK'?'Pick':'Lean'}: <b>${esc(lean.label)}</b> ${esc(lean.price_txt||'')} · prob. ${chPct(lean.p_final)}${chEdge(lean.edge)} · ${esc(pk.status)}${pk.confidence?' · confianza '+esc(pk.confidence.level):''}`);
      if(!agrees) out.push('<span class="ch-mut">Ojo: este lean no coincide con la Predicción NRNM.</span>');
    } else if(lean && !pk.published){
      out.push(`Sin pick principal${pk.discard_reason?': '+esc(pk.discard_reason):''}.`);
    } else {
      let best=null;
      mkts.forEach(m=>m.outcomes.forEach(x=>{ if(x.edge!=null&&(best==null||x.edge>best.edge)) best=x; }));
      // si el edge es ~0, alinear con la predicción (ganador proyectado)
      if(predSide && (!best || !(best.edge>0.5))){
        const ml=(mkts.find(m=>m.key==='ml')||{}).outcomes||[];
        const pref=ml.find(x=>x.side===predSide)||ml[0];
        if(pref) out.push(`Lean sugerido (alineado a la Predicción NRNM; no es pick oficial): <b>${esc(pref.label||pref.name)}</b> ${pref.best?esc(pref.best.price_txt):''} · modelo ${chPct(pref.p_final!=null?pref.p_final:pref.p_model)} vs mercado ${chPct(pref.p_nv)}${chEdge(pref.edge)}. Sin edge claro → mejor no forzar la apuesta.`);
        else out.push('Mejor no apostar: sin edge positivo y sin predicción clara.');
      } else if(best&&best.edge>0) out.push(`Lean sugerido (no es pick oficial): <b>${esc(best.label||best.name)}</b> edge +${best.edge.toFixed(1)} pp · modelo ${chPct(best.p_final!=null?best.p_final:best.p_model)} vs mercado ${chPct(best.p_nv)}.`);
      else if(best) out.push(`Mejor no apostar: ningún lado tiene edge positivo (mejor edge ${best.edge!=null?(best.edge>0?'+':'')+best.edge.toFixed(1)+' pp':'n/d'} en ${esc(best.label||'')}).`);
      else {
        const miss=(d.gaps||[]).filter(Boolean).slice(0,3);
        out.push('Sin pick todavía.'+(miss.length?' Motivo: '+miss.map(esc).join(' · '):' No hay modelo ni edge calculable con los datos actuales.'));
      }
    }
  }
  if(/ambos|btts/.test(qn)){
    const m=mkts.find(x=>x.key==='btts');
    if(m) m.outcomes.forEach(o=>out.push(`${esc(o.label)}: modelo ${chPct(o.p_model)} · mercado ${chPct(o.p_nv)}${o.best?' · '+esc(o.best.price_txt):''}${chEdge(o.edge)}`));
    else out.push('Sin datos de «Ambos anotan» para este juego.');
  }
  const rec=(d.record||[]).filter(r=>r.open_line!=null&&r.line!=null&&r.open_line!==r.line);
  rec.slice(0,3).forEach(r=>out.push(`Línea movida: ${esc(r.label)} · abrió ${r.open_line} → ${g.state==='pre'?'actual':'cierre'} ${r.line}${r.state&&r.status==='ANULADO'?' ('+esc(r.state.toLowerCase())+')':''}`));
  out.push(`<a href="${chLink(g)}">Abrir el juego →</a>`);
  return out.join('<br>');
}
const CH_NUM={dos:2,tres:3,cuatro:4,cinco:5,seis:6};
async function chParlay(qn){
  const n=Math.min(6,Math.max(2,+((qn.match(/\b([2-6])\b/)||[])[1]||CH_NUM[(qn.match(/\b(dos|tres|cuatro|cinco|seis)\b/)||[])[1]]||3)));
  const sp={nba:/nba|basket/,nfl:/nfl|americano/,nhl:/nhl|hockey/,futbol:/futbol|soccer|liga mx|premier/,tenis:/tenis|atp|wta/,mlb:/mlb|beis/};
  const spk=Object.keys(sp).find(k=>sp[k].test(qn));
  let scope=/manana/.test(qn)?'manana':'hoy', d=await api('/api/picks?scope='+scope);
  // picks oficiales si el modo estricto está encendido; si no (por defecto), el pick del juego (PICK o LEAN)
  const off=x=>((x.official&&x.official.length)?x.official:((x.status==='PICK'||x.status==='LEAN')&&x.lean?[x.lean]:[])).filter(c=>c.price!=null&&c.edge!=null&&c.edge>0&&['ML','Spread','Total','BTTS'].includes(c.market));
  const rk=c=>c.score!=null?c.score:(c.edge||0)*(c.p_final||0);
  const fut=it=>Date.parse(it.game.date)>Date.now()+60e3;          // la versión en línea puede traer juegos que ya empezaron
  let pool=d.items.filter(it=>fut(it)&&off(it).length&&(!spk||it.game.sport===spk));
  if(scope==='hoy'&&pool.length<n){ const d2=await api('/api/picks?scope=24h'); const have=new Set(pool.map(it=>it.game.league+it.game.id)); pool=pool.concat(d2.items.filter(it=>fut(it)&&off(it).length&&(!spk||it.game.sport===spk)&&!have.has(it.game.league+it.game.id))); scope='24h'; }
  pool.sort((a,b)=>(b.status==='PICK')-(a.status==='PICK')||rk(off(b)[0])-rk(off(a)[0]));
  const pick=pool.slice(0,n);
  if(!pick.length) return `No hay picks con ventaja${spk?' de '+spk.toUpperCase():''} ${scope==='manana'?'mañana':'en las próximas 24 h'}, así que no armo un parlay con relleno.`;
  const legs=pick.map(it=>tkLegFromCand(it.game,Object.assign({official:it.status==='PICK'},off(it)[0])));
  const dd=legs.reduce((a,l)=>a*tkDec(l.odds),1), pm=legs.every(l=>l.p!=null)?legs.reduce((a,l)=>a*l.p,1):null;
  CH.parlay=legs;
  const lines=pick.map((it,i)=>{ const c=off(it)[0], v=(c.signals||{}).verdict; return `${i+1}. <b>${esc(c.label)}</b> ${esc(c.price_txt||'')} — ${esc(chGame(it))} (${esc(chWhen(it.game.date))})<br>&nbsp;&nbsp;${c.score!=null?'puntaje '+c.score+'/100 · ':''}${esc(it.status)} · prob. ${chPct(c.p_final)}${chEdge(c.edge)}${v&&v!=='sin_dato'?' · señales '+esc(v.replace('_',' ')):''}`; });
  return `Parlay de ${legs.length}${legs.length<n?` (sólo hay ${legs.length} picks con ventaja; no relleno)`:''} con los picks de mayor ventaja (PICK primero), 1 por juego (sin correlación):<br>${lines.join('<br>')}
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
  // Primero entidad (equipo/jugador/torneo): «mejor pick en el juego de X» responde ese juego, no el mejor global
  const cur=chCurGame(), items=await chPicks();
  let named=chFindGame(items,qn), near=[];
  const srEnt=(!named)?await chSearchGames(qn):null;
  if(!named && srEnt && srEnt.hit) named={game:srEnt.hit.g};
  if(srEnt) near=srEnt.near||[];
  if(named){
    const mq=chParseMarket(qn);
    if(mq){
      const hit=(srEnt&&srEnt.hit)||(await chSearchGames(qn)).hit;
      if(hit) return chMarketAnswer(hit, mq, qn);
    }
    return chGameAnswer(named.game.league, named.game.id, qn);
  }
  const mq=chParseMarket(qn);
  if(mq){
    const w=qn.split(/[^a-z0-9]+/).filter(x=>x.length>=4&&!CH_STOP.has(x));
    if(w.length) return `No encontré «${esc(w.join(' '))}» en juegos en vivo o de las próximas 72 h.${near.length?' ¿Quisiste decir: '+near.map(c=>`<a href="${chLink(c.g)}">${esc(c.name)}</a>`).join(', ')+'?':''}`;
  }
  // Mejor pick / individual global SÓLO sin entidad
  if(/individual|sencill|solo uno|un solo pick|el mejor pick|mejor pick para|mejor apuesta|que le meto/.test(qn) && !/\bvs\b/.test(qn))
    return chBestSingle(qn);
  if(cur && (/(este|esta|del|el) (juego|partido)|aqui/.test(qn) || (/lesion|baja|prop|jugador|marcador|prediccion/.test(qn) && !/mejores|hoy|manana|todos/.test(qn)))) return chGameAnswer(cur.league, cur.eid, qn);
  let pool=items.filter(it=>it.lean&&it.lean.edge!=null);
  const sp={nba:/nba|basket/,nfl:/nfl|americano/,mlb:/mlb|beis/,nhl:/nhl|hockey/,futbol:/futbol|soccer|liga mx|premier|champions/,tenis:/tenis|atp|wta/};
  for(const [k,re] of Object.entries(sp)) if(re.test(qn)) pool=pool.filter(it=>it.game.sport===k);
  if(/ambos anotan|btts/.test(qn)) pool=pool.filter(it=>(it.lean.market||'')==='BTTS'||(it.top||[]).some(t=>t.market==='BTTS'));
  if(/hoy/.test(qn)){ const today=new Intl.DateTimeFormat('en-CA',{timeZone:TZ}).format(new Date()); pool=pool.filter(it=>new Intl.DateTimeFormat('en-CA',{timeZone:TZ}).format(new Date(it.game.date))===today); }
  if(/pick|recomien|apost|mejor|valor|hoy|manana|parlay|btts|ambos/.test(qn) || pool.length!==items.length){
    pool.sort((a,b)=>(b.status==='PICK')-(a.status==='PICK')||(b.lean.edge||0)-(a.lean.edge||0));
    if(!pool.length) return 'No encuentro picks con ventaja para eso en las próximas 72 h.';
    return `Mejores picks (por edge, próximas 72 h${/hoy/.test(qn)?', hoy':''}):<br>`+pool.slice(0,5).map(chPickLine).join('<br>')+'<br><span class="ch-mut">Estimaciones del modelo, no garantías. Paper trading.</span>';
  }
  return 'No encontré ese equipo/juego en los próximos 3 días. Prueba con el nombre del equipo (ej. «Real Madrid», «Lakers»), «mejores picks hoy», «props» o «lesiones» desde un juego abierto.';
}
async function chAsk(q){
  if(CH.llm==null && !STATIC){ try{ CH.llm=(await api('/api/chat/status',8000)).llm; }catch(e){ CH.llm=false; } }
  if(CH.llm && !STATIC && !/parlay|parley|combinad|ticket|arma/.test(chNorm(q))){
    try{
      const c=chCurGame();
      const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.assign({q, league:c&&c.league, eid:c&&c.eid}, (typeof BK==='function'?BK():{})))});
      const d=await r.json();
      if(d.llm&&d.text) return {html:chPolish(esc(d.text).replace(/\*\*(.+?)\*\*/g,'<b>$1</b>').replace(/\n/g,'<br>'), q), src:'IA ('+esc(d.model||'LLM')+') con datos de la app'};
    }catch(e){}
  }
  return {html: await chLocal(q), src: 'Respuesta con datos de la app (motor local'+(STATIC?', versión en línea':'')+')'};
}
function chRender(){
  let p=document.getElementById('chp');
  if(!p){ p=document.createElement('div'); p.id='chp'; p.setAttribute('role','dialog'); p.setAttribute('aria-label','Chat IA'); document.body.appendChild(p); }
  p.hidden=!CH.open; const fab=document.getElementById('chb'); if(fab) fab.classList.toggle('on',CH.open); chSyncNav();
  if(!CH.open) return;
  const _bk=typeof BK==='function'?BK():{bankroll:'',unit_pct:1};
  const sug=['Props NBA','Alineaciones','Armar ticket'].concat(chCurGame()?['Lesiones de este juego','Props de este juego']:[]);
  p.innerHTML=`<div class="ch-h"><b>Analista NRNM · datos reales</b><span>IA con datos reales</span><button type="button" class="ch-x" aria-label="Cerrar">✕</button></div>
    <div class="ch-m" id="chm">${CH.msgs.length?CH.msgs.map(m=>`<div class="ch-${m.r}">${m.h}${m.s?`<small>${m.s}</small>`:''}</div>`).join(''):'<div class="ch-a">Hola, pregúntame por picks, un equipo, lesiones, props o el récord. Uso sólo los datos de la app.</div>'}${CH.busy?'<div class="ch-a ch-dots"><i></i><i></i><i></i></div>':''}</div>
    <div class="ch-s">${sug.map(s=>`<button type="button" class="ch-sg">${esc(s)}</button>`).join('')}</div>
    <div class="ch-bk"><label>Bankroll <input id="ch-bk" type="number" min="0" step="1" value="${_bk.bankroll||''}" placeholder="opcional"></label>
    <label>1u % <input id="ch-u" type="number" min="0.1" max="5" step="0.1" value="${_bk.unit_pct}"></label></div>
    <form class="ch-f"><input id="chi" type="text" autocomplete="off" placeholder="Escribe tu pregunta…" maxlength="400"><button type="submit" aria-label="Enviar">➤</button></form>`;
  const bki=document.getElementById('ch-bk'), bku=document.getElementById('ch-u');
  const sav=()=>{ if(typeof BKSet==='function') BKSet(bki&&bki.value, bku&&bku.value); };
  if(bki) bki.addEventListener('change',sav); if(bku) bku.addEventListener('change',sav);
  const m=document.getElementById('chm'); m.scrollTop=m.scrollHeight;
}
async function chSend(q){
  q=String(q||'').trim(); if(!q||CH.busy) return;
  CH.msgs.push({r:'u',h:esc(q)}); CH.busy=true; chRender();
  try{ const a=await chAsk(q); CH.msgs.push({r:'a',h:chPolish(a.html,q),s:a.src}); }
  catch(e){ CH.msgs.push({r:'a',h:'No pude consultar los datos: '+esc(e.message)}); }
  CH.busy=false; chRender(); const i=document.getElementById('chi'); if(i) i.focus();
}
(function(){
  const b=document.createElement('button'); b.id='chb'; b.type='button'; b.setAttribute('aria-label','Abrir chat IA'); b.innerHTML='<svg class="ic" viewBox="0 0 137 131" width="26" height="25" aria-hidden="true" fill="currentColor"><path d="M33.79,30.08 C48.66,15.2 70.57,11.45 88.86,18.99 C92.91,20.5 96.44,22.64 99.19,24.63 L83.91,31.69 C69.69,25.72 53.39,29.78 43.45,39.74 C30.01,53.2 27.29,76.53 43.05,91.6 L43.03,91.6 L0,130.08 C2.73,126.32 6.11,122.76 9.49,119.21 C9.9665,118.709 10.442825,118.2082 10.91708,117.707078 L11.4850711,117.105542 C20.269773,107.77831 28.0761,98.2672 22.71,85.21 C14.99,66.42 19.49,44.4 33.79,30.08 Z M135.52,0 C135.18,0.47 134.84,0.94 134.51,1.4 C120.34,20.93 113.43,30.48 118.98,54.38 L118.95,54.35 C122.78,70.62 118.69,88.66 105.47,101.89 C88.81,118.58 62.14,122.3 40.18,107.27 L55.49,100.17 C69.51,105.68 84.84,103.26 95.86,92.23 C106.88,81.19 109.36,65.12 103.82,51.75 C102.77,49.21 99.61,48.58 97.4,50.21 L52.35,83.51 L116.88,18.6 L116.88,18.66 Z"/></svg>';
  document.body.appendChild(b);
  b.addEventListener('click',()=>{ CH.open=!CH.open; chRender(); if(CH.open){ const i=document.getElementById('chi'); if(i) i.focus(); } });

  document.addEventListener('click',e=>{
    if(e.target.closest('#chp .ch-x')){ CH.open=false; chRender(); }
    const s=e.target.closest('#chp .ch-sg'); if(s) chSend(s.textContent);
    if(e.target.closest('#chp .ch-m a')){ CH.open=false; chRender(); }
  });
  document.addEventListener('submit',e=>{ if(e.target.closest('#chp .ch-f')){ e.preventDefault(); const i=document.getElementById('chi'); const v=i.value; i.value=''; chSend(v); } });
})();
// Versión nueva: NUNCA autorecargar en bucle (iOS Safari cachea el HTML y location.reload() vuelve al viejo → pantalla en blanco).
// Como mucho 1 recarga con cache-bust por sesión; si sigue desfasado, un banner pide tocar para actualizar.
(function(){
  const KEY='nrnm_ver_reloaded', BAN='nrnm_ver_banner';
  const vers=t=>{const o=[]; const re=/<script src="([^"]+\?v=\d+)"/g; let m; while((m=re.exec(t))) o.push(m[1]); return o.sort().join('|');};
  const mine=()=>[...document.scripts].map(s=>s.getAttribute('src')||'').filter(x=>/\?v=/.test(x)).sort().join('|');
  function banner(){ if(document.getElementById(BAN)) return;
    const b=document.createElement('button'); b.id=BAN; b.type='button';
    b.textContent='Hay una versión nueva — toca para actualizar';
    b.setAttribute('style','position:fixed;left:12px;right:12px;bottom:calc(18px + env(safe-area-inset-bottom));z-index:99999;padding:14px 16px;border:0;border-radius:14px;background:linear-gradient(135deg,#FF1179,#3C85F7);color:#fff;font:600 15px/1.3 system-ui,sans-serif;box-shadow:0 8px 24px rgba(0,0,0,.45)');
    b.onclick=()=>{ try{sessionStorage.removeItem(KEY);}catch(e){} location.href=location.pathname+(location.search?location.search+'&':'?')+'_='+Date.now()+location.hash; };
    document.body.appendChild(b); }
  async function chk(){ try{
      if(sessionStorage.getItem(BAN)==='1'){ banner(); return; }
      const r=await fetch(location.pathname.replace(/\/index\.html$/,'/')||'./',{cache:'no-store',headers:{'Cache-Control':'no-cache'}});
      if(!r.ok) return;
      const vs=vers(await r.text()); if(!vs||vs===mine()) return;
      if(sessionStorage.getItem(KEY)==='1'){ try{sessionStorage.setItem(BAN,'1');}catch(e){} banner(); return; }
      try{sessionStorage.setItem(KEY,'1');}catch(e){}
      location.href=location.pathname+(location.search?location.search+'&':'?')+'_='+Date.now()+location.hash;
    }catch(e){} }
  document.addEventListener('visibilitychange',()=>{ if(document.visibilityState==='visible') chk(); });
  setTimeout(chk, 8e3);
  setInterval(()=>{ if(document.visibilityState==='visible') chk(); }, 30*60e3);
})();
