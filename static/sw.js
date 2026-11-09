/* Service worker local (LAN). En GitHub Pages NO se registra (NRNM_STATIC). Network-first HTML para no brickear. */
const V = 'shell-v30';
const SHELL = ['/', '/static/style.css?v=22', '/static/extras.js?v=15', '/static/detalle.js?v=8', '/static/props.js?v=2', '/static/app.js?v=24', '/static/recdia.js?v=2', '/static/ticket.js?v=2', '/static/chat.js?v=8', '/static/brand/icons/icon-192.png', '/manifest.webmanifest'];
self.addEventListener('install', e => {
  e.waitUntil(caches.open(V).then(c => Promise.all(SHELL.map(u => c.add(u).catch(()=>null)))).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== V && k !== 'api-v1').map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const r = e.request, u = new URL(r.url);
  if (r.method !== 'GET' || u.origin !== location.origin) return;
  if (u.pathname.startsWith('/api/')) {
    if (u.pathname === '/api/live' || u.pathname === '/api/health') return;
    e.respondWith(fetch(r).then(res => { if (res.ok) { const c = res.clone(); caches.open('api-v1').then(ch => ch.put(r, c)); } return res; })
      .catch(() => caches.match(r).then(m => m || new Response(JSON.stringify({detail: 'Sin conexión y sin datos guardados'}), {status: 503, headers: {'Content-Type': 'application/json'}}))));
    return;
  }
  // HTML / navegación: red primero (nunca servir un index viejo que dispare bucles de recarga)
  if (r.mode === 'navigate' || u.pathname === '/' || /\.html$/.test(u.pathname)) {
    e.respondWith(fetch(r).then(res => { if (res.ok) { const c = res.clone(); caches.open(V).then(ch => ch.put(r, c)); } return res; })
      .catch(() => caches.match(r).then(m => m || caches.match('/'))));
    return;
  }
  e.respondWith(caches.match(r).then(m => {
    const net = fetch(r).then(res => { if (res.ok) { const c = res.clone(); caches.open(V).then(ch => ch.put(r, c)); } return res; }).catch(() => m);
    return m || net;
  }));
});
