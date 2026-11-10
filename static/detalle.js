/* Detalle de juego premium (pt75u): 16 secciones visibles, compactas y en orden fijo. Sólo datos reales; sin datos => la sección no se dibuja. */
const DC = {pk:'#8B7CC7', tl:'#2dd4bf', bl:'#8B7CC7', am:'#F5B942', gr:'#3A3A52'};
const DST = {rec:'t0', shut:{}, info:{}};   // estado que sobrevive al refresco en vivo (pestaña, secciones plegadas, ⓘ abiertos)
const sideColor = (g,sd) => sd==='draw' ? DC.gr : sd==='over' ? DC.bl : sd==='under' ? DC.tl : (sides(g)[0]===sd ? DC.bl : DC.tl);
const n1 = (v,dg=1) => (v==null||isNaN(v)) ? SD : Number(v).toFixed(dg).replace(/\.0+$/,'').replace(/(\.\d)0$/,'$1');
const winp = s => (s&&s.n) ? (s.w+.5*(s.d||0))/s.n : null;
const tAbbr = T => esc((T&&(T.abbr||T.short))||((T&&T.name)||'').split(' ').slice(-1)[0]);

function ds(key, title, body, o={}){
  if(!body || !String(body).trim()) return '';
  const info = o.info ? `<div class="di" ${DST.info[key]?'':'hidden'}>${o.info}</div>` : '';
  return `<section class="ds ${o.cls||''}${DST.shut[key]?' shut':''}" data-k="${key}"><h3 class="dh"><span class="ttl" role="button" tabindex="0">${title}</span>${o.right?`<span class="dr">${o.right}</span>`:''}${o.info?`<button type="button" class="ib${DST.info[key]?' on':''}" aria-label="Más información">i</button>`:''}</h3>${info}<div class="db">${body}</div></section>`;
}
const nd = t => `<div class="nd">${t}</div>`;
const tag2 = (t,c='') => `<span class="tg2 ${c}">${t}</span>`;

// ---- 1. Picks registrados
// línea movida (pt90u): «Abrió 48.5 · Actual 40.5» + estado (actualizado / invertido / cancelado / cierre bloqueado)
const LMS = {ACTUALIZADO:['lm-up','Actualizado'], INVERTIDO:['lm-fl','Invertido'], CANCELADO:['lm-cx','Cancelado']};
function lineMove(r,g){
  const fl=v=>v==null?'':(/spread$/.test(r.market)?sg(v):String(v));
  const lineMoved = r.open_line!=null && r.line!=null && r.open_line!==r.line, oddsMoved = r.open_odds!=null && r.odds!=null && r.open_odds!==r.odds;
  const started = g && g.state!=='pre';
  const cur = started ? 'Cierre' : 'Actual';
  const bits=[];
  if(lineMoved) bits.push(`Abrió <b class="mono">${esc(fl(r.open_line))}</b> · ${cur} <b class="mono">${esc(fl(r.line))}</b>`);
  if(oddsMoved) bits.push(`Cuota ${esc(am(r.open_odds))} → <b class="mono">${esc(am(r.odds))}</b>`);
  const st = r.status==='ANULADO' && LMS[r.state] ? LMS[r.state] : (lineMoved||oddsMoved) && r.state==='ACTUALIZADO' ? LMS.ACTUALIZADO : null;
  if(!bits.length && !st) return '';
  const lock = started && r.status!=='ANULADO' ? `<span class="lm-tg lm-lk">🔒 Cierre</span>` : '';
  return `<span class="lm">${st?`<span class="lm-tg ${st[0]}">${st[1]}</span>`:''}${lock}${bits.join(' · ')}${r.status==='ANULADO'&&r.note?`<em>${esc(r.note)}</em>`:''}</span>`;
}
function dRec(d){
  const rows=d.record||[], g=d.game; if(!rows.length) return '';
  const fin=rows.find(r=>r.score_text);
  const right = fin ? tag2('FINAL · '+esc(fin.score_text),'fin') : g.state==='in' ? tag2('● EN VIVO','live') : tag2('PRE-JUEGO');
  const body = rows.map(r=>{
    const st = r.status==='PENDIENTE'&&g.state==='in' ? (provBadge(PROV,r.market,r.selection)||gradeBadge(r,false)) : gradeBadge(r,false);
    return `<div class="rr2${r.status==='ANULADO'&&r.state?' lmx':''}"><div class="rlx"><b>${esc(r.label)}</b><span class="mt">${r.type==='main'?'Principal':'Sugerencia'} · ${oddsTxt(r)}${r.line!=null?' · línea '+(/spread$/.test(r.market)?sg(r.line):r.line):''}${r.p_model!=null?' · modelo '+pct(r.p_model,0):''}</span>${lineMove(r,g)}</div>
      <div class="rg">${st}${r.units!=null?`<b class="mono ${r.units>0?'k-t':r.units<0?'k-p':'mut'}">${units(r.units)}</b>`:''}</div></div>`; }).join('');
  return ds('rec','Picks registrados',body,{right, info:'Cada pick guarda su línea/cuota de APERTURA y, hasta que empieza el juego, se re-evalúa con el modelo a la línea ACTUAL: si la línea se mueve se actualiza («Abrió 48.5 · Actual 40.5»); si el modelo ahora prefiere el otro lado queda INVERTIDO (y se registra el lado nuevo); si ya no hay valor queda CANCELADO. Al inicio se bloquea la línea de cierre y se califica contra ella. Se califican solos con el marcador final de ESPN cada ~10 min; mientras no haya final confirmado quedan pendientes. Unidades a 1u plano.'});
}

// ---- 2. Mejores picks

function dMiPickBooks(d){
  const l=d.picks&&d.picks.lean, mk=d.market, g=d.game;
  if(!l||!mk||!mk.books||!mk.books.length||l.p_final==null) return '';
  const key=({ML:'ml',Spread:'spread',Total:'total',BTTS:'btts'})[l.market]||String(l.market||'').toLowerCase();
  const side=l.side;
  const rows=[];
  for(const b of mk.books){
    const block=b[key]; if(!block) continue;
    let price=null, line=null;
    if(block[side]!=null && typeof block[side]==='object'){ price=block[side].price!=null?block[side].price:block[side]; line=block[side].line; }
    else if(block[side]!=null) price=block[side];
    if(price==null||isNaN(price)) continue;
    const evv=typeof ev==='function'?ev(l.p_final, price)*100:null;
    rows.push({name:b.name||b.id||'Casa', price, ev:evv, line});
  }
  if(!rows.length) return '<div class="sub">Comparación por casa: sin dato</div>';
  rows.sort((a,b)=>(b.ev==null?-999:b.ev)-(a.ev==null?-999:a.ev));
  const best=rows[0];
  return `<div class="mp-books"><div class="sub">Precio por casa (compra el mejor)</div>${rows.map(r=>`<div class="book-row ${r===best?'best':''}"><span>${esc(r.name)}</span><span class="mono">${r.price>0?'+':''}${r.price}${r.ev!=null?` · EV ${(r.ev>0?'+':'')+r.ev.toFixed(1)}%`:''}</span>${r===best?'<span class="tag-best">compra el mejor</span>':''}</div>`).join('')}</div>`;
}
function dPicks(d){
  const p=d.picks, g=d.game; if(!p) return '';
  if(p.strict) return dPicksStrict(d);
  const l=p.lean, c=p.confidence, st=STATUS[p.status]||STATUS.PASS;
  const rr=recFor(mktKey(l),l.side,l.line);
  const gb = rr ? (rr.status==='PENDIENTE'&&g.state==='in' ? (provBadge(PROV,rr.market,rr.selection)||gradeBadge(rr,true)) : gradeBadge(rr,true)) : '';
  const cell=(k,v,cls='')=>`<div class="pc"><small>${k}</small><b class="mono ${cls}">${v}</b></div>`;
  const evTxt = l.ev==null?SD:sg(l.ev)+'%';
  const edgeLbl = l.divergence_high ? 'Divergencia alta' : (l.edge==null?SD:sg(l.edge)+' pp');
  const edgeCls = l.divergence_high ? 'k-a' : (l.edge>0?'k-t':'k-p');
  const cells = l.price_txt ? [cell('Cuota',esc(l.price_txt)),cell('Prob. final',pct(l.p_final,0)),cell(l.divergence_high?'Divergencia':('Edge <abbr'+((typeof tip==='function')?tip('edge'):'')+'>s/vig</abbr>'),edgeLbl,edgeCls),cell('<abbr'+((typeof tip==='function')?tip('EV'):'')+'>EV</abbr>',evTxt,l.ev>0?'k-t':l.ev<0?'k-p':''),cell('Confianza',c?esc(c.level):SD)]
    : [cell('Cuota',SD),cell('Prob. modelo',pct(l.p_final!=null?l.p_final:l.p_model,0)),cell('Edge',SD),cell('<abbr'+((typeof tip==='function')?tip('EV'):'')+'>EV</abbr>',SD),cell('Confianza',c?esc(c.level):SD)];
  const sig=l.signals&&l.signals.verdict&&l.signals.verdict!=='sin_dato' ? `<div class="sgl"><span class="${({a_favor:'k-t',en_contra:'k-p',mixto:'k-a'})[l.signals.verdict]||'mut'}">●</span> ${esc((VERD[l.signals.verdict]||[])[1]||'')}${l.signals.best?` · mejor precio <b class="mono">${esc(l.signals.best.price_txt)}</b> en ${esc(l.signals.best.book)}`:''}</div>` : '';
  const main = `<div class="mp2 ${p.status==='PICK'?'hot':''}"><div class="mph"><span class="mpk ${p.status==='PICK'?'k-p':p.status==='LEAN'?'k-a':'mut'}">${esc(st[1])}</span>${gb}</div>
    <div class="mpl">${esc(l.label)}</div><div class="pcs">${cells.join('')}</div>${sig}${g.state==='pre'&&l.price!=null?`<div class="tkrow">${tkBtn(tkLegFromCand(g,Object.assign({official:p.status==='PICK'},l)),'Agregar al ticket')}</div>`:''}${dMiPickBooks(d)}</div>`;
  const cs=(p.candidates||[]).filter(x=>x.p_model!=null||x.p_nv!=null).slice().sort((a,b)=>{
    const da=a.divergence_high?1:0, db=b.divergence_high?1:0; if(da!==db) return da-db;
    const ea=a.ev??-999, eb=b.ev??-999; if(eb!==ea) return eb-ea;
    return (b.edge??-99)-(a.edge??-99);
  });
  const crow=x=>{ const e=x.edge, pv=x.p_model!=null?x.p_model:x.p_nv, r2=recFor(mktKey(x),x.side,x.line);
    const evb = x.ev==null?'':((x.ev>0?'+':'')+Number(x.ev).toFixed(1)+'% EV');
    return `<div class="cr2"><div class="cl"><b>${esc(shortLbl(x.label,g))}</b><span class="mt">${esc(x.price_txt||SD)}${evb?' · '+evb:''}${x.divergence_high?' · Divergencia alta':''}${r2?' · '+gradeBadge(r2,false):''}</span></div><div class="cb"><span class="pbar"><i style="width:${Math.round((pv||0)*100)}%;background:${e>=3&&!x.divergence_high?DC.tl:DC.bl}"></i></span></div><div class="cp mono">${pct(pv,0)}</div><div class="ce mono ${x.divergence_high?'k-a':e>0?'k-t':e<0?'k-p':'mut'}">${x.divergence_high?'div.':(e==null?'':sg(e))}</div>${g.state==='pre'&&x.price!=null?tkBtn(tkLegFromCand(g,Object.assign({official:x.status==='PICK'},x)),'+'):''}</div>`; };
  const top=cs.slice(0,4), rest=cs.slice(4);
  const list = cs.length ? `<div class="cl2">${top.map(crow).join('')}${rest.length?`<div class="gp"><div class="tg" role="button" tabindex="0">Ver ${rest.length} más</div><div class="sg">${rest.map(crow).join('')}</div></div>`:''}</div>` : '';
  const why=[ 'Prob. final = mezcla modelo/mercado'+(d.model&&d.model.w_model!=null?` (${Math.round(d.model.w_model*100)}% modelo, ${100-Math.round(d.model.w_model*100)}% mercado s/vig)`:'')+'. Edge = prob. final − prob. s/vig del mercado, en puntos porcentuales. Precio máx. = el que deja EV ≥ +2%.',
    c&&c.reasons&&c.reasons.length?'Confianza: '+esc(c.reasons.join(' · '))+'.':'', l.downgraded?'Era PICK pero se degradó a LEAN por confianza baja.':'', p.status==='PASS'?'Sin ventaja suficiente en ningún mercado: es el lean menos malo, no una recomendación fuerte.':'', l.price_txt?'':'Sin precio de mercado: sólo valdría la pena a ese momio o mejor.'].filter(Boolean).join(' ');
  return ds('picks','Mejores picks',main+list,{right:tag2('ESTIMACIÓN','mod'), info:why});
}

