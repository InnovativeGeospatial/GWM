<!-- wp:html -->

<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=IBM+Plex+Sans:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet"/>
<link href="https://unpkg.com/maplibre-gl@5.24.0/dist/maplibre-gl.css" rel="stylesheet"/>
<script src="https://unpkg.com/maplibre-gl@5.24.0/dist/maplibre-gl.js"></script>

<style>
#conflict-wrap{--bg:#060709;--surface:#0f1117;--surface2:#141720;--border:rgba(255,255,255,0.08);--amber:#f59e0b;--amber-dim:#b45309;--amber-soft:rgba(245,158,11,0.1);--red:#ef4444;--orange:#fb923c;--yellow:#facc15;--green:#22c55e;--blue:#38bdf8;--purple:#a78bfa;--text:#fff;--text-dim:#d0d8e8;--text-muted:#6a7588;font-family:"IBM Plex Sans",sans-serif;background:var(--bg);color:var(--text);width:100%;overflow-x:hidden;}
#conflict-wrap *{box-sizing:border-box;margin:0;padding:0;}
#conflict-wrap .c-ticker{background:#0c0e14;border-top:1px solid rgba(245,158,11,0.25);border-bottom:1px solid rgba(245,158,11,0.25);padding:0 20px;height:32px;display:flex;align-items:center;gap:16px;overflow:hidden;}
#conflict-wrap .c-ticker-label{font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:0.14em;text-transform:uppercase;color:var(--amber);white-space:nowrap;flex-shrink:0;border-right:1px solid var(--amber-dim);padding-right:16px;}
#conflict-wrap .c-ticker-track{overflow:hidden;flex:1;}
#conflict-wrap .c-ticker-inner{display:flex;gap:60px;animation:c-scroll 45s linear infinite;white-space:nowrap;}
#conflict-wrap .c-ticker-item{font-family:"IBM Plex Mono",monospace;font-size:13px;color:#e4eaf0;letter-spacing:0.04em;}
#conflict-wrap .c-ticker-flag{color:var(--amber);margin-right:6px;}
#conflict-wrap .c-ticker-sev{margin-left:6px;padding:1px 5px;border-radius:2px;font-size:10px;font-weight:700;letter-spacing:0.06em;}
#conflict-wrap .sev-crit{background:rgba(239,68,68,0.2);color:#ef4444;border:1px solid rgba(239,68,68,0.4);}
#conflict-wrap .sev-high{background:rgba(251,146,60,0.2);color:#fb923c;border:1px solid rgba(251,146,60,0.4);}
@keyframes c-scroll{0%{transform:translateX(0);}100%{transform:translateX(-50%);}}
#conflict-wrap .c-main{display:grid;grid-template-columns:300px 1fr 320px;height:calc(100vh - 94px);overflow:hidden;background:var(--bg);}
#conflict-wrap .c-panel{background:var(--surface);border:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden;}
#conflict-wrap .c-panel-header{padding:12px 14px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;flex-shrink:0;}
#conflict-wrap .c-panel-title{font-family:"IBM Plex Mono",monospace;font-size:13px;letter-spacing:0.12em;text-transform:uppercase;color:var(--amber);display:flex;align-items:center;gap:8px;}
#conflict-wrap .c-panel-meta{font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--text-dim);letter-spacing:0.04em;}
#conflict-wrap .c-panel-body{flex:1;overflow-y:auto;overflow-x:hidden;}
#conflict-wrap .c-panel-body::-webkit-scrollbar{width:3px;}
#conflict-wrap .c-panel-body::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.1);border-radius:2px;}
#conflict-wrap .c-stats{padding:14px;border-bottom:1px solid var(--border);display:grid;grid-template-columns:1fr 1fr;gap:10px;}
#conflict-wrap .c-stat{background:var(--surface2);border:1px solid var(--border);border-radius:2px;padding:10px 12px;}
#conflict-wrap .c-stat-val{font-family:"Space Mono",monospace;font-size:28px;line-height:1;}
#conflict-wrap .c-stat-val.red{color:var(--red);}
#conflict-wrap .c-stat-val.orange{color:var(--orange);}
#conflict-wrap .c-stat-val.yellow{color:var(--yellow);}
#conflict-wrap .c-stat-val.green{color:var(--green);}
#conflict-wrap .c-stat-val.amber{color:var(--amber);}
#conflict-wrap .c-stat-val.blue{color:var(--blue);}
#conflict-wrap .c-stat-lbl{font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--text-dim);letter-spacing:0.08em;text-transform:uppercase;margin-top:4px;}
#conflict-wrap .c-row{display:flex;align-items:center;padding:10px 14px;border-bottom:1px solid rgba(255,255,255,0.04);gap:10px;cursor:pointer;text-decoration:none;color:inherit;}
#conflict-wrap .c-row:hover{background:var(--surface2);}
#conflict-wrap .c-rank{font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--text-muted);width:20px;flex-shrink:0;text-align:right;}
#conflict-wrap .c-flag{font-size:18px;width:24px;flex-shrink:0;}
#conflict-wrap .c-info{flex:1;min-width:0;}
#conflict-wrap .c-name{font-size:14px;font-weight:500;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
#conflict-wrap .c-type{font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--text-dim);margin-top:2px;}
#conflict-wrap .c-score{flex-shrink:0;display:flex;flex-direction:column;align-items:flex-end;gap:3px;}
#conflict-wrap .c-score-val{font-family:"Space Mono",monospace;font-size:16px;line-height:1;}
#conflict-wrap .c-score-val.crit{color:var(--red);}
#conflict-wrap .c-score-val.high{color:var(--orange);}
#conflict-wrap .c-score-val.med{color:var(--yellow);}
#conflict-wrap .c-score-val.low{color:var(--green);}
#conflict-wrap .c-bar-wrap{width:48px;height:2px;background:rgba(255,255,255,0.06);border-radius:1px;overflow:hidden;}
#conflict-wrap .c-bar{height:100%;border-radius:1px;}
#conflict-wrap .c-bar.crit{background:var(--red);}
#conflict-wrap .c-bar.high{background:var(--orange);}
#conflict-wrap .c-bar.med{background:var(--amber);}
#conflict-wrap .c-map-panel{position:relative;overflow:hidden;}
#conflict-wrap .c-map-panel .c-panel-header{position:absolute;top:0;left:0;right:0;z-index:10;background:linear-gradient(180deg,rgba(11,13,17,0.96) 0%,rgba(11,13,17,0.7) 100%);border-bottom-color:rgba(42,48,69,0.5);backdrop-filter:blur(4px);}
#conflict-wrap #c-map{position:absolute;inset:0;width:100%;height:100%;}
#conflict-wrap .c-legend{position:absolute;bottom:16px;left:14px;z-index:10;background:rgba(11,13,17,0.9);border:1px solid rgba(255,255,255,0.1);border-radius:4px;padding:12px 14px;backdrop-filter:blur(6px);}
#conflict-wrap .c-legend-title{font-family:"IBM Plex Mono",monospace;font-size:12px;letter-spacing:0.1em;text-transform:uppercase;color:var(--text-dim);margin-bottom:8px;}
#conflict-wrap .c-legend-item{display:flex;align-items:center;gap:8px;margin-bottom:5px;font-family:"IBM Plex Mono",monospace;font-size:13px;color:var(--text-dim);}
#conflict-wrap .c-legend-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0;}
#conflict-wrap .c-zoom{position:absolute;bottom:16px;right:14px;z-index:10;display:flex;flex-direction:column;gap:2px;}
#conflict-wrap .c-zoom-btn{width:30px;height:30px;background:rgba(11,13,17,0.9);border:1px solid rgba(255,255,255,0.1);border-radius:2px;color:var(--text-dim);font-size:18px;cursor:pointer;display:flex;align-items:center;justify-content:center;}
#conflict-wrap .c-zoom-btn:hover{border-color:var(--amber-dim);color:var(--amber);}
#conflict-wrap .c-news{padding:12px 14px;border-bottom:1px solid rgba(255,255,255,0.04);cursor:pointer;position:relative;text-decoration:none;display:block;color:inherit;}
#conflict-wrap .c-news:hover{background:var(--surface2);}
#conflict-wrap .c-news-meta{display:flex;align-items:center;gap:6px;margin-bottom:6px;}
#conflict-wrap .c-news-tag{font-family:"IBM Plex Mono",monospace;font-size:12px;padding:2px 7px;border-radius:2px;background:var(--surface2);border:1px solid var(--border);color:var(--text);letter-spacing:0.04em;}
#conflict-wrap .c-news-time{font-family:"IBM Plex Mono",monospace;font-size:12px;color:#9aa3b8;margin-left:auto;}
#conflict-wrap .c-news-title{font-size:14px;font-weight:500;color:#fff;line-height:1.4;margin-bottom:5px;}
#conflict-wrap .c-news-summary{font-size:13px;color:#a8b3c8;line-height:1.45;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}
#conflict-wrap .c-loading{padding:20px 14px;font-family:"IBM Plex Mono",monospace;font-size:13px;color:#9aa3b8;letter-spacing:0.06em;}
#conflict-wrap .c-footer{background:var(--surface);border-top:1px solid var(--border);padding:0 20px;height:30px;display:flex;align-items:center;justify-content:space-between;}
#conflict-wrap .c-footer-text{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--text-muted);letter-spacing:0.06em;}
#conflict-wrap .c-footer a{color:var(--text-muted);text-decoration:none;}
#conflict-wrap .c-footer a:hover{color:var(--amber);}

