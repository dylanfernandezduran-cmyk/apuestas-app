/* Tablero «Picks NRNM» (inicio): sólo picks registrados = Predicción NRNM. Datos de /api/nrnm; nada se inventa. */
const nbSign = (v,d=1,suf='') => v==null?SD:((v>0?'+':v<0?'−':'')+Math.abs(Number(v)).toFixed(d)+suf);
const nbLine = (l,o,tot) => (l==null?'':(!tot&&Number(l)>0?'+':'')+Number(l))+(o!=null?` <span class="mut">(${o>0?'+':''}${o})</span>`:'');
function nbCard(it){
  const evc = it.ev_pct>0?'pos':it.ev_pct<0?'neg':'';
  const moved = it.line_moved||it.odds_moved;
  const lineTxt = (it.market==='ml')
    ? `${it.open_odds_txt||SD} → ${it.odds_txt}`
    : `${nbLine(it.open_line,it.open_odds,it.market==='total')} → ${nbLine(it.line,it.odds,it.market==='total')}`;
  const tags = [];
  if(it.live) tags.push('<span class="badge b-live">● En juego</span>');
  if(it.type==='main') tags.push('<span class="badge b-pick">Principal</span>');
  if(it.divergence_high) tags.push(`<span class="divf" title="Modelo crudo vs mercado sin vig: ${it.divergence_pp} pp">Divergencia alta</span>`);
  return `<a class="nb-card${it.value?'':' nb-off'}" href="${it.href}">
    <div class="nb-top"><span class="nb-meta">${esc(it.sport_name)} · ${esc((it.kickoff_cdmx||'').replace(/^\d+ \w+, /,''))}</span>${tags.join('')}<span class="nb-ev ${evc}">EV ${nbSign(it.ev_pct,1,'%')}</span></div>
    <div class="nb-game">${esc(it.game)}</div>
    <div class="nb-pick"><b>${esc(it.pick)}</b><span class="nb-mk">${esc(it.market_name)}</span><span class="nb-odds mono">${esc(it.odds_txt)}<small>${esc(it.book||'')}</small></span></div>
    <div class="nb-stats">
      <div><span>NRNM</span><b class="mono">${it.p_final.toFixed(1)}%</b></div>
      <div><span>Implícita</span><b class="mono">${it.p_implied.toFixed(1)}%</b></div>
      <div><span>Ventaja</span><b class="mono ${it.edge_pp>0?'pos':it.edge_pp<0?'neg':''}">${nbSign(it.edge_pp,1,' pp')}</b></div>
      <div><span>Confianza</span><b>${esc(it.confidence==='no aplica'?'—':it.confidence)}</b></div>
    </div>
    <div class="nb-line"><span>Apertura → actual</span><span class="mono">${lineTxt}</span>${moved?'<i class="nb-mv">movió</i>':''}</div>
  </a>`;
}
function nbPerf(rec){
  const n=x=>x==null?SD:x;
  const hit=rec.win_pct, roi=rec.roi;
  const st = rec.n_priced<30 ? 'Muestra chica: todavía no se puede concluir nada.' :
    (roi!=null&&roi<0 ? `En rojo: a estas cuotas se necesita ~${rec.breakeven?rec.breakeven.toFixed(1):'52.4'}% de acierto y va ${hit!=null?hit.toFixed(1):SD}%. Se apuesta poco y sólo con EV+.` : 'En verde con la muestra actual. No garantiza el futuro.');
  return `<div class="pf"><div class="pf-h"><span>Récord del modelo · principal</span><a class="more" href="#/record">Historial →</a></div>
   <div class="pf-g">
    <div><span>Acierto</span><b class="mono ${hit>=52.4?'pos':hit!=null?'neg':''}">${hit==null?SD:hit.toFixed(1)+'%'}</b></div>
    <div><span>ROI</span><b class="mono ${roi>0?'pos':roi<0?'neg':''}">${roi==null?SD:nbSign(roi,1,'%')}</b></div>
    <div><span>G-P-E</span><b class="mono">${rec.W}-${rec.L}${rec.P?'-'+rec.P:''}</b></div>
    <div><span>Con cuota</span><b class="mono">${n(rec.n_priced)}</b></div>
   </div>
   <div class="pf-s">${esc(st)} ${rec.n_unpriced?`<span class="mut">${rec.n_unpriced} pick${rec.n_unpriced===1?'':'s'} sin cuota no cuentan (sin cuota no es pick).</span>`:''}</div></div>`;
}
function nbCal(c){
  if(!c||!c.overall||!c.overall.n) return '';
  const f=x=>x==null?'—':x.toFixed(3);
  const tr=x=>`<tr><td>${esc(x.label)}</td><td class="mono">${x.n}</td><td class="mono ${x.hit_pct>=52.4?'pos':'neg'}">${x.hit_pct==null?'—':x.hit_pct.toFixed(1)+'%'}</td><td class="mono ${x.roi>0?'pos':'neg'}">${x.roi==null?'—':nbSign(x.roi,1,'%')}</td><td class="mono ${x.brier!=null&&x.brier_market!=null?(x.brier<=x.brier_market?'pos':'neg'):''}">${f(x.brier)}</td><td class="mono mut">${f(x.brier_market)}</td><td class="mono">${f(x.logloss)}</td></tr>`;
  const tb=(t,rows)=>`<div class="cal-t">${t}</div><div class="cal-w"><table class="cal"><thead><tr><th></th><th>n</th><th>Acierto</th><th>ROI</th><th>Brier</th><th>Mercado</th><th>Log loss</th></tr></thead><tbody>${rows.map(tr).join('')}</tbody></table></div>`;
  return `<details class="nb-cal"><summary>Calibración del modelo (Brier, log loss, por deporte y mercado)</summary>
    ${tb('Total',[c.overall])}${tb('Por deporte',c.by_sport||[])}${tb('Por mercado',c.by_market||[])}<p class="nb-foot">${esc(c.note||'')}</p></details>`;
}
function nbRec(r){
  if(!r||r.error) return '';
  const k=(l,v,c='')=>`<div class="nb-k"><span>${l}</span><b class="mono ${c}">${v}</b></div>`;
  const wlp=s=>s&&(s.W||s.L||s.P)?`${s.W}-${s.L}${s.P?'-'+s.P:''}`:SD;
  const row=(lab,s)=>s?`<div class="nb-rrow"><div class="nb-rl">${lab}<small>${s.n} calificados</small></div>
    ${k('G-P-E',wlp(s))}${k('Acierto',s.hit_pct==null?SD:s.hit_pct.toFixed(1)+'%',s.hit_pct>=52.4?'pos':s.hit_pct!=null?'neg':'')}
    ${k('Unidades',s.units==null?SD:nbSign(s.units,2,'u'),s.units>0?'pos':s.units<0?'neg':'')}${k('ROI',s.roi==null?SD:nbSign(s.roi,1,'%'),s.roi>0?'pos':s.roi<0?'neg':'')}
    ${k('CLV',s.clv_avg==null?SD:nbSign(s.clv_avg,2,'%'),s.clv_avg>0?'pos':s.clv_avg<0?'neg':'')}</div>`:'';
  return `<div class="nb-rec"><div class="nb-h2">Récord real <a class="more" href="#/record">Ver récord →</a></div>
    ${row('Coinciden y EV+',r.coincident_value)}${row('Coinciden (todos)',r.coincident)}${row('Pick principal',r.main)}
    ${r.last10?`<div class="nb-streak"><span>Últimos ${r.last10.length}</span>${[...r.last10].map(c=>`<i class="s-${c}">${c}</i>`).join('')}</div>`:''}
    ${nbCal(r.calibration)}<p class="nb-foot">${esc(r.note||'')}</p></div>`;
}
async function nrnmFill(el){
  if(!el) return;
  let d; try{ d=await api('/api/nrnm'); }catch(e){ el.innerHTML=`<div class="nb-h"><h2>Picks NRNM</h2></div><div class="nb-empty">${SD}: ${esc(e.message)}</div>`; return; }
  const items=d.items||[], off=d.no_value||[];
  const head=`<div class="nb-h"><div><h2>Picks NRNM</h2><div class="sub">Pick registrado = Predicción NRNM (mercado, lado y línea) · ${typeof agoTxt==='function'?esc(agoTxt(d.now)):''}</div></div><span class="nb-n mono">${items.length}</span></div>`;
  const empty=`<div class="nb-empty"><b>Hoy no hay picks con valor.</b> ${d.n_coincident?`${d.n_coincident} pick${d.n_coincident===1?'':'s'} coincide${d.n_coincident===1?'':'n'} con la predicción, pero con EV ≤ 0 o divergencia alta.`:'Ningún pick registrado coincide con la predicción todavía.'} No se inventa ninguno.</div>`;
  const offB = off.length?`<details class="nb-offw"><summary>Coinciden pero sin valor (${off.length}) · no se recomiendan</summary>${off.map(nbCard).join('')}</details>`:'';
  el.innerHTML = head + (items.length?`<div class="nb-list">${items.map(nbCard).join('')}</div>`:empty) + offB +
    `<p class="nb-foot">${esc(d.formula||'')} ${esc(d.note||'')}</p>` + nbRec(d.record);
}
