var cMap = new maplibregl.Map({
  container: "c-map",
  style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
  center: [20, 15],
  zoom: 2.2,
  attributionControl: false
});

cMap.addControl(new maplibregl.AttributionControl({compact: true}), "bottom-right");

var cCentroids = {
  "afghanistan":[65.0,33.9],"albania":[20.2,41.2],"algeria":[2.6,28.0],"angola":[17.9,-11.2],
  "argentina":[-63.6,-38.4],"armenia":[45.0,40.1],"australia":[133.8,-25.3],"austria":[14.6,47.5],
  "azerbaijan":[47.6,40.1],"bahrain":[50.6,26.0],"bangladesh":[90.4,23.7],"belarus":[28.0,53.7],
  "belgium":[4.5,50.5],"belize":[-88.5,17.2],"benin":[2.3,9.3],"bolivia":[-64.7,-16.3],
  "botswana":[24.7,-22.3],"brazil":[-51.9,-14.2],"bulgaria":[25.5,42.7],"burkina faso":[-1.6,12.4],
  "burundi":[29.9,-3.4],"cambodia":[104.9,12.6],"cameroon":[12.4,3.9],"canada":[-96.8,60.0],
  "central african republic":[20.9,6.6],"car":[20.9,6.6],"chad":[18.7,15.5],"chile":[-71.5,-35.7],
  "china":[104.2,35.9],"colombia":[-74.3,4.1],"comoros":[43.9,-11.9],"congo":[15.8,-0.2],
  "costa rica":[-83.8,9.7],"croatia":[15.2,45.1],"cuba":[-79.5,21.5],"cyprus":[33.4,35.1],
  "czech republic":[15.5,49.8],"denmark":[9.5,56.3],"djibouti":[42.6,11.8],
  "dr congo":[24.0,-2.9],"drc":[24.0,-2.9],"democratic republic of congo":[24.0,-2.9],
  "ecuador":[-78.1,-1.8],"egypt":[30.8,26.8],"el salvador":[-88.9,13.8],"eritrea":[39.8,15.2],
  "estonia":[25.0,58.6],"ethiopia":[40.5,9.1],"fiji":[178.1,-17.7],"finland":[26.0,64.0],
  "france":[2.2,46.2],"gabon":[11.6,-0.8],"gambia":[-15.3,13.4],"georgia":[43.4,42.3],
  "germany":[10.5,51.2],"ghana":[-1.0,7.9],"greece":[21.8,39.1],"guatemala":[-90.2,15.8],
  "guinea":[-11.3,11.0],"guyana":[-59.0,5.0],"haiti":[-72.3,19.0],"honduras":[-86.2,14.8],
  "hungary":[19.5,47.2],"iceland":[-18.7,64.9],"india":[78.7,20.6],"indonesia":[113.9,-0.8],
  "iran":[53.7,32.4],"iraq":[43.7,33.2],"ireland":[-8.2,53.4],"israel":[34.9,31.0],
  "italy":[12.6,42.5],"jamaica":[-77.3,18.1],"japan":[138.3,36.2],"jordan":[37.2,30.6],
  "kazakhstan":[66.9,48.0],"kenya":[37.9,0.0],"kuwait":[47.5,29.3],"kyrgyzstan":[74.8,41.2],
  "laos":[103.0,18.2],"latvia":[24.6,56.9],"lebanon":[35.9,33.9],"liberia":[-9.4,6.4],
  "libya":[17.2,26.3],"lithuania":[23.9,55.2],"luxembourg":[6.1,49.8],"madagascar":[46.9,-18.8],
  "malawi":[34.3,-13.2],"malaysia":[109.7,4.2],"maldives":[73.2,3.2],"mali":[-2.0,17.6],
  "malta":[14.4,35.9],"mauritania":[-10.9,20.3],"mauritius":[57.6,-20.3],"mexico":[-102.6,23.6],
  "moldova":[28.4,47.4],"mongolia":[103.8,46.9],"montenegro":[19.4,42.7],"morocco":[-7.1,31.8],
  "mozambique":[35.5,-18.7],"myanmar":[95.9,17.1],"burma":[95.9,17.1],"namibia":[18.5,-22.0],
  "nepal":[84.1,28.4],"netherlands":[5.3,52.1],"new zealand":[172.0,-41.5],"nicaragua":[-85.2,12.9],
  "niger":[8.1,17.6],"nigeria":[8.7,9.1],"north korea":[127.5,40.3],"norway":[8.5,60.5],
  "oman":[57.5,21.5],"pakistan":[69.3,30.4],"palestine":[35.2,31.9],"panama":[-80.8,8.5],
  "papua new guinea":[143.9,-6.3],"paraguay":[-58.4,-23.4],"peru":[-75.0,-9.2],
  "philippines":[122.9,12.9],"poland":[19.1,52.1],"portugal":[-8.2,39.4],"qatar":[51.2,25.4],
  "romania":[24.9,45.9],"russia":[105.3,61.5],"rwanda":[29.9,-2.0],"saudi arabia":[45.1,24.0],
  "senegal":[-14.5,14.5],"serbia":[21.0,44.0],"sierra leone":[-11.8,8.5],"singapore":[103.8,1.4],
  "slovakia":[19.7,48.7],"slovenia":[14.8,46.1],"somalia":[46.2,6.1],"south africa":[25.1,-29.0],
  "south korea":[127.8,35.9],"south sudan":[31.3,6.9],"spain":[-3.7,40.5],"sri lanka":[80.7,7.9],
  "sudan":[29.9,12.9],"sweden":[18.6,60.1],"switzerland":[8.2,46.8],"syria":[38.3,34.8],
  "taiwan":[120.9,23.7],"tajikistan":[71.3,38.9],"tanzania":[34.9,-6.4],"thailand":[101.0,15.9],
  "togo":[0.8,8.6],"trinidad and tobago":[-61.2,10.7],"tunisia":[9.0,33.9],"turkey":[35.2,38.9],
  "turkmenistan":[59.6,39.0],"uganda":[32.3,1.4],"ukraine":[31.2,48.4],"uae":[53.8,23.4],
  "united arab emirates":[53.8,23.4],"united kingdom":[-3.4,55.4],"uk":[-3.4,55.4],
  "united states":[-95.7,37.1],"usa":[-95.7,37.1],"uruguay":[-55.8,-32.5],
  "uzbekistan":[63.9,41.4],"venezuela":[-66.6,6.4],"vietnam":[108.3,14.1],"yemen":[47.6,15.6],
  "zambia":[27.8,-13.1],"zimbabwe":[30.0,-19.0],"gaza":[34.4,31.4],"west bank":[35.2,31.9],
  "hormuz":[56.0,26.5],"tehran":[51.4,35.7],"washington":[-77.0,38.9],"moscow":[37.6,55.8]
};

