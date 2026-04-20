/* =====================================================================
 * Global Witness Monitor -- Natural Disaster Intelligence Dashboard
 * disaster-dash.js  (v2 - GitHub/jsDelivr version)
 *
 * Served via jsDelivr:
 *   https://cdn.jsdelivr.net/gh/InnovativeGeospatial/GWM@main/disaster-dash.js
 *
 * Mounts into elements defined by the disaster-loader HTML:
 *   #d-map, #d-stats, #d-country-list, #d-news, #d-ticker, #d-clock,
 *   .d-fbtn (filter buttons)
 *
 * Data source:
 *   WP REST API, category 38 (Natural Disaster Reports)
 * ===================================================================== */

// =====================================================================
//  CONFIG
// =====================================================================
var WP_BASE     = "https://globalwitnessmonitor.com";
var CATEGORY_ID = 38;
var MAP_LIMIT   = 100;
var FEED_LIMIT  = 50;

// =====================================================================
//  MAP INIT
// =====================================================================
var dMap = new maplibregl.Map({
  container: "d-map",
  style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
  center: [20, 15],
  zoom: 2.2,
  attributionControl: false
});

dMap.addControl(new maplibregl.AttributionControl({compact: true}), "bottom-right");

dMap.on("style.load", function() {
  if (dMap.getLayer("boundary_country")) {
    dMap.setPaintProperty("boundary_country", "line-color", "rgba(255,255,255,0.5)");
    dMap.setPaintProperty("boundary_country", "line-width", 1);
  }
  dMap.getStyle().layers.forEach(function(layer) {
    if (layer.id.includes("boundary") || layer.id.includes("admin")) {
      try {
        dMap.setPaintProperty(layer.id, "line-color", "rgba(255,255,255,0.45)");
        dMap.setPaintProperty(layer.id, "line-opacity", 0.8);
      } catch(e) {}
    }
    if (layer.id.includes("label") || layer.id.includes("place") || layer.id.includes("country")) {
      try {
        dMap.setPaintProperty(layer.id, "text-color", "rgba(255,255,255,0.85)");
        dMap.setPaintProperty(layer.id, "text-halo-color", "rgba(0,0,0,0.9)");
        dMap.setPaintProperty(layer.id, "text-halo-width", 1.5);
      } catch(e) {}
    }
  });
});

// =====================================================================
//  TYPE COLORS AND LABELS
// =====================================================================
var dTypeColors = {
  earthquake: "#92400e",
  flood:      "#0ea5e9",
  storm:      "#a855f7",
  wildfire:   "#f97316",
  volcano:    "#dc2626",
  tsunami:    "#06b6d4",
  landslide:  "#78716c",
  drought:    "#ca8a04",
  heatwave:   "#f43f5e",
  other:      "#6b7280"
};

var dTypeLabels = {
  earthquake: "Earthquake",
  flood:      "Flood",
  storm:      "Storm / Cyclone",
  wildfire:   "Wildfire",
  volcano:    "Volcano",
  tsunami:    "Tsunami",
  landslide:  "Landslide",
  drought:    "Drought",
  heatwave:   "Heatwave",
  other:      "Other"
};

function dDetectType(title) {
  var t = (title || "").toLowerCase();
  if (t.indexOf("tsunami") !== -1 || t.indexOf("tidal wave") !== -1) return "tsunami";
  if (t.indexOf("volcano") !== -1 || t.indexOf("eruption") !== -1 ||
      t.indexOf("volcanic") !== -1 || t.indexOf("lava") !== -1) return "volcano";
  if (t.indexOf("earthquake") !== -1 || t.indexOf("quake") !== -1 ||
      t.indexOf("seismic") !== -1 || t.indexOf("aftershock") !== -1 ||
      t.indexOf("magnitude") !== -1 || t.indexOf("tremor") !== -1) return "earthquake";
  if (t.indexOf("wildfire") !== -1 || t.indexOf("bushfire") !== -1 ||
      t.indexOf("forest fire") !== -1 || t.indexOf("blaze") !== -1) return "wildfire";
  if (t.indexOf("hurricane") !== -1 || t.indexOf("typhoon") !== -1 ||
      t.indexOf("cyclone") !== -1 || t.indexOf("tropical storm") !== -1 ||
      t.indexOf("tornado") !== -1 || t.indexOf("storm surge") !== -1 ||
      t.indexOf("storm") !== -1) return "storm";
  if (t.indexOf("flood") !== -1 || t.indexOf("inundat") !== -1 || t.indexOf("deluge") !== -1) return "flood";
  if (t.indexOf("landslide") !== -1 || t.indexOf("mudslide") !== -1 ||
      t.indexOf("mudflow") !== -1 || t.indexOf("rockslide") !== -1 ||
      t.indexOf("avalanche") !== -1) return "landslide";
  if (t.indexOf("drought") !== -1 || t.indexOf("famine") !== -1) return "drought";
  if (t.indexOf("heatwave") !== -1 || t.indexOf("heat wave") !== -1 ||
      t.indexOf("extreme heat") !== -1) return "heatwave";
  return "other";
}

