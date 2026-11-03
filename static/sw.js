/* Service worker: caparazón de la app sin conexión. Requiere HTTPS (o localhost). Datos /api: red primero, con respaldo del último valor visto. */
const V = 'shell-v19';
const SHELL = ['/', '/static/style.css?v=18', '/static/extras.js?v=12', '/static/detalle.js?v=5', '/static/props.js?v=1', '/static/app.js?v=15', '/static/brand/icons/icon-192.png', '/manifest.webmanifest'];
self.addEventListener('install', e => { e.waitUntil(caches.open(V).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())); });
self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== V && k !== 'api-v1').map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener('fetch', e => {
  const r = e.request, u = new URL(r.url);
  if (r.method !== 'GET' || u.origin !== location.origin) return;
  if (u.pathname.startsWith('/api/')) {
    if (u.pathname === '/api/live' || u.pathname === '/api/health') return;        // en vivo: nunca desde caché
    e.respondWith(fetch(r).then(res => { if (res.ok) { const c = res.clone(); caches.open('api-v1').then(ch => ch.put(r, c)); } return res; })
      .catch(() => caches.match(r).then(m => m || new Response(JSON.stringify({detail: 'Sin conexión y sin datos guardados'}), {status: 503, headers: {'Content-Type': 'application/json'}}))));
    return;
  }
  if (r.mode === 'navigate') { e.respondWith(fetch(r).then(res => { const c = res.clone(); caches.open(V).then(ch => ch.put('/', c)); return res; }).catch(() => caches.match('/'))); return; }
  e.respondWith(caches.match(r).then(m => { const net = fetch(r).then(res => { if (res.ok) { const c = res.clone(); caches.open(V).then(ch => ch.put(r, c)); } return res; }).catch(() => m); return m || net; }));
});