var cTypeColors = {armed:"#ef4444",unrest:"#fb923c",coup:"#f59e0b",displacement:"#a78bfa",default:"#ef4444"};

var cFlags = {
  "afghanistan":"\u{1F1E6}\u{1F1EB}","albania":"\u{1F1E6}\u{1F1F1}","algeria":"\u{1F1E9}\u{1F1FF}","angola":"\u{1F1E6}\u{1F1F4}",
  "argentina":"\u{1F1E6}\u{1F1F7}","armenia":"\u{1F1E6}\u{1F1F2}","australia":"\u{1F1E6}\u{1F1FA}","austria":"\u{1F1E6}\u{1F1F9}",
  "azerbaijan":"\u{1F1E6}\u{1F1FF}","bahrain":"\u{1F1E7}\u{1F1ED}","bangladesh":"\u{1F1E7}\u{1F1E9}","belarus":"\u{1F1E7}\u{1F1FE}",
  "belgium":"\u{1F1E7}\u{1F1EA}","belize":"\u{1F1E7}\u{1F1FF}","benin":"\u{1F1E7}\u{1F1EF}","bolivia":"\u{1F1E7}\u{1F1F4}",
  "botswana":"\u{1F1E7}\u{1F1FC}","brazil":"\u{1F1E7}\u{1F1F7}","bulgaria":"\u{1F1E7}\u{1F1EC}","burkina faso":"\u{1F1E7}\u{1F1EB}",
  "burundi":"\u{1F1E7}\u{1F1EE}","cambodia":"\u{1F1F0}\u{1F1ED}","cameroon":"\u{1F1E8}\u{1F1F2}","canada":"\u{1F1E8}\u{1F1E6}",
  "central african republic":"\u{1F1E8}\u{1F1EB}","car":"\u{1F1E8}\u{1F1EB}","chad":"\u{1F1F9}\u{1F1E9}","chile":"\u{1F1E8}\u{1F1F1}",
  "china":"\u{1F1E8}\u{1F1F3}","colombia":"\u{1F1E8}\u{1F1F4}","comoros":"\u{1F1F0}\u{1F1F2}","congo":"\u{1F1E8}\u{1F1EC}",
  "costa rica":"\u{1F1E8}\u{1F1F7}","croatia":"\u{1F1ED}\u{1F1F7}","cuba":"\u{1F1E8}\u{1F1FA}","cyprus":"\u{1F1E8}\u{1F1FE}",
  "czech republic":"\u{1F1E8}\u{1F1FF}","denmark":"\u{1F1E9}\u{1F1F0}","djibouti":"\u{1F1E9}\u{1F1EF}",
  "dr congo":"\u{1F1E8}\u{1F1E9}","drc":"\u{1F1E8}\u{1F1E9}","democratic republic of congo":"\u{1F1E8}\u{1F1E9}",
  "ecuador":"\u{1F1EA}\u{1F1E8}","egypt":"\u{1F1EA}\u{1F1EC}","el salvador":"\u{1F1F8}\u{1F1FB}","eritrea":"\u{1F1EA}\u{1F1F7}",
  "estonia":"\u{1F1EA}\u{1F1EA}","ethiopia":"\u{1F1EA}\u{1F1F9}","fiji":"\u{1F1EB}\u{1F1EF}","finland":"\u{1F1EB}\u{1F1EE}",
  "france":"\u{1F1EB}\u{1F1F7}","gabon":"\u{1F1EC}\u{1F1E6}","gambia":"\u{1F1EC}\u{1F1F2}","georgia":"\u{1F1EC}\u{1F1EA}",
  "germany":"\u{1F1E9}\u{1F1EA}","ghana":"\u{1F1EC}\u{1F1ED}","greece":"\u{1F1EC}\u{1F1F7}","guatemala":"\u{1F1EC}\u{1F1F9}",
  "guinea":"\u{1F1EC}\u{1F1F3}","guyana":"\u{1F1EC}\u{1F1FE}","haiti":"\u{1F1ED}\u{1F1F9}","honduras":"\u{1F1ED}\u{1F1F3}",
  "hungary":"\u{1F1ED}\u{1F1FA}","iceland":"\u{1F1EE}\u{1F1F8}","india":"\u{1F1EE}\u{1F1F3}","indonesia":"\u{1F1EE}\u{1F1E9}",
  "iran":"\u{1F1EE}\u{1F1F7}","iraq":"\u{1F1EE}\u{1F1F6}","ireland":"\u{1F1EE}\u{1F1EA}","israel":"\u{1F1EE}\u{1F1F1}",
  "italy":"\u{1F1EE}\u{1F1F9}","jamaica":"\u{1F1EF}\u{1F1F2}","japan":"\u{1F1EF}\u{1F1F5}","jordan":"\u{1F1EF}\u{1F1F4}",
  "kazakhstan":"\u{1F1F0}\u{1F1FF}","kenya":"\u{1F1F0}\u{1F1EA}","kuwait":"\u{1F1F0}\u{1F1FC}","kyrgyzstan":"\u{1F1F0}\u{1F1EC}",
  "laos":"\u{1F1F1}\u{1F1E6}","latvia":"\u{1F1F1}\u{1F1FB}","lebanon":"\u{1F1F1}\u{1F1E7}","liberia":"\u{1F1F1}\u{1F1F7}",
  "libya":"\u{1F1F1}\u{1F1FE}","lithuania":"\u{1F1F1}\u{1F1F9}","luxembourg":"\u{1F1F1}\u{1F1FA}","madagascar":"\u{1F1F2}\u{1F1EC}",
  "malawi":"\u{1F1F2}\u{1F1FC}","malaysia":"\u{1F1F2}\u{1F1FE}","maldives":"\u{1F1F2}\u{1F1FB}","mali":"\u{1F1F2}\u{1F1F1}",
  "malta":"\u{1F1F2}\u{1F1F9}","mauritania":"\u{1F1F2}\u{1F1F7}","mauritius":"\u{1F1F2}\u{1F1FA}","mexico":"\u{1F1F2}\u{1F1FD}",
  "moldova":"\u{1F1F2}\u{1F1E9}","mongolia":"\u{1F1F2}\u{1F1F3}","montenegro":"\u{1F1F2}\u{1F1EA}","morocco":"\u{1F1F2}\u{1F1E6}",
  "mozambique":"\u{1F1F2}\u{1F1FF}","myanmar":"\u{1F1F2}\u{1F1F2}","burma":"\u{1F1F2}\u{1F1F2}","namibia":"\u{1F1F3}\u{1F1E6}",
  "nepal":"\u{1F1F3}\u{1F1F5}","netherlands":"\u{1F1F3}\u{1F1F1}","new zealand":"\u{1F1F3}\u{1F1FF}","nicaragua":"\u{1F1F3}\u{1F1EE}",
  "niger":"\u{1F1F3}\u{1F1EA}","nigeria":"\u{1F1F3}\u{1F1EC}","north korea":"\u{1F1F0}\u{1F1F5}","norway":"\u{1F1F3}\u{1F1F4}",
  "oman":"\u{1F1F4}\u{1F1F2}","pakistan":"\u{1F1F5}\u{1F1F0}","palestine":"\u{1F1F5}\u{1F1F8}","panama":"\u{1F1F5}\u{1F1E6}",
  "papua new guinea":"\u{1F1F5}\u{1F1EC}","paraguay":"\u{1F1F5}\u{1F1FE}","peru":"\u{1F1F5}\u{1F1EA}",
  "philippines":"\u{1F1F5}\u{1F1ED}","poland":"\u{1F1F5}\u{1F1F1}","portugal":"\u{1F1F5}\u{1F1F9}","qatar":"\u{1F1F6}\u{1F1E6}",
  "romania":"\u{1F1F7}\u{1F1F4}","russia":"\u{1F1F7}\u{1F1FA}","rwanda":"\u{1F1F7}\u{1F1FC}","saudi arabia":"\u{1F1F8}\u{1F1E6}",
  "senegal":"\u{1F1F8}\u{1F1F3}","serbia":"\u{1F1F7}\u{1F1F8}","sierra leone":"\u{1F1F8}\u{1F1F1}","singapore":"\u{1F1F8}\u{1F1EC}",
  "slovakia":"\u{1F1F8}\u{1F1F0}","slovenia":"\u{1F1F8}\u{1F1EE}","somalia":"\u{1F1F8}\u{1F1F4}","south africa":"\u{1F1FF}\u{1F1E6}",
  "south korea":"\u{1F1F0}\u{1F1F7}","south sudan":"\u{1F1F8}\u{1F1F8}","spain":"\u{1F1EA}\u{1F1F8}","sri lanka":"\u{1F1F1}\u{1F1F0}",
  "sudan":"\u{1F1F8}\u{1F1E9}","sweden":"\u{1F1F8}\u{1F1EA}","switzerland":"\u{1F1E8}\u{1F1ED}","syria":"\u{1F1F8}\u{1F1FE}",
  "taiwan":"\u{1F1F9}\u{1F1FC}","tajikistan":"\u{1F1F9}\u{1F1EF}","tanzania":"\u{1F1F9}\u{1F1FF}","thailand":"\u{1F1F9}\u{1F1ED}",
  "togo":"\u{1F1F9}\u{1F1EC}","trinidad and tobago":"\u{1F1F9}\u{1F1F9}","tunisia":"\u{1F1F9}\u{1F1F3}","turkey":"\u{1F1F9}\u{1F1F7}",
  "turkmenistan":"\u{1F1F9}\u{1F1F2}","uganda":"\u{1F1FA}\u{1F1EC}","ukraine":"\u{1F1FA}\u{1F1E6}","uae":"\u{1F1E6}\u{1F1EA}",
  "united arab emirates":"\u{1F1E6}\u{1F1EA}","united kingdom":"\u{1F1EC}\u{1F1E7}","uk":"\u{1F1EC}\u{1F1E7}",
  "united states":"\u{1F1FA}\u{1F1F8}","usa":"\u{1F1FA}\u{1F1F8}","uruguay":"\u{1F1FA}\u{1F1FE}",
  "uzbekistan":"\u{1F1FA}\u{1F1FF}","venezuela":"\u{1F1FB}\u{1F1EA}","vietnam":"\u{1F1FB}\u{1F1F3}","yemen":"\u{1F1FE}\u{1F1EA}",
  "zambia":"\u{1F1FF}\u{1F1F2}","zimbabwe":"\u{1F1FF}\u{1F1FC}","gaza":"\u{1F1F5}\u{1F1F8}","west bank":"\u{1F1F5}\u{1F1F8}",
  "hormuz":"\u{1F1EE}\u{1F1F7}","tehran":"\u{1F1EE}\u{1F1F7}","washington":"\u{1F1FA}\u{1F1F8}","moscow":"\u{1F1F7}\u{1F1FA}"
};

