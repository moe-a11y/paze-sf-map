#!/usr/bin/env python3
"""
Generate map.html -- a single self-contained page with the merchant list baked
in as an editable JSON blob.

Regenerate any time the CSV changes:  python3 scripts/make_map.py

Hand-edits to the REDEMPTIONS blob inside map.html are preserved on regenerate
(the block between the REDEMPTIONS markers is carried over if present).
"""

import csv
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "map.html")

PROMO_END = "2026-09-10"

DEFAULT_REDEMPTIONS = """{
  "maxPerCard": 10,
  "maxCreditPerCard": 100,
  "cards": {
    "Card 1": [],
    "Card 2": []
  }
}"""


def load():
    rows = list(csv.DictReader(open(os.path.join(ROOT, "data", "sf-candidates.csv"))))
    starred_urls = set()
    sp = os.path.join(ROOT, "data", "starred.json")
    if os.path.exists(sp):
        for urls in json.load(open(sp)).values():
            starred_urls.update(urls)

    out = []
    for r in rows:
        notes = r["notes"]
        if "clover-url-dead" in notes:
            status = "dead"
        elif "ordering-disabled" in notes:
            status = "disabled"
        else:
            status = "ok"
        warn = []
        if "outside-target-area" in notes or "storefront-city" in notes:
            warn.append("location unconfirmed")
        if "address-from-osm" in notes:
            warn.append("address approximate")
        if "paze-on-storefront=yes" in notes:
            paze = "yes"
        elif "paze-on-storefront=NO" in notes:
            paze = "no"
        else:
            paze = "unchecked"
        out.append({
            "n": r["name"],
            "a": r["address"],
            "h": r["neighborhood"],
            "y": float(r["lat"]),
            "x": float(r["lon"]),
            "u": r["clover_url"],
            "c": r["category"],
            "s": 1 if r["clover_url"] in starred_urls else 0,
            "st": status,
            "p": paze,
            "w": warn,
        })
    out.sort(key=lambda m: (-m["s"], m["n"].lower()))
    return out


def carry_over_redemptions():
    if not os.path.exists(OUT):
        return DEFAULT_REDEMPTIONS
    txt = open(OUT).read()
    m = re.search(r"/\* REDEMPTIONS-START \*/\s*(.*?)\s*/\* REDEMPTIONS-END \*/", txt, re.S)
    if not m:
        return DEFAULT_REDEMPTIONS
    body = m.group(1)
    body = re.sub(r"^const\s+REDEMPTIONS\s*=\s*", "", body).rstrip(";").strip()
    return body


HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#101216">
<title>Paze Map</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
      integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="">
