// ------------------------------------------------------------ récord POR DÍA + calendario (pt92u). Día = fecha del juego en hora CDMX (UTC-6).
const RD = {type:'', sport:''};
const RD_WD = ['dom','lun','mar','mié','jue','vie','sáb'], RD_MES = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'];
const rdD = s => { const [y,m,d]=s.split('-').map(Number); return new Date(Date.UTC(y,m-1,d)); };
const rdS = dt => dt.toISOString().slice(0,10);
const rdAdd = (s,n) => { const d=rdD(s); d.setUTCDate(d.getUTCDate()+n); return rdS(d); };
const rdDiff = (a,b) => Math.round((rdD(a)-rdD(b))/864e5);
function rdName(s, today){ const k=rdDiff(s,today), d=rdD(s);
  const rel={0:'Hoy','-1':'Ayer','-2':'Antier',1:'Mañana',2:'Pasado mañana'}[k];
  const full=`${RD_WD[d.getUTCDay()]} ${d.getUTCDate()} ${RD_MES[d.getUTCMonth()].slice(0,3)}`;
  return rel ? `${rel} · ${full}` : full; }
function rdAgg(rows){ let W=0,L=0,P=0,u=0,np=0,pend=0,vd=0;
  rows.forEach(r=>{ const s=r.status;
    if(s==='GANADO')W++; else if(s==='PERDIDO')L++; else if(s==='PUSH')P++; else if(s==='MEDIO_GANADO'){W+=.5;P+=.5} else if(s==='MEDIO_PERDIDO'){L+=.5;P+=.5}
    else if(s==='PENDIENTE')pend++; else if(s==='ANULADO')vd++;
    if(!['PENDIENTE','ANULADO'].includes(s)&&r.units!=null){u+=r.units;np++;} });
  return {W,L,P,pending:pend,void:vd,n:rows.length,units:Math.round(u*100)/100,n_priced:np,win_pct:W+L?W/(W+L)*100:null,roi:np?u/np*100:null}; }
const rdN = n => Number.isInteger(n)?n:n.toFixed(1);
const rdWL = a => a.W+a.L+a.P ? `${rdN(a.W)}-${rdN(a.L)}${a.P?'-'+rdN(a.P):''}` : (a.pending?`${a.pending}⏳`:'—');
const rdCls = a => a.W>a.L?'up':a.L>a.W?'dn':(a.W+a.L?'eq':'nn');
function rdTabs(on){ return `<div class="pills rtabs">${[['dia','📅 Día','#/record'],['cal','🗓️ Mes','#/record/cal'],['tk','🎟️ Tickets','#/tickets'],['total','Σ Total','#/record/total']].map(([k,l,h])=>`<a class="pill ${k===on?'on':''}" href="${h}">${l}</a>`).join('')}</div>`; }