function cDetectType(title) {
  var t = (title || "").toLowerCase();
  if (t.includes("military") || t.includes("strike") || t.includes("airstrike") || t.includes("bomb") || t.includes("attack") || t.includes("offensive") || t.includes("war") || t.includes("combat") || t.includes("troops") || t.includes("soldier") || t.includes("kill")) return "armed";
  if (t.includes("protest") || t.includes("riot") || t.includes("unrest") || t.includes("demonstration") || t.includes("civil") || t.includes("gang") || t.includes("cartel")) return "unrest";
  if (t.includes("coup") || t.includes("government") || t.includes("regime") || t.includes("crackdown") || t.includes("sanction") || t.includes("policy") || t.includes("diplomatic") || t.includes("suspension")) return "coup";
  if (t.includes("displace") || t.includes("refugee") || t.includes("flee") || t.includes("migrate") || t.includes("humanitarian")) return "displacement";
  return "armed";
}

function cDetectCountry(title, tags) {
  var text = (title || "").toLowerCase();
  
  // Check tags first - most reliable
  if (tags && tags.length) {
    for (var i = 0; i < tags.length; i++) {
      var tagName = tags[i].toLowerCase();
      if (cCentroids[tagName]) return tagName;
    }
  }
  
  // City/region to country mapping
  var cityMap = {
    "kyiv": "ukraine", "kiev": "ukraine", "kharkiv": "ukraine", "odesa": "ukraine", "odessa": "ukraine",
    "moscow": "russia", "kremlin": "russia", "russian": "russia",
    "beijing": "china", "taipei": "taiwan", "hong kong": "china", "shanghai": "china", "chinese": "china",
    "tehran": "iran", "hormuz": "iran", "strait of hormuz": "iran", "persian gulf": "iran", "iranian": "iran",
    "dublin": "ireland", "irish": "ireland",
    "gaza": "palestine", "west bank": "palestine", "ramallah": "palestine", "palestinian": "palestine",
    "tel aviv": "israel", "jerusalem": "israel", "israeli": "israel",
    "kabul": "afghanistan", "afghan": "afghanistan",
    "baghdad": "iraq", "iraqi": "iraq",
    "damascus": "syria", "aleppo": "syria", "syrian": "syria",
    "riyadh": "saudi arabia", "saudi": "saudi arabia",
    "cairo": "egypt", "egyptian": "egypt",
    "nairobi": "kenya", "kenyan": "kenya",
    "lagos": "nigeria", "nigerian": "nigeria",
    "khartoum": "sudan", "sudanese": "sudan",
    "addis ababa": "ethiopia", "ethiopian": "ethiopia",
    "kinshasa": "dr congo", "congolese": "dr congo",
    "yangon": "myanmar", "rangoon": "myanmar", "burmese": "myanmar",
    "pyongyang": "north korea", "korean": "south korea",
    "caracas": "venezuela", "venezuelan": "venezuela",
    "havana": "cuba", "cuban": "cuba",
    "minsk": "belarus", "belarusian": "belarus",
    "ankara": "turkey", "istanbul": "turkey", "turkish": "turkey",
    "karachi": "pakistan", "islamabad": "pakistan", "pakistani": "pakistan",
    "new delhi": "india", "mumbai": "india", "indian": "india",
    "dhaka": "bangladesh", "bangladeshi": "bangladesh",
    "colombo": "sri lanka", "sri lankan": "sri lanka",
    "hanoi": "vietnam", "vietnamese": "vietnam",
    "manila": "philippines", "filipino": "philippines", "philippine": "philippines",
    "jakarta": "indonesia", "indonesian": "indonesia",
    "kuala lumpur": "malaysia", "malaysian": "malaysia",
    "bangkok": "thailand", "thai": "thailand",
    "phnom penh": "cambodia", "cambodian": "cambodia",
    "mogadishu": "somalia", "somali": "somalia",
    "sanaa": "yemen", "yemeni": "yemen", "houthi": "yemen",
    "tripoli": "libya", "libyan": "libya",
    "algiers": "algeria", "algerian": "algeria",
    "tunis": "tunisia", "tunisian": "tunisia",
    "rabat": "morocco", "moroccan": "morocco",
    "luanda": "angola", "angolan": "angola",
    "maputo": "mozambique", "mozambican": "mozambique",
    "harare": "zimbabwe", "zimbabwean": "zimbabwe",
    "pretoria": "south africa", "johannesburg": "south africa", "south african": "south africa",
    "bamako": "mali", "malian": "mali",
    "ouagadougou": "burkina faso", "burkinabe": "burkina faso",
    "niamey": "niger", "nigerien": "niger",
    "ndjamena": "chad", "chadian": "chad",
    "bangui": "central african republic",
    "juba": "south sudan", "south sudanese": "south sudan",
    "port-au-prince": "haiti", "haitian": "haiti",
    "managua": "nicaragua", "nicaraguan": "nicaragua",
    "mexico city": "mexico", "mexican": "mexico"
  };
  
  // Check city/region mapping first
  for (var city in cityMap) {
    if (text.includes(city)) {
      return cityMap[city];
    }
  }
  
  // Then check country names directly
  var best = null;
  var bestLen = 0;
  var countries = Object.keys(cCentroids);
  for (var j = 0; j < countries.length; j++) {
    var c = countries[j];
    if (text.includes(c) && c.length > bestLen) {
      best = c;
      bestLen = c.length;
    }
  }
  return best;
}