// =====================================================================
//  CENTROIDS (capital cities / major cities)
// =====================================================================
var dCentroids = {
  // Africa
  "nigeria":[7.49,9.07],"nigerian":[7.49,9.07],"abuja":[7.49,9.07],"lagos":[3.38,6.52],
  "kenya":[36.82,-1.29],"kenyan":[36.82,-1.29],"nairobi":[36.82,-1.29],"mombasa":[39.66,-4.05],
  "ethiopia":[38.74,9.03],"ethiopian":[38.74,9.03],"addis ababa":[38.74,9.03],
  "somalia":[45.34,2.04],"somali":[45.34,2.04],"mogadishu":[45.34,2.04],
  "sudan":[32.53,15.59],"sudanese":[32.53,15.59],"khartoum":[32.53,15.59],
  "south sudan":[31.58,4.86],"juba":[31.58,4.86],
  "drc":[15.27,-4.32],"congo":[15.27,-4.32],"kinshasa":[15.27,-4.32],"goma":[29.24,-1.66],
  "uganda":[32.58,0.32],"ugandan":[32.58,0.32],"kampala":[32.58,0.32],
  "tanzania":[35.74,-6.17],"tanzanian":[35.74,-6.17],"dar es salaam":[39.27,-6.79],"dodoma":[35.74,-6.17],
  "rwanda":[30.06,-1.94],"rwandan":[30.06,-1.94],"kigali":[30.06,-1.94],
  "burundi":[29.36,-3.39],"bujumbura":[29.36,-3.39],
  "mali":[-8.00,12.65],"malian":[-8.00,12.65],"bamako":[-8.00,12.65],
  "burkina faso":[-1.52,12.37],"ouagadougou":[-1.52,12.37],
  "niger":[2.12,13.51],"niamey":[2.12,13.51],
  "chad":[15.05,12.13],"chadian":[15.05,12.13],"ndjamena":[15.05,12.13],
  "cameroon":[11.50,3.85],"cameroonian":[11.50,3.85],"yaounde":[11.50,3.85],
  "mozambique":[32.58,-25.97],"mozambican":[32.58,-25.97],"maputo":[32.58,-25.97],
  "madagascar":[47.52,-18.88],"malagasy":[47.52,-18.88],"antananarivo":[47.52,-18.88],
  "malawi":[33.78,-13.97],"malawian":[33.78,-13.97],"lilongwe":[33.78,-13.97],
  "zambia":[28.32,-15.39],"zambian":[28.32,-15.39],"lusaka":[28.32,-15.39],
  "zimbabwe":[31.05,-17.83],"zimbabwean":[31.05,-17.83],"harare":[31.05,-17.83],
  "south africa":[28.04,-26.20],"south african":[28.04,-26.20],"johannesburg":[28.04,-26.20],"cape town":[18.42,-33.92],"pretoria":[28.19,-25.75],
  "angola":[13.23,-8.84],"angolan":[13.23,-8.84],"luanda":[13.23,-8.84],
  "namibia":[17.08,-22.56],"namibian":[17.08,-22.56],"windhoek":[17.08,-22.56],
  "botswana":[25.91,-24.65],"gaborone":[25.91,-24.65],
  "lesotho":[27.48,-29.31],"maseru":[27.48,-29.31],
  "ghana":[-0.20,5.60],"ghanaian":[-0.20,5.60],"accra":[-0.20,5.60],
  "ivory coast":[-4.02,5.36],"abidjan":[-4.02,5.36],
  "senegal":[-17.45,14.69],"senegalese":[-17.45,14.69],"dakar":[-17.45,14.69],
  "liberia":[-10.80,6.30],"liberian":[-10.80,6.30],"monrovia":[-10.80,6.30],
  "sierra leone":[-13.23,8.49],"freetown":[-13.23,8.49],
  "morocco":[-6.84,34.02],"moroccan":[-6.84,34.02],"rabat":[-6.84,34.02],"casablanca":[-7.59,33.57],"marrakech":[-7.99,31.63],
  "algeria":[3.06,36.75],"algerian":[3.06,36.75],"algiers":[3.06,36.75],
  "tunisia":[10.18,36.81],"tunisian":[10.18,36.81],"tunis":[10.18,36.81],
  "libya":[13.18,32.89],"libyan":[13.18,32.89],"tripoli":[13.18,32.89],"benghazi":[20.07,32.12],"derna":[22.64,32.77],
  "eritrea":[38.93,15.32],"eritrean":[38.93,15.32],"asmara":[38.93,15.32],
  "djibouti":[43.15,11.59],
  "central african republic":[18.56,4.39],"car":[18.56,4.39],"bangui":[18.56,4.39],
  "gabon":[9.45,0.39],"libreville":[9.45,0.39],
  "equatorial guinea":[8.78,3.75],"malabo":[8.78,3.75],
  "guinea":[-13.71,9.64],"conakry":[-13.71,9.64],
  "guinea-bissau":[-15.60,11.86],"bissau":[-15.60,11.86],
  "gambia":[-16.58,13.45],"banjul":[-16.58,13.45],
  "togo":[1.21,6.13],"lome":[1.21,6.13],
  "benin":[2.63,6.50],"porto-novo":[2.63,6.50],"cotonou":[2.42,6.37],
  "mauritania":[-15.98,18.08],"nouakchott":[-15.98,18.08],
  "comoros":[43.26,-11.70],"moroni":[43.26,-11.70],
  "seychelles":[55.45,-4.62],
  "mauritius":[57.50,-20.16],"port louis":[57.50,-20.16],
  "cape verde":[-23.51,14.93],"praia":[-23.51,14.93],
  "eswatini":[31.13,-26.31],"swaziland":[31.13,-26.31],"mbabane":[31.13,-26.31],

  // Middle East
  "iran":[51.39,35.69],"iranian":[51.39,35.69],"tehran":[51.39,35.69],
  "iraq":[44.36,33.31],"iraqi":[44.36,33.31],"baghdad":[44.36,33.31],"mosul":[43.13,36.34],
  "syria":[36.30,33.51],"syrian":[36.30,33.51],"damascus":[36.30,33.51],"aleppo":[37.16,36.20],
  "lebanon":[35.49,33.89],"lebanese":[35.49,33.89],"beirut":[35.49,33.89],
  "israel":[35.21,31.78],"israeli":[35.21,31.78],"jerusalem":[35.21,31.78],"tel aviv":[34.78,32.08],
  "palestine":[35.45,31.95],"palestinian":[35.45,31.95],"gaza":[34.47,31.50],
  "jordan":[35.93,31.95],"jordanian":[35.93,31.95],"amman":[35.93,31.95],
  "saudi arabia":[46.67,24.71],"saudi":[46.67,24.71],"riyadh":[46.67,24.71],"jeddah":[39.20,21.49],
  "yemen":[44.21,15.35],"yemeni":[44.21,15.35],"sanaa":[44.21,15.35],"aden":[45.04,12.79],
  "oman":[58.40,23.59],"omani":[58.40,23.59],"muscat":[58.40,23.59],
  "kuwait":[47.97,29.38],"kuwaiti":[47.97,29.38],
  "qatar":[51.53,25.29],"qatari":[51.53,25.29],"doha":[51.53,25.29],
  "bahrain":[50.59,26.23],"bahraini":[50.59,26.23],"manama":[50.59,26.23],
  "uae":[54.37,24.45],"united arab emirates":[54.37,24.45],"dubai":[55.27,25.20],"abu dhabi":[54.37,24.45],
  "turkey":[32.85,39.93],"turkish":[32.85,39.93],"ankara":[32.85,39.93],"istanbul":[28.98,41.01],"gaziantep":[37.38,37.07],
  "egypt":[31.24,30.04],"egyptian":[31.24,30.04],"cairo":[31.24,30.04],"alexandria":[29.92,31.20],

  // Asia
  "china":[116.40,39.90],"chinese":[116.40,39.90],"beijing":[116.40,39.90],"shanghai":[121.47,31.23],"sichuan":[104.07,30.67],
  "india":[77.21,28.61],"indian":[77.21,28.61],"new delhi":[77.21,28.61],"mumbai":[72.88,19.08],"kolkata":[88.36,22.57],"chennai":[80.27,13.08],"kerala":[76.27,10.85],
  "pakistan":[73.05,33.69],"pakistani":[73.05,33.69],"islamabad":[73.05,33.69],"karachi":[67.01,24.86],"lahore":[74.34,31.55],
  "bangladesh":[90.41,23.81],"bangladeshi":[90.41,23.81],"dhaka":[90.41,23.81],
  "nepal":[85.32,27.70],"nepali":[85.32,27.70],"nepalese":[85.32,27.70],"kathmandu":[85.32,27.70],
  "bhutan":[89.64,27.47],"bhutanese":[89.64,27.47],"thimphu":[89.64,27.47],
  "sri lanka":[79.86,6.93],"sri lankan":[79.86,6.93],"colombo":[79.86,6.93],
  "myanmar":[96.16,16.81],"burma":[96.16,16.81],"burmese":[96.16,16.81],"naypyidaw":[96.13,19.76],"yangon":[96.16,16.81],"mandalay":[96.08,21.97],
  "thailand":[100.50,13.75],"thai":[100.50,13.75],"bangkok":[100.50,13.75],"chiang mai":[98.99,18.79],
  "vietnam":[105.83,21.03],"vietnamese":[105.83,21.03],"hanoi":[105.83,21.03],"ho chi minh":[106.66,10.76],
  "cambodia":[104.92,11.55],"cambodian":[104.92,11.55],"phnom penh":[104.92,11.55],
  "laos":[102.60,17.97],"laotian":[102.60,17.97],"vientiane":[102.60,17.97],
  "malaysia":[101.69,3.14],"malaysian":[101.69,3.14],"kuala lumpur":[101.69,3.14],
  "indonesia":[106.85,-6.21],"indonesian":[106.85,-6.21],"jakarta":[106.85,-6.21],"sumatra":[101.34,-0.79],"java":[110.00,-7.50],"bali":[115.19,-8.65],"sulawesi":[120.50,-2.55],
  "philippines":[120.98,14.60],"filipino":[120.98,14.60],"philippine":[120.98,14.60],"manila":[120.98,14.60],"cebu":[123.89,10.32],"mindanao":[124.65,7.65],
  "singapore":[103.82,1.35],"singaporean":[103.82,1.35],
  "brunei":[114.94,4.90],
  "japan":[139.69,35.69],"japanese":[139.69,35.69],"tokyo":[139.69,35.69],"osaka":[135.50,34.69],"kyoto":[135.77,35.01],"fukushima":[140.47,37.75],
  "south korea":[126.98,37.57],"korea":[126.98,37.57],"korean":[126.98,37.57],"seoul":[126.98,37.57],
  "north korea":[125.76,39.04],"pyongyang":[125.76,39.04],
  "mongolia":[106.92,47.92],"mongolian":[106.92,47.92],"ulaanbaatar":[106.92,47.92],
  "taiwan":[121.57,25.03],"taiwanese":[121.57,25.03],"taipei":[121.57,25.03],
  "afghanistan":[69.17,34.53],"afghan":[69.17,34.53],"kabul":[69.17,34.53],"herat":[62.20,34.34],
  "kazakhstan":[71.43,51.13],"kazakh":[71.43,51.13],"astana":[71.43,51.13],"almaty":[76.95,43.26],
  "uzbekistan":[69.24,41.30],"uzbek":[69.24,41.30],"tashkent":[69.24,41.30],
  "turkmenistan":[58.38,37.95],"ashgabat":[58.38,37.95],
  "kyrgyzstan":[74.59,42.87],"kyrgyz":[74.59,42.87],"bishkek":[74.59,42.87],
  "tajikistan":[68.78,38.56],"tajik":[68.78,38.56],"dushanbe":[68.78,38.56],
  "maldives":[73.51,4.18],"male":[73.51,4.18],
  "timor-leste":[125.58,-8.56],"east timor":[125.58,-8.56],"dili":[125.58,-8.56],

  // Europe
  "united kingdom":[-0.13,51.51],"uk":[-0.13,51.51],"britain":[-0.13,51.51],"british":[-0.13,51.51],"england":[-0.13,51.51],"london":[-0.13,51.51],"scotland":[-3.19,55.95],
  "ireland":[-6.27,53.35],"irish":[-6.27,53.35],"dublin":[-6.27,53.35],
  "france":[2.35,48.86],"french":[2.35,48.86],"paris":[2.35,48.86],"marseille":[5.37,43.30],
  "germany":[13.40,52.52],"german":[13.40,52.52],"berlin":[13.40,52.52],"munich":[11.58,48.14],"hamburg":[9.99,53.55],
  "spain":[-3.70,40.42],"spanish":[-3.70,40.42],"madrid":[-3.70,40.42],"barcelona":[2.17,41.39],"valencia":[-0.38,39.47],
  "portugal":[-9.14,38.72],"portuguese":[-9.14,38.72],"lisbon":[-9.14,38.72],
  "italy":[12.50,41.90],"italian":[12.50,41.90],"rome":[12.50,41.90],"milan":[9.19,45.46],"naples":[14.27,40.85],"sicily":[14.02,37.60],
  "greece":[23.73,37.98],"greek":[23.73,37.98],"athens":[23.73,37.98],
  "netherlands":[4.90,52.37],"dutch":[4.90,52.37],"amsterdam":[4.90,52.37],"rotterdam":[4.48,51.92],
  "belgium":[4.35,50.85],"belgian":[4.35,50.85],"brussels":[4.35,50.85],
  "luxembourg":[6.13,49.61],
  "switzerland":[7.45,46.95],"swiss":[7.45,46.95],"bern":[7.45,46.95],"zurich":[8.55,47.38],"geneva":[6.14,46.20],
  "austria":[16.37,48.21],"austrian":[16.37,48.21],"vienna":[16.37,48.21],
  "poland":[21.01,52.23],"polish":[21.01,52.23],"warsaw":[21.01,52.23],
  "czech republic":[14.42,50.08],"czechia":[14.42,50.08],"prague":[14.42,50.08],
  "slovakia":[17.11,48.15],"slovak":[17.11,48.15],"bratislava":[17.11,48.15],
  "hungary":[19.04,47.50],"hungarian":[19.04,47.50],"budapest":[19.04,47.50],
  "romania":[26.10,44.43],"romanian":[26.10,44.43],"bucharest":[26.10,44.43],
  "bulgaria":[23.32,42.70],"bulgarian":[23.32,42.70],"sofia":[23.32,42.70],
  "serbia":[20.46,44.80],"serbian":[20.46,44.80],"belgrade":[20.46,44.80],
  "croatia":[15.98,45.81],"croatian":[15.98,45.81],"zagreb":[15.98,45.81],
  "slovenia":[14.51,46.06],"slovenian":[14.51,46.06],"ljubljana":[14.51,46.06],
  "bosnia":[18.41,43.86],"sarajevo":[18.41,43.86],
  "albania":[19.82,41.33],"albanian":[19.82,41.33],"tirana":[19.82,41.33],
  "kosovo":[21.17,42.67],"pristina":[21.17,42.67],
  "north macedonia":[21.43,41.99],"macedonia":[21.43,41.99],"skopje":[21.43,41.99],
  "montenegro":[19.26,42.44],"podgorica":[19.26,42.44],
  "moldova":[28.84,47.01],"chisinau":[28.84,47.01],
  "ukraine":[30.52,50.45],"ukrainian":[30.52,50.45],"kyiv":[30.52,50.45],"kiev":[30.52,50.45],"kharkiv":[36.23,49.99],"odesa":[30.73,46.48],
  "belarus":[27.57,53.90],"belarusian":[27.57,53.90],"minsk":[27.57,53.90],
  "russia":[37.62,55.75],"russian":[37.62,55.75],"moscow":[37.62,55.75],"st petersburg":[30.34,59.93],"siberia":[88.00,60.00],"kamchatka":[158.65,53.04],
  "norway":[10.75,59.91],"norwegian":[10.75,59.91],"oslo":[10.75,59.91],
  "sweden":[18.07,59.33],"swedish":[18.07,59.33],"stockholm":[18.07,59.33],
  "finland":[24.94,60.17],"finnish":[24.94,60.17],"helsinki":[24.94,60.17],
  "denmark":[12.57,55.68],"danish":[12.57,55.68],"copenhagen":[12.57,55.68],
  "iceland":[-21.94,64.15],"icelandic":[-21.94,64.15],"reykjavik":[-21.94,64.15],
  "estonia":[24.75,59.44],"estonian":[24.75,59.44],"tallinn":[24.75,59.44],
  "latvia":[24.11,56.95],"latvian":[24.11,56.95],"riga":[24.11,56.95],
  "lithuania":[25.28,54.69],"lithuanian":[25.28,54.69],"vilnius":[25.28,54.69],
  "cyprus":[33.38,35.18],"cypriot":[33.38,35.18],"nicosia":[33.38,35.18],
  "malta":[14.51,35.90],"maltese":[14.51,35.90],"valletta":[14.51,35.90],
  "georgia":[44.79,41.72],"georgian":[44.79,41.72],"tbilisi":[44.79,41.72],
  "armenia":[44.51,40.18],"armenian":[44.51,40.18],"yerevan":[44.51,40.18],
  "azerbaijan":[49.87,40.41],"azerbaijani":[49.87,40.41],"baku":[49.87,40.41],

  // Americas
  "united states":[-77.04,38.91],"usa":[-77.04,38.91],"us":[-77.04,38.91],"american":[-77.04,38.91],
  "washington":[-77.04,38.91],"new york":[-74.01,40.71],"los angeles":[-118.24,34.05],"california":[-119.42,36.78],
  "florida":[-81.76,27.66],"texas":[-99.90,31.97],"louisiana":[-91.96,30.98],"new orleans":[-90.07,29.95],
  "puerto rico":[-66.59,18.22],"hawaii":[-155.58,19.90],"alaska":[-149.49,64.20],
  "canada":[-75.69,45.42],"canadian":[-75.69,45.42],"ottawa":[-75.69,45.42],"toronto":[-79.38,43.65],"vancouver":[-123.12,49.28],"montreal":[-73.57,45.50],"alberta":[-114.07,53.93],"british columbia":[-127.65,53.73],
  "mexico":[-99.13,19.43],"mexican":[-99.13,19.43],"mexico city":[-99.13,19.43],"guadalajara":[-103.35,20.66],"acapulco":[-99.88,16.86],
  "guatemala":[-90.51,14.63],"guatemalan":[-90.51,14.63],
  "honduras":[-87.20,14.07],"honduran":[-87.20,14.07],"tegucigalpa":[-87.20,14.07],
  "el salvador":[-89.19,13.69],"salvadoran":[-89.19,13.69],
  "nicaragua":[-86.25,12.11],"nicaraguan":[-86.25,12.11],"managua":[-86.25,12.11],
  "costa rica":[-84.09,9.93],"san jose":[-84.09,9.93],
  "panama":[-79.52,8.98],"panamanian":[-79.52,8.98],
  "belize":[-88.50,17.25],
  "cuba":[-82.36,23.13],"cuban":[-82.36,23.13],"havana":[-82.36,23.13],
  "haiti":[-72.34,18.59],"haitian":[-72.34,18.59],"port-au-prince":[-72.34,18.59],
  "dominican republic":[-69.93,18.49],"santo domingo":[-69.93,18.49],
  "jamaica":[-76.79,17.97],"jamaican":[-76.79,17.97],"kingston":[-76.79,17.97],
  "bahamas":[-77.34,25.05],"nassau":[-77.34,25.05],
  "trinidad":[-61.51,10.66],"tobago":[-61.51,10.66],
  "colombia":[-74.07,4.71],"colombian":[-74.07,4.71],"bogota":[-74.07,4.71],"medellin":[-75.57,6.24],
  "venezuela":[-66.91,10.48],"venezuelan":[-66.91,10.48],"caracas":[-66.91,10.48],
  "ecuador":[-78.47,-0.18],"ecuadorian":[-78.47,-0.18],"quito":[-78.47,-0.18],
  "peru":[-77.04,-12.05],"peruvian":[-77.04,-12.05],"lima":[-77.04,-12.05],
  "bolivia":[-68.12,-16.50],"bolivian":[-68.12,-16.50],"la paz":[-68.12,-16.50],
  "brazil":[-47.93,-15.78],"brazilian":[-47.93,-15.78],"brasilia":[-47.93,-15.78],"rio de janeiro":[-43.20,-22.91],"sao paulo":[-46.63,-23.55],"amazon":[-60.03,-3.10],
  "argentina":[-58.38,-34.61],"argentine":[-58.38,-34.61],"buenos aires":[-58.38,-34.61],
  "chile":[-70.65,-33.45],"chilean":[-70.65,-33.45],"santiago":[-70.65,-33.45],
  "paraguay":[-57.59,-25.26],"asuncion":[-57.59,-25.26],
  "uruguay":[-56.16,-34.90],"montevideo":[-56.16,-34.90],
  "guyana":[-58.16,6.80],"georgetown":[-58.16,6.80],
  "suriname":[-55.20,5.85],"paramaribo":[-55.20,5.85],

  // Pacific
  "australia":[149.13,-35.28],"australian":[149.13,-35.28],"sydney":[151.21,-33.87],"melbourne":[144.96,-37.81],"brisbane":[153.03,-27.47],"queensland":[145.00,-22.00],
  "new zealand":[174.78,-41.29],"wellington":[174.78,-41.29],"auckland":[174.76,-36.85],"christchurch":[172.64,-43.53],
  "papua new guinea":[147.18,-9.44],"png":[147.18,-9.44],"port moresby":[147.18,-9.44],
  "fiji":[178.45,-18.14],"fijian":[178.45,-18.14],"suva":[178.45,-18.14],
  "samoa":[-171.77,-13.83],"samoan":[-171.77,-13.83],"apia":[-171.77,-13.83],
  "tonga":[-175.20,-21.14],"tongan":[-175.20,-21.14],
  "vanuatu":[168.32,-17.74],"port vila":[168.32,-17.74],
  "solomon islands":[159.96,-9.43],"honiara":[159.96,-9.43]
};