// ---- 2. Mejores picks (estricto: máx. 1 pick oficial por juego, coherente con la Predicción NRNM; lo demás sólo «También considerado»)
const SCP = {edge:'Edge',prob:'Prob.',señales:'Señales',confianza:'Confianza',contexto:'Contexto'};
function dPicksStrict(d){
  const p=d.picks, g=d.game; if(!p) return '';
  const c=p.confidence, off=p.official||[], cons=p.considered||[];
  const cell=(k,v,cls='')=>`<div class="pc"><small>${k}</small><b class="mono ${cls}">${v}</b></div>`;
  const parts=x=>x.score_parts?`<div class="scp">${Object.entries(x.score_parts).map(([k,v])=>`<span>${SCP[k]||k} <b class="mono">${Math.round(v)}</b></span>`).join('')}</div>`:'';
  const sigL=x=>x.signals&&x.signals.verdict&&x.signals.verdict!=='sin_dato' ? `<div class="sgl"><span class="${({a_favor:'k-t',en_contra:'k-p',mixto:'k-a'})[x.signals.verdict]||'mut'}">●</span> ${esc((VERD[x.signals.verdict]||[])[1]||'')}${x.signals.best?` · mejor precio <b class="mono">${esc(x.signals.best.price_txt)}</b> en ${esc(x.signals.best.book)}`:''}</div>` : '';
  const card=(x,i)=>{ const rr=recFor(mktKey(x),x.side,x.line);
    const gb = rr ? (rr.status==='PENDIENTE'&&g.state==='in' ? (provBadge(PROV,rr.market,rr.selection)||gradeBadge(rr,true)) : gradeBadge(rr,true)) : '';
    return `<div class="mp2 hot"><div class="mph"><span class="mpk k-p">${i?'2.º PICK OFICIAL':'PICK OFICIAL'}</span><span class="scb mono">${x.score}/100</span>${gb}</div>
    <div class="mpl">${esc(x.label)}</div><div class="pcs">${[cell('Cuota',esc(x.price_txt||SD)),cell('Prob. final',pct(x.p_final,0)),cell('Edge',sg(x.edge)+' pp',x.edge>0?'k-t':'k-p'),cell('Confianza',c?esc(c.level):SD)].join('')}</div>
    ${parts(x)}${sigL(x)}${g.state==='pre'?`<div class="tkrow">${tkBtn(tkLegFromCand(g,Object.assign({official:true},x)))}</div>`:''}</div>`; };
  const l=p.lean;
  const none = `<div class="mp2"><div class="mph"><span class="mpk mut">SIN PICK OFICIAL</span></div><div class="mpl">Ningún mercado pasa el filtro estricto</div>
    <div class="sub">${l&&l.why_not&&l.why_not.length?'Mejor opción: <b>'+esc(l.label)+'</b> — no pasa por: '+esc(l.why_not.join(' · '))+'.':'Sin ventaja suficiente o sin línea.'}</div></div>`;
  const crow=x=>`<div class="cr2"><div class="cl"><b>${esc(shortLbl(x.label,g))}</b><span class="mt">${esc(x.price_txt||SD)} · ${x.score??'—'}/100${x.why_not&&x.why_not.length?' · '+esc(x.why_not[0]):''}</span></div><div class="cp mono">${pct(x.p_final,0)}</div><div class="ce mono ${x.edge>0?'k-t':'mut'}">${x.edge==null?'':sg(x.edge)}</div>${g.state==='pre'?tkBtn(tkLegFromCand(g,Object.assign({official:false},x)),'+'):''}</div>`;
  const alt = cons.length ? `<div class="gp"><div class="tg" role="button" tabindex="0">También considerado (${cons.length}) · no recomendado</div><div class="sg"><div class="cl2">${cons.map(crow).join('')}</div></div></div>` : '';
  const S=p.strict||{};
  const why=[`Pick oficial = pasa TODOS los filtros: edge ≥ ${S.edge_min??2} pp, prob. final ≥ ${Math.round((S.p_min??.55)*100)}%, señales de mercado no en contra, sin jugador clave en duda, puntaje ≥ ${S.score_min??60}/100, y coincide con la Predicción NRNM. Máximo 1 por juego (2 sólo si son de otro mercado y ambos ≥ ${S.second_min??75}/100).`,
    'Puntaje 0-100: edge 35 · prob. 25 · señales (RLM / dinero vs tickets) 15 · confianza (muestra, modelo vs mercado, lesiones, abridores) 15 · contexto (clima/datos críticos) 10. Forma, H2H, descanso y localía entran vía las calificaciones del modelo.',
    c&&c.reasons&&c.reasons.length?'Confianza: '+esc(c.reasons.join(' · '))+'.':''].filter(Boolean).join(' ');
  return ds('picks','Pick oficial',(off.length?off.map(card).join(''):none)+alt,{right:tag2('ESTRICTO','mod'), info:why});
}
// ---- 3. Probabilidades
function dProb(d){
  const P=d.probs, g=d.game; if(!P||!P.markets||!P.markets.length) return '';
  const mk=P.markets.filter(m=>m.outcomes&&m.outcomes.length).slice().sort((a,b)=>(MK_ORDER[a.key]??9)-(MK_ORDER[b.key]??9));
  const ord=m=>{ if(m.key==='ml'||m.key==='spread'){ const th=m.outcomes.length===3; const o=mlSides(g,th); return m.outcomes.slice().sort((a,b)=>o.indexOf(a.side)-o.indexOf(b.side)); } if(m.key==='total') return m.outcomes.slice().sort((a,b)=>(a.side==='over'?0:1)-(b.side==='over'?0:1)); return m.outcomes; };
  const body=mk.map(m=>{
    const outs=ord(m).filter(o=>o.p_final!=null||o.p_nv!=null||o.p_model!=null).map(o=>{
      const pf=o.p_final!=null?o.p_final:(o.p_nv!=null?o.p_nv:o.p_model), e=o.edge, rr=recFor(o.market,o.side,o.line);
      const col=e!=null&&e>=3?DC.tl:e!=null&&e<=-3?DC.pk:DC.bl;
      return `<div class="pb"><div class="pbl"><b>${esc(obLabel(o,g))}</b>${rr?gradeBadge(rr,false):''}<span class="pv mono">${pct(pf,0)}</span></div>
        <div class="pbar"><i style="width:${Math.round(pf*100)}%;background:${col}"></i>${o.p_nv!=null?`<u style="left:${(o.p_nv*100).toFixed(1)}%"></u>`:''}</div>
        <div class="pbm">${[o.p_model_raw!=null?`modelo ${pct(o.p_model,0)}`:'sin modelo',o.p_nv!=null?`mercado ${pct(o.p_nv,0)}`:'',o.fair_txt?`justa ${esc(o.fair_txt)}`:'',e!=null&&Math.abs(e)>=1?`<b class="${e>0?'k-t':'k-p'}">${sg(e)} pp</b>`:''].filter(Boolean).map(t=>`<span>${t}</span>`).join('')}</div></div>`; }).join('');
    if(!outs) return '';
    const ln=m.outcomes[0]&&m.outcomes[0].line!=null&&m.key!=='ml'?` · ${/spread$/.test(m.key)?sg(m.outcomes[0].line):m.outcomes[0].line}`:'';
    return `<div class="pbk"><div class="pbt">${esc(mkTitle(m,g))}${ln}</div>${outs}</div>`; }).join('');
  const info='<b>Barra</b> = probabilidad final (mezcla modelo/mercado)'+(P.w_model!=null?` · ${Math.round(P.w_model*100)}% modelo`:'')+'. <b>Marca blanca</b> = mercado sin comisión. <b>Edge</b> = final − mercado (pp): teal ≥ +3, rosa ≤ −3. <b>Justa</b> = momio justo de la prob. final. '+((P.notes||[]).map(esc).join(' '))+(g.neutral&&d.kind!=='tennis'?' Cancha neutral: “local” es sólo la designación del calendario.':'')+' Son estimaciones de un modelo simple, no certezas ni recomendaciones.';
  return ds('prob','Probabilidades',body,{info});
}