function cGetSeverity(title) {
  var t = (title || "").toLowerCase();
  if (t.includes("strike") || t.includes("bomb") || t.includes("attack") || t.includes("kill") || t.includes("military") || t.includes("war") || t.includes("offensive")) return "crit";
  if (t.includes("tension") || t.includes("sanction") || t.includes("protest") || t.includes("suspend") || t.includes("crisis")) return "high";
  return "high";
}

var cOriginalFeatures = [];
var cExpandedKey = null;
var C_SPREAD_RADIUS = 5;

function cSpread(features, centerLng, centerLat) {
  if (features.length === 1) return features;
  return features.map(function(f, i) {
    var angle = (2 * Math.PI * i / features.length) - Math.PI / 2;
    var newLng = centerLng + C_SPREAD_RADIUS * Math.cos(angle);
    var newLat = centerLat + C_SPREAD_RADIUS * Math.sin(angle);
    newLat = Math.max(-80, Math.min(80, newLat));
    return {type:"Feature",geometry:{type:"Point",coordinates:[newLng,newLat]},properties:f.properties};
  });
}

function cCollapseAll() {
  cExpandedKey = null;
  if (cMap.getSource("c-lines")) cMap.getSource("c-lines").setData({type:"FeatureCollection",features:[]});
  if (cMap.getSource("cpts")) cMap.getSource("cpts").setData({type:"FeatureCollection",features:cOriginalFeatures});
}

