var cMap = new maplibregl.Map({
  container: "c-map",
  style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
  center: [20, 15],
  zoom: 2.2,
  attributionControl: false
});

cMap.addControl(new maplibregl.AttributionControl({compact: true}), "bottom-right");

var cIndex = [
  {r:1,f:"\u{1F1F8}\u{1F1E9}",n:"Sudan",t:"Armed Conflict",s:97,g:"crit"},
  {r:2,f:"\u{1F1F2}\u{1F1F2}",n:"Myanmar",t:"Civil War",s:95,g:"crit"},
  {r:3,f:"\u{1F1ED}\u{1F1F9}",n:"Haiti",t:"Gang Violence",s:92,g:"crit"},
  {r:4,f:"\u{1F1FE}\u{1F1EA}",n:"Yemen",t:"Armed Conflict",s:91,g:"crit"},
  {r:5,f:"\u{1F1F8}\u{1F1F8}",n:"South Sudan",t:"Civil Conflict",s:89,g:"crit"},
  {r:6,f:"\u{1F1F8}\u{1F1F4}",n:"Somalia",t:"Armed Conflict",s:88,g:"crit"},
  {r:7,f:"\u{1F1E8}\u{1F1E9}",n:"DR Congo",t:"Armed Conflict",s:87,g:"crit"},
  {r:8,f:"\u{1F1F2}\u{1F1F1}",n:"Mali",t:"Insurgency",s:85,g:"crit"},
  {r:9,f:"\u{1F1F3}\u{1F1EE}",n:"Nicaragua",t:"Gov. Crackdown",s:84,g:"crit"},
  {r:10,f:"\u{1F1E6}\u{1F1EB}",n:"Afghanistan",t:"Insurgency",s:83,g:"crit"},
  {r:11,f:"\u{1F1F3}\u{1F1EC}",n:"Nigeria",t:"Armed Conflict",s:81,g:"high"},
  {r:12,f:"\u{1F1EA}\u{1F1F9}",n:"Ethiopia",t:"Civil Conflict",s:79,g:"high"},
  {r:13,f:"\u{1F1E8}\u{1F1EB}",n:"CAR",t:"Armed Conflict",s:78,g:"high"},
  {r:14,f:"\u{1F1F2}\u{1F1FF}",n:"Mozambique",t:"Insurgency",s:76,g:"high"},
  {r:15,f:"\u{1F1E7}\u{1F1EB}",n:"Burkina Faso",t:"Insurgency",s:74,g:"high"},
  {r:16,f:"\u{1F1EE}\u{1F1F6}",n:"Iraq",t:"Political Unrest",s:70,g:"high"},
  {r:17,f:"\u{1F1F1}\u{1F1FE}",n:"Libya",t:"Political Crisis",s:68,g:"high"},
  {r:18,f:"\u{1F1F5}\u{1F1F0}",n:"Pakistan",t:"Border Conflict",s:66,g:"high"},
  {r:19,f:"\u{1F1F0}\u{1F1F5}",n:"N. Korea",t:"Regime Risk",s:65,g:"high"},
  {r:20,f:"\u{1F1E7}\u{1F1E9}",n:"Bangladesh",t:"Civil Unrest",s:63,g:"high"},
  {r:21,f:"\u{1F1FB}\u{1F1EA}",n:"Venezuela",t:"Political Crisis",s:60,g:"med"},
  {r:22,f:"\u{1F1F7}\u{1F1FA}",n:"Russia",t:"Armed Conflict",s:58,g:"med"},
  {r:23,f:"\u{1F1F5}\u{1F1F8}",n:"Palestine",t:"Armed Conflict",s:57,g:"med"},
  {r:24,f:"\u{1F1FF}\u{1F1FC}",n:"Zimbabwe",t:"Political Unrest",s:54,g:"med"},
  {r:25,f:"\u{1F1F2}\u{1F1FD}",n:"Mexico",t:"Cartel Violence",s:52,g:"med"}
];

var cEvents = [
  {lat:15.5,lng:32.5,type:"armed",label:"Sudan - RSF-SAF clashes"},
  {lat:19.7,lng:96.1,type:"armed",label:"Myanmar - Junta airstrikes"},
  {lat:18.5,lng:-72.3,type:"unrest",label:"Haiti - Gang activity"},
  {lat:15.3,lng:44.1,type:"armed",label:"Yemen - Houthi operations"},
  {lat:6.8,lng:31.3,type:"armed",label:"South Sudan - Violence"},
  {lat:2.0,lng:45.3,type:"armed",label:"Somalia - Al-Shabaab"},
  {lat:-4.3,lng:15.3,type:"armed",label:"DR Congo - M23 advances"},
  {lat:10.5,lng:13.2,type:"armed",label:"Nigeria - Borno attack"},
  {lat:10.0,lng:38.7,type:"armed",label:"Ethiopia - Amhara clashes"},
  {lat:17.5,lng:-4.0,type:"armed",label:"Mali - Tuareg insurgency"},
  {lat:34.5,lng:69.2,type:"unrest",label:"Afghanistan - Crisis"},
  {lat:30.1,lng:67.0,type:"unrest",label:"Pakistan - Unrest"},
  {lat:10.5,lng:-66.9,type:"coup",label:"Venezuela - Crackdown"},
  {lat:23.7,lng:90.4,type:"unrest",label:"Bangladesh - Unrest"},
  {lat:-17.2,lng:35.5,type:"armed",label:"Mozambique - Insurgency"},
  {lat:12.1,lng:-86.3,type:"coup",label:"Nicaragua - Crackdown"}
];

var cTypeColors = {armed:"#ef4444",unrest:"#fb923c",coup:"#f59e0b",displacement:"#a78bfa"};

