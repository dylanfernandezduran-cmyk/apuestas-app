/* NRNM Lab: validación, simulación Monte Carlo y estadística avanzada en el detalle. Sin datos inventados: todo sale de d.model / d.odds. */
const VAL_ST = {VALIDADO:['k-t','✔ Validado'], INCIERTO:['k-a','≈ Incierto'], ESPERAR:['amb','⏳ Esperar'], PASAR:['mut','✕ Pasar']};
const valBadge = st => st ? `<span class="vb vb-${st.toLowerCase()}">${(VAL_ST[st]||[,st])[1]}</span>` : '';
function dVal(d){
  const v=d.validation, q=d.data_quality; if(!v && !q) return '';
  const bar = q ? `<div class="dq"><div class="dq-h"><span>Calidad de datos</span><b class="mono">${q.score}/100</b></div><div class="dq-b"><i style="width:${q.score}%"></i></div>
    <div class="dq-c">${q.checks.map(c=>`<span class="${c.ok?'ok':'no'}">${c.ok?'✓':'✕'} ${esc(c.label)}${c.detail?' · '+esc(c.detail):''}</span>`).join('')}</div>
    ${q.sigma_eff?`<div class="sub">Incertidumbre del margen (σ efectiva): ±${q.sigma_eff} pts</div>`:''}</div>` : '';
  return ds('val','Validación del pick', `${v?`<div class="vrow">${valBadge(v.state)}<span class="sub">${esc((v.reasons||[]).join(' · '))}</span></div>`:''}${bar}`,
    {info:'VALIDADO: EV>0, datos completos y confianza Media/Alta. INCIERTO: divergencia alta, datos incompletos o confianza baja. ESPERAR: alineación o jugador clave sin confirmar. PASAR: sin cuota, sin valor (EV≤0) o datos insuficientes.'});
}
// ---- Monte Carlo
function mbRng(seed){ let a=seed>>>0; return ()=>{ a|=0; a=a+0x6D2B79F5|0; let t=Math.imul(a^a>>>15,1|a); t=t+Math.imul(t^t>>>7,61|t)^t; return ((t^t>>>14)>>>0)/4294967296; }; }
function mbNorm(r){ let u=0,v=0; while(!u) u=r(); while(!v) v=r(); return Math.sqrt(-2*Math.log(u))*Math.cos(2*Math.PI*v); }
function mbPois(r,l){ if(l<=0) return 0; if(l>30) return Math.max(0,Math.round(l+Math.sqrt(l)*mbNorm(r))); const L=Math.exp(-l); let k=0,p=1; do{ k++; p*=r(); }while(p>L); return k-1; }
function simRun(d, o){
  const m=d.model||{}, sp=(d.game||{}).sport, N=20000, r=mbRng(20261125);
  const pace=o.pace||1, eff=o.eff||0;
  const pois = sp==='nhl'||sp==='mlb'||sp==='futbol'||m.lam_home!=null;
  let lh=m.lam_home, la=m.lam_away;
  if(pois && (lh==null||la==null)){ const T=(m.exp_total||0)*pace, M=(m.exp_margin||0)+eff; lh=Math.max(.05,(T+M)/2); la=Math.max(.05,(T-M)/2); }
  else if(pois){ lh*=pace; la*=pace; }
  const sl=((d.odds||{}).spread||{}).home, tl=((d.odds||{}).total||{}).over;
  const sLine=sl&&sl.line!=null?sl.line:null, tLine=tl&&tl.line!=null?tl.line:null;
  let hw=0,aw=0,dr=0,cov=0,cpush=0,ov=0,opush=0,sh=0,sa=0; const tots=[],mars=[];
  for(let i=0;i<N;i++){
    let h,a;
    if(pois){ h=mbPois(r,lh); a=mbPois(r,la); }
    else { const T=(m.exp_total||0)*pace + (m.tsigma||18)*Math.sqrt(pace)*mbNorm(r); const M=(m.exp_margin||0)+eff+(m.sigma||12.5)*mbNorm(r); h=(T+M)/2; a=(T-M)/2; }
    sh+=h; sa+=a; const mg=h-a, t=h+a; tots.push(t); mars.push(mg);
    if(mg>0) hw++; else if(mg<0) aw++; else dr++;
    if(sLine!=null){ const x=mg+sLine; if(Math.abs(x)<1e-9) cpush++; else if(x>0) cov++; }
    if(tLine!=null){ if(Math.abs(t-tLine)<1e-9) opush++; else if(t>tLine) ov++; }
  }
  return {N, pois, h:sh/N, a:sa/N, hw:hw/N, aw:aw/N, dr:dr/N, cov:sLine!=null?cov/N:null, cpush:cpush/N, ov:tLine!=null?ov/N:null, opush:opush/N, sLine, tLine, tots, mars};
}
function simHist(arr, line, lab){
  if(!arr.length) return '';
  const s=[...arr].sort((x,y)=>x-y), lo=s[Math.floor(s.length*.01)], hi=s[Math.floor(s.length*.99)];
  const B=24, w=(hi-lo)/B||1, c=new Array(B).fill(0);
  arr.forEach(x=>{ const i=Math.min(B-1,Math.max(0,Math.floor((x-lo)/w))); c[i]++; });
  const mx=Math.max(...c), W=300, H=70;
  const bars=c.map((v,i)=>{ const x0=lo+i*w; const on=line!=null&&x0+w>line; return `<rect x="${i*W/B+1}" y="${H-v/mx*H}" width="${W/B-2}" height="${v/mx*H}" rx="1.5" class="${on?'hb-on':'hb'}"><title>${x0.toFixed(1)}–${(x0+w).toFixed(1)}: ${(v/arr.length*100).toFixed(1)}%</title></rect>`; }).join('');
  const lx=line!=null?((line-lo)/(hi-lo))*W:null;
  return `<div class="sim-h"><div class="sub">${esc(lab)}${line!=null?` · línea ${line}`:''}</div><svg viewBox="0 0 ${W} ${H+14}" class="sim-svg" role="img" aria-label="${esc(lab)}">${bars}${lx!=null&&lx>=0&&lx<=W?`<line x1="${lx}" x2="${lx}" y1="0" y2="${H}" class="hl"/>`:''}<text x="0" y="${H+12}" class="ax">${lo.toFixed(0)}</text><text x="${W}" y="${H+12}" class="ax" text-anchor="end">${hi.toFixed(0)}</text></svg></div>`;
}
function simHtml(d, o){
  const g=d.game||{}, R=simRun(d,o), hn=(g.home||{}).abbr||(g.home||{}).name||'Local', an=(g.away||{}).abbr||(g.away||{}).name||'Visitante';
  const pc=x=>x==null?SD:(x*100).toFixed(1)+'%', dec=R.pois?1:0;
  const sp=g.sport, soc=sp==='futbol';
  const row=(l,v,nv)=>`<div class="sim-r"><span>${l}</span><div class="pbar"><i style="width:${v==null?0:(v*100).toFixed(1)}%"></i></div><b class="mono">${pc(v)}</b>${nv!=null?`<small class="mut mono">mkt ${pc(nv)}</small>`:''}</div>`;
  const nv=(d.odds||{}).nv||{};
  const lines=[row(`${esc(hn)} gana`,R.hw,(nv.ml||{}).home), soc?row('Empate',R.dr,null):'', row(`${esc(an)} gana`,R.aw,(nv.ml||{}).away)];
  if(R.cov!=null) lines.push(row(`${esc(hn)} ${R.sLine>0?'+':''}${R.sLine}`,R.cov,(nv.spread||{}).home));
  if(R.ov!=null) lines.push(row(`Más de ${R.tLine}`,R.ov,(nv.total||{}).over));
  return `<div class="sim-sc"><div><span class="sub">${esc(an)}</span><b class="mono">${R.a.toFixed(dec)}</b></div><span class="sub">marcador proyectado</span><div><span class="sub">${esc(hn)}</span><b class="mono">${R.h.toFixed(dec)}</b></div></div>
    ${lines.join('')}
    ${simHist(R.tots,R.tLine,'Distribución del total')}${simHist(R.mars,R.sLine!=null?-R.sLine:null,'Distribución del margen (local − visita)')}
    <div class="sub">${R.N.toLocaleString('es-MX')} simulaciones · ${R.pois?'Poisson por equipo':'normal (margen y total)'} con medias y varianzas del modelo NRNM${R.pois&&!soc?'; en empate se va a tiempo extra (no modelado)':''}. «mkt» = prob. del mercado sin vig. Es una estimación, no garantía.</div>`;
}
function dSim(d){
  const m=d.model; if(!m||(m.exp_total==null&&m.lam_home==null)) return '';
  const nba=(d.game||{}).sport==='nba';
  const ctr=nba?`<div class="sim-ctl"><label>Ritmo <input type="range" min="-10" max="10" step="1" value="0" data-sim="pace"><output>0%</output></label><label>Eficiencia local <input type="range" min="-6" max="6" step="0.5" value="0" data-sim="eff"><output>0</output></label><button type="button" class="pill" data-sim="reset">Restablecer</button></div>`:'';
  return ds('sim','Simulación Monte Carlo', `${ctr}<div id="sim-out">${simHtml(d,{})}</div>`, {info:'Simula el juego 20,000 veces con la media y la desviación del modelo. En NBA puedes mover el ritmo (± % de posesiones → total) y la eficiencia del local (± puntos de margen) para ver el «qué pasaría si».'});
}
document.addEventListener('input', e=>{
  const s=e.target.closest('[data-sim]'); if(!s || !window.__D) return;
  const box=s.closest('.sim-ctl'); const pace=+box.querySelector('[data-sim="pace"]').value, eff=+box.querySelector('[data-sim="eff"]').value;
  box.querySelector('[data-sim="pace"] + output').textContent=(pace>0?'+':'')+pace+'%'; box.querySelector('[data-sim="eff"] + output').textContent=(eff>0?'+':'')+eff;
  const o=document.getElementById('sim-out'); if(o) o.innerHTML=simHtml(window.__D,{pace:1+pace/100, eff});
});
document.addEventListener('click', e=>{
  const b=e.target.closest('[data-sim="reset"]'); if(!b||!window.__D) return;
  const box=b.closest('.sim-ctl'); box.querySelectorAll('input').forEach(i=>{ i.value=0; i.dispatchEvent(new Event('input',{bubbles:true})); });
});
// ---- estadística avanzada (NBA: eFG%, TS%, ritmo, ratings) si el servidor la trae
function dAdv(d){
  const a=d.advanced; if(!a||!a.sides) return '';
  const g=d.game||{}; const cols=a.cols||[];
  const nm=s=>esc((g[s]||{}).abbr||(g[s]||{}).name||s);
  const head=`<tr><th></th>${cols.map(c=>`<th>${esc(c[1])}</th>`).join('')}</tr>`;
  const tr=s=>`<tr><td>${nm(s)}</td>${cols.map(c=>{ const v=(a.sides[s]||{})[c[0]]; return `<td class="mono">${v==null?'—':v}</td>`; }).join('')}</tr>`;
  return ds('adv','Estadística avanzada', `<div class="cal-w"><table class="cal">${head}${tr('away')}${tr('home')}</table></div><div class="sub">${esc(a.note||'')}</div>`);
}
// ---- consenso público de handicappers (Covers), citado
function dHand(d){
  const c=d.handicappers; if(!c||!c.home||!c.away) return '';
  const g=d.game||{}, nm=s=>esc((g[s]||{}).abbr||(g[s]||{}).name||s);
  const row=s=>`<div class="sim-r"><span>${nm(s)} ${esc(c[s].line||'')}</span><div class="pbar"><i style="width:${c[s].pct}%"></i></div><b class="mono">${c[s].pct}%</b><small class="mut mono">${c[s].picks!=null?c[s].picks+' picks':''}</small></div>`;
  return ds('hcp','Consenso de handicappers', `${row('away')}${row('home')}<div class="sub">Fuente: <a href="${esc(c.src_url)}" target="_blank" rel="noopener">${esc(c.src)}</a>${c.n?` · ${c.n} picks`:''}. ${esc(c.note||'')}</div>`);
}