// =====================================================================
//  COUNTRY FLAGS (canonical display names)
// =====================================================================
var dFlags = {
  "Afghanistan":"\u{1F1E6}\u{1F1EB}","Albania":"\u{1F1E6}\u{1F1F1}","Algeria":"\u{1F1E9}\u{1F1FF}",
  "Angola":"\u{1F1E6}\u{1F1F4}","Argentina":"\u{1F1E6}\u{1F1F7}","Armenia":"\u{1F1E6}\u{1F1F2}",
  "Australia":"\u{1F1E6}\u{1F1FA}","Austria":"\u{1F1E6}\u{1F1F9}","Azerbaijan":"\u{1F1E6}\u{1F1FF}",
  "Bahamas":"\u{1F1E7}\u{1F1F8}","Bahrain":"\u{1F1E7}\u{1F1ED}","Bangladesh":"\u{1F1E7}\u{1F1E9}",
  "Belarus":"\u{1F1E7}\u{1F1FE}","Belgium":"\u{1F1E7}\u{1F1EA}","Belize":"\u{1F1E7}\u{1F1FF}",
  "Benin":"\u{1F1E7}\u{1F1EF}","Bhutan":"\u{1F1E7}\u{1F1F9}","Bolivia":"\u{1F1E7}\u{1F1F4}",
  "Bosnia":"\u{1F1E7}\u{1F1E6}","Botswana":"\u{1F1E7}\u{1F1FC}","Brazil":"\u{1F1E7}\u{1F1F7}",
  "Brunei":"\u{1F1E7}\u{1F1F3}","Bulgaria":"\u{1F1E7}\u{1F1EC}","Burkina Faso":"\u{1F1E7}\u{1F1EB}",
  "Burundi":"\u{1F1E7}\u{1F1EE}","Cambodia":"\u{1F1F0}\u{1F1ED}","Cameroon":"\u{1F1E8}\u{1F1F2}",
  "Canada":"\u{1F1E8}\u{1F1E6}","Cape Verde":"\u{1F1E8}\u{1F1FB}",
  "Central African Republic":"\u{1F1E8}\u{1F1EB}","Chad":"\u{1F1F9}\u{1F1E9}","Chile":"\u{1F1E8}\u{1F1F1}",
  "China":"\u{1F1E8}\u{1F1F3}","Colombia":"\u{1F1E8}\u{1F1F4}","Comoros":"\u{1F1F0}\u{1F1F2}",
  "Costa Rica":"\u{1F1E8}\u{1F1F7}","Croatia":"\u{1F1ED}\u{1F1F7}","Cuba":"\u{1F1E8}\u{1F1FA}",
  "Cyprus":"\u{1F1E8}\u{1F1FE}","Czech Republic":"\u{1F1E8}\u{1F1FF}","Denmark":"\u{1F1E9}\u{1F1F0}",
  "Djibouti":"\u{1F1E9}\u{1F1EF}","Dominican Republic":"\u{1F1E9}\u{1F1F4}","DRC":"\u{1F1E8}\u{1F1E9}",
  "Ecuador":"\u{1F1EA}\u{1F1E8}","Egypt":"\u{1F1EA}\u{1F1EC}","El Salvador":"\u{1F1F8}\u{1F1FB}",
  "Equatorial Guinea":"\u{1F1EC}\u{1F1F6}","Eritrea":"\u{1F1EA}\u{1F1F7}","Estonia":"\u{1F1EA}\u{1F1EA}",
  "Eswatini":"\u{1F1F8}\u{1F1FF}","Ethiopia":"\u{1F1EA}\u{1F1F9}","Fiji":"\u{1F1EB}\u{1F1EF}",
  "Finland":"\u{1F1EB}\u{1F1EE}","France":"\u{1F1EB}\u{1F1F7}","Gabon":"\u{1F1EC}\u{1F1E6}",
  "Gambia":"\u{1F1EC}\u{1F1F2}","Georgia":"\u{1F1EC}\u{1F1EA}","Germany":"\u{1F1E9}\u{1F1EA}",
  "Ghana":"\u{1F1EC}\u{1F1ED}","Greece":"\u{1F1EC}\u{1F1F7}","Guatemala":"\u{1F1EC}\u{1F1F9}",
  "Guinea":"\u{1F1EC}\u{1F1F3}","Guinea-Bissau":"\u{1F1EC}\u{1F1FC}","Guyana":"\u{1F1EC}\u{1F1FE}",
  "Haiti":"\u{1F1ED}\u{1F1F9}","Honduras":"\u{1F1ED}\u{1F1F3}","Hungary":"\u{1F1ED}\u{1F1FA}",
  "Iceland":"\u{1F1EE}\u{1F1F8}","India":"\u{1F1EE}\u{1F1F3}","Indonesia":"\u{1F1EE}\u{1F1E9}",
  "Iran":"\u{1F1EE}\u{1F1F7}","Iraq":"\u{1F1EE}\u{1F1F6}","Ireland":"\u{1F1EE}\u{1F1EA}",
  "Israel":"\u{1F1EE}\u{1F1F1}","Italy":"\u{1F1EE}\u{1F1F9}","Ivory Coast":"\u{1F1E8}\u{1F1EE}",
  "Jamaica":"\u{1F1EF}\u{1F1F2}","Japan":"\u{1F1EF}\u{1F1F5}","Jordan":"\u{1F1EF}\u{1F1F4}",
  "Kazakhstan":"\u{1F1F0}\u{1F1FF}","Kenya":"\u{1F1F0}\u{1F1EA}","Kosovo":"\u{1F1FD}\u{1F1F0}",
  "Kuwait":"\u{1F1F0}\u{1F1FC}","Kyrgyzstan":"\u{1F1F0}\u{1F1EC}","Laos":"\u{1F1F1}\u{1F1E6}",
  "Latvia":"\u{1F1F1}\u{1F1FB}","Lebanon":"\u{1F1F1}\u{1F1E7}","Lesotho":"\u{1F1F1}\u{1F1F8}",
  "Liberia":"\u{1F1F1}\u{1F1F7}","Libya":"\u{1F1F1}\u{1F1FE}","Lithuania":"\u{1F1F1}\u{1F1F9}",
  "Luxembourg":"\u{1F1F1}\u{1F1FA}","Madagascar":"\u{1F1F2}\u{1F1EC}","Malawi":"\u{1F1F2}\u{1F1FC}",
  "Malaysia":"\u{1F1F2}\u{1F1FE}","Maldives":"\u{1F1F2}\u{1F1FB}","Mali":"\u{1F1F2}\u{1F1F1}",
  "Malta":"\u{1F1F2}\u{1F1F9}","Mauritania":"\u{1F1F2}\u{1F1F7}","Mauritius":"\u{1F1F2}\u{1F1FA}",
  "Mexico":"\u{1F1F2}\u{1F1FD}","Moldova":"\u{1F1F2}\u{1F1E9}","Mongolia":"\u{1F1F2}\u{1F1F3}",
  "Montenegro":"\u{1F1F2}\u{1F1EA}","Morocco":"\u{1F1F2}\u{1F1E6}","Mozambique":"\u{1F1F2}\u{1F1FF}",
  "Myanmar":"\u{1F1F2}\u{1F1F2}","Namibia":"\u{1F1F3}\u{1F1E6}","Nepal":"\u{1F1F3}\u{1F1F5}",
  "Netherlands":"\u{1F1F3}\u{1F1F1}","New Zealand":"\u{1F1F3}\u{1F1FF}","Nicaragua":"\u{1F1F3}\u{1F1EE}",
  "Niger":"\u{1F1F3}\u{1F1EA}","Nigeria":"\u{1F1F3}\u{1F1EC}","North Korea":"\u{1F1F0}\u{1F1F5}",
  "North Macedonia":"\u{1F1F2}\u{1F1F0}","Norway":"\u{1F1F3}\u{1F1F4}","Oman":"\u{1F1F4}\u{1F1F2}",
  "Pakistan":"\u{1F1F5}\u{1F1F0}","Palestine":"\u{1F1F5}\u{1F1F8}","Panama":"\u{1F1F5}\u{1F1E6}",
  "Papua New Guinea":"\u{1F1F5}\u{1F1EC}","Paraguay":"\u{1F1F5}\u{1F1FE}","Peru":"\u{1F1F5}\u{1F1EA}",
  "Philippines":"\u{1F1F5}\u{1F1ED}","Poland":"\u{1F1F5}\u{1F1F1}","Portugal":"\u{1F1F5}\u{1F1F9}",
  "Qatar":"\u{1F1F6}\u{1F1E6}","Romania":"\u{1F1F7}\u{1F1F4}","Russia":"\u{1F1F7}\u{1F1FA}",
  "Rwanda":"\u{1F1F7}\u{1F1FC}","Samoa":"\u{1F1FC}\u{1F1F8}","Saudi Arabia":"\u{1F1F8}\u{1F1E6}",
  "Senegal":"\u{1F1F8}\u{1F1F3}","Serbia":"\u{1F1F7}\u{1F1F8}","Seychelles":"\u{1F1F8}\u{1F1E8}",
  "Sierra Leone":"\u{1F1F8}\u{1F1F1}","Singapore":"\u{1F1F8}\u{1F1EC}","Slovakia":"\u{1F1F8}\u{1F1F0}",
  "Slovenia":"\u{1F1F8}\u{1F1EE}","Solomon Islands":"\u{1F1F8}\u{1F1E7}","Somalia":"\u{1F1F8}\u{1F1F4}",
  "South Africa":"\u{1F1FF}\u{1F1E6}","South Korea":"\u{1F1F0}\u{1F1F7}","South Sudan":"\u{1F1F8}\u{1F1F8}",
  "Spain":"\u{1F1EA}\u{1F1F8}","Sri Lanka":"\u{1F1F1}\u{1F1F0}","Sudan":"\u{1F1F8}\u{1F1E9}",
  "Suriname":"\u{1F1F8}\u{1F1F7}","Sweden":"\u{1F1F8}\u{1F1EA}","Switzerland":"\u{1F1E8}\u{1F1ED}",
  "Syria":"\u{1F1F8}\u{1F1FE}","Taiwan":"\u{1F1F9}\u{1F1FC}","Tajikistan":"\u{1F1F9}\u{1F1EF}",
  "Tanzania":"\u{1F1F9}\u{1F1FF}","Thailand":"\u{1F1F9}\u{1F1ED}","Timor-Leste":"\u{1F1F9}\u{1F1F1}",
  "Togo":"\u{1F1F9}\u{1F1EC}","Tonga":"\u{1F1F9}\u{1F1F4}","Trinidad":"\u{1F1F9}\u{1F1F9}",
  "Tunisia":"\u{1F1F9}\u{1F1F3}","Turkey":"\u{1F1F9}\u{1F1F7}","Turkmenistan":"\u{1F1F9}\u{1F1F2}",
  "UAE":"\u{1F1E6}\u{1F1EA}","Uganda":"\u{1F1FA}\u{1F1EC}","Ukraine":"\u{1F1FA}\u{1F1E6}",
  "United Kingdom":"\u{1F1EC}\u{1F1E7}","United States":"\u{1F1FA}\u{1F1F8}","Uruguay":"\u{1F1FA}\u{1F1FE}",
  "Uzbekistan":"\u{1F1FA}\u{1F1FF}","Vanuatu":"\u{1F1FB}\u{1F1FA}","Venezuela":"\u{1F1FB}\u{1F1EA}",
  "Vietnam":"\u{1F1FB}\u{1F1F3}","Yemen":"\u{1F1FE}\u{1F1EA}","Zambia":"\u{1F1FF}\u{1F1F2}",
  "Zimbabwe":"\u{1F1FF}\u{1F1FC}"
};

