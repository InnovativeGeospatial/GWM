/* ============================================================================
   GWM Disaster Dashboard -- JSON feed edition
   Reads from: jsDelivr CDN. Pipeline purges jsDelivr after each run.
   No 100-event cap. Falls back to WP REST if JSON feed is unreachable.
   ============================================================================ */
(function () {
  "use strict";

  // -- Config --
  // Switched from jsDelivr to raw GitHub. Raw GitHub respects no-cache headers
  // and edge-propagates within ~5 min. jsDelivr was caching for hours.
  var JSON_FEED_URL = "https://raw.githubusercontent.com/InnovativeGeospatial/GWM/main/disasters.json";
  var WP_FALLBACK    = "https://globalwitnessmonitor.com/wp-json/wp/v2/posts?categories=38&per_page=100&_fields=id,title,excerpt,link,date,content&orderby=date&order=desc";
  var FLAG_BASE      = "https://flagcdn.com/24x18/";
  var SPREAD_KM      = 5;

  var TYPE_COLORS = {
    earthquake: "#92400e", flood: "#0ea5e9", storm: "#a855f7",
    wildfire: "#f97316", volcano: "#dc2626", tsunami: "#06b6d4",
    landslide: "#78716c", drought: "#d97706", heatwave: "#ef4444", disease: "#84cc16",
    other: "#6b7280"
  };

  // -- State --
  var allEvents = [];
  var activeFilter = "all";
  var dMap = null;
  var expandedKey = null;

  // -- Utilities --
  function $id(id) { return document.getElementById(id); }
  function escHtml(s) {
    if (s == null) return "";
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  function dCapFirst(s) {
    if (!s) return s;
    return s.charAt(0).toUpperCase() + s.slice(1);
  }
  function timeAgo(iso) {
    if (!iso) return "";
    var s = String(iso);
    if (!/[Zz]|[+-]\d{2}:?\d{2}$/.test(s)) s = s + "Z";
    var d = new Date(s);
    if (isNaN(d.getTime())) return "";
    var diff = Math.floor((Date.now() - d.getTime()) / 1000);
    if (diff < 0) diff = 0;
    if (diff < 60) return diff + "s ago";
    if (diff < 3600) return Math.floor(diff / 60) + "m ago";
    if (diff < 86400) return Math.floor(diff / 3600) + "h ago";
    return Math.floor(diff / 86400) + "d ago";
  }
  function typeKey(t) { return (t || "other").toString().toLowerCase(); }
  function colorForType(t) { return TYPE_COLORS[typeKey(t)] || TYPE_COLORS.other; }
  function countryKey(c) { return (c || "").toString().toLowerCase().trim(); }

  var COUNTRY_ISO2 = {
    "afghanistan":"af","albania":"al","algeria":"dz","andorra":"ad","angola":"ao",
    "argentina":"ar","armenia":"am","australia":"au","austria":"at","azerbaijan":"az",
    "bahamas":"bs","bahrain":"bh","bangladesh":"bd","barbados":"bb","belarus":"by",
    "belgium":"be","belize":"bz","benin":"bj","bhutan":"bt","bolivia":"bo",
    "bosnia":"ba","bosnia and herzegovina":"ba","botswana":"bw","brazil":"br",
    "brunei":"bn","bulgaria":"bg","burkina faso":"bf","burundi":"bi","cambodia":"kh",
    "cameroon":"cm","canada":"ca","cape verde":"cv","central african republic":"cf",
    "chad":"td","chile":"cl","china":"cn","colombia":"co","comoros":"km",
    "congo":"cd","democratic republic of congo":"cd","drc":"cd",
    "republic of congo":"cg","costa rica":"cr","croatia":"hr","cuba":"cu",
    "cyprus":"cy","czechia":"cz","czech republic":"cz","denmark":"dk",
    "djibouti":"dj","dominica":"dm","dominican republic":"do","ecuador":"ec",
    "egypt":"eg","el salvador":"sv","equatorial guinea":"gq","eritrea":"er",
    "estonia":"ee","eswatini":"sz","ethiopia":"et","fiji":"fj","finland":"fi",
    "france":"fr","gabon":"ga","gambia":"gm","georgia":"ge","germany":"de",
    "ghana":"gh","greece":"gr","guatemala":"gt","guinea":"gn","guinea-bissau":"gw",
    "guyana":"gy","haiti":"ht","honduras":"hn","hungary":"hu","iceland":"is",
    "india":"in","indonesia":"id","iran":"ir","iraq":"iq","ireland":"ie",
    "israel":"il","italy":"it","ivory coast":"ci","cote d'ivoire":"ci",
    "jamaica":"jm","japan":"jp","jordan":"jo","kazakhstan":"kz","kenya":"ke",
    "kiribati":"ki","kosovo":"xk","kuwait":"kw","kyrgyzstan":"kg","laos":"la",
    "latvia":"lv","lebanon":"lb","lesotho":"ls","liberia":"lr","libya":"ly",
    "lithuania":"lt","luxembourg":"lu","madagascar":"mg","malawi":"mw",
    "malaysia":"my","maldives":"mv","mali":"ml","malta":"mt","mauritania":"mr",
    "mauritius":"mu","mexico":"mx","moldova":"md","monaco":"mc","mongolia":"mn",
    "montenegro":"me","morocco":"ma","mozambique":"mz","myanmar":"mm","burma":"mm",
    "namibia":"na","nepal":"np","netherlands":"nl","new zealand":"nz",
    "nicaragua":"ni","niger":"ne","nigeria":"ng","north korea":"kp",
    "north macedonia":"mk","norway":"no","oman":"om","pakistan":"pk",
    "palestine":"ps","panama":"pa","papua new guinea":"pg","paraguay":"py",
    "peru":"pe","philippines":"ph","poland":"pl","portugal":"pt","qatar":"qa",
    "romania":"ro","russia":"ru","rwanda":"rw","samoa":"ws","saudi arabia":"sa",
    "senegal":"sn","serbia":"rs","sierra leone":"sl","singapore":"sg",
    "slovakia":"sk","slovenia":"si","solomon islands":"sb","somalia":"so",
    "south africa":"za","south korea":"kr","south sudan":"ss","spain":"es",
    "sri lanka":"lk","sudan":"sd","suriname":"sr","sweden":"se",
    "switzerland":"ch","syria":"sy","taiwan":"tw","tajikistan":"tj",
    "tanzania":"tz","thailand":"th","timor leste":"tl","timor-leste":"tl",
    "togo":"tg","tonga":"to","trinidad and tobago":"tt","tunisia":"tn",
    "turkey":"tr","turkmenistan":"tm","tuvalu":"tv","uganda":"ug","ukraine":"ua",
    "united arab emirates":"ae","uae":"ae","united kingdom":"gb","uk":"gb",
    "britain":"gb","united states":"us","usa":"us","u.s.":"us","us":"us",
    "uruguay":"uy","uzbekistan":"uz","vanuatu":"vu","vatican":"va","venezuela":"ve",
    "vietnam":"vn","yemen":"ye","zambia":"zm","zimbabwe":"zw"
  };

  function flagHTML(country) {
    var iso = COUNTRY_ISO2[countryKey(country)];
    if (!iso) return '<span class="d-country-flag">🌍</span>';
    return '<img class="d-country-flag" src="' + FLAG_BASE + iso + '.png" ' +
           'alt="" style="width:18px;height:13px;border-radius:2px;vertical-align:middle;">';
  }

  function fetchEvents() {
    return fetch(JSON_FEED_URL, { cache: 'no-store' })
      .then(function (r) {
        if (!r.ok) throw new Error("JSON feed HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        if (!data || !Array.isArray(data.events)) {
          throw new Error("JSON feed malformed");
        }
        console.log("[disaster-dash] loaded " + data.events.length +
                    " events from JSON feed (updated " + data.updated + ")");
        return data.events;
      })
      .catch(function (err) {
        console.warn("[disaster-dash] JSON feed failed, falling back to WP REST:", err);
        return fetch(WP_FALLBACK).then(function (r) { return r.json(); })
          .then(function (posts) {
            return posts.map(wpPostToEvent).filter(function (e) { return e; });
          });
      });
  }

  var META_RE = /data-country="([^"]*)"[^>]*data-type="([^"]*)"[^>]*data-lat="([^"]*)"[^>]*data-lng="([^"]*)"/;
  function wpPostToEvent(post) {
    var content = post.content ? post.content.rendered : "";
    var title = (post.title.rendered || "").replace(/(<([^>]+)>)/gi, "");
    var excerpt = post.excerpt ? post.excerpt.rendered.replace(/(<([^>]+)>)/gi, "") : "";
    var m = content.match(META_RE);
    var country = "", type = "other", lat = null, lng = null;
    if (m) {
      country = m[1];
      type = (m[2] || "other").toLowerCase();
      lat = m[3] ? parseFloat(m[3]) : null;
      lng = m[4] ? parseFloat(m[4]) : null;
    }
    if (!country) return null;
    return {
      wp_id: post.id, wp_link: post.link, date: post.date,
      title: title, body: excerpt, country: country, type: type,
      lat: lat, lng: lng, source_title: "", source_url: ""
    };
  }

  function filteredEvents() {
    if (activeFilter === "all") return allEvents.slice();
    return allEvents.filter(function (e) {
      return typeKey(e.type) === activeFilter;
    });
  }

  function renderStats(events) {
    var total = events.length;
    var counts = {
      earthquake:0, flood:0, storm:0, wildfire:0, volcano:0,
      tsunami:0, landslide:0, drought:0, heatwave:0, disease:0, other:0
    };
    events.forEach(function (e) {
      var k = typeKey(e.type);
      if (counts[k] != null) counts[k]++; else counts.other++;
    });

    var rows = [
      ["earthquake", "Earthquake"],
      ["flood",      "Flood"],
      ["storm",      "Storm / Cyclone"],
      ["wildfire",   "Wildfire"],
      ["volcano",    "Volcano"],
      ["tsunami",    "Tsunami"],
      ["landslide",  "Landslide"],
      ["drought",    "Drought"],
      ["heatwave",   "Heatwave"],
      ["disease",    "Disease Outbreak"],
      ["other",      "Other"]
    ];

    var html =
      '<div class="d-stat-total">' +
      '<div class="d-stat-total-num">' + total + '</div>' +
      '<div class="d-stat-total-label">Tracked Events</div>' +
      '</div>' +
      '<div class="d-stat-list">';

    rows.forEach(function (r) {
      var key = r[0], label = r[1], count = counts[key] || 0;
      html += '<div class="d-stat-row">' +
              '<span class="d-stat-dot" style="background:' + TYPE_COLORS[key] + '"></span>' +
              '<span class="d-stat-label">' + label + '</span>' +
              '<span class="d-stat-value">' + count + '</span>' +
              '</div>';
    });
    html += '</div>';
    var node = $id("d-stats");
    if (node) node.innerHTML = html;
  }

  function renderCountries(events) {
    var counts = {};
    events.forEach(function (e) {
      var c = e.country || "";
      if (!c) return;
      counts[c] = (counts[c] || 0) + 1;
    });
    var sorted = Object.keys(counts).sort(function (a, b) {
      return counts[b] - counts[a];
    });

    var node = $id("d-country-list");
    if (!node) return;
    if (!sorted.length) {
      node.innerHTML = '<div class="d-empty">No country data.</div>';
      return;
    }
    var html = sorted.map(function (c) {
      return '<button class="d-country-btn" data-country="' + escHtml(c) + '">' +
             flagHTML(c) +
             '<span class="d-country-name">' + escHtml(c) + '</span>' +
             '<span class="d-country-count">' + counts[c] + '</span>' +
             '</button>';
    }).join("");
    node.innerHTML = html;
  }

  function renderNews(events) {
    var node = $id("d-news");
    if (!node) return;
    if (!events.length) {
      node.innerHTML = '<div class="d-empty">No reports match current filter.</div>';
      return;
    }
    var html = events.slice(0, 1000).map(function (e) {
      var color = colorForType(e.type);
      var excerpt = (e.body || "").replace(/<[^>]+>/g, "")
                                  .replace(/\s+/g, " ").trim();
      if (excerpt.length > 180) excerpt = excerpt.substring(0, 180) + "…";
      return '<a class="d-news-item" href="' + escHtml(e.wp_link || "#") + '" target="_blank" rel="noopener">' +
             '<div class="d-news-bar" style="background:' + color + '"></div>' +
             '<div class="d-news-body">' +
             '<div class="d-news-meta">' +
             flagHTML(e.country) +
             '<span class="d-news-country">' + escHtml(e.country || "") + '</span>' +
             '<span class="d-news-time">' + escHtml(timeAgo(e.date)) + '</span>' +
             '</div>' +
             '<div class="d-news-title">' + escHtml(dCapFirst(e.title || "")) + '</div>' +
             (excerpt ? '<div class="d-news-excerpt">' + escHtml(excerpt) + '</div>' : '') +
             '</div></a>';
    }).join("");
    node.innerHTML = html;
  }

  function renderTicker(events) {
    var node = $id("d-ticker");
    if (!node) return;
    if (!events.length) {
      node.innerHTML = '<div class="d-ticker-track">No active events.</div>';
      return;
    }
    var items = events.slice(0, 30).map(function (e) {
      var color = colorForType(e.type);
      var typeLabel = dCapFirst(typeKey(e.type));
      var title = (e.title || "").substring(0, 90);
      return '<span class="d-ticker-item">' +
             '<span class="d-ticker-dot" style="background:' + color + '"></span>' +
             flagHTML(e.country) +
             '<span>' + escHtml(dCapFirst(title)) + '</span>' +
             '</span>';
    });
    var doubled = items.concat(items).join("");
    node.innerHTML = '<div class="d-ticker-track">' + doubled + '</div>';
    var SPEED_PX_PER_SEC = 60;
    requestAnimationFrame(function () {
      var track = node.querySelector(".d-ticker-track");
      if (!track) return;
      var distance = track.scrollWidth / 2;
      if (!distance || !isFinite(distance)) return;
      var duration = Math.max(30, Math.round(distance / SPEED_PX_PER_SEC));
      track.style.setProperty("animation-duration", duration + "s", "important");
    });
  }

  function initMap() {
    if (typeof maplibregl === "undefined") {
      console.error("[disaster-dash] MapLibre not loaded");
      return;
    }
    dMap = new maplibregl.Map({
      container: "d-map",
      style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
      center: [20, 15],
      zoom: 1.4,
      minZoom: 1,
      maxZoom: 8,
      attributionControl: false
    });
    dMap.addControl(new maplibregl.AttributionControl({
      customAttribution: '© <a href="https://carto.com" style="color:#555">CARTO</a>',
      compact: true
    }), "bottom-right");

    var s = document.createElement("style");
    s.innerHTML = '.maplibregl-ctrl-attrib{background:rgba(15,17,23,0.5)!important;color:#444!important;font-size:8px!important;}.maplibregl-ctrl-attrib a{color:#555!important;}.maplibregl-ctrl-attrib-button{display:none!important;}.maplibregl-ctrl-zoom-in,.maplibregl-ctrl-zoom-out,.maplibregl-ctrl-compass{background:#161a23!important;border-color:rgba(255,255,255,0.1)!important;}.maplibregl-ctrl-icon{filter:invert(0.7)!important;}.maplibregl-ctrl-group{background:#161a23!important;border:1px solid rgba(255,255,255,0.1)!important;}' +
      /* Force GWM popups (single + stacked menu) to render on a white card */
      '.gwm-popup .maplibregl-popup-content{background:#fff!important;color:#111!important;padding:0!important;border-radius:8px!important;box-shadow:0 6px 24px rgba(0,0,0,0.35)!important;overflow:hidden!important;}' +
      '.gwm-popup .maplibregl-popup-tip{border-top-color:#fff!important;border-bottom-color:#fff!important;}' +
      '.gwm-popup .maplibregl-popup-close-button{color:#111!important;font-size:18px!important;padding:2px 7px!important;}';
    document.head.appendChild(s);

    dMap.on("load", function () {
      dMap.addSource("incident-lines", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] }
      });
      dMap.addLayer({
        id: "incident-spider-legs", type: "line", source: "incident-lines",
        paint: { "line-color": "rgba(255,255,255,0.4)", "line-width": 1.5, "line-dasharray": [2, 2] }
      });
      dMap.addSource("incidents", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] }
      });
      dMap.addLayer({
        id: "incidents-glow", type: "circle", source: "incidents",
        paint: {
          "circle-radius": 14,
          "circle-color": ["get", "color"],
          "circle-opacity": 0.25,
          "circle-blur": 1
        }
      });
      dMap.addLayer({
        id: "incidents-dot", type: "circle", source: "incidents",
        paint: {
          "circle-radius": 7,
          "circle-color": ["get", "color"],
          "circle-opacity": 0.9,
          "circle-stroke-width": 1.5,
          "circle-stroke-color": "rgba(255,255,255,0.6)"
        }
      });

      dMap.on("click", "incidents-dot", onDotClick);
      dMap.on("click", function (e) {
        var dot = dMap.queryRenderedFeatures(e.point, { layers: ["incidents-dot"] });
        if (!dot.length && expandedKey) collapseAll();
      });
      dMap.on("mouseenter", "incidents-dot", function () {
        dMap.getCanvas().style.cursor = "pointer";
      });
      dMap.on("mouseleave", "incidents-dot", function () {
        dMap.getCanvas().style.cursor = "";
      });

      paintMap(filteredEvents());
    });
  }

  function eventsToFeatures(events) {
    return events.filter(function (e) {
      return typeof e.lat === "number" && typeof e.lng === "number";
    }).map(function (e) {
      return {
        type: "Feature",
        geometry: { type: "Point", coordinates: [e.lng, e.lat] },
        properties: {
          title: dCapFirst(e.title || ""),
          country: e.country || "",
          countryKey: countryKey(e.country),
          type: typeKey(e.type),
          color: colorForType(e.type),
          link: e.wp_link || "#",
          wp_id: e.wp_id
        }
      };
    });
  }

  function paintMap(events) {
    if (!dMap || !dMap.getSource) return;
    if (!dMap.getSource("incidents")) return;
    var features = eventsToFeatures(events);
    dMap.getSource("incidents").setData({
      type: "FeatureCollection", features: features
    });
    if (dMap.getSource("incident-lines")) {
      dMap.getSource("incident-lines").setData({
        type: "FeatureCollection", features: []
      });
    }
    expandedKey = null;
  }

  function distanceKm(lat1, lng1, lat2, lng2) {
    var R = 6371;
    var dLat = (lat2 - lat1) * Math.PI / 180;
    var dLng = (lng2 - lng1) * Math.PI / 180;
    var a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLng / 2) * Math.sin(dLng / 2);
    return 2 * R * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }

  function findStackedFeatures(centerFeature, allFeatures) {
    var centerLng = centerFeature.geometry.coordinates[0];
    var centerLat = centerFeature.geometry.coordinates[1];
    return allFeatures.filter(function (f) {
      var lng = f.geometry.coordinates[0];
      var lat = f.geometry.coordinates[1];
      return distanceKm(lat, lng, centerLat, centerLng) < SPREAD_KM;
    });
  }

  function spread(features, centerLng, centerLat) {
    if (features.length === 1) return features;
    var radiusDeg = 0.4;
    return features.map(function (f, i) {
      var angle = (2 * Math.PI * i / features.length) - Math.PI / 2;
      var newLng = centerLng + radiusDeg * Math.cos(angle);
      var newLat = centerLat + radiusDeg * Math.sin(angle);
      newLat = Math.max(-80, Math.min(80, newLat));
      return {
        type: "Feature",
        geometry: { type: "Point", coordinates: [newLng, newLat] },
        properties: f.properties
      };
    });
  }

  function expandStack(centerFeature) {
    var allFeatures = eventsToFeatures(filteredEvents());
    var stack = findStackedFeatures(centerFeature, allFeatures);
    if (stack.length < 2) return false;

    var centerLng = centerFeature.geometry.coordinates[0];
    var centerLat = centerFeature.geometry.coordinates[1];
    var spreadFeatures = spread(stack, centerLng, centerLat);
    var stackIds = {};
    stack.forEach(function (f) { stackIds[f.properties.wp_id] = true; });
    var others = allFeatures.filter(function (f) {
      return !stackIds[f.properties.wp_id];
    });

    var lines = spreadFeatures.map(function (f) {
      return {
        type: "Feature",
        geometry: {
          type: "LineString",
          coordinates: [[centerLng, centerLat], f.geometry.coordinates]
        }
      };
    });
    dMap.getSource("incident-lines").setData({
      type: "FeatureCollection", features: lines
    });
    dMap.getSource("incidents").setData({
      type: "FeatureCollection", features: others.concat(spreadFeatures)
    });
    expandedKey = "" + centerLng + "," + centerLat;
    return true;
  }

  function collapseAll() {
    if (!dMap.getSource("incidents")) return;
    dMap.getSource("incident-lines").setData({
      type: "FeatureCollection", features: []
    });
    dMap.getSource("incidents").setData({
      type: "FeatureCollection",
      features: eventsToFeatures(filteredEvents())
    });
    expandedKey = null;
  }

  function showPopup(coords, props) {
    new maplibregl.Popup({ closeButton: false, offset: 12, className: "gwm-popup" })
      .setLngLat(coords)
      .setHTML(
        '<div style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;min-width:220px;color:#111;background:#fff;border-radius:8px;padding:12px 14px;">' +
        '<div style="font-size:10px;text-transform:uppercase;letter-spacing:0.1em;color:#666;margin-bottom:5px;">' +
          escHtml(dCapFirst(props.type)) + ' · ' + escHtml(props.country) +
        '</div>' +
        '<div style="font-size:13px;font-weight:500;line-height:1.4;margin-bottom:8px;">' +
          escHtml(props.title) +
        '</div>' +
        '<a href="' + escHtml(props.link) + '" target="_blank" rel="noopener" ' +
        'style="font-size:11px;color:#0ea5e9;text-decoration:none;">Read full report →</a>' +
        '</div>'
      )
      .addTo(dMap);
  }

  function onDotClick(e) {
    e.originalEvent.stopPropagation();
    var feature = e.features[0];
    var coords = feature.geometry.coordinates.slice();
    var allF = eventsToFeatures(filteredEvents());
    var stack = findStackedFeatures(feature, allF);

    if (stack.length < 2) {
      showPopup(coords, feature.properties);
      return;
    }

    showStackList(coords, stack);
  }

  function showStackList(coords, stack) {
    var eventsByWpId = {};
    allEvents.forEach(function (ev) { eventsByWpId[ev.wp_id] = ev; });

    var items = stack.map(function (f) {
      var ev = eventsByWpId[f.properties.wp_id] || {};
      return {
        wp_id: f.properties.wp_id,
        title: f.properties.title,
        country: f.properties.country,
        type: f.properties.type,
        color: f.properties.color,
        link: f.properties.link,
        date: ev.date || ""
      };
    });
    items.sort(function (a, b) {
      return (b.date || "").localeCompare(a.date || "");
    });

    var country = items[0].country;
    var rows = items.map(function (it) {
      var d = it.date ? new Date(it.date) : null;
      var dateStr = d && !isNaN(d.getTime())
        ? d.toISOString().slice(0, 10)
        : "";
      var typeLabel = dCapFirst(it.type);
      return '<a href="' + escHtml(it.link) + '" target="_blank" rel="noopener" ' +
             'style="display:block;padding:8px 10px;border-bottom:1px solid #eee;text-decoration:none;color:#111;background:#fff;">' +
             '<div style="display:flex;align-items:center;gap:6px;margin-bottom:3px;">' +
             '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:' + it.color + ';"></span>' +
             '<span style="font-size:10px;color:#111;text-transform:uppercase;letter-spacing:0.08em;font-weight:600;">' +
             escHtml(dateStr) + (typeLabel ? ' \u00b7 ' + escHtml(typeLabel) : '') +
             '</span></div>' +
             '<div style="font-size:12px;line-height:1.35;font-weight:500;color:#111;">' +
             escHtml(it.title) +
             '</div></a>';
    }).join("");

    new maplibregl.Popup({ closeButton: true, offset: 12, maxWidth: "320px", className: "gwm-popup" })
      .setLngLat(coords)
      .setHTML(
        '<div style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;min-width:260px;max-height:340px;overflow-y:auto;color:#111;background:#fff;">' +
        '<div style="font-size:10px;text-transform:uppercase;letter-spacing:0.1em;color:#111;padding:8px 10px 6px;border-bottom:1px solid #ddd;font-weight:700;background:#fff;">' +
        items.length + ' events \u00b7 ' + escHtml(country) +
        '</div>' +
        rows +
        '</div>'
      )
      .addTo(dMap);
  }

  function setFilter(t) {
    activeFilter = t;
    var btns = document.querySelectorAll(".d-fbtn");
    for (var i = 0; i < btns.length; i++) {
      if (btns[i].getAttribute("data-type") === t) {
        btns[i].classList.add("active");
      } else {
        btns[i].classList.remove("active");
      }
    }
    var events = filteredEvents();
    renderStats(events);
    renderCountries(events);
    renderNews(events);
    renderTicker(events);
    paintMap(events);
  }

  function bindFilters() {
    var btns = document.querySelectorAll(".d-fbtn");
    for (var i = 0; i < btns.length; i++) {
      btns[i].addEventListener("click", function () {
        setFilter(this.getAttribute("data-type"));
      });
    }
  }

  function bindCountryList() {
    var node = $id("d-country-list");
    if (!node) return;
    node.addEventListener("click", function (e) {
      var btn = e.target.closest && e.target.closest(".d-country-btn");
      if (!btn) return;
      var c = countryKey(btn.getAttribute("data-country"));
      if (!c || !dMap) return;
      var matches = filteredEvents().filter(function (ev) {
        return countryKey(ev.country) === c &&
               typeof ev.lat === "number" && typeof ev.lng === "number";
      });
      if (!matches.length) return;
      var sumLat = 0, sumLng = 0;
      matches.forEach(function (m) { sumLat += m.lat; sumLng += m.lng; });
      var cLat = sumLat / matches.length;
      var cLng = sumLng / matches.length;
      dMap.flyTo({ center: [cLng, cLat], zoom: 4.5, speed: 1.4 });
    });
  }

  function startClock() {
    var node = $id("d-clock");
    if (!node) return;
    function tick() {
      var d = new Date();
      var hh = String(d.getUTCHours()).padStart(2, "0");
      var mm = String(d.getUTCMinutes()).padStart(2, "0");
      var ss = String(d.getUTCSeconds()).padStart(2, "0");
      node.textContent = hh + ":" + mm + ":" + ss + " UTC";
    }
    tick();
    setInterval(tick, 1000);
  }

  function boot() {
    startClock();
    bindFilters();
    bindCountryList();
    initMap();
    fetchEvents().then(function (events) {
      allEvents = events || [];
      var view = filteredEvents();
      renderStats(view);
      renderCountries(view);
      renderNews(view);
      renderTicker(view);
      if (dMap && dMap.loaded && dMap.loaded()) paintMap(view);
    }).catch(function (err) {
      console.error("[disaster-dash] fetch failed:", err);
      var s = $id("d-stats"); if (s) s.innerHTML = '<div class="d-empty">Failed to load events.</div>';
      var c = $id("d-country-list"); if (c) c.innerHTML = '<div class="d-empty">—</div>';
      var n = $id("d-news"); if (n) n.innerHTML = '<div class="d-empty">Unable to load reports.</div>';
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