// ---- 4. % apuestas y % dinero
function dSplits(d){
  const mk=d.market, g=d.game; if(!mk||!mk.splits||!Object.keys(mk.splits).length) return '';
  const sp=mk.splits, names={ml:'Moneyline',spread:g.sport==='futbol'?'Hándicap':'Spread',total:'Total'};
  const lab=s=>s==='draw'?'Empate':s==='over'?'Más':s==='under'?'Menos':esc(tAbbr(g[s]));
  const ordr={ml:mlSides(g,true),spread:sides(g),total:['over','under']};
  const body=['ml','spread','total'].filter(m=>sp[m]).map(m=>{
    const ss=ordr[m].filter(s=>sp[m][s]);
    const seg=k=>{ const tot=ss.reduce((a,s)=>a+(sp[m][s][k]||0),0)||1; return `<div class="seg">${ss.map(s=>{ const v=sp[m][s][k]; if(v==null) return ''; return `<i style="flex:${Math.max(v,.5)};background:${sideColor(g,s)}">${v>=11?v+'%':''}</i>`; }).join('')}</div>`; };
    const flags=ss.map(s=>{ const t=sp[m][s].t, mo=sp[m][s].m; return (t!=null&&mo!=null&&mo-t>=10)?`<span class="tg2 k-t">$ &gt; apuestas · ${lab(s)} +${mo-t}</span>`:''; }).join('');
    return `<div class="spk"><div class="spt"><b>${names[m]}</b><span class="lg">${ss.map(s=>`<span><i style="background:${sideColor(g,s)}"></i>${lab(s)}</span>`).join('')}</span></div>
      <div class="sx"><em>Apuestas</em>${seg('t')}</div><div class="sx"><em>Dinero</em>${seg('m')}</div>${flags?`<div class="spf">${flags}</div>`:''}</div>`; }).join('');
  return ds('splits','% apuestas y % dinero',body,{right:tag2('Action Network'), info:`% apuestas = proporción de tickets; % dinero = proporción del monto apostado. Cubre las casas de EE. UU. que reporta la fuente, no el mercado total. Fuente: ${esc(mk.splits_src||'Action Network')} · ${tsFmt(mk.splits_ts)}.`});
}

// ---- 5. RLM y dinero inteligente
function dRlm(d){
  const mk=d.market, g=d.game; if(!mk) return '';
  const sg_=mk.signals||{}, names={ml:'Moneyline',spread:'Spread',total:'Total'};
  const lab=s=>s==='draw'?'Empate':s==='over'?'Más':s==='under'?'Menos':esc(tAbbr(g[s]));
  const items=['ml','spread','total'].filter(m=>sg_[m]&&sg_[m].tickets).map(m=>{
    const s=sg_[m], pub=s.public_side, chips=[];
    if(s.rlm) chips.push(`<span class="tg2 k-p">RLM → ${lab(s.rlm_side)}</span>`);
    else if(s.move_dir==='con') chips.push(`<span class="tg2">Línea con el público</span>`);
    else chips.push(`<span class="tg2">Sin movimiento clave</span>`);
    if(s.sharp_side) chips.push(`<span class="tg2 k-t">Dinero → ${lab(s.sharp_side)} +${s.sharp_diff} pp</span>`);
    return `<div class="rl2"><div class="rl2t"><b>${names[m]}</b><span class="mt">${pub?`público: ${lab(pub)} ${s.tickets[pub]}%`:'sin lado público claro'}</span></div><div class="rl2c">${chips.join('')}</div>${s.move_text?`<div class="mt">${esc(s.move_text)}</div>`:''}</div>`; }).join('');
  return ds('rlm','RLM y dinero inteligente',items,{right:tag2('Indicador'), info:'RLM (movimiento inverso de línea): el público (≥55% de tickets; ≥45% y mayoría en 3 vías) está de un lado pero la línea o el precio se mueve en su contra (≥0.25 pts o ≥1.5 pp s/vig entre apertura y actual). “Dinero” = el % de dinero supera al % de tickets por ≥10 pp en un lado. Son indicadores que a veces fallan; no garantizan resultado.'});
}

// ---- 6/7. Movimiento de líneas y Cuotas actuales: ver movementSection / marketSection / oddsSection (app.js), envueltas con ds()

// ---- 8. Comparativa del duelo
function cmpRow(lbl,a,b,o={}){
  let ca='eq',cb='eq';
  if(o.hi && a.v!=null && b.v!=null && a.v!==b.v){ const aw=(o.hi==='hi')===(a.v>b.v); ca=aw?'good':'bad'; cb=aw?'bad':'good'; }
  const mx=o.max||Math.max(Math.abs(a.v||0),Math.abs(b.v||0))||1;
  const w=v=>v==null?0:Math.max(8,Math.min(100,Math.abs(v)/mx*100));
  return `<div class="cm"><div class="cv ${ca}" style="--w:${w(a.v)}%"><span>${a.t}</span></div><div class="ck">${lbl}</div><div class="cv r ${cb}" style="--w:${w(b.v)}%"><span>${b.t}</span></div></div>`;
}
function dCmp(d){
  const g=d.game, [s0,s1]=sides(g), T0=g[s0], T1=g[s1], t0=d.teams&&d.teams[T0.id], t1=d.teams&&d.teams[T1.id], m=d.model;
  if(!t0||!t1||d.kind==='tennis') return '';
  const unit = g.league==='mlb'?'Carreras':g.sport==='futbol'||g.sport==='nhl'?'Goles':'Puntos';
  const rec=(t,k,sfx)=>{ const s=t[k]; return s&&s.n?{t:esc(s.text)+(sfx?` <em>${sfx}</em>`:''),v:winp(s)}:{t:SD,v:null}; };
  const stk=t=>{ const x=t.streak; if(!x) return {t:SD,v:null}; const n=parseInt(String(x).slice(1))||0; return {t:`<b class="${x[0]==='W'?'k-t':x[0]==='L'?'k-p':''}">${esc(String(x).replace('W','G').replace('L','P').replace('D','E'))}</b>`,v:x[0]==='W'?n:x[0]==='L'?-n:0}; };
  const pf=(t,k)=>{ const s=t[k]; return s&&s.n?{t:n1(s.pf),v:s.pf}:{t:SD,v:null}; };
  const pa=(t,k)=>{ const s=t[k]; return s&&s.n?{t:n1(s.pa),v:s.pa}:{t:SD,v:null}; };
  const df=t=>{ const s=t.overall; return s&&s.n?{t:sg(s.pf-s.pa),v:s.pf-s.pa}:{t:SD,v:null}; };
  const R=d.rest||{};
  const rows=[
    cmpRow('Récord',rec(t0,'overall'),rec(t1,'overall'),{hi:'hi',max:1}),
    cmpRow(s0==='home'?'Local · Visita':'Visita · Local',rec(t0,s0,s0==='home'?'L':'V'),rec(t1,s1,s1==='home'?'L':'V'),{hi:'hi',max:1}),
    cmpRow('Últimos 5',rec(t0,'last5'),rec(t1,'last5'),{hi:'hi',max:1}),
    cmpRow('Últimos 10',rec(t0,'last10'),rec(t1,'last10'),{hi:'hi',max:1}),
    cmpRow('Racha',stk(t0),stk(t1),{hi:'hi',max:5}),
    cmpRow(unit+' a favor',pf(t0,'overall'),pf(t1,'overall'),{hi:'hi'}),
    cmpRow(unit+' en contra',pa(t0,'overall'),pa(t1,'overall'),{hi:'lo'}),
    cmpRow('Diferencial',df(t0),df(t1),{hi:'hi'}),
    m&&m.rating_home!=null?cmpRow('Rating del modelo',{t:sg(m['rating_'+s0],2),v:m['rating_'+s0]},{t:sg(m['rating_'+s1],2),v:m['rating_'+s1]},{hi:'hi'}):'',
    m&&m.lam_home!=null?cmpRow('Goles esperados',{t:num(m['lam_'+s0],2),v:m['lam_'+s0]},{t:num(m['lam_'+s1],2),v:m['lam_'+s1]},{hi:'hi'}):'',
    (R.home||R.away)?cmpRow('Descanso',{t:R[s0]?(R[s0].b2b?'<b class="k-p">B2B</b>':R[s0].days+' d'):SD,v:null},{t:R[s1]?(R[s1].b2b?'<b class="k-p">B2B</b>':R[s1].days+' d'):SD,v:null},{}):''
  ].join('');
  const head=`<div class="cm hd"><div class="cv"><span>${badge(T0,20)}<b>${tAbbr(T0)}</b></span></div><div class="ck"></div><div class="cv r"><span><b>${tAbbr(T1)}</b>${badge(T1,20)}</span></div></div>`;
  return ds('cmp','Comparativa del duelo',head+rows,{right:tag2('ESPN'), info:`Teal = ventaja en esa fila; rosa = desventaja; la barra es proporcional al valor. Récord = % de victorias (empate = ½). ${unit} a favor/en contra = promedio por juego (menos en contra es mejor). Calculado con resultados finales de la temporada (n = ${t0.n} / ${t1.n} juegos).`});
}
function dPitch(d){
  const g=d.game, P=d.pitchers; if(!P) return '';
  const pc=p=>p?`<div class="pt"><b>${esc(p.name)}</b>${p.hand?`<em>${esc(p.hand)}</em>`:''}<div class="mt">ERA ${esc(p.era||SD)} · WHIP ${esc(p.whip||SD)} · ${esc(p.ip||SD)} IP · ${p.w??'?'}-${p.l??'?'} · K ${p.k??SD}</div></div>`:`<div class="nd">Abridor sin anunciar</div>`;
  const body=`<div class="two">${sides(g).map(s=>`<div><div class="mh">${badge(g[s],18)}<b>${tAbbr(g[s])}</b></div>${pc(P[s])}</div>`).join('')}</div>`;
  return ds('pit','Lanzadores abridores',body,{right:tag2('Probables'), info:'Probables = anunciados por MLB, sujetos a cambio hasta el primer lanzamiento. Fuente: MLB StatsAPI.'+(d.model&&d.model.pitcher_adj!=null?` Ajuste del modelo por abridores: ${sg(d.model.pitcher_adj,2)} carreras de margen (local).`:'')});
}

