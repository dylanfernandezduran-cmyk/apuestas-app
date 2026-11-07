// ------------------------------------------------------------ Tickets / parlays de PAPEL (sin dinero). Carrito en localStorage; guardar/calificar en el servidor.
const TK = { legs: (()=>{ try{ return JSON.parse(localStorage.getItem('nrnm_ticket')||'[]'); }catch(e){ return []; } })(), reg:{}, n:0 };
const tkSave_ = () => { try{ localStorage.setItem('nrnm_ticket', JSON.stringify(TK.legs)); }catch(e){} tkFab(); };
const tkKey = l => [l.kind||'game',l.league,l.eid,l.market,l.aid||'',l.key||'',l.selection].join('|');
const tkDec = a => a==null ? null : (a>0 ? 1+a/100 : 1+100/(-a));
const tkAm = d => d==null||d<=1 ? '—' : d>=2 ? '+'+Math.round((d-1)*100) : String(Math.round(-100/(d-1)));
function tkLegFromCand(g, c){
  const mk={ML:'ml',Spread:'spread',Total:'total',BTTS:'btts'}[c.market]; if(!mk||c.price==null) return null;
  return {kind:'game', league:g.league, eid:String(g.id), sport:g.sport, start_ts:Math.round(Date.parse(g.date)/1000), home:g.home.name, away:g.away.name,
          home_id:String(g.home.id||''), away_id:String(g.away.id||''), market:mk, selection:c.side, line:c.line??null, odds:c.price, label:shortLbl(c.label,g), p:c.p_final??null, official:!!c.official};
}
// botón «+ Ticket»: registra la pierna y devuelve el HTML (dentro de enlaces no navega)
function tkBtn(leg, txt){
  if(!leg) return '';
  const id='t'+(++TK.n); TK.reg[id]=leg; const on=TK.legs.some(x=>tkKey(x)===tkKey(leg));
  return `<button type="button" class="tkadd ${on?'on':''}" data-tk="${id}" aria-label="Agregar al ticket">${on?'✓ En ticket':(txt||'+ Ticket')}</button>`;
}
document.addEventListener('click', e=>{
  const b=e.target.closest('.tkadd'); if(!b||!b.dataset.tk) return;
  e.preventDefault(); e.stopPropagation();
  const leg=TK.reg[b.dataset.tk]; if(!leg) return;
  const i=TK.legs.findIndex(x=>tkKey(x)===tkKey(leg));
  if(i>=0){ TK.legs.splice(i,1); b.classList.remove('on'); b.textContent='+ Ticket'; }
  else { if(leg.start_ts && leg.start_ts*1000<=Date.now()){ tkToast('Ese juego ya empezó: sólo piernas pre-juego.'); return; }
    TK.legs.push(leg); b.classList.add('on'); b.textContent='✓ En ticket'; tkToast('Agregado al ticket ('+TK.legs.length+')'); }
  tkSave_();
}, true);
function tkToast(t){ let el=document.getElementById('tkt'); if(!el){ el=document.createElement('div'); el.id='tkt'; document.body.appendChild(el); } el.textContent=t; el.classList.add('on'); clearTimeout(el._t); el._t=setTimeout(()=>el.classList.remove('on'),1800); }
function tkFab(){
  let b=document.getElementById('tkb');
  if(!TK.legs.length){ if(b) b.remove(); return; }
  if(!b){ b=document.createElement('button'); b.id='tkb'; b.type='button'; b.onclick=tkOpen; document.body.appendChild(b); }
  b.innerHTML=`🎟️<span>${TK.legs.length}</span>`; b.setAttribute('aria-label','Ver ticket ('+TK.legs.length+' piernas)');
}
// mismas reglas que server/tickets.py check()
function tkCheck(legs){
  const err=[], warn=[], seen={};
  legs.forEach((l,i)=>{ const g=l.league+'/'+l.eid;
    (seen[g]||[]).forEach(j=>{ const m=legs[j];
      const same=(m.kind||'game')===(l.kind||'game')&&m.market===l.market&&(m.aid||'')===(l.aid||'')&&(m.key||'')===(l.key||'');
      if(same) err.push(m.selection!==l.selection?`Contradictorias: «${m.label}» y «${l.label}»`:`Repetida: «${l.label}»`);
      else if((l.kind||'game')==='game'&&(m.kind||'game')==='game'&&[m.market,l.market].sort().join()==='ml,spread') warn.push(m.selection===l.selection?`Correlacionadas: «${m.label}» + «${l.label}» (mismo lado)`:`Se contradicen en parte: «${m.label}» y «${l.label}»`);
      else warn.push(`Mismo juego: «${m.label}» + «${l.label}» (correlacionadas; la prob. combinada asume independencia)`); });
    (seen[g]=seen[g]||[]).push(i); });
  if(legs.some(l=>l.official===false)) warn.push('Incluye piernas que NO son pick oficial (no pasaron el filtro estricto).');
  return {err:[...new Set(err)], warn:[...new Set(warn)]};
}
function tkSheet(html){ let s=document.getElementById('tks'); if(!s){ s=document.createElement('div'); s.id='tks'; document.body.appendChild(s);
  s.addEventListener('click',e=>{ if(e.target===s) tkClose(); }); } s.innerHTML=`<div class="tks-in">${html}</div>`; s.classList.add('on'); document.body.classList.add('noscroll'); }