var indexEl = document.getElementById("c-index");
if (indexEl) {
  var indexHtml = "";
  for (var i = 0; i < cIndex.length; i++) {
    var c = cIndex[i];
    indexHtml += "<div class='c-row'><div class='c-rank'>" + c.r + "</div><div class='c-flag'>" + c.f + "</div><div class='c-info'><div class='c-name'>" + c.n + "</div><div class='c-type'>" + c.t + "</div></div><div class='c-score'><div class='c-score-val " + c.g + "'>" + c.s + "</div><div class='c-bar-wrap'><div class='c-bar " + c.g + "' style='width:" + c.s + "%'></div></div></div></div>";
  }
  indexEl.innerHTML = indexHtml;
}

cMap.on("load", function() {
  var features = [];
  for (var j = 0; j < cEvents.length; j++) {
    var ev = cEvents[j];
    features.push({
      type: "Feature",
      geometry: {type: "Point", coordinates: [ev.lng, ev.lat]},
      properties: {label: ev.label, color: cTypeColors[ev.type] || "#ef4444"}
    });
  }
  cMap.addSource("cpts", {type: "geojson", data: {type: "FeatureCollection", features: features}});
  cMap.addLayer({id: "cglow", type: "circle", source: "cpts", paint: {"circle-radius": 18, "circle-color": ["get", "color"], "circle-opacity": 0.15, "circle-blur": 1}});
  cMap.addLayer({id: "cdots", type: "circle", source: "cpts", paint: {"circle-radius": 7, "circle-color": ["get", "color"], "circle-opacity": 0.9, "circle-stroke-width": 1, "circle-stroke-color": "rgba(255,255,255,0.3)"}});
  cMap.on("click", "cdots", function(e) {
    var p = e.features[0].properties;
    var coords = e.features[0].geometry.coordinates.slice();
    new maplibregl.Popup({closeButton: false, offset: 10})
      .setLngLat(coords)
      .setHTML("<div style='font-family:IBM Plex Mono,monospace;font-size:12px;color:#333;padding:4px;'>" + p.label + "</div>")
      .addTo(cMap);
  });
  cMap.on("mouseenter", "cdots", function() { cMap.getCanvas().style.cursor = "pointer"; });
  cMap.on("mouseleave", "cdots", function() { cMap.getCanvas().style.cursor = ""; });
  document.getElementById("c-map-count").textContent = cEvents.length + " EVENTS";
  setTimeout(function() { cMap.resize(); }, 200);
});

var zinBtn = document.getElementById("c-zin");
var zoutBtn = document.getElementById("c-zout");
if (zinBtn) zinBtn.onclick = function() { cMap.zoomIn(); };
if (zoutBtn) zoutBtn.onclick = function() { cMap.zoomOut(); };

fetch("https://globalwitnessmonitor.com/wp-json/wp/v2/posts?categories=8&per_page=20&orderby=date&order=desc&_embed=1")
  .then(function(r) { return r.json(); })
  .then(function(posts) {
    var feed = document.getElementById("c-feed");
    var countEl = document.getElementById("c-news-count");
    var liveEl = document.getElementById("c-live-count");
    if (!feed) return;
    if (!posts || !posts.length) {
      feed.innerHTML = "<div class='c-loading'>NO REPORTS FOUND</div>";
      return;
    }
    if (countEl) countEl.textContent = posts.length + " REPORTS";
    if (liveEl) liveEl.textContent = posts.length;
    var html = "";
    for (var k = 0; k < posts.length; k++) {
      var p = posts[k];
      var title = p.title.rendered.replace(/<[^>]+>/g, "");
      var excerpt = p.excerpt.rendered.replace(/<[^>]+>/g, "").substring(0, 100);
      var link = p.link || "#";
      var tag = "Global";
      if (p._embedded && p._embedded["wp:term"]) {
        for (var m = 0; m < p._embedded["wp:term"].length; m++) {
          for (var n = 0; n < p._embedded["wp:term"][m].length; n++) {
            var term = p._embedded["wp:term"][m][n];
            if (term.taxonomy === "post_tag" && term.name.length < 25) {
              tag = term.name;
              break;
            }
          }
        }
      }
      var diff = Math.floor((new Date() - new Date(p.date)) / 60000);
      var ago = diff < 60 ? diff + "m" : diff < 1440 ? Math.floor(diff/60) + "h" : Math.floor(diff/1440) + "d";
      html += "<a class='c-news' href='" + link + "' target='_blank'><div class='c-news-meta'><span class='c-news-tag'>" + tag + "</span><span class='c-news-time'>" + ago + " ago</span></div><div class='c-news-title'>" + title + "</div><div class='c-news-summary'>" + excerpt + "</div></a>";
    }
    feed.innerHTML = html;
  })
  .catch(function(err) {
    var feed = document.getElementById("c-feed");
    if (feed) feed.innerHTML = "<div class='c-loading'>FEED ERROR</div>";
  });

setInterval(function() {
  var d = new Date();
  var h = d.getUTCHours();
  var m = d.getUTCMinutes();
  var s = d.getUTCSeconds();
  var clockEl = document.getElementById("c-clock");
  if (clockEl) clockEl.textContent = (h<10?"0":"") + h + ":" + (m<10?"0":"") + m + ":" + (s<10?"0":"") + s + " UTC";
}, 1000);

var filterBtns = document.querySelectorAll(".c-fbtn");
filterBtns.forEach(function(btn) {
  btn.addEventListener("click", function() {
    filterBtns.forEach(function(b) { b.classList.remove("active"); });
    this.classList.add("active");
  });
});
