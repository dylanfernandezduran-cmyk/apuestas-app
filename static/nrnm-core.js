// ===== NRNM · núcleo de cálculo (momios americanos) =====
const implied = o => o < 0 ? -o / (-o + 100) : 100 / (o + 100);
const decimal = o => o < 0 ? 1 + 100 / -o : 1 + o / 100;
const fairOdds = p => p >= 0.5 ? Math.round(-100 * p / (1 - p)) : Math.round(100 * (1 - p) / p);
const noVig = (oA, oB) => { const a = implied(oA), b = implied(oB), s = a + b; return [a / s, b / s]; };
const ev = (p, o) => p * decimal(o) - 1;                       // EV por 1u
const edgePP = (pFinal, pNoVig) => (pFinal - pNoVig) * 100;    // en puntos porcentuales
const kelly = (p, o) => Math.max(0, (p * decimal(o) - 1) / (decimal(o) - 1));
const stakePct = (p, o, { frac = 0.25, cap = 0.02 } = {}) => Math.min(cap, kelly(p, o) * frac); // fracción del bankroll
const clamp = (x, lo, hi) => Math.min(hi, Math.max(lo, x));

// Mezcla modelo + mercado: el peso del modelo (máx. maxW) crece con la muestra
function pFinal(pModel, pMarket, nGames, { maxW = 0.5, n0 = 100, maxGap = 0.20 } = {}) {
  const w = maxW * Math.min(1, nGames / n0);
  const pm = clamp(pModel, pMarket - maxGap, pMarket + maxGap);
  return w * pm + (1 - w) * pMarket;
}

const DIVERGENCE_MAX_PP = 10;
function pickState({ edge, evVal, conf, gapPP }) {
  if (gapPP > DIVERGENCE_MAX_PP) return 'REVISAR';            // el modelo probablemente no ve algo
  if (edge >= 3 && evVal >= 0 && conf !== 'baja') return 'PICK';
  if (edge >= 1) return 'LEAN';
  return 'PASS';
}

// Ticket/parlay: el EV es un TOPE (supone independencia y acumula el error del modelo)
function parlay(legs) { // legs: [{ odds, pModel }]
  const dec = legs.reduce((a, l) => a * decimal(l.odds), 1);
  const pModel = legs.reduce((a, l) => a * l.pModel, 1);
  const pImp = legs.reduce((a, l) => a * implied(l.odds), 1);
  const american = dec >= 2 ? Math.round((dec - 1) * 100) : Math.round(-100 / (dec - 1));
  return { american, pModel, pImp, evCap: pModel * dec - 1 };
}

// ===== Detector de movimientos de línea =====
const movePP = (oOpen, oNow) => (implied(oNow) - implied(oOpen)) * 100;
const median = a => { const s = [...a].sort((x, y) => x - y), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };

/**
 * snaps: [{ book, t (ms), odds }] de UN lado de UN mercado, tomados cada 5-10 min.
 * ctx: { pctTickets (0-1, de ESE lado), sharp: 'Pinnacle', windowMin: 180 }
 * Para spread/total compara también el número de la línea, no solo el precio.
 */
function detectMoves(snaps, { pctTickets = null, sharp = 'Pinnacle', windowMin = 180 } = {}) {
  const tNow = Math.max(...snaps.map(s => s.t));
  const win = snaps.filter(s => tNow - s.t <= windowMin * 60000);
  const byBook = {};
  for (const s of win) (byBook[s.book] ??= []).push(s);
  const moves = Object.entries(byBook).map(([book, a]) => ({
    book, now: a[a.length - 1], pp: movePP(a[0].odds, a[a.length - 1].odds) }));
  const cons = median(moves.map(m => m.pp));                   // cambio de consenso en pp
  const same = moves.filter(m => Math.sign(m.pp) === Math.sign(cons) && Math.abs(m.pp) >= 2);
  const sharpMove = moves.find(m => m.book === sharp);
  const tags = [];
  if (Math.abs(cons) >= 3 && same.length >= 3 && (!sharpMove || Math.abs(sharpMove.pp) >= 2)) tags.push('STEAM');
  if (cons >= 3 && pctTickets !== null && pctTickets <= 0.45) tags.push('RLM');
  const medNow = median(moves.map(m => implied(m.now.odds)));
  const laggards = moves.filter(m => medNow - implied(m.now.odds) >= 0.02)   // precio mejor que el consenso
    .map(m => ({ book: m.book, odds: m.now.odds }));
  if (laggards.length) tags.push('REZAGADA');
  return { ppConsensus: cons, tags, laggards, books: moves.length };
}