function cExpandCluster(countryKey) {
  var clusterFeatures = cOriginalFeatures.filter(function(f){return f.properties.countryKey===countryKey;});
  var otherFeatures = cOriginalFeatures.filter(function(f){return f.properties.countryKey!==countryKey;});
  var center = clusterFeatures[0].geometry.coordinates;
  var spread = cSpread(clusterFeatures, center[0], center[1]);
  cExpandedKey = countryKey;
  var lineFeatures = spread.map(function(f){return{type:"Feature",geometry:{type:"LineString",coordinates:[center,f.geometry.coordinates]}};});
  cMap.getSource("c-lines").setData({type:"FeatureCollection",features:lineFeatures});
  cMap.getSource("cpts").setData({type:"FeatureCollection",features:otherFeatures.concat(spread)});
}

function cShowPopup(coords, props) {
  new maplibregl.Popup({closeButton:false,offset:10})
    .setLngLat(coords)
    .setHTML("<div style='font-family:IBM Plex Sans,sans-serif;min-width:200px;'><div style='font-size:10px;text-transform:uppercase;letter-spacing:0.1em;color:#888;margin-bottom:4px;'>"+(props.country||"Unknown")+"</div><div style='font-size:13px;font-weight:500;color:#111;line-height:1.4;margin-bottom:6px;'>"+(props.title||"")+"</div><a href='"+(props.link||"#")+"' target='_blank' style='font-size:11px;color:#ef4444;text-decoration:none;'>Read full report &rarr;</a></div>")
    .addTo(cMap);
}

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