@media (max-width: 768px) {
  #conflict-wrap .c-main {
    grid-template-columns: 1fr;
    grid-template-rows: auto auto auto;
    height: auto;
    overflow: visible;
  }
  #conflict-wrap .c-panel {
    max-height: 460px;
  }
  #conflict-wrap .c-map-panel {
    max-height: none;
    height: 60vh;
    min-height: 320px;
  }
  #conflict-wrap #c-map {
    position: absolute;
    inset: 0;
  }
  #conflict-wrap .c-stats {
    grid-template-columns: 1fr 1fr;
  }
  #conflict-wrap .c-ticker {
    height: auto;
    min-height: 32px;
    flex-wrap: wrap;
    padding: 6px 14px;
  }
  #conflict-wrap .c-footer {
    height: auto;
    flex-direction: column;
    gap: 4px;
    padding: 8px 14px;
  }
}

</style>

<div id="conflict-wrap">

<div class="c-ticker">
  <div class="c-ticker-label">&#9650; ALERTS</div>
  <div class="c-ticker-track">
    <div class="c-ticker-inner" id="c-ticker-content">
      <span class="c-ticker-item">Loading alerts...</span>
    </div>
  </div>
</div>

<div class="c-main">

  <div class="c-panel">
    <div class="c-panel-header">
      <div class="c-panel-title">&#9658; U.S. State Department<br> Travel Advisories</div>
      
    </div>
    <div class="c-stats">
      <div class="c-stat"><div class="c-stat-val red" id="c-level4">--</div><div class="c-stat-lbl">Level 4</div></div>
      <div class="c-stat"><div class="c-stat-val orange" id="c-level3">--</div><div class="c-stat-lbl">Level 3</div></div>
      <div class="c-stat"><div class="c-stat-val yellow" id="c-level2">--</div><div class="c-stat-lbl">Level 2</div></div>
      <div class="c-stat"><div class="c-stat-val green" id="c-level1">--</div><div class="c-stat-lbl">Level 1</div></div>
    </div>
    <div class="c-panel-body" id="c-index"></div>
  </div>

  <div class="c-panel c-map-panel">
    <div class="c-panel-header">
      <div class="c-panel-title">&#9658; Global Conflict Map</div>
      <div class="c-panel-meta" id="c-map-count">LOADING...</div>
    </div>
    <div id="c-map"></div>
    <div class="c-legend">
      <div class="c-legend-title">Event Type</div>
      <div class="c-legend-item"><span class="c-legend-dot" style="background:#ef4444"></span>Armed Conflict</div>
      <div class="c-legend-item"><span class="c-legend-dot" style="background:#fb923c"></span>Civil Unrest</div>
      <div class="c-legend-item"><span class="c-legend-dot" style="background:#22c55e"></span>Coup / Crisis</div>
      <div class="c-legend-item"><span class="c-legend-dot" style="background:#a78bfa"></span>Displacement</div>
    </div>
    <div class="c-zoom">
      <button class="c-zoom-btn" id="c-zin">+</button>
      <button class="c-zoom-btn" id="c-zout">&#8722;</button>
    </div>
  </div>

  <div class="c-panel">
    <div class="c-panel-header">
      <div class="c-panel-title">&#9658; Incident Reports</div>
      <div class="c-panel-meta" id="c-news-count">FETCHING...</div>
    </div>
    <div class="c-panel-body" id="c-feed">
      <div class="c-loading">CONNECTING TO FEED...</div>
    </div>
  </div>

</div>

<div class="c-footer">
  <div class="c-footer-text">GWM CONFLICT v1.1 | <span id="c-clock">--:--:-- UTC</span></div>
  <div class="c-footer-text"><a href="/">globalwitnessmonitor.com</a></div>
</div>

</div>

<script src="https://cdn.jsdelivr.net/gh/InnovativeGeospatial/GWM@df6e1689db8683b8b61cc403a5ee656095769f83/conflict-dash.js"></script>


<!-- /wp:html -->