async function viewRecordDay(date){
  SPORTS = SPORTS || await api('/api/sports');
  loading('Cargando récord del día…');
  const d = await api('/api/record/day'+(date?'?date='+encodeURIComponent(date):''));
  date = d.date; const today=d.today;
  const byDay = Object.fromEntries(d.days.map(x=>[x.date,x]));
  // franja de días: desde el primer día con picks hasta mañana (o el último día con picks), más reciente a la derecha
  const first = d.days.length ? d.days[d.days.length-1].date : today, last0 = d.days.length ? d.days[0].date : today;
  let lo = rdDiff(first, today)<-60 ? rdAdd(today,-60) : first, hi = [last0, rdAdd(today,1), date].sort().pop();
  if(date<lo) lo=date;
  const strip=[]; for(let s=lo; s<=hi; s=rdAdd(s,1)) strip.push(s);
  const chip = s => { const a=byDay[s], dt=rdD(s);
    return `<a class="rdc ${s===date?'on':''} ${s===today?'td':''}" href="#/record/dia/${s}" data-d="${s}"><span class="w">${s===today?'Hoy':RD_WD[dt.getUTCDay()]}</span><span class="n mono">${dt.getUTCDate()}</span><span class="r mono ${a?rdCls(a):'nn'}">${a?rdWL(a):'·'}</span></a>`; };
  const rows = d.picks.filter(r=>(!RD.type||r.type===RD.type)&&(!RD.sport||r.sport===RD.sport));
  const A = rdAgg(rows);
  const kpi=(l,v,c='')=>`<div class="kpi"><div class="sub">${l}</div><div class="v mono ${c}">${v}</div></div>`;
  const spK = Object.keys(d.by_sport);
  const spOrder = (SPORTS||[]).map(s=>s.key).filter(k=>spK.includes(k));
  let html = `<h1>📒 Récord</h1>${rdTabs('dia')}
   <div class="rdnav"><a class="rdar" href="#/record/dia/${rdAdd(date,-1)}" aria-label="Día anterior">‹</a>
     <div class="rdt"><b>${rdName(date,today)}</b><span class="sub">${RD_MES[rdD(date).getUTCMonth()]} ${rdD(date).getUTCFullYear()} · hora CDMX</span></div>
     <a class="rdar" href="#/record/dia/${rdAdd(date,1)}" aria-label="Día siguiente">›</a></div>
   <div class="rdstrip" id="rdstrip">${strip.map(chip).join('')}</div>
   ${date!==today?`<div style="text-align:center;margin:-2px 0 8px"><a class="pill" href="#/record">↩ Volver a hoy</a></div>`:''}
   <div class="pills">${[['','Todos'],['main','Pick principal'],['suggestion','Sugerencias']].map(([v,l])=>`<span class="pill ${RD.type===v?'on':''}" onclick="RD.type='${v}';route()">${l}</span>`).join('')}</div>
   <div class="kpis">${kpi('Récord del día G-P-E',A.W+A.L+A.P?`${rdN(A.W)}-${rdN(A.L)}-${rdN(A.P)}`:SD)}${kpi('% acierto',A.win_pct==null?SD:A.win_pct.toFixed(1)+'%',A.win_pct>=52.4?'pos':A.win_pct!=null?'neg':'')}
    ${kpi('Unidades (1u)',A.n_priced?units(A.units):SD,A.units>0?'pos':A.units<0?'neg':'')}${kpi('ROI',A.roi==null?SD:sg(A.roi)+'%',A.roi>0?'pos':A.roi<0?'neg':'')}</div>
   <div class="kpis s">${kpi('Picks',A.n)}${kpi('⏳ Pendientes',A.pending)}${kpi('⚪ Anulados',A.void)}</div>`;
  if(spOrder.length>1||RD.sport) html += `<div class="day">Por deporte</div><div class="rdsp">${[['', 'Todos', rdAgg(d.picks.filter(r=>!RD.type||r.type===RD.type))], ...spOrder.map(k=>[k,(SPORT_EM[k]||'')+' '+esc(((SPORTS||[]).find(s=>s.key===k)||{name:k}).name), rdAgg(d.picks.filter(r=>r.sport===k&&(!RD.type||r.type===RD.type)))])].map(([k,l,a])=>
     `<span class="rdsr ${RD.sport===k?'on':''}" onclick="RD.sport='${k}';route()"><span>${l}</span><b class="mono ${rdCls(a)}">${rdWL(a)}</b><span class="mono sub">${a.n_priced?units(a.units):''}</span></span>`).join('')}</div>`;
  if(!rows.length) html += `<div class="card mut" style="margin-top:10px">${d.picks.length?'Sin picks con ese filtro este día.':(date>today?'Aún no hay picks registrados para este día: se registran cuando el modelo analiza los juegos (antes de empezar).':'No hubo picks registrados este día.')}</div>`;
  else {
    // agrupado por juego, en orden de hora (CDMX)
    const games=[]; const gi={};
    rows.forEach(r=>{ const k=r.league+'/'+r.eid; if(!(k in gi)){gi[k]=games.length; games.push([r,[]]);} games[gi[k]][1].push(r); });
    html += `<div class="day">Picks del día (${rows.length}) · por hora de inicio</div>`+games.map(([g,rs])=>`<div class="rec-list rdg">
      <a class="rdgh" href="#/juego/${encodeURIComponent(g.league)}/${encodeURIComponent(g.eid)}"><span class="mono sub">${fmtTime(new Date(g.start_ts*1000).toISOString())} · ${SPORT_EM[g.sport]||''} ${esc(g.league.toUpperCase())}</span><div class="rl-m">${recMatch(g)}</div>${g.score_text?`<div class="sub mono">${esc(g.score_text)}</div>`:''}</a>
      ${rs.map(r=>`<div class="rec-r"><div class="rl">${typeLbl(r.type)}${r.basis==='mercado'?' <span class="sub">(sólo mercado)</span>':''}<div><b>${esc(r.label)}</b> <span class="mono sub">${oddsTxt(r)}</span></div>${lineMove(r,{state:r.start_ts*1000<Date.now()?'post':'pre'})}${r.note?`<div class="sub">ℹ️ ${esc(r.note)}</div>`:''}</div>
      <div class="rr">${gradeBadge(r,false)}<div class="mono ${r.units>0?'pos':r.units<0?'neg':'mut'}">${units(r.units)}</div></div></div>`).join('')}</div>`).join('');
  }
  html += `<div class="sub" style="margin-top:10px">El día es la fecha del juego en hora de CDMX. Unidades = 1u plano a la cuota registrada (línea de cierre). Calificación automática cada ${d.grading.every_min} min${d.grading.last?' · última '+tsFmt(d.grading.last):''}.</div>`;
  $app.innerHTML = html;
  const st=document.getElementById('rdstrip'), on=st&&st.querySelector('.on'); if(on) st.scrollLeft = on.offsetLeft - st.clientWidth/2 + on.offsetWidth/2;
}