// =====================================================================
//  HELPERS
// =====================================================================
function dEscapeHtml(s) {
  return (s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function dStripTags(s) {
  return (s || "").replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim();
}

function dRelativeTime(iso) {
  var then = new Date(iso).getTime();
  var now = Date.now();
  var diff = Math.max(0, Math.floor((now - then) / 1000));
  if (diff < 60) return diff + "s ago";
  if (diff < 3600) return Math.floor(diff / 60) + "m ago";
  if (diff < 86400) return Math.floor(diff / 3600) + "h ago";
  return Math.floor(diff / 86400) + "d ago";
}

// Country canonical mapping (key -> display name)
var dCanonicalMap = {
  "drc":"DRC","congo":"DRC","kinshasa":"DRC","goma":"DRC",
  "south sudan":"South Sudan","juba":"South Sudan",
  "south africa":"South Africa","johannesburg":"South Africa","cape town":"South Africa","pretoria":"South Africa",
  "ivory coast":"Ivory Coast","abidjan":"Ivory Coast",
  "burkina faso":"Burkina Faso","ouagadougou":"Burkina Faso",
  "central african republic":"Central African Republic","car":"Central African Republic","bangui":"Central African Republic",
  "equatorial guinea":"Equatorial Guinea","malabo":"Equatorial Guinea",
  "uae":"UAE","united arab emirates":"UAE","dubai":"UAE","abu dhabi":"UAE",
  "saudi arabia":"Saudi Arabia","riyadh":"Saudi Arabia","jeddah":"Saudi Arabia",
  "north korea":"North Korea","pyongyang":"North Korea",
  "south korea":"South Korea","korea":"South Korea","seoul":"South Korea",
  "sri lanka":"Sri Lanka","colombo":"Sri Lanka",
  "new zealand":"New Zealand","wellington":"New Zealand","auckland":"New Zealand","christchurch":"New Zealand",
  "papua new guinea":"Papua New Guinea","png":"Papua New Guinea","port moresby":"Papua New Guinea",
  "solomon islands":"Solomon Islands","honiara":"Solomon Islands",
  "united kingdom":"United Kingdom","uk":"United Kingdom","britain":"United Kingdom","england":"United Kingdom","london":"United Kingdom",
  "united states":"United States","usa":"United States","us":"United States","american":"United States","washington":"United States","new york":"United States","los angeles":"United States","california":"United States","florida":"United States","texas":"United States","louisiana":"United States","new orleans":"United States","puerto rico":"United States","hawaii":"United States","alaska":"United States",
  "dominican republic":"Dominican Republic","santo domingo":"Dominican Republic",
  "el salvador":"El Salvador",
  "costa rica":"Costa Rica",
  "north macedonia":"North Macedonia","macedonia":"North Macedonia",
  "czech republic":"Czech Republic","czechia":"Czech Republic",
  "bosnia":"Bosnia","sarajevo":"Bosnia",
  "timor-leste":"Timor-Leste","east timor":"Timor-Leste",
  "guinea-bissau":"Guinea-Bissau","bissau":"Guinea-Bissau",
  "cape verde":"Cape Verde",
  "eswatini":"Eswatini","swaziland":"Eswatini",
  "myanmar":"Myanmar","burma":"Myanmar","burmese":"Myanmar",
  "iranian":"Iran","iraqi":"Iraq","syrian":"Syria","yemeni":"Yemen",
  "israeli":"Israel","palestinian":"Palestine","lebanese":"Lebanon",
  "jordanian":"Jordan","saudi":"Saudi Arabia","omani":"Oman",
  "kuwaiti":"Kuwait","qatari":"Qatar","bahraini":"Bahrain",
  "turkish":"Turkey","egyptian":"Egypt","chinese":"China",
  "indian":"India","pakistani":"Pakistan","bangladeshi":"Bangladesh",
  "nepali":"Nepal","nepalese":"Nepal","bhutanese":"Bhutan",
  "sri lankan":"Sri Lanka","thai":"Thailand","vietnamese":"Vietnam",
  "cambodian":"Cambodia","laotian":"Laos","malaysian":"Malaysia",
  "indonesian":"Indonesia","filipino":"Philippines","philippine":"Philippines",
  "singaporean":"Singapore","japanese":"Japan","korean":"South Korea",
  "mongolian":"Mongolia","taiwanese":"Taiwan","afghan":"Afghanistan",
  "kazakh":"Kazakhstan","uzbek":"Uzbekistan","kyrgyz":"Kyrgyzstan",
  "tajik":"Tajikistan","irish":"Ireland","french":"France",
  "german":"Germany","spanish":"Spain","portuguese":"Portugal",
  "italian":"Italy","greek":"Greece","dutch":"Netherlands",
  "belgian":"Belgium","swiss":"Switzerland","austrian":"Austria",
  "polish":"Poland","slovak":"Slovakia","hungarian":"Hungary",
  "romanian":"Romania","bulgarian":"Bulgaria","serbian":"Serbia",
  "croatian":"Croatia","slovenian":"Slovenia","albanian":"Albania",
  "ukrainian":"Ukraine","belarusian":"Belarus","russian":"Russia",
  "norwegian":"Norway","swedish":"Sweden","finnish":"Finland",
  "danish":"Denmark","icelandic":"Iceland","estonian":"Estonia",
  "latvian":"Latvia","lithuanian":"Lithuania","cypriot":"Cyprus",
  "maltese":"Malta","canadian":"Canada","mexican":"Mexico",
  "guatemalan":"Guatemala","honduran":"Honduras","salvadoran":"El Salvador",
  "nicaraguan":"Nicaragua","panamanian":"Panama","cuban":"Cuba",
  "haitian":"Haiti","jamaican":"Jamaica","colombian":"Colombia",
  "venezuelan":"Venezuela","ecuadorian":"Ecuador","peruvian":"Peru",
  "bolivian":"Bolivia","brazilian":"Brazil","argentine":"Argentina",
  "chilean":"Chile","australian":"Australia","fijian":"Fiji",
  "samoan":"Samoa","tongan":"Tonga","nigerian":"Nigeria",
  "kenyan":"Kenya","ethiopian":"Ethiopia","somali":"Somalia",
  "sudanese":"Sudan","ugandan":"Uganda","tanzanian":"Tanzania",
  "rwandan":"Rwanda","malian":"Mali","chadian":"Chad",
  "cameroonian":"Cameroon","mozambican":"Mozambique","malagasy":"Madagascar",
  "malawian":"Malawi","zambian":"Zambia","zimbabwean":"Zimbabwe",
  "south african":"South Africa","angolan":"Angola","namibian":"Namibia",
  "ghanaian":"Ghana","senegalese":"Senegal","liberian":"Liberia",
  "moroccan":"Morocco","algerian":"Algeria","tunisian":"Tunisia",
  "libyan":"Libya","eritrean":"Eritrea","georgian":"Georgia",
  "armenian":"Armenia","azerbaijani":"Azerbaijan","moldovan":"Moldova",
  "british":"United Kingdom"
};

function dKeyToCanonical(key) {
  if (dCanonicalMap[key]) return dCanonicalMap[key];
  // default - title case
  return key.split(" ").map(function (w) {
    return w.charAt(0).toUpperCase() + w.slice(1);
  }).join(" ");
}

function dCountryFromText(text) {
  if (!text) return null;
  var t = text.toLowerCase();
  var keys = Object.keys(dCentroids).sort(function (a, b) { return b.length - a.length; });
  for (var i = 0; i < keys.length; i++) {
    var k = keys[i];
    var pat = new RegExp("\\b" + k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\b", "i");
    if (pat.test(t)) {
      return dKeyToCanonical(k);
    }
  }
  return null;
}

function dCountryFromPost(post) {
  // 1) check tag names if embedded
  try {
    var terms = post._embedded && post._embedded["wp:term"];
    if (terms && terms.length) {
      for (var g = 0; g < terms.length; g++) {
        var group = terms[g];
        for (var i = 0; i < group.length; i++) {
          var name = group[i] && group[i].name;
          if (!name) continue;
          if (dFlags[name]) return name;
          var fromName = dCountryFromText(name);
          if (fromName) return fromName;
        }
      }
    }
  } catch (e) { /* ignore */ }
  // 2) fall back to title text scan
  var title = post.title && (post.title.rendered || post.title);
  return dCountryFromText(dStripTags(title));
}

// =====================================================================
//  CLUSTER EXPANSION (fan-out on click)
// =====================================================================
var dOriginalFeatures = [];
var dExpandedKey = null;
var D_SPREAD_RADIUS = 4;

function dSpread(features, centerLng, centerLat) {
  if (features.length === 1) return features;
  return features.map(function(f, i) {
    var angle = (2 * Math.PI * i / features.length) - Math.PI / 2;
    var newLng = centerLng + D_SPREAD_RADIUS * Math.cos(angle);
    var newLat = centerLat + D_SPREAD_RADIUS * Math.sin(angle);
    newLat = Math.max(-80, Math.min(80, newLat));
    return {type:"Feature",geometry:{type:"Point",coordinates:[newLng,newLat]},properties:f.properties};
  });
}

function dCollapseAll() {
  dExpandedKey = null;
  if (dMap.getSource("d-lines")) dMap.getSource("d-lines").setData({type:"FeatureCollection",features:[]});
  if (dMap.getSource("dpts")) dMap.getSource("dpts").setData({type:"FeatureCollection",features:dOriginalFeatures});
}

function dExpandCluster(countryKey) {
  var clusterFeatures = dOriginalFeatures.filter(function(f){return f.properties.countryKey===countryKey;});
  var otherFeatures = dOriginalFeatures.filter(function(f){return f.properties.countryKey!==countryKey;});
  var center = clusterFeatures[0].geometry.coordinates;
  var spread = dSpread(clusterFeatures, center[0], center[1]);
  dExpandedKey = countryKey;
  var lineFeatures = spread.map(function(f){return{type:"Feature",geometry:{type:"LineString",coordinates:[center,f.geometry.coordinates]}};});
  dMap.getSource("d-lines").setData({type:"FeatureCollection",features:lineFeatures});
  dMap.getSource("dpts").setData({type:"FeatureCollection",features:otherFeatures.concat(spread)});
}

function dShowPopup(coords, props) {
  var flag = dFlags[props.country] || "";
  var color = dTypeColors[props.type] || dTypeColors.other;
  var typeLabel = dTypeLabels[props.type] || dTypeLabels.other;
  new maplibregl.Popup({closeButton:false,offset:10})
    .setLngLat(coords)
    .setHTML(
      "<div style='font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;min-width:200px;'>" +
        "<div style='font-size:9px;text-transform:uppercase;letter-spacing:0.15em;color:" + color + ";font-weight:700;margin-bottom:4px;'>" + typeLabel + "</div>" +
        "<div style='font-size:13px;font-weight:500;color:#111;line-height:1.4;margin-bottom:6px;'>" + dEscapeHtml(props.title || "") + "</div>" +
        "<div style='font-size:10px;color:#666;margin-bottom:6px;'>" + flag + " " + dEscapeHtml(props.country || "") + "</div>" +
        "<a href='" + (props.link || "#") + "' target='_blank' rel='noopener' style='font-size:11px;color:#ef4444;text-decoration:none;'>Read full report &rarr;</a>" +
      "</div>"
    )
    .addTo(dMap);
}

// =====================================================================
//  STATS PANEL
// =====================================================================
function dRenderStats(events) {
  var counts = {};
  Object.keys(dTypeColors).forEach(function(k){ counts[k] = 0; });
  events.forEach(function (e) { counts[e.type] = (counts[e.type] || 0) + 1; });

  var box = document.getElementById("d-stats");
  if (!box) return;

  var types = ["earthquake","flood","storm","wildfire","volcano","tsunami","landslide","drought","heatwave","other"];
  var rows = types.map(function (t) {
    return (
      "<div class='d-stat-row' data-type='" + t + "'>" +
        "<span class='d-stat-dot' style='background:" + dTypeColors[t] + "'></span>" +
        "<span class='d-stat-label'>" + dTypeLabels[t] + "</span>" +
        "<span class='d-stat-value'>" + counts[t] + "</span>" +
      "</div>"
    );
  }).join("");

  box.innerHTML =
    "<div class='d-stat-total'>" +
      "<div class='d-stat-total-num'>" + events.length + "</div>" +
      "<div class='d-stat-total-label'>Tracked Events</div>" +
    "</div>" +
    "<div class='d-stat-list'>" + rows + "</div>";
}

function dRenderCountryList(events) {
  var box = document.getElementById("d-country-list");
  if (!box) return;
  var grouped = {};
  events.forEach(function (e) {
    if (!e.country) return;
    grouped[e.country] = (grouped[e.country] || 0) + 1;
  });
  var arr = Object.keys(grouped).sort().map(function (c) {
    return { country: c, n: grouped[c] };
  });
  if (!arr.length) {
    box.innerHTML = "<div class='d-empty'>No country data yet</div>";
    return;
  }
  box.innerHTML = arr.map(function (r) {
    return (
      "<button class='d-country-btn' data-country='" + dEscapeHtml(r.country) + "'>" +
        "<span class='d-country-flag'>" + (dFlags[r.country] || "\u{1F3F3}") + "</span>" +
        "<span class='d-country-name'>" + dEscapeHtml(r.country) + "</span>" +
        "<span class='d-country-count'>" + r.n + "</span>" +
      "</button>"
    );
  }).join("");

  var btns = box.querySelectorAll(".d-country-btn");
  btns.forEach(function (b) {
    b.addEventListener("click", function () {
      var c = b.getAttribute("data-country");
      dFlyToCountry(c);
    });
  });
}

function dFlyToCountry(country) {
  if (!dMap || !country) return;
  var key = country.toLowerCase();
  var c = dCentroids[key];
  if (!c) return;
  dMap.flyTo({ center: c, zoom: 4.4, speed: 1.1 });
}

// =====================================================================
//  NEWS FEED (right panel)
// =====================================================================
function dRenderNewsFeed(posts) {
  var box = document.getElementById("d-news");
  if (!box) return;
  if (!posts.length) {
    box.innerHTML = "<div class='d-empty'>No reports yet</div>";
    return;
  }
  box.innerHTML = posts.map(function (p) {
    var title = dStripTags(p.title.rendered || "");
    var country = dCountryFromPost(p);
    var type = dDetectType(title);
    var color = dTypeColors[type];
    var excerpt = dStripTags(p.excerpt && p.excerpt.rendered || "").slice(0, 160);
    return (
      "<a class='d-news-item' href='" + p.link + "' target='_blank' rel='noopener'>" +
        "<div class='d-news-bar' style='background:" + color + "'></div>" +
        "<div class='d-news-body'>" +
          "<div class='d-news-meta'>" +
            "<span class='d-news-type' style='color:" + color + "'>" + dTypeLabels[type] + "</span>" +
            "<span class='d-news-flag'>" + (dFlags[country] || "") + "</span>" +
            "<span class='d-news-country'>" + (country || "Global") + "</span>" +
            "<span class='d-news-time'>" + dRelativeTime(p.date_gmt + "Z") + "</span>" +
          "</div>" +
          "<div class='d-news-title'>" + dEscapeHtml(title) + "</div>" +
          (excerpt ? "<div class='d-news-excerpt'>" + dEscapeHtml(excerpt) + "\u2026</div>" : "") +
        "</div>" +
      "</a>"
    );
  }).join("");
}

// =====================================================================
//  TICKER
// =====================================================================
function dRenderTicker(events) {
  var box = document.getElementById("d-ticker");
  if (!box) return;
  if (!events.length) {
    box.innerHTML = "<div class='d-ticker-track' style='color: var(--text-muted);'>Awaiting events...</div>";
    return;
  }
  var items = events.slice(0, 10).map(function (e) {
    var color = dTypeColors[e.type];
    return (
      "<span class='d-ticker-item'>" +
        "<span class='d-ticker-dot' style='background:" + color + "'></span>" +
        "<strong style='color:" + color + "'>" + dTypeLabels[e.type].toUpperCase() + "</strong>" +
        " &middot; " + (dFlags[e.country] || "") + " " + dEscapeHtml(e.country || "Global") +
        " &middot; " + dEscapeHtml(e.title.slice(0, 90)) +
      "</span>"
    );
  }).join("<span class='d-ticker-sep'>\u2022</span>");
  box.innerHTML = "<div class='d-ticker-track'>" + items + "<span class='d-ticker-sep'>\u2022</span>" + items + "</div>";
}

// =====================================================================
//  UTC CLOCK
// =====================================================================
function dStartClock() {
  var el = document.getElementById("d-clock");
  if (!el) return;
  function pad(n){ return n < 10 ? "0" + n : "" + n; }
  function tick() {
    var d = new Date();
    el.textContent = pad(d.getUTCHours()) + ":" + pad(d.getUTCMinutes()) + ":" + pad(d.getUTCSeconds()) + " UTC";
  }
  tick();
  setInterval(tick, 1000);
}

// =====================================================================
//  MAP SOURCES / LAYERS / INTERACTION
// =====================================================================
dMap.on("load", function() {
  dMap.addSource("d-lines", {type:"geojson",data:{type:"FeatureCollection",features:[]}});
  dMap.addLayer({
    id:"d-spider-legs",
    type:"line",
    source:"d-lines",
    paint:{"line-color":"rgba(255,255,255,0.5)","line-width":1,"line-dasharray":[2,2]}
  });
  dMap.addSource("dpts", {type:"geojson",data:{type:"FeatureCollection",features:[]}});
  dMap.addLayer({
    id:"dglow",
    type:"circle",
    source:"dpts",
    paint:{"circle-radius":16,"circle-color":["get","color"],"circle-opacity":0.18,"circle-blur":1}
  });
  dMap.addLayer({
    id:"ddots",
    type:"circle",
    source:"dpts",
    paint:{
      "circle-radius":7,
      "circle-color":["get","color"],
      "circle-opacity":0.9,
      "circle-stroke-width":1.5,
      "circle-stroke-color":"rgba(255,255,255,0.4)"
    }
  });

  dMap.on("click", "ddots", function(e) {
    e.originalEvent.stopPropagation();
    var props = e.features[0].properties;
    var coords = e.features[0].geometry.coordinates.slice();
    var countryKey = props.countryKey;
    var clusterSize = dOriginalFeatures.filter(function(f){return f.properties.countryKey===countryKey;}).length;
    if (dExpandedKey === countryKey) { dShowPopup(coords, props); return; }
    if (clusterSize > 1) { dExpandCluster(countryKey); return; }
    dShowPopup(coords, props);
  });

  dMap.on("click", function(e) {
    var dot = dMap.queryRenderedFeatures(e.point, {layers:["ddots"]});
    if (!dot.length && dExpandedKey) dCollapseAll();
  });

  dMap.on("mouseenter", "ddots", function(){dMap.getCanvas().style.cursor="pointer";});
  dMap.on("mouseleave", "ddots", function(){dMap.getCanvas().style.cursor="";});

  dLoadData();
  setInterval(dLoadData, 5 * 60 * 1000);
});

// =====================================================================
//  DATA LOAD
// =====================================================================
var dAllEvents = [];
var dCurrentTypeFilter = "all";

function dLoadData() {
  var mapUrl  = WP_BASE + "/wp-json/wp/v2/posts?categories=" + CATEGORY_ID + "&per_page=" + MAP_LIMIT + "&orderby=date&order=desc&_embed=1";
  var feedUrl = WP_BASE + "/wp-json/wp/v2/posts?categories=" + CATEGORY_ID + "&per_page=" + FEED_LIMIT + "&orderby=date&order=desc&_embed=1";

  fetch(mapUrl).then(function (r) { return r.json(); }).then(function (posts) {
    if (!Array.isArray(posts)) { posts = []; }
    dAllEvents = posts.map(function (p) {
      var title = dStripTags(p.title.rendered || "");
      var country = dCountryFromPost(p);
      var type = dDetectType(title);
      var coords = null;
      if (country) {
        var key = country.toLowerCase();
        coords = dCentroids[key] || null;
      }
      return {
        id: p.id,
        title: title,
        country: country,
        countryKey: country ? country.toLowerCase() : null,
        type: type,
        coords: coords,
        date: p.date_gmt + "Z",
        link: p.link
      };
    });

    dApplyTypeFilter(dCurrentTypeFilter);
    dRenderStats(dAllEvents);
    dRenderCountryList(dAllEvents);
    dRenderTicker(dAllEvents);
  }).catch(function (e) {
    console.error("[disaster-dash] map fetch failed", e);
  });

  fetch(feedUrl).then(function (r) { return r.json(); }).then(function (posts) {
    if (!Array.isArray(posts)) { posts = []; }
    dRenderNewsFeed(posts);
  }).catch(function (e) {
    console.error("[disaster-dash] feed fetch failed", e);
  });
}

// =====================================================================
//  TYPE FILTER BUTTONS
// =====================================================================
function dApplyTypeFilter(filterType) {
  dCurrentTypeFilter = filterType;
  var filtered;
  if (filterType === "all") {
    filtered = dAllEvents.filter(function(e){ return e.coords; });
  } else {
    filtered = dAllEvents.filter(function(e){ return e.coords && e.type === filterType; });
  }

  // build GeoJSON features
  var features = filtered.map(function(e) {
    return {
      type: "Feature",
      geometry: {type: "Point", coordinates: [e.coords[0], e.coords[1]]},
      properties: {
        title: e.title,
        country: e.country || "Unknown",
        countryKey: e.countryKey || "_",
        type: e.type,
        color: dTypeColors[e.type] || dTypeColors.other,
        link: e.link
      }
    };
  });

  dOriginalFeatures = features;
  dExpandedKey = null;
  if (dMap.getSource("d-lines")) {
    dMap.getSource("d-lines").setData({type:"FeatureCollection",features:[]});
  }
  if (dMap.getSource("dpts")) {
    dMap.getSource("dpts").setData({type:"FeatureCollection",features:features});
  }
}

// Bind filter buttons
var filterBtns = document.querySelectorAll(".d-fbtn");
filterBtns.forEach(function(btn) {
  btn.addEventListener("click", function() {
    filterBtns.forEach(function(b){b.classList.remove("active");});
    this.classList.add("active");
    var filterText = this.getAttribute("data-type") || this.textContent.trim().toLowerCase();
    dApplyTypeFilter(filterText);
  });
});

// =====================================================================
//  BOOT
// =====================================================================
dStartClock();