function tkClose(){ const s=document.getElementById('tks'); if(s) s.classList.remove('on'); document.body.classList.remove('noscroll'); }
function tkOpen(){
  const L=TK.legs, d=L.reduce((a,l)=>a*(tkDec(l.odds)||1),1), pOk=L.every(l=>l.p!=null), p=pOk?L.reduce((a,l)=>a*l.p,1):null, ev=p!=null?p*d-1:null, ck=tkCheck(L);
  const row=(l,i)=>`<div class="tkl"><div class="tkl-t"><b>${esc(l.label)}</b><span class="sub">${esc(l.kind==='prop'?(l.player||'Prop'):l.home+' vs '+l.away)} · ${fmtShort(new Date(l.start_ts*1000).toISOString())} ${fmtTime(new Date(l.start_ts*1000).toISOString())}</span>
      <span class="sub">${l.p!=null?'modelo '+Math.round(l.p*100)+'% · ':''}${l.official?'<span class="k-t">pick oficial</span>':l.kind==='prop'?'prop (sin prob. de modelo)':'<span class="k-a">no oficial</span>'}</span></div>
      <b class="mono">${l.odds>0?'+'+l.odds:l.odds}</b><button type="button" class="tkx" onclick="tkDel(${i})" aria-label="Quitar">✕</button></div>`;
  tkSheet(`<div class="tks-h"><b>🎟️ Ticket (papel)</b><button type="button" class="tkx" onclick="tkClose()" aria-label="Cerrar">✕</button></div>
    ${L.length?L.map(row).join(''):'<div class="sub">Ticket vacío.</div>'}
    <div class="kpis s tkk"><div class="kpi"><div class="sub">Momio combinado</div><div class="v mono">${tkAm(d)}</div></div><div class="kpi"><div class="sub">Prob. modelo</div><div class="v mono">${p==null?'—':(p*100).toFixed(1)+'%'}</div></div>
      <div class="kpi"><div class="sub">Prob. implícita</div><div class="v mono">${(100/d).toFixed(1)}%</div></div><div class="kpi"><div class="sub">EV por 1u</div><div class="v mono ${ev>0?'pos':ev<0?'neg':''}">${ev==null?'—':(ev>0?'+':'')+ev.toFixed(2)+'u'}</div></div></div>
    ${ck.err.map(x=>`<div class="tkw err">⛔ ${esc(x)}</div>`).join('')}${ck.warn.map(x=>`<div class="tkw">⚠️ ${esc(x)}</div>`).join('')}
    <div class="sub" style="margin:6px 0">Paper trading: no se apuesta dinero. Prob. combinada = producto de las probabilidades del modelo (asume independencia). ${L.length>3?'Más piernas = mucho menos probable.':''}</div>
    <input id="tkn" class="tkin" maxlength="60" placeholder="Nombre del ticket (opcional)">
    <div class="tkbtns"><button type="button" class="btn" onclick="TK.legs=[];tkSave_();tkClose();route()">Vaciar</button><button type="button" class="btn pri" ${ck.err.length||!L.length||STATIC?'disabled':''} onclick="tkSubmit(this)">${STATIC?'Guardar (sólo en link local)':'Guardar ticket'}</button></div>`);
}
function tkDel(i){ TK.legs.splice(i,1); tkSave_(); if(TK.legs.length) tkOpen(); else tkClose(); }
async function tkSubmit(btn){
  btn.disabled=true; btn.textContent='Guardando…';
  try{ const r=await fetch('/api/tickets',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({legs:TK.legs,name:(document.getElementById('tkn')||{}).value||''})});
    const j=await r.json(); if(!r.ok) throw new Error(j.detail||'Error');
    TK.legs=[]; tkSave_(); tkClose(); location.hash='#/tickets/'+(j.day||''); tkToast('Ticket #'+j.id+' guardado'); }
  catch(e){ btn.disabled=false; btn.textContent='Guardar ticket'; tkToast(e.message); }
}
// ---------------- sección Tickets (por día, como el Récord)
const TKST = {GANADO:['✅','Ganado','g-w'],PERDIDO:['❌','Perdido','g-l'],PUSH:['➖','Push','g-p'],PENDIENTE:['⏳','Pendiente','g-n'],ANULADO:['⚪','Anulado','g-v'],MEDIO_GANADO:['✅','Medio ganado','g-w'],MEDIO_PERDIDO:['❌','Medio perdido','g-l']};
const tkBadge = s => { const x=TKST[s]||TKST.PENDIENTE; return `<span class="gbadge ${x[2]}">${x[0]} ${x[1]}</span>`; };
async function viewTickets(date){
  loading('Cargando tickets…');
  const d = await api('/api/tickets'+(date?'?date='+encodeURIComponent(date):''));
  date=d.date; const today=d.today, byDay=Object.fromEntries(d.days.map(x=>[x.date,x]));
  const lo=[...d.days.map(x=>x.date), rdAdd(today,-6)].sort()[0], hi=[...d.days.map(x=>x.date), rdAdd(today,1), date].sort().pop();
  const strip=[]; for(let s=lo; s<=hi && strip.length<120; s=rdAdd(s,1)) strip.push(s);
  const chip=s=>{ const a=byDay[s], dt=rdD(s); return `<a class="rdc ${s===date?'on':''} ${s===today?'td':''}" href="#/tickets/${s}"><span class="w">${s===today?'Hoy':RD_WD[dt.getUTCDay()]}</span><span class="n mono">${dt.getUTCDate()}</span><span class="r mono ${a?rdCls(a):'nn'}">${a?rdWL(a):'·'}</span></a>`; };
  const A=d.summary, T=d.total;
  const kpi=(l,v,c='')=>`<div class="kpi"><div class="sub">${l}</div><div class="v mono ${c}">${v}</div></div>`;
  const card=t=>`<div class="rec-list rdg tkc"><div class="rdgh tkch"><span><b>${esc(t.name||'Ticket #'+t.id)}</b> <span class="sub">${t.legs.length} pierna${t.legs.length>1?'s':''} · ${t.american>0?'+':''}${t.american??'—'}${t.p_model!=null?' · modelo '+(t.p_model*100).toFixed(1)+'%':''}</span></span><span>${tkBadge(t.status)} <span class="mono ${t.units>0?'pos':t.units<0?'neg':'mut'}">${units(t.units)}</span></span></div>
     ${t.legs.map(l=>`<div class="rec-r"><div class="rl"><b>${esc(l.label)}</b> <span class="mono sub">${l.odds>0?'+'+l.odds:l.odds}</span><div class="sub">${esc(l.kind==='prop'?(l.player||'prop'):l.home+' vs '+l.away)} · ${fmtShort(new Date(l.start_ts*1000).toISOString())} ${fmtTime(new Date(l.start_ts*1000).toISOString())}</div></div><div class="rr">${tkBadge(l.status)}</div></div>`).join('')}
     ${t.status==='PENDIENTE'&&!STATIC?`<div style="padding:6px 0 10px"><button class="btn" onclick="tkRm(${t.id})">Borrar ticket</button></div>`:''}</div>`;
  $app.innerHTML=`<h1>📒 Récord</h1>${rdTabs('tk')}
   <div class="rdnav"><a class="rdar" href="#/tickets/${rdAdd(date,-1)}" aria-label="Día anterior">‹</a><div class="rdt"><b>${rdName(date,today)}</b><span class="sub">Tickets de papel · día del primer juego (CDMX)</span></div><a class="rdar" href="#/tickets/${rdAdd(date,1)}" aria-label="Día siguiente">›</a></div>
   <div class="rdstrip" id="rdstrip">${strip.map(chip).join('')}</div>
   <div class="kpis">${kpi('Tickets del día G-P',A.W+A.L+A.P?`${A.W}-${A.L}${A.P?'-'+A.P:''}`:SD)}${kpi('Unidades (1u)',A.n_priced?units(A.units):SD,A.units>0?'pos':A.units<0?'neg':'')}</div>
   <div class="kpis s">${kpi('Tickets',A.n)}${kpi('⏳ Pendientes',A.pending)}${kpi('Total histórico',T.W+T.L+T.P?`${T.W}-${T.L}-${T.P} · ${units(T.units)}`:SD)}</div>
   ${d.tickets.length?d.tickets.map(card).join(''):`<div class="card mut" style="margin-top:10px">Sin tickets este día. Agrega piernas con <b>+ Ticket</b> en los picks, el detalle de un juego o un prop, o pídele al chat «arma un parlay de 3 con lo más seguro de hoy».</div>`}
   <div class="sub" style="margin-top:10px">Se califican solos con el marcador final real (cada pierna y el ticket). Push/anulada = la pierna se quita del momio. Paper trading: sin dinero real.</div>`;
  const st=document.getElementById('rdstrip'), on=st&&st.querySelector('.on'); if(on) st.scrollLeft=on.offsetLeft-st.clientWidth/2+on.offsetWidth/2;
}
async function tkRm(id){ if(!confirm('¿Borrar este ticket pendiente?')) return; await fetch('/api/tickets/'+id,{method:'DELETE'}); route(); }
// cargar piernas sugeridas (chat) al ticket y abrirlo
function tkLoad(legs){ legs.forEach(l=>{ if(!TK.legs.some(x=>tkKey(x)===tkKey(l))) TK.legs.push(Object.assign({official:true},l)); }); tkSave_(); tkOpen(); }
// pierna de un prop (pantalla del jugador): completa hora/equipos con el juego (cacheado en el servidor)
async function tkAddProp(side){
  const C=PDET.cur; if(!C) return; const L=C.d.line, price=side==='over'?L.over:L.under;
  if(L.ref||L.value==null||price==null){ tkToast('Sin línea/cuota real de DraftKings para este lado.'); return; }
  let g; try{ g=(await api(`/api/game/${encodeURIComponent(C.league)}/${encodeURIComponent(C.eid)}`)).game; }catch(e){ tkToast(e.message); return; }
  const leg={kind:'prop', league:C.league, eid:String(C.eid), sport:g.sport, start_ts:Math.round(Date.parse(g.date)/1000), home:g.home.name, away:g.away.name, home_id:String(g.home.id||''), away_id:String(g.away.id||''),
    market:'prop', aid:String(C.aid), key:C.key, player:C.d.info.name, selection:side, line:L.value, odds:price, label:`${C.d.info.name} ${side==='over'?'Más':'Menos'} ${pNum(L.value)} ${C.d.label}`, p:null, official:false};
  if(g.state!=='pre'){ tkToast('Ese juego ya empezó: sólo piernas pre-juego.'); return; }
  if(TK.legs.some(x=>tkKey(x)===tkKey(leg))){ tkToast('Ya está en el ticket'); return; }
  TK.legs.push(leg); tkSave_(); tkToast('Agregado al ticket ('+TK.legs.length+')');
}
tkFab();
