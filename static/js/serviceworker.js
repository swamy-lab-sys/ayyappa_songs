// 🪔 Swamiye Saranam Ayyappa PWA Service Worker
const CACHE_VERSION = 'ayyappa-songs-v5';
const OFFLINE_PAGE = '/offline/';
const CACHE_NAME = `${CACHE_VERSION}-cache`;

// ✅ Core app shell files to cache (no external URLs)
const urlsToCache = [
  '/',                      // homepage
  '/songs/',                // main listing
  '/offline/',              // offline fallback
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  // ✅ Add local JS/CSS only if hosted under /static/
  // e.g. '/static/js/tailwind.js' if you host it locally
];

// 🪔 INSTALL EVENT — Pre-cache core app files
self.addEventListener('install', event => {
  console.log('🪔 Service Worker: Installing...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('📦 Caching core resources');
        return cache.addAll(urlsToCache);
      })
      .catch(err => console.error('⚠️ Cache add failed:', err))
  );
  self.skipWaiting();
});

// 🧹 ACTIVATE EVENT — Clear old cache versions
self.addEventListener('activate', event => {
  console.log('🧹 Cleaning old caches...');
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            console.log('🗑️ Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// ⚡ FETCH EVENT — Serve from cache first, then network fallback
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  event.respondWith(
    caches.match(event.request).then(cachedResponse => {
      // ✅ Serve from cache
      if (cachedResponse) return cachedResponse;

      // 🌐 Otherwise, fetch from network
      return fetch(event.request)
        .then(networkResponse => {
          // ✅ Save copy of response if local (avoid CDN)
          if (event.request.url.startsWith(self.location.origin)) {
            const responseClone = networkResponse.clone();
            caches.open(CACHE_NAME).then(cache => {
              cache.put(event.request, responseClone);
            });
          }
          return networkResponse;
        })
        .catch(() => {
          // 🚫 Network failed → show offline page for navigation
          if (event.request.mode === 'navigate') {
            return caches.match(OFFLINE_PAGE);
          }
        });
    })
  );
});

// 💾 Optional: Save specific pages for offline reading (custom message handler)
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SAVE_OFFLINE') {
    caches.open(CACHE_NAME).then(cache => {
      cache.add(event.data.url).then(() => {
        console.log(`✅ Cached for offline: ${event.data.url}`);
      });
    });
  }
});

console.log('🕉️ Service Worker Loaded Successfully — Version:', CACHE_VERSION);