var indexEl = document.getElementById("c-index");
if (indexEl) {
  var indexHtml = "";
  for (var i = 0; i < cIndex.length; i++) {
    var c = cIndex[i];
    indexHtml += "<div class='c-row'><div class='c-rank'>"+c.r+"</div><div class='c-flag'>"+c.f+"</div><div class='c-info'><div class='c-name'>"+c.n+"</div><div class='c-type'>"+c.t+"</div></div><div class='c-score'><div class='c-score-val "+c.g+"'>"+c.s+"</div><div class='c-bar-wrap'><div class='c-bar "+c.g+"' style='width:"+c.s+"%'></div></div></div></div>";
  }
  indexEl.innerHTML = indexHtml;
}

cMap.on("load", function() {
  cMap.addSource("c-lines", {type:"geojson",data:{type:"FeatureCollection",features:[]}});
  cMap.addLayer({id:"c-spider-legs",type:"line",source:"c-lines",paint:{"line-color":"rgba(255,255,255,0.5)","line-width":1,"line-dasharray":[2,2]}});
  cMap.addSource("cpts", {type:"geojson",data:{type:"FeatureCollection",features:[]}});
  cMap.addLayer({id:"cglow",type:"circle",source:"cpts",paint:{"circle-radius":16,"circle-color":["get","color"],"circle-opacity":0.18,"circle-blur":1}});
  cMap.addLayer({id:"cdots",type:"circle",source:"cpts",paint:{"circle-radius":7,"circle-color":["get","color"],"circle-opacity":0.9,"circle-stroke-width":1.5,"circle-stroke-color":"rgba(255,255,255,0.4)"}});

  cMap.on("click", "cdots", function(e) {
    e.originalEvent.stopPropagation();
    var props = e.features[0].properties;
    var coords = e.features[0].geometry.coordinates.slice();
    var countryKey = props.countryKey;
    var clusterSize = cOriginalFeatures.filter(function(f){return f.properties.countryKey===countryKey;}).length;
    if (cExpandedKey === countryKey) { cShowPopup(coords, props); return; }
    if (clusterSize > 1) { cExpandCluster(countryKey); return; }
    cShowPopup(coords, props);
  });

  cMap.on("click", function(e) {
    var dot = cMap.queryRenderedFeatures(e.point, {layers:["cdots"]});
    if (!dot.length && cExpandedKey) cCollapseAll();
  });

  cMap.on("mouseenter", "cdots", function(){cMap.getCanvas().style.cursor="pointer";});
  cMap.on("mouseleave", "cdots", function(){cMap.getCanvas().style.cursor="";});

  fetch("https://globalwitnessmonitor.com/wp-json/wp/v2/posts?categories=8&per_page=100&orderby=date&order=desc&_embed=1")
    .then(function(r){return r.json();})
    .then(function(posts) {
      var features = [];
      var tickerItems = [];
      
      posts.forEach(function(post) {
        var title = post.title.rendered.replace(/<[^>]+>/g,"");
        var tags = [];
        if (post._embedded && post._embedded["wp:term"]) {
          post._embedded["wp:term"].forEach(function(termGroup) {
            termGroup.forEach(function(term) {
              if (term.taxonomy === "post_tag") tags.push(term.name);
            });
          });
        }
        var country = cDetectCountry(title, tags);
        var incType = cDetectType(title);
        var sev = cGetSeverity(title);
        
        // Add to map if country detected
        if (country && cCentroids[country]) {
          var coords = cCentroids[country];
          features.push({
            type:"Feature",
            geometry:{type:"Point",coordinates:[coords[0],coords[1]]},
            properties:{title:title,country:country.charAt(0).toUpperCase()+country.slice(1),countryKey:country,type:incType,color:cTypeColors[incType]||cTypeColors.default,link:post.link}
          });
        }
        
        // Build ticker item (limit to first 10 for ticker) - always add if we have a country
        if (tickerItems.length < 10 && country) {
          var shortTitle = title.length > 50 ? title.substring(0, 47) + "..." : title;
          var sevClass = sev === "crit" ? "sev-crit" : "sev-high";
          var sevLabel = sev === "crit" ? "CRITICAL" : "HIGH";
          var flag = cFlags[country] || "";
          var countryName = country.charAt(0).toUpperCase() + country.slice(1);
          tickerItems.push("<span class='c-ticker-item'><span class='c-ticker-flag'>" + flag + "</span> " + countryName + " — " + shortTitle + " <span class='c-ticker-sev " + sevClass + "'>" + sevLabel + "</span></span>");
        }
      });
      
      cOriginalFeatures = features;
      cMap.getSource("cpts").setData({type:"FeatureCollection",features:features});
      document.getElementById("c-map-count").textContent = features.length + " EVENTS";
      
      // Populate ticker - duplicate for seamless scroll
      var tickerEl = document.getElementById("c-ticker-content");
      if (tickerEl && tickerItems.length > 0) {
        var tickerHtml = tickerItems.join("") + tickerItems.join("");
        tickerEl.innerHTML = tickerHtml;
      }
      
      console.log("Plotted " + features.length + " conflict events on map");
    })
    .catch(function(e) {
      console.log("Map feed error:", e);
      document.getElementById("c-map-count").textContent = "FEED ERROR";
    });

  setTimeout(function(){cMap.resize();}, 200);
});

