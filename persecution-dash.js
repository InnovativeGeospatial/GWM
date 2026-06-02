/* ============================================================================
   GWM Persecution Dashboard — external module (parallel to conflict/disaster)
   Loaded via: <script src="...jsdelivr.../persecution-dash.js?v=YYYYMMDDNN">
   Data feeds read from raw.githubusercontent.com (no jsDelivr lag).
   Requires Chart.js and maplibre-gl to be loaded BEFORE this file.
   Contains, in order: (1) 20-year trend chart, (2) map + rankings + news
   feed, (3) header stat counters.
   ============================================================================ */

/* ---- (1) 20-Year Incident Trend Chart -------------------------------------- */
(function() {
  var years = ['2005','2006','2007','2008','2009','2010','2011','2012','2013','2014','2015','2016','2017','2018','2019','2020','2021','2022','2023','2024','2025'];

  var data = {
    killings:      [1200,1350,1480,1620,1750,2100,2450,2800,3200,4800,5800,4600,4100,4400,4900,4100,4600,5200,5900,6200,5800],
    arrests:       [2800,3100,3400,3700,4100,4600,5100,5700,6300,7400,8600,9200,9800,10400,11000,9800,10600,12000,13400,14800,15200],
    churchAttacks: [980,1100,1250,1400,1600,1900,2300,2700,3100,4400,5600,5100,4800,5100,5700,5100,5600,6300,7000,7600,7200],
    displacement:  [18000,20000,23000,26000,30000,36000,44000,54000,68000,110000,145000,132000,121000,128000,140000,124000,136000,156000,172000,188000,182000]
  };

  var ctx = document.getElementById('gwm-trend-chart').getContext('2d');

  var gradKill = ctx.createLinearGradient(0,0,0,280);
  gradKill.addColorStop(0,'rgba(224,69,53,0.25)');
  gradKill.addColorStop(1,'rgba(224,69,53,0)');

  var gradArr = ctx.createLinearGradient(0,0,0,280);
  gradArr.addColorStop(0,'rgba(155,89,182,0.2)');
  gradArr.addColorStop(1,'rgba(155,89,182,0)');

  var gradChurch = ctx.createLinearGradient(0,0,0,280);
  gradChurch.addColorStop(0,'rgba(26,188,156,0.2)');
  gradChurch.addColorStop(1,'rgba(26,188,156,0)');

  var gradDisp = ctx.createLinearGradient(0,0,0,280);
  gradDisp.addColorStop(0,'rgba(212,170,110,0.15)');
  gradDisp.addColorStop(1,'rgba(212,170,110,0)');

  new Chart(ctx, {
    type: 'line',
    data: {
      labels: years,
      datasets: [
        { label: 'Killings', data: data.killings, borderColor: '#e04535', backgroundColor: gradKill, borderWidth: 2.5, pointRadius: 3, pointBackgroundColor: '#e04535', pointHoverRadius: 6, tension: 0.4, fill: true, yAxisID: 'y' },
        { label: 'Arrests', data: data.arrests, borderColor: '#9b59b6', backgroundColor: gradArr, borderWidth: 2.5, pointRadius: 3, pointBackgroundColor: '#9b59b6', pointHoverRadius: 6, tension: 0.4, fill: true, yAxisID: 'y' },
        { label: 'Church Attacks', data: data.churchAttacks, borderColor: '#1abc9c', backgroundColor: gradChurch, borderWidth: 2.5, pointRadius: 3, pointBackgroundColor: '#1abc9c', pointHoverRadius: 6, tension: 0.4, fill: true, yAxisID: 'y' },
        { label: 'Displacement', data: data.displacement, borderColor: '#d4aa6e', backgroundColor: gradDisp, borderWidth: 2.5, pointRadius: 3, pointBackgroundColor: '#d4aa6e', pointHoverRadius: 6, tension: 0.4, fill: true, yAxisID: 'y2' }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: { backgroundColor: 'rgba(15,18,25,0.95)', titleColor: '#fff', bodyColor: '#ccc', borderColor: 'rgba(255,255,255,0.1)', borderWidth: 1, padding: 12, titleFont: { family: 'DM Sans', size: 13 }, bodyFont: { family: 'DM Sans', size: 12 } }
      },
      scales: {
        x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#ccc', font: { family: 'DM Sans', size: 12 } } },
        y: { position: 'left', grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#ccc', font: { family: 'DM Sans', size: 12 } }, beginAtZero: true, title: { display: true, text: 'Incidents', color: '#aaa', font: { size: 11, family: 'DM Sans' } } },
        y2: { position: 'right', grid: { drawOnChartArea: false }, ticks: { color: '#d4aa6e', font: { family: 'DM Sans', size: 12 } }, beginAtZero: true, title: { display: true, text: 'Displaced Persons', color: '#d4aa6e', font: { size: 11, family: 'DM Sans' } } }
      }
    }
  });
})();


/* ---- (2) Map + Rankings + Live News Feed ----------------------------------- */
/* Reads from raw.githubusercontent.com (edge-propagates ~5 min, no jsDelivr lag).
   Stacked incidents (same country centroid) open a white dropdown menu
   listing every report — matching the conflict/disaster dashboards. */

var GWM_JSON_FEED_URL    = 'https://raw.githubusercontent.com/InnovativeGeospatial/GWM/main/persecution.json';
var GWM_WP_FALLBACK      = 'https://globalwitnessmonitor.com/wp-json/wp/v2/posts?categories=7&per_page=100&_fields=id,title,excerpt,link,date,content&orderby=date&order=desc';
var GWM_RANKINGS_URL     = 'https://raw.githubusercontent.com/InnovativeGeospatial/GWM/main/rankings.json';

var gwmMap = new maplibregl.Map({
  container: 'gwm-leaflet',
  style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
  center: [0, 20],
  zoom: 1.0,
  minZoom: 0.8,
  maxZoom: 8,
  attributionControl: false
});

gwmMap.addControl(new maplibregl.AttributionControl({
  customAttribution: '© <a href="https://carto.com" style="color:#555">CARTO</a>',
  compact: true
}), 'bottom-right');

var mlStyle = document.createElement('style');
mlStyle.innerHTML = '.maplibregl-ctrl-attrib { background: rgba(10,12,16,0.5) !important; color: #444 !important; font-size: 9px !important; } .maplibregl-ctrl-attrib a { color: #555 !important; } .maplibregl-ctrl-attrib-button { display: none !important; } .maplibregl-ctrl-zoom-in, .maplibregl-ctrl-zoom-out, .maplibregl-ctrl-compass { background: #161a23 !important; border-color: rgba(255,255,255,0.1) !important; } .maplibregl-ctrl-icon { filter: invert(0.7) !important; } .maplibregl-ctrl-group { background: #161a23 !important; border: 1px solid rgba(255,255,255,0.1) !important; } .maplibregl-popup-content { border-radius: 6px !important; padding: 10px 14px !important; }' +
  /* White dropdown menu for stacked incidents (overrides the padding rule above) */
  '.gwm-popup .maplibregl-popup-content{background:#fff !important;color:#111 !important;padding:0 !important;border-radius:8px !important;box-shadow:0 6px 24px rgba(0,0,0,0.35) !important;overflow:hidden !important;}' +
  '.gwm-popup .maplibregl-popup-tip{border-top-color:#fff !important;border-bottom-color:#fff !important;}' +
  '.gwm-popup .maplibregl-popup-close-button{color:#111 !important;font-size:18px !important;padding:2px 7px !important;}';
document.head.appendChild(mlStyle);

/* ── GWM theme overrides: brighter reds, bright-white body text, header spacing ──
   --crimson drives the rank bars AND the EXTREME/VERY HIGH labels, so one bump
   brightens both. --text-dim/--text-muted -> white covers most dim text; the
   !important rules below catch the few hardcoded greys. "Latest Reports" (inline
   green) and the tier labels (crimson/amber/gold) are intentionally NOT touched. */
var gwmTheme = document.createElement('style');
gwmTheme.innerHTML =
  '#gwm-wrap{--crimson:#ff5a47;--amber:#ffa94d;--gold:#e8c07d;--text-dim:#ffffff;--text-muted:#ffffff;}' +
  '#gwm-wrap .gwm-left .gwm-panel-header{padding:38px 18px 14px;}' +
  '#gwm-wrap .gwm-right .gwm-panel-header{padding:16px 18px 8px;}' +
  '#gwm-wrap .gwm-sources{display:none !important;}' +
  '#gwm-wrap .gwm-stat-label{color:#fff !important;}' +
  '#gwm-wrap .gwm-stat-value{color:#fff !important;}' +
  '#gwm-wrap .gwm-stat-delta{color:#fff !important;}' +
  '#gwm-wrap .gwm-stat-delta.neutral{color:#fff !important;}' +
  '#gwm-wrap .gwm-cname{color:#fff !important;}' +
  '#gwm-wrap .gwm-rank{color:#fff !important;}' +
  '#gwm-wrap .gwm-nsummary{color:#fff !important;}' +
  '#gwm-wrap .gwm-ntitle{color:#fff !important;}' +
  '#gwm-wrap .gwm-ntime{color:#fff !important;}' +
  '#gwm-wrap .gwm-tag{color:#fff !important;}' +
  '#gwm-wrap .gwm-source-badge{color:#fff !important;}' +
  '#gwm-wrap .gwm-legend-title{color:#fff !important;}' +
  '#gwm-wrap .gwm-legend-item{color:#fff !important;}' +
  '#gwm-wrap .gwm-trend-title{color:#fff !important;}' +
  '#gwm-wrap .gwm-tlabel{color:#fff !important;}' +
  '#gwm-wrap #gwm-trends div{color:#fff !important;}';
document.head.appendChild(gwmTheme);

var gwmCentroids = {
  'afghanistan':[65.0,33.9],'albania':[20.2,41.2],'algeria':[2.6,28.0],'angola':[17.9,-11.2],
  'argentina':[-63.6,-38.4],'armenia':[45.0,40.1],'australia':[133.8,-25.3],'austria':[14.6,47.5],
  'azerbaijan':[47.6,40.1],'bahrain':[50.6,26.0],'bangladesh':[90.4,23.7],'belarus':[28.0,53.7],
  'belgium':[4.5,50.5],'belize':[-88.5,17.2],'benin':[2.3,9.3],'bolivia':[-64.7,-16.3],
  'bosnia':[17.7,43.9],'bosnia and herzegovina':[17.7,43.9],
  'botswana':[24.7,-22.3],'brazil':[-51.9,-14.2],'brunei':[114.7,4.5],'bulgaria':[25.5,42.7],
  'burkina faso':[-1.6,12.4],'burundi':[29.9,-3.4],'cambodia':[104.9,12.6],'cameroon':[12.4,3.9],
  'canada':[-96.8,60.0],'cape verde':[-24.0,16.0],'cabo verde':[-24.0,16.0],
  'central african republic':[20.9,6.6],'car':[20.9,6.6],
  'chad':[18.7,15.5],'chile':[-71.5,-35.7],'china':[104.2,35.9],
  'colombia':[-74.3,4.1],'comoros':[43.9,-11.9],
  'congo':[15.8,-0.2],'republic of congo':[15.8,-0.2],'republic of the congo':[15.8,-0.2],
  'dr congo':[24.0,-2.9],'drc':[24.0,-2.9],
  'democratic republic of congo':[24.0,-2.9],'democratic republic of the congo':[24.0,-2.9],
  'costa rica':[-83.8,9.7],'croatia':[15.2,45.1],'cuba':[-79.5,21.5],'cyprus':[33.4,35.1],
  'czechia':[15.5,49.8],'czech republic':[15.5,49.8],
  'denmark':[9.5,56.3],'djibouti':[42.6,11.8],'dominica':[-61.4,15.4],
  'dominican republic':[-70.5,18.7],'ecuador':[-78.1,-1.8],
  'egypt':[30.8,26.8],'el salvador':[-88.9,13.8],'equatorial guinea':[10.3,1.7],
  'eritrea':[39.8,15.2],'estonia':[25.0,58.6],'eswatini':[31.5,-26.5],'swaziland':[31.5,-26.5],
  'ethiopia':[40.5,9.1],'fiji':[178.1,-17.7],'finland':[26.0,64.0],'france':[2.2,46.2],
  'gabon':[11.6,-0.8],'gambia':[-15.3,13.4],'georgia':[43.4,42.3],'germany':[10.5,51.2],
  'ghana':[-1.0,7.9],'greece':[21.8,39.1],'guatemala':[-90.2,15.8],'guinea':[-11.3,11.0],
  'guinea-bissau':[-15.2,11.8],'guinea bissau':[-15.2,11.8],
  'guyana':[-59.0,5.0],'haiti':[-72.3,19.0],'honduras':[-86.2,14.8],'hungary':[19.5,47.2],
  'iceland':[-18.7,64.9],'india':[78.7,20.6],'indonesia':[113.9,-0.8],'iran':[53.7,32.4],
  'iraq':[43.7,33.2],'ireland':[-8.2,53.4],'israel':[34.9,31.0],'italy':[12.6,42.5],
  'ivory coast':[-5.5,7.5],"cote d'ivoire":[-5.5,7.5],'cote divoire':[-5.5,7.5],
  'jamaica':[-77.3,18.1],'japan':[138.3,36.2],'jordan':[37.2,30.6],'kazakhstan':[66.9,48.0],
  'kenya':[37.9,0.0],'kiribati':[-168.7,-3.4],'kosovo':[20.9,42.6],
  'kuwait':[47.5,29.3],'kyrgyzstan':[74.8,41.2],'laos':[103.0,18.2],
  'latvia':[24.6,56.9],'lebanon':[35.9,33.9],'lesotho':[28.2,-29.6],
  'liberia':[-9.4,6.4],'libya':[17.2,26.3],
  'lithuania':[23.9,55.2],'luxembourg':[6.1,49.8],
  'madagascar':[46.9,-18.8],'malawi':[34.3,-13.2],
  'malaysia':[109.7,4.2],'maldives':[73.2,3.2],'mali':[-2.0,17.6],'malta':[14.4,35.9],
  'marshall islands':[171.2,7.1],
  'mauritania':[-10.9,20.3],'mauritius':[57.6,-20.3],
  'mexico':[-102.6,23.6],'micronesia':[150.6,7.4],
  'moldova':[28.4,47.4],'monaco':[7.4,43.7],
  'mongolia':[103.8,46.9],'montenegro':[19.4,42.7],'morocco':[-7.1,31.8],
  'mozambique':[35.5,-18.7],'myanmar':[95.9,17.1],'burma':[95.9,17.1],
  'namibia':[18.5,-22.0],'nauru':[166.9,-0.5],'nepal':[84.1,28.4],'netherlands':[5.3,52.1],
  'new zealand':[172.0,-41.5],'nicaragua':[-85.2,12.9],'niger':[8.1,17.6],'nigeria':[8.7,9.1],
  'north korea':[127.5,40.3],'north macedonia':[21.7,41.6],'macedonia':[21.7,41.6],
  'norway':[8.5,60.5],'oman':[57.5,21.5],'pakistan':[69.3,30.4],
  'palau':[134.6,7.5],'palestine':[35.2,31.9],'gaza':[34.4,31.5],'west bank':[35.3,32.0],
  'panama':[-80.8,8.5],'papua new guinea':[143.9,-6.3],'paraguay':[-58.4,-23.4],'peru':[-75.0,-9.2],
  'philippines':[122.9,12.9],'poland':[19.1,52.1],'portugal':[-8.2,39.4],'qatar':[51.2,25.4],
  'romania':[24.9,45.9],'russia':[105.3,61.5],'russian federation':[105.3,61.5],
  'rwanda':[29.9,-2.0],'samoa':[-172.1,-13.8],'san marino':[12.5,43.9],
  'sao tome and principe':[6.6,0.2],'saudi arabia':[45.1,24.0],
  'senegal':[-14.5,14.5],'serbia':[21.0,44.0],'seychelles':[55.5,-4.7],
  'sierra leone':[-11.8,8.5],'singapore':[103.8,1.4],
  'slovakia':[19.7,48.7],'slovenia':[14.8,46.1],'solomon islands':[160.2,-9.6],
  'somalia':[46.2,6.1],'south africa':[25.1,-29.0],
  'south korea':[127.8,35.9],'korea':[127.8,35.9],
  'south sudan':[31.3,6.9],'spain':[-3.7,40.5],'sri lanka':[80.7,7.9],
  'sudan':[29.9,12.9],'suriname':[-56.0,3.9],
  'sweden':[18.6,60.1],'switzerland':[8.2,46.8],'syria':[38.3,34.8],
  'taiwan':[120.9,23.7],'tajikistan':[71.3,38.9],'tanzania':[34.9,-6.4],'thailand':[101.0,15.9],
  'timor leste':[125.7,-8.9],'timor-leste':[125.7,-8.9],'east timor':[125.7,-8.9],
  'togo':[0.8,8.6],'tonga':[-175.2,-21.2],
  'trinidad and tobago':[-61.2,10.7],'trinidad':[-61.2,10.7],
  'tunisia':[9.0,33.9],'turkey':[35.2,38.9],'turkiye':[35.2,38.9],
  'turkmenistan':[59.6,39.0],'tuvalu':[179.2,-7.1],
  'uganda':[32.3,1.4],'ukraine':[31.2,48.4],
  'united arab emirates':[53.8,23.4],'uae':[53.8,23.4],
  'united kingdom':[-3.4,55.4],'uk':[-3.4,55.4],'britain':[-3.4,55.4],'great britain':[-3.4,55.4],
  'united states':[-95.7,37.1],'usa':[-95.7,37.1],'us':[-95.7,37.1],'u.s.':[-95.7,37.1],
  'america':[-95.7,37.1],
  'uruguay':[-55.8,-32.5],
  'uzbekistan':[63.9,41.4],'vanuatu':[166.9,-15.4],
  'vatican':[12.5,41.9],'vatican city':[12.5,41.9],'holy see':[12.5,41.9],
  'venezuela':[-66.6,6.4],'vietnam':[108.3,14.1],'yemen':[47.6,15.6],
  'zambia':[27.8,-13.1],'zimbabwe':[30.0,-19.0]
};

var typeColors = {
  killing: '#e04535',
  arrest: '#9b59b6',
  church: '#1abc9c',
  displacement: '#d4aa6e',
  default: '#e04535'
};

function gwmDetectType(title) {
  var t = (title || '').toLowerCase();
  if (t.includes('kill') || t.includes('murder') || t.includes('execut') || t.includes('death') || t.includes('martyr')) return 'killing';
  if (t.includes('arrest') || t.includes('detain') || t.includes('jail') || t.includes('imprison') || t.includes('sentenc')) return 'arrest';
  if (t.includes('church') || t.includes('demolish') || t.includes('burn') || t.includes('attack') || t.includes('raid')) return 'church';
  if (t.includes('displace') || t.includes('flee') || t.includes('refugee') || t.includes('expel')) return 'displacement';
  return 'killing';
}

function gwmDetectCountry(title, content) {
  var text = ((title || '') + ' ' + (content || '')).toLowerCase();
  var best = null;
  var bestLen = 0;
  Object.keys(gwmCentroids).forEach(function(c) {
    if (text.includes(c) && c.length > bestLen) {
      best = c;
      bestLen = c.length;
    }
  });
  return best;
}

// ── Map feature store ─────────────────────────────────────
var gwmOriginalFeatures = [];

function gwmCapFirst(s) {
  if (!s) return '';
  return s.charAt(0).toUpperCase() + s.slice(1);
}

// Single-incident popup (white card)
function gwmShowPopup(coords, props) {
  new maplibregl.Popup({ closeButton: false, offset: 10, className: 'gwm-popup' })
    .setLngLat(coords)
    .setHTML(
      '<div style="font-family:DM Sans,sans-serif;min-width:220px;color:#111;padding:12px 14px;">' +
      '<div style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:#888;margin-bottom:5px;">' + gwmEscape(props.country || '') + '</div>' +
      '<div style="font-size:13px;font-weight:500;color:#111;line-height:1.45;margin-bottom:8px;">' + gwmEscape(props.title || '') + '</div>' +
      '<a href="' + gwmEscape(props.link || '#') + '" target="_blank" rel="noopener" style="font-size:11px;color:#e04535;text-decoration:none;">Read full report &rarr;</a>' +
      '</div>'
    )
    .addTo(gwmMap);
}

// Stacked-incident dropdown menu (white card, black font) — lists every
// report at this country's centroid, newest first.
function gwmShowStackList(coords, countryKey) {
  var items = gwmOriginalFeatures
    .filter(function(f) { return f.properties.countryKey === countryKey; })
    .map(function(f) { return f.properties; });
  items.sort(function(a, b) {
    return String(b.date || '').localeCompare(String(a.date || ''));
  });

  var country = items.length ? items[0].country : '';
  var rows = items.map(function(it) {
    var d = it.date ? new Date(it.date) : null;
    var dateStr = d && !isNaN(d.getTime()) ? d.toISOString().slice(0, 10) : '';
    var typeLabel = gwmCapFirst(it.type || '');
    return '<a href="' + gwmEscape(it.link || '#') + '" target="_blank" rel="noopener" ' +
      'style="display:block;padding:8px 10px;border-bottom:1px solid #eee;text-decoration:none;color:#111;background:#fff;">' +
      '<div style="display:flex;align-items:center;gap:6px;margin-bottom:3px;">' +
      '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:' + (it.color || '#e04535') + ';"></span>' +
      '<span style="font-size:10px;color:#111;text-transform:uppercase;letter-spacing:0.08em;font-weight:600;">' +
      gwmEscape(dateStr) + (typeLabel ? ' \u00b7 ' + gwmEscape(typeLabel) : '') +
      '</span></div>' +
      '<div style="font-size:12px;line-height:1.35;font-weight:500;color:#111;">' +
      gwmEscape(it.title || '') +
      '</div></a>';
  }).join('');

  new maplibregl.Popup({ closeButton: true, offset: 10, maxWidth: '320px', className: 'gwm-popup' })
    .setLngLat(coords)
    .setHTML(
      '<div style="font-family:DM Sans,sans-serif;min-width:260px;max-height:340px;overflow-y:auto;color:#111;background:#fff;">' +
      '<div style="font-size:10px;text-transform:uppercase;letter-spacing:0.1em;color:#111;padding:8px 10px 6px;border-bottom:1px solid #ddd;font-weight:700;background:#fff;">' +
      items.length + ' events \u00b7 ' + gwmEscape(country) +
      '</div>' +
      rows +
      '</div>'
    )
    .addTo(gwmMap);
}

// ── Convert a JSON feed event to a map feature ─────────────
function gwmEventToFeature(event) {
  var country = (event.country || '').toLowerCase().trim();
  var lat = event.lat;
  var lng = event.lng;
  if ((typeof lat !== 'number' || typeof lng !== 'number') && country && gwmCentroids[country]) {
    lng = gwmCentroids[country][0];
    lat = gwmCentroids[country][1];
  }
  if (typeof lat !== 'number' || typeof lng !== 'number') return null;
  var incType = (event.type || 'arrest').toLowerCase();
  if (!typeColors[incType]) incType = gwmDetectType(event.title || '');
  return {
    type: 'Feature',
    geometry: { type: 'Point', coordinates: [lng, lat] },
    properties: {
      title: event.title || '',
      country: country ? country.charAt(0).toUpperCase() + country.slice(1) : '',
      countryKey: country || 'unknown',
      type: incType,
      color: typeColors[incType] || typeColors.default,
      link: event.wp_link || '#',
      date: event.date
    }
  };
}

function gwmPostToFeature(post) {
  var title = post.title.rendered.replace(/(<([^>]+)>)/gi, '');
  var content = post.content ? post.content.rendered : '';
  var metaMatch = content.match(/data-country="([^"]*)"[^>]*data-type="([^"]*)"[^>]*data-lat="([^"]*)"[^>]*data-lng="([^"]*)"/);
  var country, incType, lat, lng;
  if (metaMatch && metaMatch[3] && metaMatch[4]) {
    country = metaMatch[1];
    incType = metaMatch[2] || 'arrest';
    lat = parseFloat(metaMatch[3]);
    lng = parseFloat(metaMatch[4]);
  } else {
    var excerpt = post.excerpt ? post.excerpt.rendered.replace(/(<([^>]+)>)/gi, '') : '';
    country = gwmDetectCountry(title, excerpt);
    if (!country || !gwmCentroids[country]) return null;
    var coords = gwmCentroids[country];
    incType = gwmDetectType(title);
    lat = coords[1];
    lng = coords[0];
  }
  if (!lat || !lng) return null;
  return {
    type: 'Feature',
    geometry: { type: 'Point', coordinates: [lng, lat] },
    properties: {
      title: title,
      country: country ? country.charAt(0).toUpperCase() + country.slice(1) : '',
      countryKey: country || 'unknown',
      type: incType,
      color: typeColors[incType] || typeColors.default,
      link: post.link,
      date: post.date
    }
  };
}

gwmMap.on('load', function() {
  try { gwmMap.setPaintProperty('admin-0-boundary', 'line-color', 'rgba(255,255,255,0.65)'); } catch(e){}
  try { gwmMap.setPaintProperty('admin-0-boundary', 'line-width', 1.5); } catch(e){}
  try { gwmMap.setPaintProperty('admin-1-boundary', 'line-color', 'rgba(255,255,255,0.32)'); } catch(e){}
  try { gwmMap.setPaintProperty('country-label', 'text-color', 'rgba(255,255,255,0.95)'); } catch(e){}
  try { gwmMap.setPaintProperty('country-label', 'text-halo-color', 'rgba(0,0,0,0.6)'); } catch(e){}
  try { gwmMap.setPaintProperty('country-label', 'text-halo-width', 1.5); } catch(e){}

  gwmMap.fitBounds([[-150, -55], [160, 70]], { padding: 10, duration: 0 });

  gwmMap.getStyle().layers.forEach(function(layer) {
    var id = layer.id.toLowerCase();
    if (id.includes('continent') || id.includes('ocean') || id.includes('marine') || id.includes('sea_') || id.includes('_sea')) {
      gwmMap.setLayoutProperty(layer.id, 'visibility', 'none');
    }
    if (layer.type === 'symbol' && layer.minzoom !== undefined && layer.minzoom === 0) {
      gwmMap.setLayoutProperty(layer.id, 'visibility', 'none');
    }
  });

  gwmMap.addSource('incidents', {
    type: 'geojson',
    data: { type: 'FeatureCollection', features: [] }
  });

  gwmMap.addLayer({
    id: 'incidents-glow',
    type: 'circle',
    source: 'incidents',
    paint: {
      'circle-radius': 14,
      'circle-color': ['get', 'color'],
      'circle-opacity': 0.2,
      'circle-blur': 1
    }
  });

  gwmMap.addLayer({
    id: 'incidents-dot',
    type: 'circle',
    source: 'incidents',
    paint: {
      'circle-radius': 7,
      'circle-color': ['get', 'color'],
      'circle-opacity': 0.95,
      'circle-stroke-width': 1.5,
      'circle-stroke-color': 'rgba(255,255,255,0.5)'
    }
  });

  gwmMap.on('click', 'incidents-dot', function(e) {
    e.originalEvent.stopPropagation();
    var props = e.features[0].properties;
    var coords = e.features[0].geometry.coordinates.slice();
    var countryKey = props.countryKey;

    var clusterSize = gwmOriginalFeatures.filter(function(f) {
      return f.properties.countryKey === countryKey;
    }).length;

    if (clusterSize > 1) {
      gwmShowStackList(coords, countryKey);
    } else {
      gwmShowPopup(coords, props);
    }
  });

  gwmMap.on('mouseenter', 'incidents-dot', function() { gwmMap.getCanvas().style.cursor = 'pointer'; });
  gwmMap.on('mouseleave', 'incidents-dot', function() { gwmMap.getCanvas().style.cursor = ''; });

  fetch(GWM_JSON_FEED_URL, { cache: 'no-store' })
    .then(function(r) { if (!r.ok) throw new Error('JSON HTTP ' + r.status); return r.json(); })
    .then(function(data) {
      if (!data || !Array.isArray(data.events)) throw new Error('JSON malformed');
      console.log('[persecution-dash] loaded ' + data.events.length + ' events from JSON feed');
      var features = data.events.map(gwmEventToFeature).filter(function(f) { return f; });
      gwmOriginalFeatures = features;
      gwmMap.getSource('incidents').setData({
        type: 'FeatureCollection',
        features: features
      });
    })
    .catch(function(err) {
      console.warn('[persecution-dash] JSON feed failed, falling back to WP REST:', err);
      fetch(GWM_WP_FALLBACK, { cache: 'no-store' })
        .then(function(r) { return r.json(); })
        .then(function(posts) {
          var features = posts.map(gwmPostToFeature).filter(function(f) { return f; });
          gwmOriginalFeatures = features;
          gwmMap.getSource('incidents').setData({
            type: 'FeatureCollection',
            features: features
          });
          console.log('[persecution-dash] (fallback) plotted ' + features.length + ' incidents');
        })
        .catch(function(e) { console.log('Map feed error:', e); });
    });
});

// ── Rankings Left Panel ──────────────────────────────────────
function gwmEscape(s) {
  if (s == null) return '';
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function gwmTierClass(tier) {
  if (tier === 1) return 'extreme';
  if (tier === 2) return 'extreme';
  if (tier === 3) return 'high';
  return 'elevated';
}

function gwmRenderRankings(countries, generatedAt) {
  var listEl = document.getElementById('gwm-rankings-list');
  var metaEl = document.getElementById('gwm-rankings-meta');
  if (!listEl) return;
  var top50 = countries.slice(0, 50);
  listEl.innerHTML = top50.map(function(c) {
    var cls = gwmTierClass(c.tier);
    var label = c.tier_label || '';
    var rankStr = c.rank < 10 ? '0' + c.rank : '' + c.rank;
    var width = Math.max(20, Math.round(c.score)) + '%';
    return '<a class="gwm-country-item" href="/country-profiles/' + gwmEscape(c.slug) + '/">' +
      '<span class="gwm-rank">' + rankStr + '</span>' +
      '<span class="gwm-cname">' + gwmEscape(c.name) + '</span>' +
      '<div class="gwm-rbar-wrap"><div class="gwm-rbar ' + cls + '" style="width:' + width + '"></div></div>' +
      '<span class="gwm-rlabel ' + cls + '">' + gwmEscape(label) + '</span>' +
      '</a>';
  }).join('');
  if (metaEl) {
    metaEl.innerHTML = '<a href="https://globalwitnessmonitor.com/persecution-ranking-process/" ' +
      'style="color:#fff;font-size:13px;text-decoration:underline;text-decoration-color:rgba(255,255,255,0.4);">' +
      'How we calculate this &rarr;</a>';
  }
}

function gwmUpdateHeaderStamp(generatedAt) {
  var el = document.getElementById('gwm-update-stamp');
  if (!el) return;
  el.innerHTML = '<a href="https://globalwitnessmonitor.com/persecution-ranking-process/" ' +
    'style="color:inherit;text-decoration:underline;text-decoration-color:rgba(255,255,255,0.35);">' +
    'How we calculate this &rarr;</a>';
}

// Static fallback ranking — top 50 only
var GWM_RANKINGS_FALLBACK = [
  {rank:1,name:"North Korea",slug:"north-korea",tier:1,tier_label:"Extreme",score:100},
  {rank:2,name:"Somalia",slug:"somalia",tier:1,tier_label:"Extreme",score:98},
  {rank:3,name:"Yemen",slug:"yemen",tier:1,tier_label:"Extreme",score:96},
  {rank:4,name:"Eritrea",slug:"eritrea",tier:1,tier_label:"Extreme",score:94},
  {rank:5,name:"Libya",slug:"libya",tier:1,tier_label:"Extreme",score:92},
  {rank:6,name:"Nigeria",slug:"nigeria",tier:1,tier_label:"Extreme",score:90},
  {rank:7,name:"Pakistan",slug:"pakistan",tier:1,tier_label:"Extreme",score:88},
  {rank:8,name:"Sudan",slug:"sudan",tier:1,tier_label:"Extreme",score:86},
  {rank:9,name:"Iran",slug:"iran",tier:1,tier_label:"Extreme",score:84},
  {rank:10,name:"Afghanistan",slug:"afghanistan",tier:1,tier_label:"Extreme",score:82},
  {rank:11,name:"India",slug:"india",tier:2,tier_label:"Very High",score:80},
  {rank:12,name:"Syria",slug:"syria",tier:2,tier_label:"Very High",score:78},
  {rank:13,name:"Myanmar",slug:"myanmar-burma",tier:2,tier_label:"Very High",score:76},
  {rank:14,name:"Morocco",slug:"morocco",tier:2,tier_label:"Very High",score:74},
  {rank:15,name:"Algeria",slug:"algeria",tier:2,tier_label:"Very High",score:72},
  {rank:16,name:"Maldives",slug:"maldives",tier:2,tier_label:"Very High",score:70},
  {rank:17,name:"Mali",slug:"mali",tier:2,tier_label:"Very High",score:68},
  {rank:18,name:"Saudi Arabia",slug:"saudi-arabia",tier:2,tier_label:"Very High",score:67},
  {rank:19,name:"Turkmenistan",slug:"turkmenistan",tier:2,tier_label:"Very High",score:66},
  {rank:20,name:"Mauritania",slug:"mauritania",tier:2,tier_label:"Very High",score:65},
  {rank:21,name:"Laos",slug:"laos",tier:2,tier_label:"Very High",score:64},
  {rank:22,name:"China",slug:"china",tier:2,tier_label:"Very High",score:63},
  {rank:23,name:"Vietnam",slug:"vietnam",tier:2,tier_label:"Very High",score:62},
  {rank:24,name:"Burkina Faso",slug:"burkina-faso",tier:2,tier_label:"Very High",score:61},
  {rank:25,name:"Qatar",slug:"qatar",tier:2,tier_label:"Very High",score:60},
  {rank:26,name:"Uzbekistan",slug:"uzbekistan",tier:3,tier_label:"High",score:58},
  {rank:27,name:"Niger",slug:"niger",tier:3,tier_label:"High",score:57},
  {rank:28,name:"Iraq",slug:"iraq",tier:3,tier_label:"High",score:56},
  {rank:29,name:"Tajikistan",slug:"tajikistan",tier:3,tier_label:"High",score:55},
  {rank:30,name:"Egypt",slug:"egypt",tier:3,tier_label:"High",score:54},
  {rank:31,name:"Central African Republic",slug:"central-african-republic",tier:3,tier_label:"High",score:53},
  {rank:32,name:"Ethiopia",slug:"ethiopia",tier:3,tier_label:"High",score:52},
  {rank:33,name:"Bangladesh",slug:"bangladesh",tier:3,tier_label:"High",score:51},
  {rank:34,name:"Jordan",slug:"jordan",tier:3,tier_label:"High",score:50},
  {rank:35,name:"Comoros",slug:"comoros",tier:3,tier_label:"High",score:49},
  {rank:36,name:"Tunisia",slug:"tunisia",tier:3,tier_label:"High",score:48},
  {rank:37,name:"Kazakhstan",slug:"kazakhstan",tier:3,tier_label:"High",score:47},
  {rank:38,name:"DR Congo",slug:"dr-congo",tier:3,tier_label:"High",score:46},
  {rank:39,name:"Sri Lanka",slug:"sri-lanka",tier:3,tier_label:"High",score:45},
  {rank:40,name:"Nepal",slug:"nepal",tier:3,tier_label:"High",score:44},
  {rank:41,name:"Turkey",slug:"turkey",tier:3,tier_label:"High",score:43},
  {rank:42,name:"Kuwait",slug:"kuwait",tier:3,tier_label:"High",score:42},
  {rank:43,name:"United Arab Emirates",slug:"united-arab-emirates",tier:3,tier_label:"High",score:41},
  {rank:44,name:"Kyrgyzstan",slug:"kyrgyzstan",tier:3,tier_label:"High",score:40},
  {rank:45,name:"Colombia",slug:"colombia",tier:3,tier_label:"High",score:39},
  {rank:46,name:"Indonesia",slug:"indonesia",tier:3,tier_label:"High",score:38},
  {rank:47,name:"Cuba",slug:"cuba",tier:3,tier_label:"High",score:37},
  {rank:48,name:"Mexico",slug:"mexico",tier:3,tier_label:"High",score:36},
  {rank:49,name:"Cameroon",slug:"cameroon",tier:3,tier_label:"High",score:35},
  {rank:50,name:"Mozambique",slug:"mozambique",tier:3,tier_label:"High",score:34}
];

function gwmLoadRankings() {
  fetch(GWM_RANKINGS_URL, { cache: 'no-store' })
    .then(function(r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(function(data) {
      if (!data || !Array.isArray(data.countries)) throw new Error('malformed');
      var generatedAt = data.metadata && data.metadata.generated_at;
      gwmRenderRankings(data.countries, generatedAt);
      gwmUpdateHeaderStamp(generatedAt);
    })
    .catch(function(err) {
      console.warn('[persecution-dash] rankings feed failed, using fallback:', err);
      gwmRenderRankings(GWM_RANKINGS_FALLBACK, null);
      gwmUpdateHeaderStamp(null);
    });
}

gwmLoadRankings();

// ── Live News Feed ───────────────────────────────────────────
function gwmTimeAgo(dateStr) {
  if (!dateStr) return '';
  var s = String(dateStr);
  if (!/[Zz]|[+-]\d{2}:?\d{2}$/.test(s)) s = s + 'Z';
  var diff = Math.floor((new Date() - new Date(s)) / 1000);
  if (diff < 0) diff = 0;
  if (diff < 3600) return Math.floor(diff/60) + 'm ago';
  if (diff < 86400) return Math.floor(diff/3600) + 'h ago';
  return Math.floor(diff/86400) + 'd ago';
}

function gwmRenderFeed(events, feedEl) {
  if (!events || !events.length) {
    feedEl.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-muted);font-size:12px;">No reports yet.</div>';
    return;
  }
  feedEl.innerHTML = events.slice(0, 195).map(function(e) {
    var title = gwmEscape(e.title || '');
    var excerpt = (e.body || '').replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
    if (excerpt.length > 120) excerpt = excerpt.substring(0, 120) + '...';
    var timeAgo = gwmTimeAgo(e.date);
    var link = gwmEscape(e.wp_link || '#');
    return '<div class="gwm-news-item" onclick="window.location.href=\'' + link + '\'" style="cursor:pointer;">' +
      '<div class="gwm-news-meta">' +
      '<span class="gwm-nsource vom">GWM</span>' +
      '<div class="gwm-ndot"></div>' +
      '<span class="gwm-ntime">' + timeAgo + '</span>' +
      '</div>' +
      '<div class="gwm-ntitle" style="text-decoration:underline;text-decoration-color:rgba(255,255,255,0.2);">' + title + '</div>' +
      '<div class="gwm-nsummary">' + gwmEscape(excerpt) + '</div>' +
      '</div>';
  }).join('');
}

function gwmLoadFeed() {
  var feed = document.getElementById('gwm-live-feed');
  if (!feed) return;
  fetch(GWM_JSON_FEED_URL, { cache: 'no-store' })
    .then(function(r) { if (!r.ok) throw new Error('JSON HTTP ' + r.status); return r.json(); })
    .then(function(data) {
      if (!data || !Array.isArray(data.events)) throw new Error('JSON malformed');
      gwmRenderFeed(data.events, feed);
    })
    .catch(function(err) {
      console.warn('[persecution-dash] feed JSON failed, falling back to WP REST:', err);
      fetch('https://globalwitnessmonitor.com/wp-json/wp/v2/posts?categories=7&per_page=50&_fields=id,title,excerpt,link,date&orderby=date&order=desc')
        .then(function(r) { return r.json(); })
        .then(function(posts) {
          var events = posts.map(function(p) {
            return {
              title: p.title.rendered.replace(/(<([^>]+)>)/gi, ''),
              body: p.excerpt.rendered.replace(/(<([^>]+)>)/gi, ''),
              wp_link: p.link,
              date: p.date
            };
          });
          gwmRenderFeed(events, feed);
        })
        .catch(function() {
          feed.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-muted);font-size:12px;">Unable to load reports.</div>';
        });
    });
}

gwmLoadFeed();

// ── Nav interactions ─────────────────────────────────────────
document.querySelectorAll('.gwm-nav a').forEach(function(link) {
  link.addEventListener('click', function() {
    document.querySelectorAll('.gwm-nav a').forEach(function(l){ l.classList.remove('active'); });
    this.classList.add('active');
  });
});


/* ---- (3) Header Stat Counters ---------------------------------------------- */
(function () {
  var RANKINGS = 'https://raw.githubusercontent.com/InnovativeGeospatial/GWM/main/rankings.json';
  var WP = 'https://globalwitnessmonitor.com/wp-json/wp/v2/posts?categories=7';
  var opts = { cache: 'no-store' };

  function setText(id, val) {
    var el = document.getElementById(id);
    if (el) el.textContent = val;
  }

  function countAll(url, cb) {
    var total = 0;
    function page(p) {
      fetch(url + '&per_page=100&page=' + p + '&_fields=id', opts)
        .then(function (r) { if (r.status === 400) { cb(total); return null; } return r.json(); })
        .then(function (arr) {
          if (arr == null) return;
          if (!Array.isArray(arr)) { cb(total); return; }
          total += arr.length;
          if (arr.length < 100) { cb(total); } else { page(p + 1); }
        })
        .catch(function () { cb(total); });
    }
    page(1);
  }

  var now = new Date();
  var monthStart = new Date(now.getFullYear(), now.getMonth(), 1).toISOString();
  var lastStart = new Date(now.getFullYear(), now.getMonth() - 1, 1).toISOString();
  // Compare like-for-like: month-to-date vs the SAME day range last month,
  // so the 1st of a month doesn't read as a ~100% drop against a full month.
  var lastSamePoint = new Date(now.getFullYear(), now.getMonth() - 1, now.getDate(),
                               now.getHours(), now.getMinutes()).toISOString();
  var ago48 = new Date(now - 48 * 60 * 60 * 1000).toISOString();

  var thisMonth = null, lastMonth = null;
  function delta() {
    if (thisMonth == null || lastMonth == null || lastMonth === 0) return;
    var el = document.getElementById('gwm-stat-month-delta');
    if (!el) return;
    var diff = thisMonth - lastMonth;
    var pct = Math.round((diff / lastMonth) * 100);
    var arrow = diff >= 0 ? String.fromCharCode(8593) : String.fromCharCode(8595);
    el.textContent = arrow + ' ' + Math.abs(pct) + '% vs same point last month';
    el.className = 'gwm-stat-delta' + (diff < 0 ? ' neutral' : '');
  }

  countAll(WP + '&after=' + monthStart, function (n) { thisMonth = n; setText('gwm-stat-month', n); delta(); });
  countAll(WP + '&after=' + lastStart + '&before=' + lastSamePoint, function (n) { lastMonth = n; delta(); });
  countAll(WP + '&after=' + ago48, function (n) { setText('gwm-stat-48hr', n); });

  fetch(RANKINGS, { cache: 'no-store' })
    .then(function (r) { return r.json(); })
    .then(function (d) {
      var n = (d.countries || []).filter(function (c) { return c.tier === 1; }).length;
      setText('gwm-stat-extreme', n);
    })
    .catch(function () { setText('gwm-stat-extreme', '4'); });
}());
