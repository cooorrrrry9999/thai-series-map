// Thai GL Map — Service Worker (PWA)
// 役割：再訪問時にアプリ本体を毎回ダウンロードし直さない＋オフライン対応。
// 注意：data.json はネットワーク優先（常に最新を取りに行き、オフライン時だけキャッシュを使う）。
//       これはFirestore読み取りとは無関係（data.jsonは静的ファイル）だが、通信量と表示速度を改善する。

const CACHE = 'tglmap-v18';                 // ★中身を更新したらここの番号を上げる（v2, v3…）= 古いキャッシュを捨てる合図
const SHELL = [
  './',
  './index.html',
  './manifest.json',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
];

// インストール時：アプリ本体（シェル）を先読みキャッシュ
self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE)
      .then(c => c.addAll(SHELL).catch(() => {})) // 一部失敗してもインストールは続行
      .then(() => self.skipWaiting())
  );
});

// 有効化時：古いバージョンのキャッシュを削除
self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return; // 書き込み等はそのまま通す

  const url = new URL(req.url);

  // ⓪ Firebase（Firestore・認証）の通信には一切触らない。
  //    ここをキャッシュ処理に通すと、保存（書き込み）の応答が返らず画面が固まる原因になる。
  //    キャッシュしてよそのオリジンは、フォントとLeaflet（unpkg）だけに限定する。
  if (url.origin !== self.location.origin
      && !/^(fonts\.googleapis\.com|fonts\.gstatic\.com|unpkg\.com)$/.test(url.hostname)) return;

  // ① data.json はネットワーク優先（最新を取りに行く／オフラインならキャッシュ）
  if (url.pathname.endsWith('/data.json')) {
    e.respondWith(
      fetch(req)
        .then(res => {
          const copy = res.clone();
          caches.open(CACHE).then(c => c.put(req, copy));
          return res;
        })
        .catch(() => caches.match(req))
    );
    return;
  }

  // ② 地図タイル（cartocdn / openstreetmap）はキャッシュしない＝容量肥大を防ぐ
  if (/basemaps\.cartocdn\.com|tile\.openstreetmap\.org/.test(url.hostname)) return;

  // ③ HTMLページ（index.html / admin.html など画面本体）はネットワーク優先。
  //    ＝ファイルを更新したら、オンラインなら必ず最新が表示される（古いキャッシュが出続けない）。
  //      オフラインのときだけキャッシュを使う。
  const isHTML = req.mode === 'navigate'
    || url.pathname.endsWith('.html')
    || url.pathname.endsWith('/');
  if (isHTML) {
    e.respondWith(
      fetch(req)
        .then(res => {
          if (res && res.status === 200) {
            const copy = res.clone();
            caches.open(CACHE).then(c => c.put(req, copy));
          }
          return res;
        })
        .catch(() => caches.match(req).then(c => c || caches.match('./index.html')))
    );
    return;
  }

  // ④ それ以外（Leaflet などのライブラリ）はキャッシュ優先＋裏で更新（stale-while-revalidate）
  e.respondWith(
    caches.match(req).then(cached => {
      const network = fetch(req).then(res => {
        if (res && res.status === 200) {
          const copy = res.clone();
          caches.open(CACHE).then(c => c.put(req, copy));
        }
        return res;
      }).catch(() => cached);
      return cached || network;
    })
  );
});
