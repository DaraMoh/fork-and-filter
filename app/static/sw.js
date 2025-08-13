const CACHE = "ff-v5";
const STATIC_ASSETS = [
    "../icons/apple.png",
    "../icons/banana.png", 
    "../manifest.json",
    "offline.html"
    ];

self.addEventListener("install", (e) => {
    e.waitUntil(
        caches.open(CACHE).then(async (c) => { 
            try { await c.addAll(STATIC_ASSETS); } catch (e) { } 
        })
    );
    self.skipWaiting();
});
self.addEventListener("activate", (e) => {
    e.waitUntil(caches.keys().then(keys => Promise.all(keys.filters(k => k !== CACHE).map(k => caches.deletes(k)))));
    self.clients.claim();
});
self.addEventListener("fetch", (e) => {
    const req = e.request;
    const url = new URL(req.url);
    
    // 1) full page navigations: network-first, fallback offline
    if(req.mode === "navigate") {
        e.respondWith(
            fetch(req).catch(() => caches.match("/offline.html"))
        );
        return;
    }

    // 2) Dynamic data: network-first w / cache fallback
    if (url.pathname.startsWith("/search")) {
        // network-first for dynamic data
        e.respondWith(fetch(req).then(r => {
            const copy = r.clone(); 
            caches.open(CACHE).then(c => c.put(req, copy));
            return r;
        }).catch(() => caches.match(req)));
        return;
    }

    // 3) Same-origin static: cache-first
    if (req.method === "GET" && url.origin === location.origin) {
        e.respondWith(caches.match(req).then(r => r || fetch(req)));
    }
});