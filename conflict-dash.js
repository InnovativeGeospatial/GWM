/* =====================================================================
 * GWM Conflict & Unrest Dashboard -- JSON feed edition
 * Reads from: jsDelivr CDN. Pipeline purges jsDelivr after each run.
 * No ?nocache query string -- jsDelivr /gh/ URLs reject query strings.
 * No 100-event cap. Falls back to WP REST if JSON feed unreachable.
 * ===================================================================== */
(function () {
  "use strict";

  // -- Config --
  // Feeds served from jsDelivr. The pipeline purges jsDelivr after each
  // run so the CDN serves fresh data within minutes. Do NOT append a
  // query string to jsDelivr /gh/ URLs -- it causes a 404.
  var JSON_FEED_URL = "https://raw.githubusercontent.com/InnovativeGeospatial/GWM/main/conflict.json";
  var WP_FALLBACK   = "https://globalwitnessmonitor.com/wp-json/wp/v2/posts?categories=8&per_page=100&_fields=id,title,excerpt,link,date,content&orderby=date&order=desc";
  var ADVISORY_URL  = "https://cdn.jsdelivr.net/gh/InnovativeGeospatial/GWM@main/travel_advisories.json";
  var FLAG_BASE     = "https://flagcdn.com/24x18/";
  var SPREAD_KM     = 5;

  var TYPE_COLORS = {
    "armed conflict": "#ef4444",
    "civil unrest":   "#fb923c",
    "coup or crisis": "#22c55e",
    "displacement":   "#a78bfa",
    "other":          "#94a3b8"
  };

  var TYPE_KEY_MAP = {
    "armed":         "armed conflict",
    "armed conflict":"armed conflict",
    "unrest":        "civil unrest",
    "civil unrest":  "civil unrest",
    "coup":          "coup or crisis",
    "coup or crisis":"coup or crisis",
    "displacement":  "displacement",
    "other":         "other",
    "all":           "all"
  };

  var allEvents = [];
  var activeFilter = "all";
  var cMap = null;
  var expandedKey = null;

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
    if (diff < 60) return "now";
    if (diff < 3600) return Math.floor(diff / 60) + "m";
    if (diff < 86400) return Math.floor(diff / 3600) + "h";
    return Math.floor(diff / 86400) + "d";
  }
  function typeKey(t) {
    var k = (t || "other").toString().toLowerCase().trim();
    return TYPE_KEY_MAP[k] || k;
  }
  function colorForType(t) {
    return TYPE_COLORS[typeKey(t)] || TYPE_COLORS.other;
  }
  function countryKey(c) {
    return (c || "").toString().toLowerCase().trim()
      .replace(/\s*\([^)]*\)\s*/g, "").trim();
  }
  function displayTypeLabel(t) {
    var k = typeKey(t);
    if (k === "other") return "";
    if (k === "coup or crisis") return "Coup/Crisis";
    return k.replace(/\b\w/g, function(c) { return c.toUpperCase(); });
  }

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
    if (!iso) return '<span class="c-country-flag">\uD83C\uDF0D</span>';
    return '<img class="c-country-flag" src="' + FLAG_BASE + iso + '.png" ' +
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
        console.log("[conflict-dash] loaded " + data.events.length +
                    " events from JSON feed (updated " + data.updated + ")");
        return data.events;
      })
      .catch(function (err) {
        console.warn("[conflict-dash] JSON feed failed, falling back to WP REST:", err);
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
    var country = "", etype = "Other", lat = null, lng = null;
    if (m) {
      country = m[1];
      etype = m[2] || "Other";
      lat = m[3] ? parseFloat(m[3]) : null;
      lng = m[4] ? parseFloat(m[4]) : null;
    }
    if (!country) return null;
    return {
      wp_id: post.id, wp_link: post.link, date: post.date,
      title: title, body: excerpt, country: country, type: etype,
      lat: lat, lng: lng, source_title: "", source_url: ""
    };
  }

  function filteredEvents() {
    if (activeFilter === "all") return allEvents.slice();
    return allEvents.filter(function (e) { return typeKey(e.type) === activeFilter; });
  }

  function loadAdvisories() {
    fetch(ADVISORY_URL, { cache: 'no-store' })
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(function (payload) {
        renderAdvisories(payload.advisories || []);
      })
      .catch(function (err) {
        console.error("[conflict-dash] Travel advisory fetch failed:", err);
        var indexEl = $id("c-index");
        if (indexEl) indexEl.innerHTML = "<div class='c-loading'>Advisory data unavailable</div>";
      });
  }
  function renderAdvisories(advisories) {
    var levelText  = {1:"Normal Precautions", 2:"Increased Caution", 3:"Reconsider Travel", 4:"Do Not Travel"};
    var levelGrade = {1:"low", 2:"med", 3:"high", 4:"crit"};
    var counts = {1:0, 2:0, 3:0, 4:0};
    var rows = advisories.map(function (a) {
      counts[a.level] = (counts[a.level] || 0) + 1;
      return {n: a.country, l: a.level, t: levelText[a.level] || "", g: levelGrade[a.level] || "low"};
    });
    rows.sort(function (a, b) {
      if (b.l !== a.l) return b.l - a.l;
      return a.n.localeCompare(b.n);
    });
    var indexEl = $id("c-index");
    if (indexEl) {
      var html = "";
      for (var i = 0; i < rows.length; i++) {
        var c = rows[i];
        html += "<div class='c-row'><div class='c-rank'>" + (i + 1) + "</div>" +
                "<div class='c-flag'>" + flagHTML(c.n) + "</div>" +
                "<div class='c-info'><div class='c-name'>" + escHtml(c.n) + "</div>" +
                "<div class='c-type'>Level " + c.l + ": " + c.t + "</div></div>" +
                "<div class='c-score'><div class='c-score-val " + c.g + "'>" + c.l + "</div></div></div>";
      }
      indexEl.innerHTML = html;
    }
    var l4 = $id("c-level4"), l3 = $id("c-level3"), l2 = $id("c-level2"), l1 = $id("c-level1");
    if (l4) l4.textContent = counts[4];
    if (l3) l3.textContent = counts[3];
    if (l2) l2.textContent = counts[2];
    if (l1) l1.textContent = counts[1];
  }

  function renderNews(events) {
    var feed = $id("c-feed");
    var countEl = $id("c-news-count");
    var liveEl = $id("c-live-count");
    if (!feed) return;
    if (!events.length) {
      feed.innerHTML = "<div class='c-loading'>No reports match current filter</div>";
      if (countEl) countEl.textContent = "0 REPORTS";
      if (liveEl) liveEl.textContent = "0";
      return;
    }
    if (countEl) countEl.textContent = events.length + " REPORTS";
    if (liveEl) liveEl.textContent = events.length;

    var html = events.slice(0, 300).map(function (e) {
      var color = colorForType(e.type);
      var excerpt = (e.body || "").replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim();
      if (excerpt.length > 140) excerpt = excerpt.substring(0, 140) + "\u2026";
      var ago = timeAgo(e.date);

      return "<a class='c-news' href='" + escHtml(e.wp_link || "#") + "' target='_blank' rel='noopener' style='display:flex;text-decoration:none;color:inherit;'>" +
             "<div style='width:3px;flex-shrink:0;background:" + color + ";'></div>" +
             "<div style='flex:1;min-width:0;padding:10px 14px;'>" +
             "<div class='c-news-meta'>" +
             flagHTML(e.country) +
             "<span class='c-news-country'>" + escHtml(e.country || "") + "</span>" +
             "<span class='c-news-time'>" + escHtml(ago) + "</span>" +
             "</div>" +
             "<div class='c-news-title'>" + escHtml(e.title || "") + "</div>" +
             (excerpt ? "<div class='c-news-summary'>" + escHtml(excerpt) + "</div>" : "") +
             "</div></a>";

    }).join("");
    feed.innerHTML = html;
  }

  function renderTicker(events) {
    var node = $id("c-ticker-content");
    if (!node) return;
    if (!events.length) {
      node.innerHTML = "<span class='c-ticker-item'>No active events</span>";
      return;
    }
    var items = events.slice(0, 30).map(function (e) {
      var title = (e.title || "").substring(0, 90);
      return "<span class='c-ticker-item'>" +
             flagHTML(e.country) +
             "<span>" + escHtml(e.country || "") + "</span>" +
             "<span class='c-ticker-sep'>\u00b7</span>" +
             "<span>" + escHtml(title) + "</span>" +
             "</span>";
    });

    var MIN_ITEMS_FOR_SCROLL = 5;
    var SPEED_PX_PER_SEC = 250;

    if (items.length < MIN_ITEMS_FOR_SCROLL) {
      node.innerHTML = items.join("<span class='c-ticker-sep'>\u00b7</span>");
      node.style.setProperty("animation", "none", "important");
      node.style.setProperty("transform", "none", "important");
      var parent = node.parentElement;
      if (parent) {
        parent.style.setProperty("animation", "none", "important");
      }
      return;
    }

    var doubled = items.concat(items).join("");
    node.innerHTML = doubled;
    requestAnimationFrame(function () {
      var distance = node.scrollWidth / 2;
      if (!distance || !isFinite(distance)) return;
      var duration = Math.round(distance / SPEED_PX_PER_SEC);
      node.style.setProperty("animation-duration", duration + "s", "important");
      var parent = node.parentElement;
      if (parent) {
        parent.style.setProperty("animation-duration", duration + "s", "important");
      }
    });
  }

  function initMap() {
    if (typeof maplibregl === "undefined") {
      console.error("[conflict-dash] MapLibre not loaded");
      return;
    }
    cMap = new maplibregl.Map({
      container: "c-map",
      style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
      center: [20, 15],
      zoom: 2.2,
      minZoom: 1,
      maxZoom: 8,
      attributionControl: false
    });
    cMap.addControl(new maplibregl.AttributionControl({
      customAttribution: '\u00a9 <a href="https://carto.com" style="color:#555">CARTO</a>',
      compact: true
    }), "bottom-right");

    var s = document.createElement("style");
    s.innerHTML = '.maplibregl-ctrl-attrib{background:rgba(15,17,23,0.5)!important;color:#444!important;font-size:8px!important;}.maplibregl-ctrl-attrib a{color:#555!important;}.maplibregl-ctrl-attrib-button{display:none!important;}.maplibregl-ctrl-zoom-in,.maplibregl-ctrl-zoom-out,.maplibregl-ctrl-compass{background:#161a23!important;border-color:rgba(255,255,255,0.1)!important;}.maplibregl-ctrl-icon{filter:invert(0.7)!important;}.maplibregl-ctrl-group{background:#161a23!important;border:1px solid rgba(255,255,255,0.1)!important;}';
    document.head.appendChild(s);

    cMap.on("load", function () {
      cMap.addSource("c-lines", { type:"geojson", data:{type:"FeatureCollection", features:[]} });
      cMap.addLayer({ id:"c-spider-legs", type:"line", source:"c-lines",
        paint:{"line-color":"rgba(255,255,255,0.4)","line-width":1.5,"line-dasharray":[2,2]} });
      cMap.addSource("cpts", { type:"geojson", data:{type:"FeatureCollection", features:[]} });
      cMap.addLayer({ id:"cglow", type:"circle", source:"cpts",
        paint:{"circle-radius":14,"circle-color":["get","color"],"circle-opacity":0.25,"circle-blur":1} });
      cMap.addLayer({ id:"cdots", type:"circle", source:"cpts",
        paint:{"circle-radius":7,"circle-color":["get","color"],"circle-opacity":0.9,
               "circle-stroke-width":1.5,"circle-stroke-color":"rgba(255,255,255,0.6)"} });

      cMap.on("click", "cdots", onDotClick);
      cMap.on("click", function (e) {
        var dot = cMap.queryRenderedFeatures(e.point, { layers:["cdots"] });
        if (!dot.length && expandedKey) collapseAll();
      });
      cMap.on("mouseenter", "cdots", function () { cMap.getCanvas().style.cursor = "pointer"; });
      cMap.on("mouseleave", "cdots", function () { cMap.getCanvas().style.cursor = ""; });

      paintMap(filteredEvents());
    });

    var zin = $id("c-zin"), zout = $id("c-zout");
    if (zin) zin.onclick = function () { cMap.zoomIn(); };
    if (zout) zout.onclick = function () { cMap.zoomOut(); };
  }

  function eventsToFeatures(events) {
    return events.filter(function (e) {
      return typeof e.lat === "number" && typeof e.lng === "number";
    }).map(function (e) {
      return {
        type: "Feature",
        geometry: { type: "Point", coordinates: [e.lng, e.lat] },
        properties: {
          title: e.title || "",
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
    if (!cMap || !cMap.getSource) return;
    if (!cMap.getSource("cpts")) return;
    var features = eventsToFeatures(events);
    cMap.getSource("cpts").setData({ type:"FeatureCollection", features:features });
    if (cMap.getSource("c-lines")) {
      cMap.getSource("c-lines").setData({ type:"FeatureCollection", features:[] });
    }
    expandedKey = null;
    var mapCountEl = $id("c-map-count");
    if (mapCountEl) mapCountEl.textContent = features.length + " EVENTS";
  }

  function distanceKm(lat1, lng1, lat2, lng2) {
    var R = 6371;
    var dLat = (lat2 - lat1) * Math.PI / 180;
    var dLng = (lng2 - lng1) * Math.PI / 180;
    var a = Math.sin(dLat/2)*Math.sin(dLat/2) +
            Math.cos(lat1*Math.PI/180)*Math.cos(lat2*Math.PI/180) *
            Math.sin(dLng/2)*Math.sin(dLng/2);
    return 2 * R * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  }

  function findStackedFeatures(centerFeature, allFeatures) {
    var cLng = centerFeature.geometry.coordinates[0];
    var cLat = centerFeature.geometry.coordinates[1];
    return allFeatures.filter(function (f) {
      var lng = f.geometry.coordinates[0];
      var lat = f.geometry.coordinates[1];
      return distanceKm(lat, lng, cLat, cLng) < SPREAD_KM;
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
    var allF = eventsToFeatures(filteredEvents());
    var stack = findStackedFeatures(centerFeature, allF);
    if (stack.length < 2) return false;

    var cLng = centerFeature.geometry.coordinates[0];
    var cLat = centerFeature.geometry.coordinates[1];
    var spreadFeatures = spread(stack, cLng, cLat);
    var stackIds = {};
    stack.forEach(function (f) { stackIds[f.properties.wp_id] = true; });
    var others = allF.filter(function (f) { return !stackIds[f.properties.wp_id]; });

    var lines = spreadFeatures.map(function (f) {
      return {
        type: "Feature",
        geometry: { type: "LineString",
                    coordinates: [[cLng, cLat], f.geometry.coordinates] }
      };
    });
    cMap.getSource("c-lines").setData({ type:"FeatureCollection", features:lines });
    cMap.getSource("cpts").setData({
      type:"FeatureCollection", features: others.concat(spreadFeatures)
    });
    expandedKey = "" + cLng + "," + cLat;
    return true;
  }

  function collapseAll() {
    if (!cMap.getSource("cpts")) return;
    cMap.getSource("c-lines").setData({ type:"FeatureCollection", features:[] });
    cMap.getSource("cpts").setData({
      type:"FeatureCollection", features: eventsToFeatures(filteredEvents())
    });
    expandedKey = null;
  }

  function showPopup(coords, props) {
    var typeLabel = displayTypeLabel(props.type);
    var headerLine = typeLabel
      ? escHtml(typeLabel) + ' \u00b7 ' + escHtml(props.country)
      : escHtml(props.country);
    new maplibregl.Popup({ closeButton:false, offset:12 })
      .setLngLat(coords)
      .setHTML(
        '<div style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;min-width:220px;color:#666;">' +
        '<div style="font-size:10px;text-transform:uppercase;letter-spacing:0.1em;color:#111;margin-bottom:5px;">' +
          headerLine +
        '</div>' +
        '<div style="font-size:13px;font-weight:500;line-height:1.4;margin-bottom:8px;">' +
          escHtml(props.title) +
        '</div>' +
        '<a href="' + escHtml(props.link) + '" target="_blank" rel="noopener" ' +
        'style="font-size:11px;color:#ef4444;text-decoration:none;">Read full report \u2192</a>' +
        '</div>'
      )
      .addTo(cMap);
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
    // Sort newest first by matching back to allEvents for the date
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
      var typeLabel = displayTypeLabel(it.type);
      return '<a href="' + escHtml(it.link) + '" target="_blank" rel="noopener" ' +
             'style="display:block;padding:8px 10px;border-bottom:1px solid #eee;text-decoration:none;color:#111;">' +
             '<div style="display:flex;align-items:center;gap:6px;margin-bottom:3px;">' +
             '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:' + it.color + ';"></span>' +
             '<span style="font-size:10px;color:#111;text-transform:uppercase;letter-spacing:0.08em;">' +
             escHtml(dateStr) + (typeLabel ? ' \u00b7 ' + escHtml(typeLabel) : '') +
             '</span></div>' +
             '<div style="font-size:12px;line-height:1.35;font-weight:500;">' +
             escHtml(it.title) +
             '</div></a>';
    }).join("");

    new maplibregl.Popup({ closeButton: true, offset: 12, maxWidth: "320px" })
      .setLngLat(coords)
      .setHTML(
        '<div style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;min-width:260px;max-height:340px;overflow-y:auto;color:#111;">' +
        '<div style="font-size:10px;text-transform:uppercase;letter-spacing:0.1em;color:#111;padding:8px 10px 6px;border-bottom:1px solid #ddd;font-weight:600;">' +
        items.length + ' events \u00b7 ' + escHtml(country) +
        '</div>' +
        rows +
        '</div>'
      )
      .addTo(cMap);
  }

  function setFilter(t) {
    activeFilter = typeKey(t);
    var btns = document.querySelectorAll(".c-fbtn");
    for (var i = 0; i < btns.length; i++) {
      var btnText = (btns[i].textContent || "").trim().toLowerCase();
      if (typeKey(btnText) === activeFilter) {
        btns[i].classList.add("active");
      } else {
        btns[i].classList.remove("active");
      }
    }
    var events = filteredEvents();
    renderNews(events);
    renderTicker(events);
    paintMap(events);
  }

  function bindFilters() {
    var btns = document.querySelectorAll(".c-fbtn");
    for (var i = 0; i < btns.length; i++) {
      btns[i].addEventListener("click", function () {
        var label = (this.textContent || "").trim().toLowerCase();
        setFilter(label);
      });
    }
  }

  function startClock() {
    var node = $id("c-clock");
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
    loadAdvisories();
    bindFilters();
    initMap();
    fetchEvents().then(function (events) {
      allEvents = events || [];
      var view = filteredEvents();
      renderNews(view);
      renderTicker(view);
      if (cMap && cMap.loaded && cMap.loaded()) paintMap(view);
    }).catch(function (err) {
      console.error("[conflict-dash] fetch failed:", err);
      var f = $id("c-feed"); if (f) f.innerHTML = "<div class='c-loading'>FEED ERROR</div>";
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