<style>
  :root{
    --ink:#12141a; --muted:#6b7280; --line:#e6e8ee; --card:#fff; --bg:#f4f5f8;
    --star:#f0a500; --ok:#12b76a; --dead:#e5484d; --warn:#f79009; --accent:#2f6bff;
    --sb: env(safe-area-inset-bottom, 0px);
    --st: env(safe-area-inset-top, 0px);
    --sheet-peek: 132px;
  }
  @media (prefers-color-scheme: dark){
    :root{ --ink:#eceef4; --muted:#98a0b3; --line:#2a2e3a; --card:#181b22; --bg:#0e1014; }
  }
  *{box-sizing:border-box; -webkit-tap-highlight-color:transparent}
  html,body{margin:0;height:100%;overflow:hidden;overscroll-behavior:none}
  body{
    background:var(--bg); color:var(--ink);
    font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  }

  /* ---------- full-bleed map ---------- */
  #map{position:fixed;inset:0;z-index:0;background:var(--bg)}

  /* ---------- floating top bar ---------- */
  .top{
    position:fixed;z-index:500;left:10px;right:10px;top:calc(10px + var(--st));
    display:flex;gap:8px;align-items:center;pointer-events:none;
  }
  .chip{
    pointer-events:auto;background:var(--card);border:1px solid var(--line);
    border-radius:999px;padding:8px 13px;font-size:12.5px;font-weight:650;
    box-shadow:0 4px 18px rgba(10,15,30,.14);white-space:nowrap;
  }
  .chip .n{color:var(--ok)}
  .chip .d{color:var(--warn)}
  .grow{flex:1 1 auto}

  /* ---------- locate button ---------- */
  .locbtn{
    position:fixed;z-index:500;right:12px;
    bottom:calc(var(--sheet-peek) + 16px + var(--sb));
    width:46px;height:46px;border-radius:50%;
    background:var(--card);border:1px solid var(--line);color:var(--accent);
    box-shadow:0 5px 20px rgba(10,15,30,.20);
    display:grid;place-items:center;cursor:pointer;transition:bottom .28s cubic-bezier(.3,.9,.3,1);
  }
  .locbtn svg{width:21px;height:21px;display:block}
  .locbtn.up{bottom:calc(78vh + 12px)}
  .toast{
    position:fixed;z-index:600;left:50%;transform:translateX(-50%);
    bottom:calc(var(--sheet-peek) + 74px + var(--sb));
    background:#1b1e26;color:#fff;font-size:12.5px;font-weight:600;
    padding:8px 14px;border-radius:999px;opacity:0;transition:opacity .25s;pointer-events:none;
    box-shadow:0 6px 22px rgba(0,0,0,.3);
  }
  .toast.on{opacity:1}

  /* ---------- pull-up sheet ---------- */
  .sheet{
    position:fixed;z-index:550;left:0;right:0;bottom:0;
    height:78vh;background:var(--card);
    border-radius:18px 18px 0 0;
    box-shadow:0 -8px 34px rgba(10,15,30,.20);
    display:flex;flex-direction:column;
    transform:translateY(calc(78vh - var(--sheet-peek)));
    transition:transform .3s cubic-bezier(.3,.9,.3,1);
    touch-action:none;
  }
  .sheet.open{transform:translateY(0)}
  .sheet.drag{transition:none}
  .grab{padding:9px 0 5px;display:grid;place-items:center;cursor:grab;flex:0 0 auto}
  .grab i{display:block;width:38px;height:4.5px;border-radius:3px;background:var(--line)}
  .shead{padding:0 14px 9px;display:flex;gap:8px;align-items:center;flex:0 0 auto}
  .count{font-size:13px;font-weight:750;letter-spacing:.2px}
  .count em{color:var(--muted);font-style:normal;font-weight:500}
  .seg{margin-left:auto;display:flex;background:var(--bg);border:1px solid var(--line);
       border-radius:9px;overflow:hidden}
  .seg button{background:none;border:0;color:var(--muted);font:inherit;font-size:12.5px;
              font-weight:650;padding:7px 11px;cursor:pointer}
  .seg button[aria-pressed=true]{background:var(--accent);color:#fff}
  .srch{padding:0 14px 10px;flex:0 0 auto}
  .srch input{
    width:100%;background:var(--bg);border:1px solid var(--line);color:var(--ink);
    border-radius:10px;padding:10px 12px;font-size:15px;
  }
  .srch input::placeholder{color:var(--muted)}
  #list{flex:1 1 auto;overflow-y:auto;-webkit-overflow-scrolling:touch;
        padding-bottom:calc(16px + var(--sb));touch-action:pan-y}
  .item{display:flex;gap:11px;align-items:center;padding:11px 14px;
        border-top:1px solid var(--line);cursor:pointer}
  .item:active{background:var(--bg)}
  .dot{flex:0 0 auto;width:11px;height:11px;border-radius:50%;box-shadow:0 0 0 3px rgba(0,0,0,.05)}
  .body{flex:1 1 auto;min-width:0}
  .nm{font-weight:650;font-size:14.5px;display:flex;gap:5px;align-items:center}
  .nm .t{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .meta{color:var(--muted);font-size:12.5px;margin-top:1px;
        overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .dist{flex:0 0 auto;color:var(--accent);font-size:12.5px;font-weight:750;min-width:54px;text-align:right}
  .pill{font-size:9.5px;font-weight:800;padding:1.5px 5px;border-radius:5px;letter-spacing:.3px}
  .pill.dead{background:rgba(229,72,77,.13);color:var(--dead)}
  .pill.off{background:rgba(247,144,9,.14);color:var(--warn)}
  .empty{padding:30px 16px;text-align:center;color:var(--muted)}

  /* ---------- markers ---------- */
  .pin{position:relative;width:100%;height:100%}
  .pin b{
    position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);
    width:15px;height:15px;border-radius:50%;background:var(--accent);
    border:3px solid #fff;box-shadow:0 2px 7px rgba(10,15,30,.45);
  }
  .pin.s b{width:25px;height:25px;background:var(--star);border-width:3.5px;
           box-shadow:0 3px 11px rgba(180,120,0,.55)}
  .pin.s:after{
    content:"\\2605";position:absolute;left:50%;top:50%;
    transform:translate(-50%,-50%);color:#fff;font-size:13px;line-height:1;
    text-shadow:0 1px 1px rgba(0,0,0,.35);
  }
  .pin.off b{background:var(--warn)}
  .pin.dead b{background:var(--dead);opacity:.65}
  .pin.hi b{outline:3px solid var(--accent);outline-offset:3px}
  .me{width:100%;height:100%;border-radius:50%;background:var(--accent);
      border:3px solid #fff;box-shadow:0 0 0 6px rgba(47,107,255,.22),0 2px 8px rgba(0,0,0,.35)}

  .leaflet-popup-content-wrapper{background:var(--card);color:var(--ink);
    border-radius:13px;box-shadow:0 8px 30px rgba(10,15,30,.22)}
  .leaflet-popup-tip{background:var(--card)}
  .leaflet-popup-content{margin:12px 14px;font-size:14px}
  .pop h3{margin:0 0 3px;font-size:15px;line-height:1.25}
  .pop .pm{color:var(--muted);font-size:12.5px;margin-bottom:9px}
  .pop a{display:inline-block;background:var(--accent);color:#fff;font-weight:700;
         text-decoration:none;padding:8px 13px;border-radius:9px;font-size:13px}
  .pop a.off{background:var(--bg);color:var(--muted);pointer-events:none}
  .leaflet-control-attribution{font-size:9px;opacity:.6}
</style>
</head>
<body>

<div id="map"></div>

<div class="top">
  <div class="chip"><span class="n" id="credits"></span></div>
  <div class="chip"><span class="d" id="days"></span></div>
  <div class="grow"></div>
</div>

<button class="locbtn" id="loc" aria-label="Locate me">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
       stroke-linecap="round" stroke-linejoin="round">
    <circle cx="12" cy="12" r="3.2"></circle><path d="M12 2v3.2M12 18.8V22M2 12h3.2M18.8 12H22"></path>
    <circle cx="12" cy="12" r="8"></circle>
  </svg>
</button>
<div class="toast" id="toast"></div>

<div class="sheet" id="sheet">
  <div class="grab" id="grab"><i></i></div>
  <div class="shead">
    <div class="count" id="count"></div>
    <div class="seg">
      <button id="bAll"  aria-pressed="true">All</button>
      <button id="bStar" aria-pressed="false">&#9733;</button>
      <button id="bOpen" aria-pressed="false">Usable</button>
    </div>
  </div>
  <div class="srch"><input type="search" id="q" placeholder="Search name or area…" autocomplete="off"></div>
  <div id="list"></div>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
        integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<script>
/* ------------------------------------------------------------------
   HAND-EDIT THIS BLOCK. One entry per redemption you actually used.
   Counter = maxPerCard minus how many you have logged, per card.
   ------------------------------------------------------------------ */
/* REDEMPTIONS-START */
const REDEMPTIONS = __REDEMPTIONS__;
/* REDEMPTIONS-END */

/* Merchant data. Regenerate: python3 scripts/make_map.py
   n=name a=address h=area y=lat x=lon u=url c=category
   s=starred st=status(ok|disabled|dead) p=paze w=warnings */
const M = __MERCHANTS__;

const PROMO_END = "__PROMO_END__";
const SF = [37.7749, -122.4194];

/* ---------- header ---------- */
(function(){
  const end = new Date(PROMO_END + "T23:59:59");
  const days = Math.max(0, Math.ceil((end - new Date()) / 86400000));
  document.getElementById('days').textContent =
    days === 0 ? "promo ended" : days + "d left";
  const per = REDEMPTIONS.maxPerCard || 10, cards = REDEMPTIONS.cards || {};
  let used = 0, total = 0;
  for (const k in cards){ used += (cards[k]||[]).length; total += per; }
  document.getElementById('credits').textContent =
    Math.max(0, total - used) + "/" + total + " left";
})();

/* ---------- map ---------- */
const map = L.map('map', {zoomControl:false, attributionControl:true})
             .setView(SF, 12.5);

const light = L.tileLayer(
  'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
  {maxZoom:20, subdomains:'abcd', attribution:'&copy; OSM &copy; CARTO'});
const dark = L.tileLayer(
  'https://{s}.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}{r}.png',
  {maxZoom:20, subdomains:'abcd', attribution:'&copy; OSM &copy; CARTO'});

const mq = window.matchMedia('(prefers-color-scheme: dark)');
let base = (mq.matches ? dark : light).addTo(map);
mq.addEventListener('change', e => {
  map.removeLayer(base);
  base = (e.matches ? dark : light).addTo(map);
});

function cls(m){
  return 'pin' + (m.s ? ' s' : '') + (m.st==='dead' ? ' dead'
       : m.st==='disabled' ? ' off' : '');
}
function icon(m){
  const sz = m.s ? 32 : 21;
  return L.divIcon({className:'', html:'<div class="'+cls(m)+'"><b></b></div>',
                    iconSize:[sz,sz], iconAnchor:[sz/2,sz/2], popupAnchor:[0,-sz/2]});
}

const markers = M.map((m,i) => {
  m._i = i;
  const mk = L.marker([m.y,m.x], {icon:icon(m), zIndexOffset: m.s ? 1000 : 0});
  mk.bindPopup(() => popup(m), {maxWidth:265, closeButton:false});
  mk.addTo(map);
  return mk;
});

function popup(m){
  const d = here ? ' &middot; ' + fmt(dist(here,m)) : '';
  const bad = m.st === 'dead';
  return '<div class="pop"><h3>' + (m.s?'&#9733; ':'') + esc(m.n) + '</h3>'
    + '<div class="pm">' + esc(m.h) + d + (m.a ? '<br>' + esc(m.a) : '')
    + (bad ? '<br><b style="color:#e5484d">ordering page is gone</b>' : '')
    + (m.st==='disabled' ? '<br><b style="color:#f79009">online ordering switched off</b>' : '')
    + (m.w && m.w.length ? '<br>' + esc(m.w.join(' · ')) : '')
    + '</div><a class="' + (bad?'off':'') + '" href="' + esc(m.u)
    + '" target="_blank" rel="noopener">' + (bad?'unavailable':'Order &rarr;') + '</a></div>';
}

/* ---------- geolocation ---------- */
let here = null, meMk = null, meRing = null;
function toast(t){
  const el = document.getElementById('toast');
  el.textContent = t; el.classList.add('on');
  setTimeout(()=>el.classList.remove('on'), 3000);
}
function setHere(lat, lon, acc){
  here = [lat, lon];
  if (meMk){ map.removeLayer(meMk); map.removeLayer(meRing); }
  meRing = L.circle(here, {radius:Math.min(acc||60,400), color:'#2f6bff', weight:1,
                           fillColor:'#2f6bff', fillOpacity:.10}).addTo(map);
  meMk = L.marker(here, {icon:L.divIcon({className:'', html:'<div class="me"></div>',
        iconSize:[18,18], iconAnchor:[9,9]}), zIndexOffset:2000}).addTo(map);
  render();
}
function locate(pan){
  if (!isSecureContext) { toast('needs https for location'); return; }
  if (!navigator.geolocation){ toast('geolocation unavailable'); return; }
  navigator.geolocation.getCurrentPosition(
    p => { setHere(p.coords.latitude, p.coords.longitude, p.coords.accuracy);
           if (pan) map.setView(here, 15); },
    e => toast(e.code===1 ? 'location declined — showing SF' : 'location unavailable — showing SF'),
    {enableHighAccuracy:true, timeout:10000, maximumAge:60000});
}
document.getElementById('loc').addEventListener('click', ()=>locate(true));

/* ---------- helpers ---------- */
function dist(a,m){
  const R=6371,t=Math.PI/180, dLat=(m.y-a[0])*t, dLon=(m.x-a[1])*t;
  const s=Math.sin(dLat/2)**2+Math.cos(a[0]*t)*Math.cos(m.y*t)*Math.sin(dLon/2)**2;
  return 2*R*Math.asin(Math.sqrt(s));
}
function fmt(km){ const mi=km*0.621371;
  return mi<0.19 ? Math.round(mi*5280)+' ft' : mi.toFixed(mi<10?1:0)+' mi'; }
function esc(s){ return String(s==null?'':s).replace(/[&<>"']/g,
  c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

/* ---------- sheet ---------- */
const sheet = document.getElementById('sheet');
const grab  = document.getElementById('grab');
const locBtn= document.getElementById('loc');
let open=false;
function setOpen(v){
  open=v; sheet.classList.toggle('open',v); locBtn.classList.toggle('up',v);
}
grab.addEventListener('click', ()=>setOpen(!open));

let sy=0, sTrans=0, dragging=false;
function onDown(e){
  dragging=true; sy=(e.touches?e.touches[0].clientY:e.clientY);
  sTrans = sheet.getBoundingClientRect().top;
  sheet.classList.add('drag');
}
function onMove(e){
  if(!dragging) return;
  const y=(e.touches?e.touches[0].clientY:e.clientY);
  const h=sheet.offsetHeight, peek=132;
  let off = Math.min(Math.max(0, (sTrans - (window.innerHeight-h)) + (y-sy)), h-peek);
  sheet.style.transform='translateY('+off+'px)';
  e.preventDefault();
}
function onUp(){
  if(!dragging) return;
  dragging=false; sheet.classList.remove('drag'); sheet.style.transform='';
  const h=sheet.offsetHeight, top=sheet.getBoundingClientRect().top;
  setOpen(top < window.innerHeight - h*0.55);
}
grab.addEventListener('touchstart',onDown,{passive:true});
grab.addEventListener('touchmove',onMove,{passive:false});
grab.addEventListener('touchend',onUp);
grab.addEventListener('mousedown',onDown);
window.addEventListener('mousemove',onMove);
window.addEventListener('mouseup',onUp);

/* ---------- list ---------- */
let mode='all';
const listEl=document.getElementById('list'), qEl=document.getElementById('q');
const COLOR={dead:'var(--dead)',disabled:'var(--warn)'};

function render(){
  const q=qEl.value.trim().toLowerCase();
  let rows=M.filter(m=>{
    if(mode==='star'&&!m.s) return false;
    if(mode==='open'&&m.st!=='ok') return false;
    if(q && !(m.n.toLowerCase().includes(q)||(m.h||'').toLowerCase().includes(q)
             ||(m.a||'').toLowerCase().includes(q))) return false;
    return true;
  });
  const set=new Set(rows);
  if(here) rows.forEach(m=>m._d=dist(here,m));
  rows.sort((a,b)=> here ? a._d-b._d : (b.s-a.s)||a.n.localeCompare(b.n));

  markers.forEach((mk,i)=>{
    const on=set.has(M[i]);
    if(on && !map.hasLayer(mk)) mk.addTo(map);
    if(!on && map.hasLayer(mk)) map.removeLayer(mk);
  });

  document.getElementById('count').innerHTML =
    rows.length + ' place' + (rows.length===1?'':'s') +
    (here ? ' <em>&middot; nearest first</em>' : ' <em>&middot; pull up for list</em>');

  if(!rows.length){ listEl.innerHTML='<div class="empty">nothing matches</div>'; return; }
  listEl.innerHTML = rows.map(m=>{
    const pill = m.st==='dead' ? '<span class="pill dead">GONE</span>'
               : m.st==='disabled' ? '<span class="pill off">OFF</span>' : '';
    const col = COLOR[m.st] || (m.s ? 'var(--star)' : 'var(--accent)');
    return '<div class="item" data-i="'+m._i+'">'
      + '<span class="dot" style="background:'+col+'"></span>'
      + '<div class="body"><div class="nm"><span class="t">'
      + (m.s?'&#9733; ':'') + esc(m.n) + '</span>' + pill + '</div>'
      + '<div class="meta">' + esc(m.h) + (m.a?' &middot; '+esc(m.a):'') + '</div></div>'
      + '<div class="dist">' + (here?fmt(m._d):'') + '</div></div>';
  }).join('');
}

listEl.addEventListener('click', e=>{
  const it=e.target.closest('.item'); if(!it) return;
  const m=M[+it.dataset.i];
  setOpen(false);
  setTimeout(()=>{ map.setView([m.y,m.x], Math.max(map.getZoom(),16));
                   markers[m._i].openPopup(); }, 260);
});
qEl.addEventListener('input', render);
function seg(id,val){ document.getElementById(id).addEventListener('click',()=>{
  mode=val; ['bAll','bStar','bOpen'].forEach(b=>
    document.getElementById(b).setAttribute('aria-pressed',String(b===id)));
  render(); }); }
seg('bAll','all'); seg('bStar','star'); seg('bOpen','open');

render();
locate(false);
</script>
</body>
</html>
"""


def main():
    merchants = load()
    html = (HTML
            .replace("__MERCHANTS__", json.dumps(merchants, separators=(",", ":")))
            .replace("__REDEMPTIONS__", carry_over_redemptions())
            .replace("__PROMO_END__", PROMO_END))
    with open(OUT, "w") as fh:
        fh.write(html)
    stars = sum(1 for m in merchants if m["s"])
    dead = sum(1 for m in merchants if m["st"] == "dead")
    dis = sum(1 for m in merchants if m["st"] == "disabled")
    print("wrote %s  (%.0f KB)" % (OUT, os.path.getsize(OUT) / 1024))
    print("  merchants %d | starred %d | dead %d | ordering-off %d"
          % (len(merchants), stars, dead, dis))


if __name__ == "__main__":
    main()