// ---- 9. Tendencias
function dTrends(d){
  const g=d.game; if(d.kind==='tennis') return '';
  const heat=s=>{ const w=winp(s); return w==null?'dim':w>=.6?'good':w<=.4?'bad':'eq'; };
  const tile=(lbl,s)=>`<div class="ht ${heat(s)}"><b>${s&&s.n?esc(s.text):SD}</b><small>${lbl}</small></div>`;
  const blocks=sides(g).map(sd=>{ const T=g[sd], t=d.teams&&d.teams[T.id]; if(!t||!t.overall||!t.overall.n) return '';
    const frm=(t.form||[]).slice(-6).map(x=>`<span class="wl s ${x}">${x==='W'?'G':x==='L'?'P':'E'}</span>`).join('');
    return `<div class="tr"><div class="trh">${badge(T,18)}<b>${tAbbr(T)}</b>${t.streak?`<span class="tg2 ${t.streak[0]==='W'?'k-t':t.streak[0]==='L'?'k-p':''}">${esc(String(t.streak).replace('W','G').replace('L','P').replace('D','E'))}</span>`:''}<span class="frm">${frm}</span></div>
      <div class="hts">${tile('Temporada',t.overall)}${tile(sd==='home'?'Local':'Visita',t[sd])}${tile('Últ. 5',t.last5)}${tile('Últ. 10',t.last10)}</div></div>`; }).join('');
  const lines=(d.trends||[]).length?`<ul class="tl2">${d.trends.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:'';
  const ats=(d.ats||[]).length?`<div class="fine">ATS (ESPN): ${d.ats.map(a=>esc(a.team)+' '+a.records.map(r=>esc(r.displayValue||r.summary)).join(' / ')).join(' · ')}</div>`:'';
  const pr=d.espn_predictor?`<div class="fine">Referencia ESPN (no es de este modelo): ${sides(g).map(sd=>`${tAbbr(g[sd])} <b>${esc(d.espn_predictor[sd])}%</b>`).join(' · ')}</div>`:'';
  return ds('trd','Tendencias',blocks+lines+ats+pr,{info:'Cada bloque se colorea por % de victorias: teal ≥ 60%, rosa ≤ 40%, gris en medio. G = ganó · P = perdió · E = empató; la tira muestra los últimos 6 resultados (más reciente a la derecha).'});
}

// ---- 10. Resultados recientes (control segmentado: Equipo | H2H | Equipo)
const fmtSc = v => { const x=Number(v); return isNaN(x)?esc(v):(Number.isInteger(x)?String(x):x.toFixed(1)); };
const wlb = (r,sz='') => r?`<span class="wl ${sz} ${r}" title="${r==='W'?'Ganó':r==='L'?'Perdió':'Empató'}">${r==='W'?'G':r==='L'?'P':'E'}</span>`:`<span class="wl ${sz} N">·</span>`;
function h2hItems(d){
  const g=d.game, s=d.h2h&&d.h2h[0]; if(!s||!s.events||!s.events.length) return [];
  const [s0]=sides(g), nm=String(g[s0].name||'').toLowerCase();
  return s.events.map(e=>{ const hs=Number(e.hs), as=Number(e.as_), mine=String(e.home||'').toLowerCase()===nm?'h':String(e.away||'').toLowerCase()===nm?'a':null;
    let res=null; if(mine&&!isNaN(hs)&&!isNaN(as)){ const a=mine==='h'?hs:as, b=mine==='h'?as:hs; res=a>b?'W':a<b?'L':'D'; }
    return {res, date:e.date, hs:e.hs, as:e.as_, home:e.home, away:e.away, comp:e.comp}; });
}
function dRecent(d){
  const g=d.game, [s0,s1]=sides(g);
  let panels=[];
  if(d.kind==='tennis'){
    const F=d.form||{}; const it=l=>(l||[]).slice(0,6).map(r=>({res:r.res,date:r.date,opp:'vs '+r.opp,sub:r.round||'',score:r.score}));
    panels=[{k:'t0',lbl:esc(g[s0].short||g[s0].name),items:it(F[s0])},{k:'t1',lbl:esc(g[s1].short||g[s1].name),items:it(F[s1])}];
  } else {
    const it=t=>((t&&t.recent)||[]).slice(0,6).map(r=>({res:r.res,date:r.date,opp:(r.home?'vs ':'@ ')+r.opp,sub:'',score:fmtSc(r.pf)+'-'+fmtSc(r.pa)}));
    const T0=d.teams&&d.teams[g[s0].id], T1=d.teams&&d.teams[g[s1].id];
    panels=[{k:'t0',lbl:tAbbr(g[s0]),items:it(T0)}];
    const h=h2hItems(d); if(h.length) panels.push({k:'h2h',lbl:'H2H',items:h.slice(0,6).map(e=>({res:e.res,date:e.date,opp:`${esc(e.home)} – ${esc(e.away)}`,raw:1,sub:e.comp||'',score:fmtSc(e.hs)+'-'+fmtSc(e.as)}))});
    panels.push({k:'t1',lbl:tAbbr(g[s1]),items:it(T1)});
  }
  panels=panels.filter(p=>p.items.length);
  if(!panels.length) return '';
  if(!panels.some(p=>p.k===DST.rec)) DST.rec=panels[0].k;
  const row=r=>`<div class="rcx">${wlb(r.res)}<div class="rt"><b>${r.raw?r.opp:esc(r.opp)}</b><small>${esc(fmtShort(r.date))}${r.date?' '+new Date(r.date).getFullYear():''}${r.sub?' · '+esc(r.sub):''}</small></div><span class="scx mono">${r.score}</span></div>`;
  const ctl=panels.length>1?`<div class="sgc">${panels.map(p=>`<button type="button" data-p="${p.k}" class="${p.k===DST.rec?'on':''}">${p.lbl}</button>`).join('')}</div>`:'';
  const body=ctl+panels.map(p=>`<div class="pn" data-p="${p.k}" ${p.k===DST.rec?'':'hidden'}>${p.items.map(row).join('')}</div>`).join('');
  return ds('rcn','Resultados recientes',body,{info:'Últimos juegos finalizados de cada equipo (resultado desde su punto de vista; vs = local, @ = visita). La pestaña H2H muestra los enfrentamientos directos desde el punto de vista del primer equipo.'+(d.kind==='tennis'?' Forma = partidos de singles terminados en los torneos en curso/recientes que publica ESPN (muestra limitada).':'')});
}

// ---- 12. Lesiones y suspensiones
function dInj(d){
  const f=d.injuries_full, g=d.game; if(!f||f.tennis) return '';
  const any=['home','away'].some(s=>f.sides[s]&&((f.sides[s].entries||[]).length||(f.sides[s].returning||[]).length));
  if(!any) return '';
  const cls=e=>/suspend|suspen/i.test((e.status||'')+(e.status_es||''))?['Suspendido','out']:e.bucket==='out'?['Baja','out']:e.bucket==='doubt'?['Dudoso','dbt']:['Duda leve','dtd'];
  const ab=T=>(T.abbr||T.short||T.name||'').toUpperCase();
  const row=(e,T)=>{ const c=cls(e); const det=[ab(T),e.pos||'',e.detail||e.status_es||''].filter(Boolean).map(x=>esc(x)).join(' • ');
    return `<div class="ij"><span class="ph">${badge({logo:e.headshot,name:e.name},36)}</span><div class="ijt"><b>${esc(e.name)}${e.key?' <i class="star" title="Líder del equipo">★</i>':''}</b><small>${det}</small></div><div class="ijs ${c[1]}">${c[0]}${e.ret?`<small>${esc(fmtDM(e.ret))}</small>`:''}</div></div>`; };
  const ret=(r,T)=>`<div class="ij"><span class="ph">${badge({name:r.name},36)}</span><div class="ijt"><b>${esc(r.name)}</b><small class="wr">${esc(ab(T))} • ${esc(r.pos||'')} • ${r.kind==='salio'?'salió del reporte':'mejoró: '+esc(r.old||'—')+' → '+esc(r.new||'—')}</small></div><div class="ijs ret">Regresa<small>${esc(fmtDM(r.ts))}</small></div></div>`;
  const body=sides(g).map(sd=>{ const T=g[sd], S=f.sides[sd]; if(!S) return '';
    const es=S.entries||[], rt=S.returning||[]; if(!es.length&&!rt.length) return '';
    const c=S.counts||{}; const first=es.slice(0,4), rest=es.slice(4);
    const chips=[c.out?`<span class="tg2 k-p">${c.out} baja${c.out>1?'s':''}</span>`:'',(c.doubt||c.dtd)?`<span class="tg2 k-a">${(c.doubt||0)+(c.dtd||0)} duda${(c.doubt||0)+(c.dtd||0)>1?'s':''}</span>`:'',rt.length?`<span class="tg2 k-t">${rt.length} regresa${rt.length>1?'n':''}</span>`:''].join('');
    return `<div class="ijb"><div class="mh">${badge(T,18)}<b>${esc(T.name)}</b><span class="chs">${chips}</span></div>${first.map(e=>row(e,T)).join('')}${rest.length?`<div class="gp"><div class="tg" role="button" tabindex="0">Ver ${rest.length} más</div><div class="sg">${rest.map(e=>row(e,T)).join('')}</div></div>`:''}${rt.map(r=>ret(r,T)).join('')}</div>`; }).join('');
  const since=f.tracking_since?` Seguimiento propio desde ${esc(fmtDMH(f.tracking_since))} CDMX: «Regresa» = el jugador salió del reporte de ESPN o mejoró de estado en los últimos 10 días (no confirma que jugará).`:'';
  return ds('inj','Lesiones y suspensiones',body,{right:f.fetched?tag2('ESPN · '+esc(fmtHMS(f.fetched))):'', info:'Baja = Out / reserva de lesionados / suspendido · Dudoso · Duda leve = cuestionable / día a día. ★ = líder estadístico del equipo.'+since});
}

// ---- 13. Clima del estadio: cancha cenital en SVG con flecha de viento
const GR1='#2f8f4a', GR2='#2a8243';
function fieldSoccer(){
  let s=''; for(let i=0;i<10;i++) s+=`<rect x="${10+i*30}" y="10" width="30" height="180" fill="${i%2?GR1:GR2}"/>`;
  const L='stroke="#fff" stroke-opacity=".85" stroke-width="1.4" fill="none"';
  return {cx:160,cy:100,svg:s+`<g ${L}><rect x="10" y="10" width="300" height="180"/><line x1="160" y1="10" x2="160" y2="190"/><circle cx="160" cy="100" r="26"/><rect x="10" y="48" width="50" height="104"/><rect x="260" y="48" width="50" height="104"/><rect x="10" y="76" width="18" height="48"/><rect x="292" y="76" width="18" height="48"/><rect x="3" y="88" width="7" height="24"/><rect x="310" y="88" width="7" height="24"/><path d="M60 82 A26 26 0 0 1 60 118"/><path d="M260 82 A26 26 0 0 0 260 118"/></g><circle cx="160" cy="100" r="2" fill="#fff"/>`};
}
function fieldFootball(){
  let s=''; for(let i=0;i<20;i++) s+=`<rect x="${35+i*12.5}" y="12" width="12.5" height="136" fill="${i%2?GR1:GR2}"/>`;
  let ln='',nums=''; for(let i=0;i<=20;i++){ const x=35+i*12.5, big=i%2===0; ln+=`<line x1="${x}" y1="12" x2="${x}" y2="148" stroke="#fff" stroke-opacity="${big?.8:.35}" stroke-width="${big?1.3:.8}"/>`; if(big&&i>0&&i<20){ const y=Math.round(i/2)<=5?i/2*10:(10-i/2)*10; nums+=`<text x="${x}" y="40" text-anchor="middle" font-size="8" font-weight="700" fill="#fff" fill-opacity=".7">${y}</text><text x="${x}" y="126" text-anchor="middle" font-size="8" font-weight="700" fill="#fff" fill-opacity=".7">${y}</text>`; } }
  let hash=''; for(let i=1;i<100;i++){ const x=35+i*2.5; hash+=`<line x1="${x}" y1="62" x2="${x}" y2="65" stroke="#fff" stroke-opacity=".5" stroke-width=".7"/><line x1="${x}" y1="95" x2="${x}" y2="98" stroke="#fff" stroke-opacity=".5" stroke-width=".7"/>`; }
  return {cx:160,cy:80,svg:`<rect x="10" y="12" width="300" height="136" fill="${GR2}"/><rect x="10" y="12" width="25" height="136" fill="#0d4a5a"/><rect x="285" y="12" width="25" height="136" fill="#1b3f8f"/>${s}${ln}${hash}${nums}<rect x="10" y="12" width="300" height="136" fill="none" stroke="#fff" stroke-opacity=".9" stroke-width="1.6"/>`};
}
function fieldBaseball(){
  const hx=160,hy=186;
  let r=''; for(let i=7;i>=1;i--) r+=`<circle cx="${hx}" cy="${hy}" r="${i*21}" fill="${i%2?GR1:GR2}"/>`;
  return {cx:160,cy:96,svg:`<defs><clipPath id="bbc"><path d="M${hx} ${hy} L58 84 A144 144 0 0 1 262 84 Z"/></clipPath></defs><rect width="320" height="200" fill="#0b0b0b" opacity="0"/>
    <g clip-path="url(#bbc)">${r}<path d="M160 186 L214 132 L160 78 L106 132 Z" fill="#b5784a" transform="translate(0 2) scale(1)"/><circle cx="160" cy="132" r="42" fill="#b5784a" opacity="0"/><path d="M160 176 L204 132 L160 88 L116 132 Z" fill="${GR2}"/></g>
    <path d="M${hx} ${hy} L58 84 M${hx} ${hy} L262 84" stroke="#fff" stroke-opacity=".85" stroke-width="1.4"/><path d="M58 84 A144 144 0 0 1 262 84" fill="none" stroke="#fff" stroke-opacity=".5" stroke-width="2"/>
    <circle cx="160" cy="134" r="4" fill="#b5784a" stroke="#d9a074" stroke-width=".6"/><g fill="#fff"><rect x="155" y="127" width="10" height="2" opacity="0"/><path d="M160 180 l5 -3 v-4 h-10 v4z"/><rect x="209" y="127" width="7" height="7" transform="rotate(45 212.5 130.5)"/><rect x="156.5" y="80" width="7" height="7" transform="rotate(45 160 83.5)"/><rect x="104" y="127" width="7" height="7" transform="rotate(45 107.5 130.5)"/></g>`};
}
function fieldGeneric(){
  let s=''; for(let i=0;i<10;i++) s+=`<rect x="${10+i*30}" y="10" width="30" height="180" fill="${i%2?GR1:GR2}"/>`;
  return {cx:160,cy:100,svg:s+'<rect x="10" y="10" width="300" height="180" fill="none" stroke="#fff" stroke-opacity=".8" stroke-width="1.4"/>'};
}
function stadiumWidget(d){
  const w=d.weather, g=d.game; if(!w||w.status==='no_aplica') return '';
  const fld = g.sport==='futbol'?fieldSoccer():g.sport==='nfl'?fieldFootball():g.sport==='mlb'?fieldBaseball():fieldGeneric();
  const vb = g.sport==='nfl'?'0 0 320 160':'0 0 320 200';
  const roofed = w.status==='techado', has = w.status==='ok'||w.status==='retractil';
  let arrow='';
  if(has && w.wind_kmh!=null){
    const rot = w.wind_dir!=null ? Math.round(w.wind_dir+180) : null, cx=fld.cx, cy=fld.cy;
    arrow = `<g class="wxa" transform="translate(${cx} ${cy})"><circle r="19" fill="#fff" opacity=".96"/>${rot!=null?`<g class="wxr" data-rot="${rot}" transform="rotate(${rot})"><path d="M0 -11 L8 10 L0 5.5 L-8 10 Z" fill="${DC.bl}"/></g>`:`<text y="4" text-anchor="middle" font-size="11" font-weight="700" fill="#111">—</text>`}</g>
      <g transform="translate(${cx} ${cy-34})"><rect x="-37" y="-11" width="74" height="22" rx="11" fill="#000" fill-opacity=".78"/><text y="4" text-anchor="middle" font-size="11" font-weight="700" fill="#fff">${Math.round(w.wind_kmh)} km/h</text></g>`;
  }
  const compass=`<g transform="translate(298 ${g.sport==='nfl'?26:24})" opacity=".9"><circle r="9" fill="#000" fill-opacity=".55"/><path d="M0 -6 L3 3 L0 1.2 L-3 3 Z" fill="#fff"/><text y="-12" text-anchor="middle" font-size="7" font-weight="700" fill="#fff">N</text></g>`;
  const chips=[];
  if(has&&w.temp_c!=null) chips.push(`<span class="wxc">${w.icon||''} <b>${Math.round(w.temp_c)}°C</b></span>`);
  if(has&&w.precip_prob!=null) chips.push(`<span class="wxc ${w.precip_prob>=50?'wet':''}">💧 <b>${Math.round(w.precip_prob)}%</b></span>`);
  const roofTag = roofed?`<div class="wxroof">Techado</div>`:'';
  return `<div class="stad ${roofed?'roofed':''}"><svg viewBox="${vb}" role="img" aria-label="Cancha vista desde arriba con la dirección del viento">${fld.svg}${has?compass:''}${arrow}</svg><div class="wxchips">${chips.join('')}</div>${roofTag}</div>`;
}
function dWx(d){
  const w=d.weather; if(!w||w.status==='no_aplica'||d.kind==='tennis') return '';
  if(w.status==='sin_dato'&&!w.espn) return '';
  const roofed=w.status==='techado', has=w.status==='ok'||w.status==='retractil';
  let body;
  if(roofed) body=stadiumWidget(d)+`<div class="wxl"><b>${esc(w.venue||'Estadio')}</b><span class="mt">Recinto cubierto: el clima exterior no influye.</span></div>`;
  else if(!has){ const e=w.espn; body=stadiumWidget(d)+`<div class="wxl"><span class="mt">Pronóstico: sin dato · ESPN ${e.temp_f}°F${e.gust?` · ráfagas ${e.gust} mph`:''}${e.precip?` · lluvia ${e.precip}%`:''}</span></div>`; }
  else {
    const kv=(k,v)=>v==null?'':`<div class="kv2"><small>${k}</small><b class="mono">${v}</b></div>`;
    body=stadiumWidget(d)+`<div class="wxl"><b>${esc(w.text||'')}</b><span class="mt">${w.wind_kmh!=null?`Viento ${w.wind_from?'del '+esc(w.wind_from)+' · ':''}${Math.round(w.wind_kmh)} km/h${w.gust_kmh?' · ráfagas '+Math.round(w.gust_kmh):''}`:'Viento sin dato'}</span></div>
      <div class="kvr">${kv('Sensación',w.feels_c!=null?Math.round(w.feels_c)+'°C':null)}${kv('Humedad',w.humidity!=null?Math.round(w.humidity)+'%':null)}${kv('Lluvia',w.precip_mm?w.precip_mm.toFixed(1)+' mm':null)}${w.elevation_m!=null&&w.elevation_m>=800?kv('Altitud',Math.round(w.elevation_m)+' m'):''}</div>${w.roof==='retractil'?'<div class="fine">Techo retráctil: si lo cierran, el clima exterior pesa menos.</div>':''}`;
  }
  const info=(has?`Pronóstico para ${esc(fmtDMH(w.at))} CDMX en ${esc(w.venue||'el estadio')}${w.city?', '+esc(w.city):''} (Open-Meteo). La flecha apunta hacia donde sopla el viento (norte arriba; la cancha es esquemática). `:'')+((w.notes||[]).map(esc).join(' '))+' Es contexto: no modifica las probabilidades del modelo.';
  return ds('wx','Clima del estadio',body,{right:has?tag2('Open-Meteo'):roofed?tag2('Techado'):'', info});
}

// ---- 14. Enfrentamiento directo
function dH2h(d){
  const g=d.game, s=d.h2h&&d.h2h[0]; if(!s||!s.events||!s.events.length) return '';
  const items=h2hItems(d).slice(0,6);
  const body=(s.summary?`<div class="fine" style="margin:0 0 6px">${esc(s.summary)}</div>`:'')+items.map(e=>{
    const wh=Number(e.hs)>Number(e.as), wa=Number(e.as)>Number(e.hs); const hm=homeFirst(g)?[[e.home,e.hs,wh],[e.away,e.as,wa]]:[[e.away,e.as,wa],[e.home,e.hs,wh]];
    return `<div class="rcx">${wlb(e.res)}<div class="rt"><b>${hm.map(([n,sc,w])=>`<span class="${w?'wn':''}">${esc(n)}</span>`).join(' <i>–</i> ')}</b><small>${esc(fmtShort(e.date))} ${new Date(e.date).getFullYear()}${e.comp?' · '+esc(e.comp):''}</small></div><span class="scx mono">${homeFirst(g)?fmtSc(e.hs)+'-'+fmtSc(e.as):fmtSc(e.as)+'-'+fmtSc(e.hs)}</span></div>`; }).join('');
  return ds('h2h','Enfrentamiento directo',body,{info:`El círculo muestra el resultado desde el punto de vista de ${esc(g[sides(g)[0]].name)}.`});
}

// ---- 15. Jugadores clave
function dKey(d){
  const g=d.game; if(d.kind==='tennis'||!d.leaders) return '';
  const blk=T=>{ const l=(d.leaders||{})[T.id]; if(!l||!l.length) return '';
    return `<div><div class="mh">${badge(T,18)}<b>${tAbbr(T)}</b></div>${l.slice(0,5).map(x=>`<div class="kp"><small>${esc(x.cat)}</small><b>${esc(x.name)}</b><span class="mt">${esc(x.value)}</span></div>`).join('')}</div>`; };
  const body=sides(g).map(s=>blk(g[s])).join('');
  return body.trim()?ds('key','Jugadores clave',`<div class="two">${body}</div>`,{info:'Líderes estadísticos de cada equipo según ESPN.'}):'';
}

// ---- 16. Detalle del modelo
function dModel(d){
  const g=d.game, m=d.model; if(!m) return '';
  const [s0,s1]=sides(g); let body='';
  if(d.kind==='tennis'){
    body=`<div class="seg big"><i style="flex:${m.p_home};background:${DC.bl}">${pct(m.p_home,0)}</i><i style="flex:${m.p_away};background:${DC.tl}">${pct(m.p_away,0)}</i></div><div class="spt lgd"><span><i style="background:${DC.bl}"></i>${esc(g.home.short||g.home.name)}</span><span><i style="background:${DC.tl}"></i>${esc(g.away.short||g.away.name)}</span></div>`;
    return ds('mdl','Detalle del modelo',body,{info:esc(m.label||'')+'. No hay cuotas gratuitas en ESPN para tenis, así que no hay edge: sólo línea justa y precio máximo sugerido.'});
  }
  const parts=[[s0,m['p_'+s0]]]; if(m.p_draw!=null) parts.push(['draw',m.p_draw]); parts.push([s1,m['p_'+s1]]);
  body=`<div class="seg big">${parts.map(([s,v])=>`<i style="flex:${Math.max(v,.02)};background:${sideColor(g,s)}">${v>=.1?pct(v,0):''}</i>`).join('')}</div>
    <div class="spt lgd">${parts.map(([s])=>`<span><i style="background:${sideColor(g,s)}"></i>${s==='draw'?'Empate':tAbbr(g[s])}</span>`).join('')}</div>`;
  const kv=(k,v)=>v==null?'':`<div class="kvl"><span>${k}</span><b class="mono">${v}</b></div>`;
  body+=`<div class="kvg">${kv('Margen esperado (local)',m.exp_margin!=null?sg(m.exp_margin,2):null)}${kv('Total esperado',m.exp_total!=null?num(m.exp_total,1):null)}${kv('Ventaja de local',m.hfa!=null?sg(m.hfa,2):null)}${kv('Muestra (juegos)',(m['n_'+s0]!=null?m['n_'+s0]+' / '+m['n_'+s1]:null))}</div>`;
  if(m.top_scores) body+=`<div class="chs2">${m.top_scores.map(s=>`<span class="tg2">${s[0]}-${s[1]} · ${(s[2]*100).toFixed(1)}%</span>`).join('')}</div>`;
  return ds('mdl','Detalle del modelo',body,{right:tag2(m.kind==='poisson'?'Poisson':'SRS','mod'), info:(m.kind==='poisson'?'Poisson con fuerza de ataque/defensa suavizada y ventaja local de la liga.':'Rating SRS (margen ajustado por rival y localía) suavizado + forma reciente; probabilidad con distribución normal.')+' Ver pestaña Metodología.'});
}

// ---- tenis: jugadores y forma (encabezado)
function dPlayers(d){
  const g=d.game; if(d.kind!=='tennis') return '';
  const body=sides(g).map(s=>{ const p=g[s]; return `<div class="pl"><b>${badge(p,26)}${esc(p.name)}</b><span class="mt">${p.rank?`#${p.rank} · ${p.points} pts`:'Ranking: '+SD}${p.country?' · '+esc(p.country):''}</span></div>`; }).join('');
  return ds('ply','Jugadores',`<div class="two">${body}</div>`,{info:`Superficie, H2H y lesiones: ${SD} (no disponible en fuentes gratuitas).`});
}

function dFoot(d){
  const gaps=(d.gaps||[]);
  const fin=`<div class="fine ctr">Estimaciones de un modelo simple, no certezas ni recomendaciones de apuesta. Verifica los precios en tu casa.</div>`;
  if(!gaps.length) return fin;
  return `<section class="ds mini" data-k="gaps"><h3 class="dh"><span class="ttl2">Datos no disponibles · ${gaps.length}</span><button type="button" class="ib${DST.info.gaps?' on':''}" aria-label="Ver detalle">i</button></h3><div class="di" ${DST.info.gaps?'':'hidden'}><ul class="tl2">${gaps.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div></section>${fin}`;
}


function dAnalisis(d){
  const an=d.analysis||(d.picks&&d.picks.analysis); if(!an||!an.signals||!an.signals.length) return '';
  const V={a_favor:['✅','A favor','pos'],en_contra:['⚠️','En contra','neg'],mixto:['↔️','Mixto','amb'],neutral:['➖','Neutral','mut'],sin_dato:['🕳️','Sin dato','mut']};
  const am=o=>o==null?'sin dato':(o>0?'+'+o:String(o));
  const fig=s=>{
    const f=s.figures||{}, bits=[];
    if(f.p_final!=null) bits.push('pFinal '+(f.p_final*100).toFixed(1)+'%');
    if(f.p_model!=null) bits.push('modelo '+(f.p_model*100).toFixed(1)+'%');
    if(f.p_nv!=null) bits.push('mercado s/vig '+(f.p_nv*100).toFixed(1)+'%');
    if(f.ev!=null) bits.push('EV '+(f.ev>=0?'+':'')+(f.ev*100).toFixed(1)+'%');
    if(f.open_odds!=null||f.now_odds!=null) bits.push('cuota '+am(f.open_odds)+' → '+am(f.now_odds));
    if(f.open_line!=null||f.now_line!=null) bits.push('línea '+(f.open_line??'sin dato')+' → '+(f.now_line??'sin dato'));
    if(f.d_nv_pp!=null) bits.push((f.d_nv_pp>0?'+':'')+Number(f.d_nv_pp).toFixed(1)+' pp');
    if(f.tickets!=null||f.money!=null) bits.push((f.tickets!=null?f.tickets+'% apuestas':'% apuestas sin dato')+' / '+(f.money!=null?f.money+'% dinero':'% dinero sin dato'));
    if(f.books&&f.books.length) bits.push(f.books.slice(0,6).map(b=>esc(b.book)+' '+am(b.open_odds)+'→'+am(b.now_odds)).join(' · '));
    if(Array.isArray(f.tags)&&f.tags.length) bits.push(f.tags.map(t=>Array.isArray(t)?t[1]||t[0]:t).join(', '));
    return bits.length?`<div class="an-fig mono">${bits.map(x=>esc(String(x))).join(' · ')}</div>`:'';
  };
  const rows=an.signals.map(s=>{
    const v=V[s.verdict]||V.sin_dato;
    return `<div class="an-row"><div class="an-h"><span class="${v[2]}">${v[0]} <b>${esc(s.label)}</b> · ${v[1]}</span></div>
      <div class="sub">${esc(s.detail||'sin dato')}</div>${fig(s)}</div>`;
  }).join('');
  const pk=d.picks||{}, pub=pk.published, why=pk.discard_reason;
  const sum=`${an.n_agree||0} a favor · ${an.n_against||0} en contra · ${an.n_present||0} con dato (se exigen ${an.n_required||4} presentes y ${an.min_agree||4} a favor)`;
  const foot=pub?`<div class="sub pos">Pick principal publicado · ${esc(sum)}</div>`:`<div class="sub ${pk.status==='REVISAR'?'neg':'mut'}">${esc(why||'Sin pick principal')} · ${esc(sum)}</div>`;
  return ds('analisis','Análisis a detalle',rows+foot,{info:'Seis señales: modelo (pFinal), movimiento de línea, RLM/%apuestas/%dinero, tendencias, lesiones y alineaciones, contexto físico/clima. Si falta un dato se muestra «sin dato»: no se inventa ni cuenta a favor ni en contra. El pick principal se publica sólo si hay al menos 4 señales con dato, 4 a favor, EV>0 y confianza Media/Alta, y coincide con la Predicción NRNM.'});
}

function detailSections(d){
  const tn_=d.kind==='tennis';
  const mercados=[dPicks(d), dProb(d), (marketSection(d)||((d.odds&&d.odds.src==='espn')?oddsSection(d):'')), dCmp(d), dPitch(d), dTrends(d), dRecent(d), dH2h(d), dKey(d), dModel(d)].join('');
  const lineas=[dSplits(d), dRlm(d), movementSection(d)].join('')||'<div class="card mut">Sin movimientos de línea publicados para este juego.</div>';
  const props=dProps(d)||'<div class="card mut">Sin props para este juego.</div>';
  const alin=[tn_?'':lineupsSection(d), dInj(d), dWx(d), dPlayers(d)].join('')||'<div class="card mut">Sin alineaciones ni lesiones publicadas.</div>';
  const tabs=[['mercados','Mercados'],['lineas','Líneas'],['props','Props'],['alin','Alineaciones']];
  const panes={mercados, lineas, props, alin};
  return [dPred(d), dAnalisis(d), dRec(d),
    `<div id="d-tabs"><div class="ds-tabs" role="tablist">${tabs.map((x,i)=>`<button type="button" role="tab" data-dt="${x[0]}" class="${i?'':'on'}" aria-selected="${i? 'false':'true'}">${x[1]}</button>`).join('')}</div>`,
    tabs.map((x,i)=>`<div class="ds-pane" data-dt="${x[0]}" ${i?'hidden':''}>${panes[x[0]]}</div>`).join(''),
    `</div>`, dFoot(d)].join('');
}

// ---- interacción (delegada, fase de captura para convivir con foldCards)
document.addEventListener('click',e=>{
  const tb=e.target.closest('#d-tabs .ds-tabs button');
  if(tb){ const wrap=tb.closest('#d-tabs'); wrap.querySelectorAll('.ds-tabs button').forEach(b=>{ const on=b===tb; b.classList.toggle('on',on); b.setAttribute('aria-selected', on?'true':'false'); }); wrap.querySelectorAll('.ds-pane').forEach(p=>{ p.hidden=p.dataset.dt!==tb.dataset.dt; }); e.preventDefault(); return; }
  const ib=e.target.closest('.ds .ib');
  if(ib){ const s=ib.closest('.ds'), k=s.dataset.k, di=s.querySelector(':scope > .di'); if(di){ di.hidden=!di.hidden; DST.info[k]=!di.hidden; ib.classList.toggle('on',!di.hidden); } e.preventDefault(); e.stopPropagation(); return; }
  const tt=e.target.closest('.ds .ttl');
  if(tt){ const s=tt.closest('.ds'); s.classList.toggle('shut'); DST.shut[s.dataset.k]=s.classList.contains('shut'); return; }
  const sb=e.target.closest('.sgc button');
  if(sb){ const s=sb.closest('.ds'); s.querySelectorAll('.sgc button').forEach(b=>b.classList.toggle('on',b===sb)); s.querySelectorAll('.pn').forEach(p=>{ p.hidden=p.dataset.p!==sb.dataset.p; }); DST.rec=sb.dataset.p; }
},true);
document.addEventListener('keydown',e=>{ if((e.key==='Enter'||e.key===' ')&&e.target.classList&&e.target.classList.contains('ttl')){ e.preventDefault(); e.target.click(); } });

// ================= CANCHA EN VIVO (pt75u): SVG por deporte + datos reales de ESPN (marcador, reloj, última jugada, situación). Sin balón animado inventado.
function fieldBasket(){
  const L='stroke="#fff" stroke-opacity=".85" stroke-width="1.3" fill="none"';
  const half=(m)=>`<g transform="${m}"><rect x="10" y="69" width="60" height="42" fill="rgba(90,59,140,.28)" stroke="#fff" stroke-opacity=".85" stroke-width="1.3"/><circle cx="70" cy="90" r="16" ${L}/><path d="M10 20 H56.6 A76 76 0 0 1 56.6 160 H10" ${L}/><circle cx="27" cy="90" r="3.5" stroke="#8B7CC7" stroke-width="1.6" fill="none"/><line x1="22" y1="82" x2="22" y2="98" stroke="#fff" stroke-width="1.6"/></g>`;
  return {svg:`<defs><linearGradient id="wd" x1="0" x2="1"><stop offset="0" stop-color="#c58446"/><stop offset=".5" stop-color="#d0924f"/><stop offset="1" stop-color="#c58446"/></linearGradient></defs><rect x="10" y="10" width="300" height="160" rx="4" fill="url(#wd)"/><g ${L}><rect x="10" y="10" width="300" height="160"/><line x1="160" y1="10" x2="160" y2="170"/><circle cx="160" cy="90" r="18"/></g>${half('')}${half('translate(320 0) scale(-1 1)')}`, vb:'0 0 320 180'};
}
function fieldHockey(){
  const R='stroke="#e5484d" stroke-width="1.4" fill="none"';
  return {svg:`<rect x="10" y="10" width="300" height="120" rx="34" fill="#eaf3fa"/><g><line x1="160" y1="10" x2="160" y2="130" stroke="#e5484d" stroke-width="3"/><line x1="118" y1="10" x2="118" y2="130" stroke="#3C85F7" stroke-width="3"/><line x1="202" y1="10" x2="202" y2="130" stroke="#3C85F7" stroke-width="3"/><line x1="32" y1="12" x2="32" y2="128" stroke="#e5484d" stroke-width="1.2"/><line x1="288" y1="12" x2="288" y2="128" stroke="#e5484d" stroke-width="1.2"/><circle cx="160" cy="70" r="18" stroke="#3C85F7" stroke-width="1.4" fill="none"/><circle cx="160" cy="70" r="2.5" fill="#3C85F7"/><circle cx="64" cy="38" r="16" ${R}/><circle cx="64" cy="102" r="16" ${R}/><circle cx="256" cy="38" r="16" ${R}/><circle cx="256" cy="102" r="16" ${R}/><path d="M32 60 a10 10 0 0 1 0 20" stroke="#3C85F7" stroke-width="1.4" fill="rgba(60,133,247,.25)"/><path d="M288 60 a10 10 0 0 0 0 20" stroke="#3C85F7" stroke-width="1.4" fill="rgba(60,133,247,.25)"/></g><rect x="10" y="10" width="300" height="120" rx="34" fill="none" stroke="#c8d6e2" stroke-width="2"/>`, vb:'0 0 320 140'};
}
function fieldTennis(){
  const L='stroke="#fff" stroke-width="1.5" fill="none"';
  return {svg:`<rect x="0" y="0" width="320" height="190" fill="#14367e"/><rect x="22" y="14" width="276" height="162" fill="#2459c9"/><g ${L}><rect x="40" y="26" width="240" height="138"/><line x1="40" y1="46" x2="280" y2="46"/><line x1="40" y1="144" x2="280" y2="144"/><line x1="100" y1="46" x2="100" y2="144"/><line x1="220" y1="46" x2="220" y2="144"/><line x1="100" y1="95" x2="220" y2="95"/><line x1="40" y1="95" x2="46" y2="95"/><line x1="274" y1="95" x2="280" y2="95"/></g><line x1="160" y1="18" x2="160" y2="172" stroke="#fff" stroke-opacity=".9" stroke-width="2.2" stroke-dasharray="3 2"/><circle cx="160" cy="18" r="2.6" fill="#fff"/><circle cx="160" cy="172" r="2.6" fill="#fff"/>`, vb:'0 0 320 190'};
}
function fieldFor(g){ return g.sport==='futbol'?Object.assign(fieldSoccer(),{vb:'0 0 320 200'}):g.sport==='nfl'?Object.assign(fieldFootball(),{vb:'0 0 320 160'}):g.sport==='mlb'?Object.assign(fieldBaseball(),{vb:'0 0 320 200'}):g.sport==='nba'?fieldBasket():g.sport==='nhl'?fieldHockey():g.sport==='tenis'?fieldTennis():Object.assign(fieldGeneric(),{vb:'0 0 320 200'}); }

function courtLive(d){
  const g=d.game; if(g.state!=='in') return '';
  const L=d.live||g.live||{}, sit=L.situation||null, [s0,s1]=sides(g), tennis=d.kind==='tennis';
  const f=fieldFor(g); let over='', chips='';
  if(g.sport==='nfl'&&sit){
    const posSd = sit.possession ? (String(g.home.id)===String(sit.possession)?'home':String(g.away.id)===String(sit.possession)?'away':null) : null;
    if(sit.yard!=null){
      let own=null; const ab=x=>String(x&&x.abbr||'').toUpperCase();
      if(posSd && sit.yard_team){ own = sit.yard_team===ab(g[posSd]) ? sit.yard : sit.yard_team===ab(g[posSd==='home'?'away':'home']) ? 100-sit.yard : null; }
      else if(!sit.yard_team) own=sit.yard;
      if(own!=null){ const x=35+Math.max(0,Math.min(100,own))*2.5, fx=sit.distance!=null?Math.min(285,x+sit.distance*2.5):null;
        over+=`<line x1="${x}" y1="12" x2="${x}" y2="148" stroke="#3C85F7" stroke-width="2.4"/>${fx!=null?`<line x1="${fx}" y1="12" x2="${fx}" y2="148" stroke="#F5B942" stroke-width="2.4"/>`:''}<g transform="translate(${x} 80)"><circle class="cvpulse" r="9" fill="none" stroke="#8B7CC7" stroke-width="2"/><ellipse rx="6.5" ry="4" fill="#8a4b1f" stroke="#fff" stroke-width=".8"/><line x1="-2" y1="0" x2="2" y2="0" stroke="#fff" stroke-width=".8"/></g>`; }
    }
    const dn = sit.down ? `${sit.down}º y ${sit.distance!=null?sit.distance:'—'}` : '';
    if(posSd||dn) chips=`<span class="cvch">${posSd?badge(g[posSd],16)+'<b>'+tAbbr(g[posSd])+'</b>':''}${dn?`<span>${esc(dn)}</span>`:''}${sit.yard_team?`<span class="mt">${esc(sit.yard_team)} ${sit.yard}</span>`:''}${sit.red_zone?'<span class="tg2 k-p">Zona roja</span>':''}</span>`;
  }
  if(g.sport==='mlb'&&sit&&sit.bases){
    const pos=[[214,132],[160,78],[106,132]];
    sit.bases.forEach((on,i)=>{ if(on) over+=`<g transform="translate(${pos[i][0]} ${pos[i][1]})"><circle class="cvpulse" r="10" fill="rgba(90,59,140,.25)" stroke="#8B7CC7" stroke-width="1.6"/><rect x="-5" y="-5" width="10" height="10" fill="#8B7CC7" transform="rotate(45)"/></g>`; });
    const outs=sit.outs!=null?`<span class="cvo">${[0,1,2].map(i=>`<i class="${i<sit.outs?'on':''}"></i>`).join('')}<small>outs</small></span>`:'';
    const cnt=(sit.balls!=null&&sit.strikes!=null)?`<span class="cvch"><b class="mono">${sit.balls}-${sit.strikes}</b><small>cuenta</small></span>`:'';
    chips=outs+cnt;
  }
  // marcador y reloj
  const sc=(sd)=>tennis?'':esc(g[sd].score??'');
  const head=`<div class="cvh"><span class="tg2 live">● EN VIVO</span><span class="cvt mono">${esc(L.text||g.status||'')}</span><span class="cvlg">${esc(g.league_name||'')}</span></div>`;
  const scoreBar = tennis ? '' : `<div class="cvs"><span class="cvtm">${badge(g[s0],22)}<b>${tAbbr(g[s0])}</b></span><span class="cvsc mono">${sc(s0)}<i>–</i>${sc(s1)}</span><span class="cvtm r"><b>${tAbbr(g[s1])}</b>${badge(g[s1],22)}</span></div>`;
  let tbl='', tblRows='';
  if(tennis){
    const A=g[s0].sets||[], B=g[s1].sets||[], n=Math.max(A.length,B.length);
    if(n){ const cur=n-1;
      const big=`<div class="cvbig"><small>Set ${n}</small><b class="mono">${A[cur]??0}<i>–</i>${B[cur]??0}</b><small>games</small></div>`;
      const row=(sd,arr)=>`<div class="tbr"><span class="tbn">${badge(g[sd],22)}<b>${esc(g[sd].short||g[sd].name)}</b>${L.server===sd?'<i class="srv" title="Al servicio"></i>':''}</span>${Array.from({length:n},(_,i)=>`<span class="tbs mono ${i===cur?'cur':''}">${arr[i]??''}</span>`).join('')}</div>`;
      over=''; tbl=big; tblRows=`<div class="tbt">${row(s0,A)}${row(s1,B)}</div>`;
    }
  }
  const plays=L.plays||[], lp=plays[0], lastTxt=lp?((lp.clock?lp.clock+' · ':'')+lp.text):(sit&&sit.last_play)||'';
  const last=lastTxt?`<div class="cvl"><small>Última jugada</small><span>${esc(lastTxt.length>170?lastTxt.slice(0,167)+'…':lastTxt)}</span></div>`:'';
  const who=(g.sport==='mlb'&&sit&&(sit.batter||sit.pitcher))?`<div class="fine" style="margin:6px 2px 0">${sit.batter?'Al bat <b>'+esc(sit.batter)+'</b>':''}${sit.batter&&sit.pitcher?' · ':''}${sit.pitcher?'Lanza <b>'+esc(sit.pitcher)+'</b>':''}</div>`:'';
  return `<div class="card cvw" data-sport="${esc(g.sport)}">${head}<div class="cvf ${tennis?'tn':''}"><svg viewBox="${f.vb}" role="img" aria-label="Cancha en vivo">${f.svg}${over}</svg>${scoreBar}${tennis?tbl:''}${chips?`<div class="cvc">${chips}</div>`:''}</div>${tblRows}${last}${who}</div>`;
}

// ================= PREDICCIÓN NRNM (pt75u): marcador proyectado + ganador + total + hándicap, derivados del modelo; bloqueada al inicio
const PRK = {GANADO:['ok','✓'],MEDIO_GANADO:['ok','✓'],PERDIDO:['no','✕'],MEDIO_PERDIDO:['no','✕'],PUSH:['pu','↔']};
const prMark = r => r&&PRK[r]?`<i class="pmk ${PRK[r][0]}" title="${r==='PUSH'?'Devolución':PRK[r][0]==='ok'?'Acertó':'Falló'}">${PRK[r][1]}</i>`:'';
function dPred(d){
  const p=d.pred, g=d.game; if(!p||!p.score||!p.winner) return '';
  const [s0,s1]=sides(g), R=p.result||null, tennis=d.kind==='tennis';
  const nm=sd=>esc(g[sd].short||g[sd].name);
  const unit=tennis?'juegos':g.sport==='futbol'?'goles':g.sport==='mlb'?'carreras':'pts';
  const w=p.winner, wl=w.side==='draw'?'Empate':nm(w.side);
  let big;
  if(tennis){
    big=`<div class="pdsc tn">${(p.score.sets||[]).map(x=>`<b class="mono">${x[0]}<i>-</i>${x[1]}</b>`).join('')}</div><div class="pdt">${nm(s0)} <i>vs</i> ${nm(s1)} · <b>${p.score.home}-${p.score.away}</b> en sets</div>`;
  } else {
    big=`<div class="pdsc"><span class="pdtm">${badge(g[s0],34)}<small>${tAbbr(g[s0])}</small></span><b class="mono">${p.score[s0]}<i>–</i>${p.score[s1]}</b><span class="pdtm">${badge(g[s1],34)}<small>${tAbbr(g[s1])}</small></span></div>`;
  }
  const pr=w.probs||{}; const seg=[[s0,DC.bl],...(pr.draw!=null?[['draw','#4b5563']]:[]),[s1,DC.pk]];
  const stack=`<div class="pdst">${seg.map(([k,c])=>`<i style="flex:${Math.max(.02,pr[k]||0)};background:${c}"></i>`).join('')}</div><div class="pdsl">${seg.map(([k,c])=>`<span><u style="background:${c}"></u>${k==='draw'?'Empate':nm(k)} <b class="mono">${pct(pr[k],0)}</b></span>`).join('')}</div>`;
  const mains=[];
  const row=(ttl,main,sub,prob,mark)=>(mains.push(main),`<div class="pdr"><div class="pdl"><small>${ttl}</small><b>${main}</b>${sub?`<em>${sub}</em>`:''}</div><div class="pdp"><b class="mono">${pct(prob,prob<.1?1:0)}</b><span class="pbar"><i style="width:${Math.round((prob||0)*100)}%;background:linear-gradient(90deg,#8B7CC7,#5A3B8C)"></i></span></div>${mark}</div>`);
  const rows=[], sc=p.score;
  const al=o=>o&&o.aligned==='pick'?' · alineado con el pick del modelo':o&&o.aligned==='marcador'?' · ajustado al marcador exacto':'';
  rows.push(row('Ganador',`${w.side==='draw'?'Empate':'Gana '+wl}`,al(w).slice(3),w.p,prMark(R&&R.ml)));
  if(tennis) rows.push(row('Marcador exacto',(sc.sets||[]).map(x=>x.join('-')).join(' '),`sets ${sc.home}-${sc.away} ${pct(sc.p,0)} · set por set ${pct(sc.p_seq,1)}`,sc.p_seq,prMark(R&&R.score)));
  else rows.push(row('Marcador exacto',`${sc[s0]}–${sc[s1]}`,`el más probable que cumple ganador, total, hándicap${p.btts?' y ambos anotan':''} · ${pct(sc.p,1)}`,sc.p,prMark(R&&R.score)));
  if(p.total){ const t=p.total; rows.push(row('Total'+(g.sport==='futbol'?' de goles':tennis?' de juegos':''),esc(t.label)+(g.sport==='futbol'?' goles':tennis?' juegos':''),`proyectado ${t.proj!=null?t.proj.toFixed(1):SD} ${unit} · ${t.line_src==='modelo'?(tennis?'línea del modelo (mediana de juegos)':'línea estándar (sin línea de mercado)'):'línea de mercado'+(p.book?' '+esc(p.book):'')}${al(t)}`,t.p,prMark(R&&R.total))); }
  if(p.corners){ const c=p.corners; rows.push(row('Córners',esc(c.label),`proyectado ${c.proj.toFixed(1)} (${nm(s0)} ${(s0==='home'?c.home:c.away).toFixed(1)} · ${nm(s1)} ${(s1==='home'?c.home:c.away).toFixed(1)}) · línea = promedio de sus últimos partidos`,c.p,prMark(R&&R.corners))); }
  if(p.btts){ const b=p.btts; rows.push(row('Ambos anotan',esc(b.label),`modelo (Poisson) Sí ${pct(b.p_yes,0)} · No ${pct(1-b.p_yes,0)}${b.price!=null?` · ${esc(b.book||'')} ${am(b.price)}`:' · sin cuota de mercado'}${al(b)}`,b.p,prMark(R&&R.btts))); }
  if(p.spread){ const sp=p.spread, L=sp.line, lbl=sp.side==='home'?`${nm('home')} ${sg(L)}`:`${nm('away')} ${sg(-L)}`;
    rows.push(row('Hándicap',lbl,`margen proyectado ${nm('home')} ${sp.proj!=null?sg(sp.proj):SD} ${unit} · ${sp.line_src==='modelo'?'línea del modelo (sin hándicap de mercado)':'línea de mercado'}${al(sp)}`,sp.p,prMark(R&&R.spread))); }
  const fin = R&&R.score_text?`<div class="pdf">Resultado final <b class="mono">${esc(R.score_text)}</b></div>`:'';
  const lockTag = p.locked?tag2('🔒 Bloqueada al inicio','k-a'):tag2('Se bloquea al inicio','k-t');
  const info=`Se deriva de las proyecciones del modelo, sin datos inventados: ${tennis?'ranking → prob. de partido → prob. de set → prob. de juego; el marcador es el set-a-set factible más cercano a los juegos esperados del resultado de sets más probable que cumple total y hándicap':g.sport==='futbol'?'goles esperados (Poisson) → el marcador más probable de la matriz que cumple a la vez ganador, total y hándicap (y los picks del modelo; si dos líneas se contradicen, se corrige la más débil para que nada se contradiga)':'margen y total proyectados → puntos/carreras por equipo (marcador exacto de mayor probabilidad cerca de la proyección)'}. Total y hándicap usan la línea de mercado; en fútbol, si no hay, se usa la línea estándar del modelo (2.5 goles / −1.5 o −0.5) y se indica. Los córners sólo aparecen si ESPN tiene datos reales de córners de los últimos partidos de ambos equipos. Se guarda antes de que empiece el juego, se bloquea al inicio y se califica con el marcador final en Récord → Predicción NRNM. Es una estimación, no una garantía.`;
  return ds('pred','Predicción NRNM',`<div class="pdh">${big}</div>${stack}<div class="pdsm">${mains.map(m=>`<span>${m}</span>`).join('')}</div><div class="pdrs">${rows.join('')}</div>${fin}`,{right:lockTag,info,cls:'pred'});
}
function predRecord(P){
  if(!P) return '';
  const cell=(l,a)=>`<div class="pkc"><small>${l}</small><b class="mono">${a&&a.n?a.pct.toFixed(0)+'%':SD}</b><em class="mono">${a&&a.n?`${a.hit}-${a.miss}${a.push?'-'+a.push:''}`:'—'}</em><span class="pbar"><i style="width:${a&&a.n?Math.round(a.pct):0}%;background:linear-gradient(90deg,#8B7CC7,#5A3B8C)"></i></span></div>`;
  const rec=(P.recent||[]).slice(0,6).map(r=>`<div class="pkr"><span class="sub mono">${esc(r.league.toUpperCase())}</span><span class="pkm">${esc(r.home)} <i>vs</i> ${esc(r.away)}</span><span class="mono pkn">${esc(r.score_text||'')}</span>${prMark(r.ml)}${prMark(r.total)}${prMark(r.spread)}${prMark(r.corners)}${prMark(r.score)}</div>`).join('');
  return `<div class="card pkw"><h2>🎯 Predicción NRNM <span class="tg2" style="margin-left:6px">${P.graded} calificadas · ${P.pending} pendientes</span></h2><div>${P.graded?`<div class="pkg">${cell('Ganador',P.ml)}${cell('Total',P.total)}${cell('Hándicap',P.spread)}${P.corners&&P.corners.n?cell('Córners',P.corners):''}${P.btts&&P.btts.n?cell('Ambos anotan',P.btts):''}${cell('Marcador exacto',P.score)}${P.sets&&P.sets.n?cell('Sets (tenis)',P.sets):''}</div>${rec?`<div class="pkl">${rec}</div>`:''}`:`<div class="mut">Aún no hay predicciones calificadas. Se guardan antes de cada juego, se bloquean al inicio y se califican con el marcador final.</div>`}<div class="fine" style="margin-top:8px">% de acierto = aciertos / (aciertos + fallos), sin devoluciones. Marcador exacto es muy difícil: lo normal es un porcentaje bajo.</div></div></div>`;
}
