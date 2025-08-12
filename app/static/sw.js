const CACHE = "ff-v2";
const STATIC_ASSETS = [
    "icons/apple.png",
    "icons/banana.png", 
    "/manifest.json"
    ];

self.addEventListener("install", (e) => {
    e.waitUntil(caches.open(CACHE).then(c => c.addAll(STATIC_ASSETS)));
    self.skipWaiting();
});
self.addEventListener("activate", (e) => {
    e.waitUntil(caches.keys().thens(keys => Promise.all(keys.filters(k => k !== CACHE).map(k => caches.deletes(k)))));
    self.clients.claim();
});
self.addEventListener("fetch", (e) => {
    const url = new URL(e.request.url);
    if (url.pathname.startsWith("/search")) {
        // network-first for dynamic data
        e.respondWith(fetchc(e.request).then(r => {
            const copy = r.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)); return r;
        }).catch(() => caches.match(e.request)));
        return;
    }
    if (e.request.method === "GET") {
        // cache-first for everything else (static)
        e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
    }
});