async function viewRecordCal(ym){
  loading('Cargando calendario…');
  const d = await api('/api/record/day');
  const today=d.today; ym = ym && /^\d{4}-\d{2}$/.test(ym) ? ym : today.slice(0,7);
  const byDay = Object.fromEntries(d.days.map(x=>[x.date,x]));
  const [y,m]=ym.split('-').map(Number), first=new Date(Date.UTC(y,m-1,1)), nd=new Date(Date.UTC(y,m,0)).getUTCDate();
  const prev=rdS(new Date(Date.UTC(y,m-2,1))).slice(0,7), next=rdS(new Date(Date.UTC(y,m,1))).slice(0,7);
  const mrows=d.days.filter(x=>x.date.startsWith(ym));
  const M=mrows.reduce((a,x)=>({W:a.W+x.W,L:a.L+x.L,P:a.P+x.P,units:a.units+x.units,n_priced:a.n_priced+x.n_priced,pending:a.pending+x.pending}),{W:0,L:0,P:0,units:0,n_priced:0,pending:0});
  const off=(first.getUTCDay()+6)%7; // semana empieza en lunes
  let cells=''; for(let i=0;i<off;i++) cells+='<span class="cc e"></span>';
  for(let k=1;k<=nd;k++){ const s=`${ym}-${String(k).padStart(2,'0')}`, a=byDay[s];
    cells+=`<a class="cc ${a?rdCls(a):'nn'} ${s===today?'td':''}" href="#/record/dia/${s}"><span class="n">${k}</span>${a?`<span class="r mono">${rdWL(a)}</span>${a.n_priced?`<span class="u mono">${units(a.units)}</span>`:''}`:''}</a>`; }
  const wins=mrows.filter(x=>x.W>x.L).length, loss=mrows.filter(x=>x.L>x.W).length;
  $app.innerHTML = `<h1>📒 Récord</h1>${rdTabs('cal')}
   <div class="rdnav"><a class="rdar" href="#/record/cal/${prev}" aria-label="Mes anterior">‹</a><div class="rdt"><b>${RD_MES[m-1][0].toUpperCase()+RD_MES[m-1].slice(1)} ${y}</b><span class="sub">${M.W+M.L+M.P?`Mes ${rdN(M.W)}-${rdN(M.L)}-${rdN(M.P)} · ${units(Math.round(M.units*100)/100)} · días ganadores ${wins}, perdedores ${loss}`:'Sin picks calificados este mes'}</span></div><a class="rdar" href="#/record/cal/${next}" aria-label="Mes siguiente">›</a></div>
   <div class="cal"><span class="ch">L</span><span class="ch">M</span><span class="ch">M</span><span class="ch">J</span><span class="ch">V</span><span class="ch">S</span><span class="ch">D</span>${cells}</div>
   <div class="sub" style="margin-top:8px"><span class="dot up"></span> día ganador (más G que P) · <span class="dot dn"></span> día perdedor · <span class="dot eq"></span> empate · ⏳ = sólo pendientes. Toca un día para ver sus picks. Fecha del juego en hora CDMX.</div>`;
}