var zinBtn = document.getElementById("c-zin");
var zoutBtn = document.getElementById("c-zout");
if (zinBtn) zinBtn.onclick = function(){cMap.zoomIn();};
if (zoutBtn) zoutBtn.onclick = function(){cMap.zoomOut();};

fetch("https://globalwitnessmonitor.com/wp-json/wp/v2/posts?categories=8&per_page=20&orderby=date&order=desc&_embed=1")
  .then(function(r){return r.json();})
  .then(function(posts) {
    var feed = document.getElementById("c-feed");
    var countEl = document.getElementById("c-news-count");
    var liveEl = document.getElementById("c-live-count");
    if (!feed) return;
    if (!posts || !posts.length) { feed.innerHTML = "<div class='c-loading'>NO REPORTS FOUND</div>"; return; }
    if (countEl) countEl.textContent = posts.length + " REPORTS";
    if (liveEl) liveEl.textContent = posts.length;
    var html = "";
    for (var k = 0; k < posts.length; k++) {
      var p = posts[k];
      var title = p.title.rendered.replace(/<[^>]+>/g,"");
      var excerpt = p.excerpt.rendered.replace(/<[^>]+>/g,"").substring(0,100);
      var link = p.link || "#";
      var tag = "Global";
      if (p._embedded && p._embedded["wp:term"]) {
        for (var m = 0; m < p._embedded["wp:term"].length; m++) {
          for (var n = 0; n < p._embedded["wp:term"][m].length; n++) {
            var term = p._embedded["wp:term"][m][n];
            if (term.taxonomy === "post_tag" && term.name.length < 25) { tag = term.name; break; }
          }
        }
      }
      var diff = Math.floor((new Date() - new Date(p.date)) / 60000);
      var ago = diff < 1 ? "now" : diff < 60 ? diff+"m" : diff < 1440 ? Math.floor(diff/60)+"h" : Math.floor(diff/1440)+"d";
      html += "<a class='c-news' href='"+link+"' target='_blank'><div class='c-news-meta'><span class='c-news-tag'>"+tag+"</span><span class='c-news-time'>"+ago+" ago</span></div><div class='c-news-title'>"+title+"</div><div class='c-news-summary'>"+excerpt+"</div></a>";
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
  if (clockEl) clockEl.textContent = (h<10?"0":"")+h+":"+(m<10?"0":"")+m+":"+(s<10?"0":"")+s+" UTC";
}, 1000);

var filterBtns = document.querySelectorAll(".c-fbtn");
filterBtns.forEach(function(btn) {
  btn.addEventListener("click", function() {
    filterBtns.forEach(function(b){b.classList.remove("active");});
    this.classList.add("active");
  });
});
