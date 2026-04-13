var cMap = new maplibregl.Map({
  container: "c-map",
  style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
  center: [20, 15],
  zoom: 2.2,
  attributionControl: false
});

cMap.addControl(new maplibregl.AttributionControl({compact: true}), "bottom-right");

var cCentroids = {
  // All coordinates are capital cities (or major city for that location)
  // Format: [longitude, latitude]
  // A
  "afghanistan":[69.17,34.53],"afghan":[69.17,34.53],"kabul":[69.17,34.53],
  "albania":[19.82,41.33],"albanian":[19.82,41.33],"tirana":[19.82,41.33],
  "algeria":[3.04,36.75],"algerian":[3.04,36.75],"algiers":[3.04,36.75],
  "angola":[13.23,-8.84],"angolan":[13.23,-8.84],"luanda":[13.23,-8.84],
  "argentina":[-58.38,-34.60],"argentine":[-58.38,-34.60],"argentinian":[-58.38,-34.60],"buenos aires":[-58.38,-34.60],
  "armenia":[44.51,40.18],"armenian":[44.51,40.18],"yerevan":[44.51,40.18],
  "australia":[149.13,-35.28],"australian":[149.13,-35.28],"canberra":[149.13,-35.28],"sydney":[151.21,-33.87],"melbourne":[144.96,-37.81],
  "austria":[16.37,48.21],"austrian":[16.37,48.21],"vienna":[16.37,48.21],
  "azerbaijan":[49.87,40.41],"azerbaijani":[49.87,40.41],"baku":[49.87,40.41],
  // B
  "bahrain":[50.58,26.23],"bahraini":[50.58,26.23],"manama":[50.58,26.23],
  "bangladesh":[90.41,23.81],"bangladeshi":[90.41,23.81],"dhaka":[90.41,23.81],
  "belarus":[27.57,53.90],"belarusian":[27.57,53.90],"minsk":[27.57,53.90],
  "belgium":[4.35,50.85],"belgian":[4.35,50.85],"brussels":[4.35,50.85],
  "belize":[-88.77,17.25],"belizean":[-88.77,17.25],"belmopan":[-88.77,17.25],
  "benin":[2.36,6.50],"beninese":[2.36,6.50],"porto-novo":[2.36,6.50],
  "bolivia":[-68.15,-16.49],"bolivian":[-68.15,-16.49],"la paz":[-68.15,-16.49],
  "botswana":[25.91,-24.65],"gaborone":[25.91,-24.65],
  "brazil":[-47.93,-15.78],"brazilian":[-47.93,-15.78],"brasilia":[-47.93,-15.78],"sao paulo":[-46.63,-23.55],"rio de janeiro":[-43.17,-22.91],
  "bulgaria":[23.32,42.70],"bulgarian":[23.32,42.70],"sofia":[23.32,42.70],
  "burkina faso":[-1.52,12.37],"burkinabe":[-1.52,12.37],"ouagadougou":[-1.52,12.37],
  "burundi":[29.36,-3.38],"burundian":[29.36,-3.38],"bujumbura":[29.36,-3.38],"gitega":[29.92,-3.43],
  // C
  "cambodia":[104.92,11.56],"cambodian":[104.92,11.56],"phnom penh":[104.92,11.56],
  "cameroon":[11.52,3.87],"cameroonian":[11.52,3.87],"yaounde":[11.52,3.87],
  "canada":[-75.70,45.42],"canadian":[-75.70,45.42],"ottawa":[-75.70,45.42],"toronto":[-79.38,43.65],
  "central african republic":[18.56,4.36],"car":[18.56,4.36],"bangui":[18.56,4.36],
  "chad":[15.04,12.11],"chadian":[15.04,12.11],"ndjamena":[15.04,12.11],
  "chile":[-70.65,-33.45],"chilean":[-70.65,-33.45],"santiago":[-70.65,-33.45],
  "china":[116.41,39.90],"chinese":[116.41,39.90],"beijing":[116.41,39.90],"shanghai":[121.47,31.23],"hong kong":[114.17,22.32],"prc":[116.41,39.90],
  "colombia":[-74.07,4.71],"colombian":[-74.07,4.71],"bogota":[-74.07,4.71],
  "comoros":[43.26,-11.70],"comorian":[43.26,-11.70],"moroni":[43.26,-11.70],
  "congo":[15.28,-4.27],"congolese":[15.28,-4.27],"brazzaville":[15.28,-4.27],
  "costa rica":[-84.09,9.93],"costa rican":[-84.09,9.93],"san jose":[-84.09,9.93],
  "croatia":[15.98,45.81],"croatian":[15.98,45.81],"zagreb":[15.98,45.81],
  "cuba":[-82.37,23.11],"cuban":[-82.37,23.11],"havana":[-82.37,23.11],
  "cyprus":[33.38,35.19],"cypriot":[33.38,35.19],"nicosia":[33.38,35.19],
  "czech republic":[14.42,50.08],"czech":[14.42,50.08],"prague":[14.42,50.08],"czechia":[14.42,50.08],
  // D
  "denmark":[12.57,55.68],"danish":[12.57,55.68],"copenhagen":[12.57,55.68],
  "djibouti":[43.15,11.59],"djiboutian":[43.15,11.59],
  "dr congo":[15.31,-4.32],"drc":[15.31,-4.32],"democratic republic of congo":[15.31,-4.32],"kinshasa":[15.31,-4.32],
  // E
  "ecuador":[-78.47,-0.18],"ecuadorian":[-78.47,-0.18],"quito":[-78.47,-0.18],
  "egypt":[31.24,30.04],"egyptian":[31.24,30.04],"cairo":[31.24,30.04],
  "el salvador":[-89.19,13.69],"salvadoran":[-89.19,13.69],"san salvador":[-89.19,13.69],
  "eritrea":[38.93,15.33],"eritrean":[38.93,15.33],"asmara":[38.93,15.33],
  "estonia":[24.75,59.44],"estonian":[24.75,59.44],"tallinn":[24.75,59.44],
  "ethiopia":[38.76,9.02],"ethiopian":[38.76,9.02],"addis ababa":[38.76,9.02],
  // F
  "fiji":[178.44,-18.14],"fijian":[178.44,-18.14],"suva":[178.44,-18.14],
  "finland":[24.94,60.17],"finnish":[24.94,60.17],"helsinki":[24.94,60.17],
  "france":[2.35,48.86],"french":[2.35,48.86],"paris":[2.35,48.86],
  // G
  "gabon":[9.45,0.39],"gabonese":[9.45,0.39],"libreville":[9.45,0.39],
  "gambia":[-16.58,13.45],"gambian":[-16.58,13.45],"banjul":[-16.58,13.45],
  "georgia":[44.79,41.72],"georgian":[44.79,41.72],"tbilisi":[44.79,41.72],
  "germany":[13.40,52.52],"german":[13.40,52.52],"berlin":[13.40,52.52],
  "ghana":[-0.19,5.56],"ghanaian":[-0.19,5.56],"accra":[-0.19,5.56],
  "greece":[23.73,37.98],"greek":[23.73,37.98],"athens":[23.73,37.98],
  "guatemala":[-90.51,14.63],"guatemalan":[-90.51,14.63],"guatemala city":[-90.51,14.63],
  "guinea":[-13.68,9.64],"guinean":[-13.68,9.64],"conakry":[-13.68,9.64],
  "guyana":[-58.16,6.80],"guyanese":[-58.16,6.80],"georgetown":[-58.16,6.80],
  // H
  "haiti":[-72.34,18.54],"haitian":[-72.34,18.54],"port-au-prince":[-72.34,18.54],
  "honduras":[-87.21,14.08],"honduran":[-87.21,14.08],"tegucigalpa":[-87.21,14.08],
  "hungary":[19.04,47.50],"hungarian":[19.04,47.50],"budapest":[19.04,47.50],
  "hormuz":[56.27,26.60],"strait of hormuz":[56.27,26.60],
  // I
  "iceland":[-21.90,64.14],"icelandic":[-21.90,64.14],"reykjavik":[-21.90,64.14],
  "india":[77.21,28.61],"indian":[77.21,28.61],"new delhi":[77.21,28.61],"mumbai":[72.88,19.08],"delhi":[77.21,28.61],
  "indonesia":[106.85,-6.21],"indonesian":[106.85,-6.21],"jakarta":[106.85,-6.21],
  "iran":[51.39,35.69],"iranian":[51.39,35.69],"tehran":[51.39,35.69],"persian":[51.39,35.69],
  "iraq":[44.37,33.31],"iraqi":[44.37,33.31],"baghdad":[44.37,33.31],
  "ireland":[-6.26,53.35],"irish":[-6.26,53.35],"dublin":[-6.26,53.35],
  "israel":[35.22,31.77],"israeli":[35.22,31.77],"tel aviv":[34.78,32.08],"jerusalem":[35.22,31.77],
  "italy":[12.50,41.90],"italian":[12.50,41.90],"rome":[12.50,41.90],
  // J
  "jamaica":[-76.79,18.00],"jamaican":[-76.79,18.00],"kingston":[-76.79,18.00],
  "japan":[139.69,35.69],"japanese":[139.69,35.69],"tokyo":[139.69,35.69],
  "jordan":[35.93,31.95],"jordanian":[35.93,31.95],"amman":[35.93,31.95],
  // K
  "kazakhstan":[71.43,51.17],"kazakh":[71.43,51.17],"astana":[71.43,51.17],"almaty":[76.95,43.24],
  "kenya":[36.82,-1.29],"kenyan":[36.82,-1.29],"nairobi":[36.82,-1.29],
  "kuwait":[47.98,29.38],"kuwaiti":[47.98,29.38],"kuwait city":[47.98,29.38],
  "kyrgyzstan":[74.59,42.87],"kyrgyz":[74.59,42.87],"bishkek":[74.59,42.87],
  // L
  "laos":[102.63,17.97],"laotian":[102.63,17.97],"vientiane":[102.63,17.97],
  "latvia":[24.11,56.95],"latvian":[24.11,56.95],"riga":[24.11,56.95],
  "lebanon":[35.50,33.89],"lebanese":[35.50,33.89],"beirut":[35.50,33.89],
  "liberia":[-10.80,6.30],"liberian":[-10.80,6.30],"monrovia":[-10.80,6.30],
  "libya":[13.19,32.90],"libyan":[13.19,32.90],"tripoli":[13.19,32.90],
  "lithuania":[25.28,54.69],"lithuanian":[25.28,54.69],"vilnius":[25.28,54.69],
  "luxembourg":[6.13,49.61],"luxembourgish":[6.13,49.61],
  // M
  "madagascar":[47.52,-18.91],"malagasy":[47.52,-18.91],"antananarivo":[47.52,-18.91],
  "malawi":[33.79,-13.97],"malawian":[33.79,-13.97],"lilongwe":[33.79,-13.97],
  "malaysia":[101.69,3.14],"malaysian":[101.69,3.14],"kuala lumpur":[101.69,3.14],
  "maldives":[73.51,4.18],"maldivian":[73.51,4.18],"male":[73.51,4.18],
  "mali":[-8.00,12.65],"malian":[-8.00,12.65],"bamako":[-8.00,12.65],
  "malta":[14.51,35.90],"maltese":[14.51,35.90],"valletta":[14.51,35.90],
  "mauritania":[-15.98,18.09],"mauritanian":[-15.98,18.09],"nouakchott":[-15.98,18.09],
  "mauritius":[57.50,-20.16],"mauritian":[57.50,-20.16],"port louis":[57.50,-20.16],
  "mexico":[-99.13,19.43],"mexican":[-99.13,19.43],"mexico city":[-99.13,19.43],
  "moldova":[28.83,47.01],"moldovan":[28.83,47.01],"chisinau":[28.83,47.01],
  "mongolia":[106.91,47.92],"mongolian":[106.91,47.92],"ulaanbaatar":[106.91,47.92],
  "montenegro":[19.26,42.44],"montenegrin":[19.26,42.44],"podgorica":[19.26,42.44],
  "morocco":[-6.83,34.02],"moroccan":[-6.83,34.02],"rabat":[-6.83,34.02],
  "mozambique":[32.59,-25.97],"mozambican":[32.59,-25.97],"maputo":[32.59,-25.97],
  "myanmar":[96.20,16.87],"burmese":[96.20,16.87],"burma":[96.20,16.87],"yangon":[96.20,16.87],"rangoon":[96.20,16.87],"naypyidaw":[96.13,19.76],
  // N
  "namibia":[17.08,-22.56],"namibian":[17.08,-22.56],"windhoek":[17.08,-22.56],
  "nepal":[85.32,27.72],"nepali":[85.32,27.72],"nepalese":[85.32,27.72],"kathmandu":[85.32,27.72],
  "netherlands":[4.90,52.37],"dutch":[4.90,52.37],"amsterdam":[4.90,52.37],"the hague":[4.30,52.08],
  "new zealand":[174.78,-41.29],"kiwi":[174.78,-41.29],"wellington":[174.78,-41.29],"auckland":[174.76,-36.85],
  "nicaragua":[-86.25,12.11],"nicaraguan":[-86.25,12.11],"managua":[-86.25,12.11],
  "niger":[2.11,13.51],"nigerien":[2.11,13.51],"niamey":[2.11,13.51],
  "nigeria":[7.49,9.06],"nigerian":[7.49,9.06],"abuja":[7.49,9.06],"lagos":[3.39,6.45],
  "north korea":[125.75,39.04],"dprk":[125.75,39.04],"pyongyang":[125.75,39.04],
  "norway":[10.75,59.91],"norwegian":[10.75,59.91],"oslo":[10.75,59.91],
  // O
  "oman":[58.39,23.59],"omani":[58.39,23.59],"muscat":[58.39,23.59],
  // P
  "pakistan":[73.04,33.69],"pakistani":[73.04,33.69],"islamabad":[73.04,33.69],"karachi":[67.01,24.86],
  "palestine":[35.23,31.90],"palestinian":[35.23,31.90],"gaza":[34.47,31.50],"west bank":[35.23,31.90],"ramallah":[35.20,31.90],
  "panama":[-79.52,8.98],"panamanian":[-79.52,8.98],"panama city":[-79.52,8.98],
  "papua new guinea":[147.19,-9.44],"png":[147.19,-9.44],"port moresby":[147.19,-9.44],
  "paraguay":[-57.58,-25.26],"paraguayan":[-57.58,-25.26],"asuncion":[-57.58,-25.26],
  "peru":[-77.04,-12.05],"peruvian":[-77.04,-12.05],"lima":[-77.04,-12.05],
  "philippines":[120.98,14.60],"filipino":[120.98,14.60],"philippine":[120.98,14.60],"manila":[120.98,14.60],
  "poland":[21.02,52.23],"polish":[21.02,52.23],"warsaw":[21.02,52.23],
  "portugal":[-9.14,38.74],"portuguese":[-9.14,38.74],"lisbon":[-9.14,38.74],
  // Q
  "qatar":[51.53,25.29],"qatari":[51.53,25.29],"doha":[51.53,25.29],
  // R
  "romania":[26.10,44.43],"romanian":[26.10,44.43],"bucharest":[26.10,44.43],
  "russia":[37.62,55.75],"russian":[37.62,55.75],"moscow":[37.62,55.75],"kremlin":[37.62,55.75],"st petersburg":[30.31,59.94],
  "rwanda":[30.06,-1.94],"rwandan":[30.06,-1.94],"kigali":[30.06,-1.94],
  // S
  "saudi arabia":[46.72,24.69],"saudi":[46.72,24.69],"riyadh":[46.72,24.69],
  "senegal":[-17.44,14.69],"senegalese":[-17.44,14.69],"dakar":[-17.44,14.69],
  "serbia":[20.46,44.82],"serbian":[20.46,44.82],"belgrade":[20.46,44.82],
  "sierra leone":[-13.23,8.48],"freetown":[-13.23,8.48],
  "singapore":[103.85,1.29],"singaporean":[103.85,1.29],
  "slovakia":[17.11,48.15],"slovak":[17.11,48.15],"bratislava":[17.11,48.15],
  "slovenia":[14.51,46.05],"slovenian":[14.51,46.05],"ljubljana":[14.51,46.05],
  "somalia":[45.34,2.04],"somali":[45.34,2.04],"mogadishu":[45.34,2.04],
  "south africa":[28.19,-25.75],"south african":[28.19,-25.75],"pretoria":[28.19,-25.75],"johannesburg":[28.05,-26.20],"cape town":[18.42,-33.93],
  "south korea":[126.98,37.57],"korean":[126.98,37.57],"seoul":[126.98,37.57],
  "south sudan":[31.58,4.86],"south sudanese":[31.58,4.86],"juba":[31.58,4.86],
  "spain":[-3.70,40.42],"spanish":[-3.70,40.42],"madrid":[-3.70,40.42],"barcelona":[2.17,41.39],
  "sri lanka":[79.86,6.93],"sri lankan":[79.86,6.93],"colombo":[79.86,6.93],
  "sudan":[32.53,15.59],"sudanese":[32.53,15.59],"khartoum":[32.53,15.59],
  "sweden":[18.07,59.33],"swedish":[18.07,59.33],"stockholm":[18.07,59.33],
  "switzerland":[7.45,46.95],"swiss":[7.45,46.95],"bern":[7.45,46.95],"geneva":[6.15,46.20],"zurich":[8.54,47.38],
  "syria":[36.28,33.51],"syrian":[36.28,33.51],"damascus":[36.28,33.51],"aleppo":[37.16,36.20],
  // T
  "taiwan":[121.56,25.03],"taiwanese":[121.56,25.03],"taipei":[121.56,25.03],
  "tajikistan":[68.77,38.54],"tajik":[68.77,38.54],"dushanbe":[68.77,38.54],
  "tanzania":[39.27,-6.81],"tanzanian":[39.27,-6.81],"dar es salaam":[39.27,-6.81],"dodoma":[35.75,-6.17],
  "thailand":[100.50,13.76],"thai":[100.50,13.76],"bangkok":[100.50,13.76],
  "togo":[1.22,6.14],"togolese":[1.22,6.14],"lome":[1.22,6.14],
  "trinidad and tobago":[-61.50,10.65],"trinidadian":[-61.50,10.65],"port of spain":[-61.50,10.65],
  "tunisia":[10.18,36.81],"tunisian":[10.18,36.81],"tunis":[10.18,36.81],
  "turkey":[32.87,39.93],"turkish":[32.87,39.93],"ankara":[32.87,39.93],"istanbul":[28.98,41.01],
  "turkmenistan":[58.38,37.95],"turkmen":[58.38,37.95],"ashgabat":[58.38,37.95],
  // U
  "uganda":[32.58,0.31],"ugandan":[32.58,0.31],"kampala":[32.58,0.31],
  "ukraine":[30.52,50.45],"ukrainian":[30.52,50.45],"kyiv":[30.52,50.45],"kiev":[30.52,50.45],"kharkiv":[36.23,49.99],"odesa":[30.73,46.48],"odessa":[30.73,46.48],
  "uae":[54.37,24.45],"emirati":[54.37,24.45],"united arab emirates":[54.37,24.45],"dubai":[55.27,25.20],"abu dhabi":[54.37,24.45],
  "united kingdom":[-0.12,51.51],"british":[-0.12,51.51],"uk":[-0.12,51.51],"london":[-0.12,51.51],"britain":[-0.12,51.51],
  "united states":[-77.04,38.91],"american":[-77.04,38.91],"usa":[-77.04,38.91],"washington":[-77.04,38.91],"new york":[-74.01,40.71],
  "uruguay":[-56.19,-34.90],"uruguayan":[-56.19,-34.90],"montevideo":[-56.19,-34.90],
  "uzbekistan":[69.28,41.31],"uzbek":[69.28,41.31],"tashkent":[69.28,41.31],
  // V
  "venezuela":[-66.90,10.49],"venezuelan":[-66.90,10.49],"caracas":[-66.90,10.49],
  "vietnam":[105.85,21.03],"vietnamese":[105.85,21.03],"hanoi":[105.85,21.03],"ho chi minh":[106.63,10.82],
  // Y
  "yemen":[44.21,15.35],"yemeni":[44.21,15.35],"sanaa":[44.21,15.35],"houthi":[44.21,15.35],
  // Z
  "zambia":[28.32,-15.39],"zambian":[28.32,-15.39],"lusaka":[28.32,-15.39],
  "zimbabwe":[31.05,-17.83],"zimbabwean":[31.05,-17.83],"harare":[31.05,-17.83],
  // Special entries
  "global":[0,20]
};

var cTypeColors = {armed:"#ef4444",unrest:"#fb923c",coup:"#f59e0b",displacement:"#a78bfa",default:"#ef4444"};

var cFlags = {
  "afghanistan":"\u{1F1E6}\u{1F1EB}","afghan":"\u{1F1E6}\u{1F1EB}","kabul":"\u{1F1E6}\u{1F1EB}",
  "albania":"\u{1F1E6}\u{1F1F1}","albanian":"\u{1F1E6}\u{1F1F1}","tirana":"\u{1F1E6}\u{1F1F1}",
  "algeria":"\u{1F1E9}\u{1F1FF}","algerian":"\u{1F1E9}\u{1F1FF}","algiers":"\u{1F1E9}\u{1F1FF}",
  "angola":"\u{1F1E6}\u{1F1F4}","angolan":"\u{1F1E6}\u{1F1F4}","luanda":"\u{1F1E6}\u{1F1F4}",
  "argentina":"\u{1F1E6}\u{1F1F7}","argentine":"\u{1F1E6}\u{1F1F7}","argentinian":"\u{1F1E6}\u{1F1F7}","buenos aires":"\u{1F1E6}\u{1F1F7}",
  "armenia":"\u{1F1E6}\u{1F1F2}","armenian":"\u{1F1E6}\u{1F1F2}","yerevan":"\u{1F1E6}\u{1F1F2}",
  "australia":"\u{1F1E6}\u{1F1FA}","australian":"\u{1F1E6}\u{1F1FA}","sydney":"\u{1F1E6}\u{1F1FA}","melbourne":"\u{1F1E6}\u{1F1FA}",
  "austria":"\u{1F1E6}\u{1F1F9}","austrian":"\u{1F1E6}\u{1F1F9}","vienna":"\u{1F1E6}\u{1F1F9}",
  "azerbaijan":"\u{1F1E6}\u{1F1FF}","azerbaijani":"\u{1F1E6}\u{1F1FF}","baku":"\u{1F1E6}\u{1F1FF}",
  "bahrain":"\u{1F1E7}\u{1F1ED}","bahraini":"\u{1F1E7}\u{1F1ED}","manama":"\u{1F1E7}\u{1F1ED}",
  "bangladesh":"\u{1F1E7}\u{1F1E9}","bangladeshi":"\u{1F1E7}\u{1F1E9}","dhaka":"\u{1F1E7}\u{1F1E9}",
  "belarus":"\u{1F1E7}\u{1F1FE}","belarusian":"\u{1F1E7}\u{1F1FE}","minsk":"\u{1F1E7}\u{1F1FE}",
  "belgium":"\u{1F1E7}\u{1F1EA}","belgian":"\u{1F1E7}\u{1F1EA}","brussels":"\u{1F1E7}\u{1F1EA}",
  "belize":"\u{1F1E7}\u{1F1FF}","belizean":"\u{1F1E7}\u{1F1FF}",
  "benin":"\u{1F1E7}\u{1F1EF}","beninese":"\u{1F1E7}\u{1F1EF}",
  "bolivia":"\u{1F1E7}\u{1F1F4}","bolivian":"\u{1F1E7}\u{1F1F4}","la paz":"\u{1F1E7}\u{1F1F4}",
  "botswana":"\u{1F1E7}\u{1F1FC}","gaborone":"\u{1F1E7}\u{1F1FC}",
  "brazil":"\u{1F1E7}\u{1F1F7}","brazilian":"\u{1F1E7}\u{1F1F7}","brasilia":"\u{1F1E7}\u{1F1F7}","sao paulo":"\u{1F1E7}\u{1F1F7}","rio de janeiro":"\u{1F1E7}\u{1F1F7}",
  "bulgaria":"\u{1F1E7}\u{1F1EC}","bulgarian":"\u{1F1E7}\u{1F1EC}","sofia":"\u{1F1E7}\u{1F1EC}",
  "burkina faso":"\u{1F1E7}\u{1F1EB}","burkinabe":"\u{1F1E7}\u{1F1EB}","ouagadougou":"\u{1F1E7}\u{1F1EB}",
  "burundi":"\u{1F1E7}\u{1F1EE}","burundian":"\u{1F1E7}\u{1F1EE}","bujumbura":"\u{1F1E7}\u{1F1EE}",
  "cambodia":"\u{1F1F0}\u{1F1ED}","cambodian":"\u{1F1F0}\u{1F1ED}","phnom penh":"\u{1F1F0}\u{1F1ED}",
  "cameroon":"\u{1F1E8}\u{1F1F2}","cameroonian":"\u{1F1E8}\u{1F1F2}","yaounde":"\u{1F1E8}\u{1F1F2}",
  "canada":"\u{1F1E8}\u{1F1E6}","canadian":"\u{1F1E8}\u{1F1E6}","ottawa":"\u{1F1E8}\u{1F1E6}","toronto":"\u{1F1E8}\u{1F1E6}",
  "central african republic":"\u{1F1E8}\u{1F1EB}","car":"\u{1F1E8}\u{1F1EB}","bangui":"\u{1F1E8}\u{1F1EB}",
  "chad":"\u{1F1F9}\u{1F1E9}","chadian":"\u{1F1F9}\u{1F1E9}","ndjamena":"\u{1F1F9}\u{1F1E9}",
  "chile":"\u{1F1E8}\u{1F1F1}","chilean":"\u{1F1E8}\u{1F1F1}","santiago":"\u{1F1E8}\u{1F1F1}",
  "china":"\u{1F1E8}\u{1F1F3}","chinese":"\u{1F1E8}\u{1F1F3}","beijing":"\u{1F1E8}\u{1F1F3}","shanghai":"\u{1F1E8}\u{1F1F3}","hong kong":"\u{1F1E8}\u{1F1F3}","prc":"\u{1F1E8}\u{1F1F3}",
  "colombia":"\u{1F1E8}\u{1F1F4}","colombian":"\u{1F1E8}\u{1F1F4}","bogota":"\u{1F1E8}\u{1F1F4}",
  "comoros":"\u{1F1F0}\u{1F1F2}","comorian":"\u{1F1F0}\u{1F1F2}",
  "congo":"\u{1F1E8}\u{1F1EC}","congolese":"\u{1F1E8}\u{1F1EC}","brazzaville":"\u{1F1E8}\u{1F1EC}",
  "costa rica":"\u{1F1E8}\u{1F1F7}","costa rican":"\u{1F1E8}\u{1F1F7}",
  "croatia":"\u{1F1ED}\u{1F1F7}","croatian":"\u{1F1ED}\u{1F1F7}","zagreb":"\u{1F1ED}\u{1F1F7}",
  "cuba":"\u{1F1E8}\u{1F1FA}","cuban":"\u{1F1E8}\u{1F1FA}","havana":"\u{1F1E8}\u{1F1FA}",
  "cyprus":"\u{1F1E8}\u{1F1FE}","cypriot":"\u{1F1E8}\u{1F1FE}","nicosia":"\u{1F1E8}\u{1F1FE}",
  "czech republic":"\u{1F1E8}\u{1F1FF}","czech":"\u{1F1E8}\u{1F1FF}","prague":"\u{1F1E8}\u{1F1FF}","czechia":"\u{1F1E8}\u{1F1FF}",
  "denmark":"\u{1F1E9}\u{1F1F0}","danish":"\u{1F1E9}\u{1F1F0}","copenhagen":"\u{1F1E9}\u{1F1F0}",
  "djibouti":"\u{1F1E9}\u{1F1EF}","djiboutian":"\u{1F1E9}\u{1F1EF}",
  "dr congo":"\u{1F1E8}\u{1F1E9}","drc":"\u{1F1E8}\u{1F1E9}","democratic republic of congo":"\u{1F1E8}\u{1F1E9}","kinshasa":"\u{1F1E8}\u{1F1E9}",
  "ecuador":"\u{1F1EA}\u{1F1E8}","ecuadorian":"\u{1F1EA}\u{1F1E8}","quito":"\u{1F1EA}\u{1F1E8}",
  "egypt":"\u{1F1EA}\u{1F1EC}","egyptian":"\u{1F1EA}\u{1F1EC}","cairo":"\u{1F1EA}\u{1F1EC}",
  "el salvador":"\u{1F1F8}\u{1F1FB}","salvadoran":"\u{1F1F8}\u{1F1FB}","san salvador":"\u{1F1F8}\u{1F1FB}",
  "eritrea":"\u{1F1EA}\u{1F1F7}","eritrean":"\u{1F1EA}\u{1F1F7}","asmara":"\u{1F1EA}\u{1F1F7}",
  "estonia":"\u{1F1EA}\u{1F1EA}","estonian":"\u{1F1EA}\u{1F1EA}","tallinn":"\u{1F1EA}\u{1F1EA}",
  "ethiopia":"\u{1F1EA}\u{1F1F9}","ethiopian":"\u{1F1EA}\u{1F1F9}","addis ababa":"\u{1F1EA}\u{1F1F9}",
  "fiji":"\u{1F1EB}\u{1F1EF}","fijian":"\u{1F1EB}\u{1F1EF}","suva":"\u{1F1EB}\u{1F1EF}",
  "finland":"\u{1F1EB}\u{1F1EE}","finnish":"\u{1F1EB}\u{1F1EE}","helsinki":"\u{1F1EB}\u{1F1EE}",
  "france":"\u{1F1EB}\u{1F1F7}","french":"\u{1F1EB}\u{1F1F7}","paris":"\u{1F1EB}\u{1F1F7}",
  "gabon":"\u{1F1EC}\u{1F1E6}","gabonese":"\u{1F1EC}\u{1F1E6}","libreville":"\u{1F1EC}\u{1F1E6}",
  "gambia":"\u{1F1EC}\u{1F1F2}","gambian":"\u{1F1EC}\u{1F1F2}","banjul":"\u{1F1EC}\u{1F1F2}",
  "georgia":"\u{1F1EC}\u{1F1EA}","georgian":"\u{1F1EC}\u{1F1EA}","tbilisi":"\u{1F1EC}\u{1F1EA}",
  "germany":"\u{1F1E9}\u{1F1EA}","german":"\u{1F1E9}\u{1F1EA}","berlin":"\u{1F1E9}\u{1F1EA}",
  "ghana":"\u{1F1EC}\u{1F1ED}","ghanaian":"\u{1F1EC}\u{1F1ED}","accra":"\u{1F1EC}\u{1F1ED}",
  "greece":"\u{1F1EC}\u{1F1F7}","greek":"\u{1F1EC}\u{1F1F7}","athens":"\u{1F1EC}\u{1F1F7}",
  "guatemala":"\u{1F1EC}\u{1F1F9}","guatemalan":"\u{1F1EC}\u{1F1F9}",
  "guinea":"\u{1F1EC}\u{1F1F3}","guinean":"\u{1F1EC}\u{1F1F3}","conakry":"\u{1F1EC}\u{1F1F3}",
  "guyana":"\u{1F1EC}\u{1F1FE}","guyanese":"\u{1F1EC}\u{1F1FE}","georgetown":"\u{1F1EC}\u{1F1FE}",
  "haiti":"\u{1F1ED}\u{1F1F9}","haitian":"\u{1F1ED}\u{1F1F9}","port-au-prince":"\u{1F1ED}\u{1F1F9}",
  "honduras":"\u{1F1ED}\u{1F1F3}","honduran":"\u{1F1ED}\u{1F1F3}","tegucigalpa":"\u{1F1ED}\u{1F1F3}",
  "hungary":"\u{1F1ED}\u{1F1FA}","hungarian":"\u{1F1ED}\u{1F1FA}","budapest":"\u{1F1ED}\u{1F1FA}",
  "hormuz":"\u{1F1EE}\u{1F1F7}","strait of hormuz":"\u{1F1EE}\u{1F1F7}",
  "iceland":"\u{1F1EE}\u{1F1F8}","icelandic":"\u{1F1EE}\u{1F1F8}","reykjavik":"\u{1F1EE}\u{1F1F8}",
  "india":"\u{1F1EE}\u{1F1F3}","indian":"\u{1F1EE}\u{1F1F3}","new delhi":"\u{1F1EE}\u{1F1F3}","mumbai":"\u{1F1EE}\u{1F1F3}","delhi":"\u{1F1EE}\u{1F1F3}",
  "indonesia":"\u{1F1EE}\u{1F1E9}","indonesian":"\u{1F1EE}\u{1F1E9}","jakarta":"\u{1F1EE}\u{1F1E9}",
  "iran":"\u{1F1EE}\u{1F1F7}","iranian":"\u{1F1EE}\u{1F1F7}","tehran":"\u{1F1EE}\u{1F1F7}","persian":"\u{1F1EE}\u{1F1F7}",
  "iraq":"\u{1F1EE}\u{1F1F6}","iraqi":"\u{1F1EE}\u{1F1F6}","baghdad":"\u{1F1EE}\u{1F1F6}",
  "ireland":"\u{1F1EE}\u{1F1EA}","irish":"\u{1F1EE}\u{1F1EA}","dublin":"\u{1F1EE}\u{1F1EA}",
  "israel":"\u{1F1EE}\u{1F1F1}","israeli":"\u{1F1EE}\u{1F1F1}","tel aviv":"\u{1F1EE}\u{1F1F1}","jerusalem":"\u{1F1EE}\u{1F1F1}",
  "italy":"\u{1F1EE}\u{1F1F9}","italian":"\u{1F1EE}\u{1F1F9}","rome":"\u{1F1EE}\u{1F1F9}",
  "jamaica":"\u{1F1EF}\u{1F1F2}","jamaican":"\u{1F1EF}\u{1F1F2}","kingston":"\u{1F1EF}\u{1F1F2}",
  "japan":"\u{1F1EF}\u{1F1F5}","japanese":"\u{1F1EF}\u{1F1F5}","tokyo":"\u{1F1EF}\u{1F1F5}",
  "jordan":"\u{1F1EF}\u{1F1F4}","jordanian":"\u{1F1EF}\u{1F1F4}","amman":"\u{1F1EF}\u{1F1F4}",
  "kazakhstan":"\u{1F1F0}\u{1F1FF}","kazakh":"\u{1F1F0}\u{1F1FF}","astana":"\u{1F1F0}\u{1F1FF}","almaty":"\u{1F1F0}\u{1F1FF}",
  "kenya":"\u{1F1F0}\u{1F1EA}","kenyan":"\u{1F1F0}\u{1F1EA}","nairobi":"\u{1F1F0}\u{1F1EA}",
  "kuwait":"\u{1F1F0}\u{1F1FC}","kuwaiti":"\u{1F1F0}\u{1F1FC}",
  "kyrgyzstan":"\u{1F1F0}\u{1F1EC}","kyrgyz":"\u{1F1F0}\u{1F1EC}","bishkek":"\u{1F1F0}\u{1F1EC}",
  "laos":"\u{1F1F1}\u{1F1E6}","laotian":"\u{1F1F1}\u{1F1E6}","vientiane":"\u{1F1F1}\u{1F1E6}",
  "latvia":"\u{1F1F1}\u{1F1FB}","latvian":"\u{1F1F1}\u{1F1FB}","riga":"\u{1F1F1}\u{1F1FB}",
  "lebanon":"\u{1F1F1}\u{1F1E7}","lebanese":"\u{1F1F1}\u{1F1E7}","beirut":"\u{1F1F1}\u{1F1E7}",
  "liberia":"\u{1F1F1}\u{1F1F7}","liberian":"\u{1F1F1}\u{1F1F7}","monrovia":"\u{1F1F1}\u{1F1F7}",
  "libya":"\u{1F1F1}\u{1F1FE}","libyan":"\u{1F1F1}\u{1F1FE}","tripoli":"\u{1F1F1}\u{1F1FE}",
  "lithuania":"\u{1F1F1}\u{1F1F9}","lithuanian":"\u{1F1F1}\u{1F1F9}","vilnius":"\u{1F1F1}\u{1F1F9}",
  "luxembourg":"\u{1F1F1}\u{1F1FA}","luxembourgish":"\u{1F1F1}\u{1F1FA}",
  "madagascar":"\u{1F1F2}\u{1F1EC}","malagasy":"\u{1F1F2}\u{1F1EC}","antananarivo":"\u{1F1F2}\u{1F1EC}",
  "malawi":"\u{1F1F2}\u{1F1FC}","malawian":"\u{1F1F2}\u{1F1FC}","lilongwe":"\u{1F1F2}\u{1F1FC}",
  "malaysia":"\u{1F1F2}\u{1F1FE}","malaysian":"\u{1F1F2}\u{1F1FE}","kuala lumpur":"\u{1F1F2}\u{1F1FE}",
  "maldives":"\u{1F1F2}\u{1F1FB}","maldivian":"\u{1F1F2}\u{1F1FB}","male":"\u{1F1F2}\u{1F1FB}",
  "mali":"\u{1F1F2}\u{1F1F1}","malian":"\u{1F1F2}\u{1F1F1}","bamako":"\u{1F1F2}\u{1F1F1}",
  "malta":"\u{1F1F2}\u{1F1F9}","maltese":"\u{1F1F2}\u{1F1F9}","valletta":"\u{1F1F2}\u{1F1F9}",
  "mauritania":"\u{1F1F2}\u{1F1F7}","mauritanian":"\u{1F1F2}\u{1F1F7}","nouakchott":"\u{1F1F2}\u{1F1F7}",
  "mauritius":"\u{1F1F2}\u{1F1FA}","mauritian":"\u{1F1F2}\u{1F1FA}",
  "mexico":"\u{1F1F2}\u{1F1FD}","mexican":"\u{1F1F2}\u{1F1FD}","mexico city":"\u{1F1F2}\u{1F1FD}",
  "moldova":"\u{1F1F2}\u{1F1E9}","moldovan":"\u{1F1F2}\u{1F1E9}","chisinau":"\u{1F1F2}\u{1F1E9}",
  "mongolia":"\u{1F1F2}\u{1F1F3}","mongolian":"\u{1F1F2}\u{1F1F3}","ulaanbaatar":"\u{1F1F2}\u{1F1F3}",
  "montenegro":"\u{1F1F2}\u{1F1EA}","montenegrin":"\u{1F1F2}\u{1F1EA}","podgorica":"\u{1F1F2}\u{1F1EA}",
  "morocco":"\u{1F1F2}\u{1F1E6}","moroccan":"\u{1F1F2}\u{1F1E6}","rabat":"\u{1F1F2}\u{1F1E6}",
  "mozambique":"\u{1F1F2}\u{1F1FF}","mozambican":"\u{1F1F2}\u{1F1FF}","maputo":"\u{1F1F2}\u{1F1FF}",
  "myanmar":"\u{1F1F2}\u{1F1F2}","burmese":"\u{1F1F2}\u{1F1F2}","burma":"\u{1F1F2}\u{1F1F2}","yangon":"\u{1F1F2}\u{1F1F2}","rangoon":"\u{1F1F2}\u{1F1F2}","naypyidaw":"\u{1F1F2}\u{1F1F2}",
  "namibia":"\u{1F1F3}\u{1F1E6}","namibian":"\u{1F1F3}\u{1F1E6}","windhoek":"\u{1F1F3}\u{1F1E6}",
  "nepal":"\u{1F1F3}\u{1F1F5}","nepali":"\u{1F1F3}\u{1F1F5}","nepalese":"\u{1F1F3}\u{1F1F5}","kathmandu":"\u{1F1F3}\u{1F1F5}",
  "netherlands":"\u{1F1F3}\u{1F1F1}","dutch":"\u{1F1F3}\u{1F1F1}","amsterdam":"\u{1F1F3}\u{1F1F1}","the hague":"\u{1F1F3}\u{1F1F1}",
  "new zealand":"\u{1F1F3}\u{1F1FF}","kiwi":"\u{1F1F3}\u{1F1FF}","wellington":"\u{1F1F3}\u{1F1FF}","auckland":"\u{1F1F3}\u{1F1FF}",
  "nicaragua":"\u{1F1F3}\u{1F1EE}","nicaraguan":"\u{1F1F3}\u{1F1EE}","managua":"\u{1F1F3}\u{1F1EE}",
  "niger":"\u{1F1F3}\u{1F1EA}","nigerien":"\u{1F1F3}\u{1F1EA}","niamey":"\u{1F1F3}\u{1F1EA}",
  "nigeria":"\u{1F1F3}\u{1F1EC}","nigerian":"\u{1F1F3}\u{1F1EC}","abuja":"\u{1F1F3}\u{1F1EC}","lagos":"\u{1F1F3}\u{1F1EC}",
  "north korea":"\u{1F1F0}\u{1F1F5}","dprk":"\u{1F1F0}\u{1F1F5}","pyongyang":"\u{1F1F0}\u{1F1F5}",
  "norway":"\u{1F1F3}\u{1F1F4}","norwegian":"\u{1F1F3}\u{1F1F4}","oslo":"\u{1F1F3}\u{1F1F4}",
  "oman":"\u{1F1F4}\u{1F1F2}","omani":"\u{1F1F4}\u{1F1F2}","muscat":"\u{1F1F4}\u{1F1F2}",
  "pakistan":"\u{1F1F5}\u{1F1F0}","pakistani":"\u{1F1F5}\u{1F1F0}","islamabad":"\u{1F1F5}\u{1F1F0}","karachi":"\u{1F1F5}\u{1F1F0}",
  "palestine":"\u{1F1F5}\u{1F1F8}","palestinian":"\u{1F1F5}\u{1F1F8}","gaza":"\u{1F1F5}\u{1F1F8}","west bank":"\u{1F1F5}\u{1F1F8}","ramallah":"\u{1F1F5}\u{1F1F8}",
  "panama":"\u{1F1F5}\u{1F1E6}","panamanian":"\u{1F1F5}\u{1F1E6}",
  "papua new guinea":"\u{1F1F5}\u{1F1EC}","png":"\u{1F1F5}\u{1F1EC}",
  "paraguay":"\u{1F1F5}\u{1F1FE}","paraguayan":"\u{1F1F5}\u{1F1FE}","asuncion":"\u{1F1F5}\u{1F1FE}",
  "peru":"\u{1F1F5}\u{1F1EA}","peruvian":"\u{1F1F5}\u{1F1EA}","lima":"\u{1F1F5}\u{1F1EA}",
  "philippines":"\u{1F1F5}\u{1F1ED}","filipino":"\u{1F1F5}\u{1F1ED}","philippine":"\u{1F1F5}\u{1F1ED}","manila":"\u{1F1F5}\u{1F1ED}",
  "poland":"\u{1F1F5}\u{1F1F1}","polish":"\u{1F1F5}\u{1F1F1}","warsaw":"\u{1F1F5}\u{1F1F1}",
  "portugal":"\u{1F1F5}\u{1F1F9}","portuguese":"\u{1F1F5}\u{1F1F9}","lisbon":"\u{1F1F5}\u{1F1F9}",
  "qatar":"\u{1F1F6}\u{1F1E6}","qatari":"\u{1F1F6}\u{1F1E6}","doha":"\u{1F1F6}\u{1F1E6}",
  "romania":"\u{1F1F7}\u{1F1F4}","romanian":"\u{1F1F7}\u{1F1F4}","bucharest":"\u{1F1F7}\u{1F1F4}",
  "russia":"\u{1F1F7}\u{1F1FA}","russian":"\u{1F1F7}\u{1F1FA}","moscow":"\u{1F1F7}\u{1F1FA}","kremlin":"\u{1F1F7}\u{1F1FA}","st petersburg":"\u{1F1F7}\u{1F1FA}",
  "rwanda":"\u{1F1F7}\u{1F1FC}","rwandan":"\u{1F1F7}\u{1F1FC}","kigali":"\u{1F1F7}\u{1F1FC}",
  "saudi arabia":"\u{1F1F8}\u{1F1E6}","saudi":"\u{1F1F8}\u{1F1E6}","riyadh":"\u{1F1F8}\u{1F1E6}",
  "senegal":"\u{1F1F8}\u{1F1F3}","senegalese":"\u{1F1F8}\u{1F1F3}","dakar":"\u{1F1F8}\u{1F1F3}",
  "serbia":"\u{1F1F7}\u{1F1F8}","serbian":"\u{1F1F7}\u{1F1F8}","belgrade":"\u{1F1F7}\u{1F1F8}",
  "sierra leone":"\u{1F1F8}\u{1F1F1}","freetown":"\u{1F1F8}\u{1F1F1}",
  "singapore":"\u{1F1F8}\u{1F1EC}","singaporean":"\u{1F1F8}\u{1F1EC}",
  "slovakia":"\u{1F1F8}\u{1F1F0}","slovak":"\u{1F1F8}\u{1F1F0}","bratislava":"\u{1F1F8}\u{1F1F0}",
  "slovenia":"\u{1F1F8}\u{1F1EE}","slovenian":"\u{1F1F8}\u{1F1EE}","ljubljana":"\u{1F1F8}\u{1F1EE}",
  "somalia":"\u{1F1F8}\u{1F1F4}","somali":"\u{1F1F8}\u{1F1F4}","mogadishu":"\u{1F1F8}\u{1F1F4}",
  "south africa":"\u{1F1FF}\u{1F1E6}","south african":"\u{1F1FF}\u{1F1E6}","pretoria":"\u{1F1FF}\u{1F1E6}","johannesburg":"\u{1F1FF}\u{1F1E6}","cape town":"\u{1F1FF}\u{1F1E6}",
  "south korea":"\u{1F1F0}\u{1F1F7}","korean":"\u{1F1F0}\u{1F1F7}","seoul":"\u{1F1F0}\u{1F1F7}",
  "south sudan":"\u{1F1F8}\u{1F1F8}","south sudanese":"\u{1F1F8}\u{1F1F8}","juba":"\u{1F1F8}\u{1F1F8}",
  "spain":"\u{1F1EA}\u{1F1F8}","spanish":"\u{1F1EA}\u{1F1F8}","madrid":"\u{1F1EA}\u{1F1F8}","barcelona":"\u{1F1EA}\u{1F1F8}",
  "sri lanka":"\u{1F1F1}\u{1F1F0}","sri lankan":"\u{1F1F1}\u{1F1F0}","colombo":"\u{1F1F1}\u{1F1F0}",
  "sudan":"\u{1F1F8}\u{1F1E9}","sudanese":"\u{1F1F8}\u{1F1E9}","khartoum":"\u{1F1F8}\u{1F1E9}",
  "sweden":"\u{1F1F8}\u{1F1EA}","swedish":"\u{1F1F8}\u{1F1EA}","stockholm":"\u{1F1F8}\u{1F1EA}",
  "switzerland":"\u{1F1E8}\u{1F1ED}","swiss":"\u{1F1E8}\u{1F1ED}","bern":"\u{1F1E8}\u{1F1ED}","geneva":"\u{1F1E8}\u{1F1ED}","zurich":"\u{1F1E8}\u{1F1ED}",
  "syria":"\u{1F1F8}\u{1F1FE}","syrian":"\u{1F1F8}\u{1F1FE}","damascus":"\u{1F1F8}\u{1F1FE}","aleppo":"\u{1F1F8}\u{1F1FE}",
  "taiwan":"\u{1F1F9}\u{1F1FC}","taiwanese":"\u{1F1F9}\u{1F1FC}","taipei":"\u{1F1F9}\u{1F1FC}",
  "tajikistan":"\u{1F1F9}\u{1F1EF}","tajik":"\u{1F1F9}\u{1F1EF}","dushanbe":"\u{1F1F9}\u{1F1EF}",
  "tanzania":"\u{1F1F9}\u{1F1FF}","tanzanian":"\u{1F1F9}\u{1F1FF}","dar es salaam":"\u{1F1F9}\u{1F1FF}","dodoma":"\u{1F1F9}\u{1F1FF}",
  "thailand":"\u{1F1F9}\u{1F1ED}","thai":"\u{1F1F9}\u{1F1ED}","bangkok":"\u{1F1F9}\u{1F1ED}",
  "togo":"\u{1F1F9}\u{1F1EC}","togolese":"\u{1F1F9}\u{1F1EC}","lome":"\u{1F1F9}\u{1F1EC}",
  "trinidad and tobago":"\u{1F1F9}\u{1F1F9}","trinidadian":"\u{1F1F9}\u{1F1F9}",
  "tunisia":"\u{1F1F9}\u{1F1F3}","tunisian":"\u{1F1F9}\u{1F1F3}","tunis":"\u{1F1F9}\u{1F1F3}",
  "turkey":"\u{1F1F9}\u{1F1F7}","turkish":"\u{1F1F9}\u{1F1F7}","ankara":"\u{1F1F9}\u{1F1F7}","istanbul":"\u{1F1F9}\u{1F1F7}",
  "turkmenistan":"\u{1F1F9}\u{1F1F2}","turkmen":"\u{1F1F9}\u{1F1F2}","ashgabat":"\u{1F1F9}\u{1F1F2}",
  "uganda":"\u{1F1FA}\u{1F1EC}","ugandan":"\u{1F1FA}\u{1F1EC}","kampala":"\u{1F1FA}\u{1F1EC}",
  "ukraine":"\u{1F1FA}\u{1F1E6}","ukrainian":"\u{1F1FA}\u{1F1E6}","kyiv":"\u{1F1FA}\u{1F1E6}","kiev":"\u{1F1FA}\u{1F1E6}","kharkiv":"\u{1F1FA}\u{1F1E6}","odesa":"\u{1F1FA}\u{1F1E6}","odessa":"\u{1F1FA}\u{1F1E6}",
  "uae":"\u{1F1E6}\u{1F1EA}","emirati":"\u{1F1E6}\u{1F1EA}","united arab emirates":"\u{1F1E6}\u{1F1EA}","dubai":"\u{1F1E6}\u{1F1EA}","abu dhabi":"\u{1F1E6}\u{1F1EA}",
  "united kingdom":"\u{1F1EC}\u{1F1E7}","british":"\u{1F1EC}\u{1F1E7}","uk":"\u{1F1EC}\u{1F1E7}","london":"\u{1F1EC}\u{1F1E7}","britain":"\u{1F1EC}\u{1F1E7}",
  "united states":"\u{1F1FA}\u{1F1F8}","american":"\u{1F1FA}\u{1F1F8}","usa":"\u{1F1FA}\u{1F1F8}","washington":"\u{1F1FA}\u{1F1F8}","new york":"\u{1F1FA}\u{1F1F8}",
  "uruguay":"\u{1F1FA}\u{1F1FE}","uruguayan":"\u{1F1FA}\u{1F1FE}","montevideo":"\u{1F1FA}\u{1F1FE}",
  "uzbekistan":"\u{1F1FA}\u{1F1FF}","uzbek":"\u{1F1FA}\u{1F1FF}","tashkent":"\u{1F1FA}\u{1F1FF}",
  "venezuela":"\u{1F1FB}\u{1F1EA}","venezuelan":"\u{1F1FB}\u{1F1EA}","caracas":"\u{1F1FB}\u{1F1EA}",
  "vietnam":"\u{1F1FB}\u{1F1F3}","vietnamese":"\u{1F1FB}\u{1F1F3}","hanoi":"\u{1F1FB}\u{1F1F3}","ho chi minh":"\u{1F1FB}\u{1F1F3}",
  "yemen":"\u{1F1FE}\u{1F1EA}","yemeni":"\u{1F1FE}\u{1F1EA}","sanaa":"\u{1F1FE}\u{1F1EA}","houthi":"\u{1F1FE}\u{1F1EA}",
  "zambia":"\u{1F1FF}\u{1F1F2}","zambian":"\u{1F1FF}\u{1F1F2}","lusaka":"\u{1F1FF}\u{1F1F2}",
  "zimbabwe":"\u{1F1FF}\u{1F1FC}","zimbabwean":"\u{1F1FF}\u{1F1FC}","harare":"\u{1F1FF}\u{1F1FC}"
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
  
  // Check title against all entries in centroids (longest match wins)
  var best = null;
  var bestLen = 0;
  var keys = Object.keys(cCentroids);
  for (var j = 0; j < keys.length; j++) {
    var k = keys[j];
    if (text.includes(k) && k.length > bestLen) {
      best = k;
      bestLen = k.length;
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

var cIndex = [];

// State Department Travel Advisories - Embedded data (updated Apr 2026)
var cStateDeptAdvisories = [
  {n:"Afghanistan",l:4,c:"AF"},{n:"Algeria",l:2,c:"DZ"},{n:"Angola",l:2,c:"AO"},{n:"Argentina",l:1,c:"AR"},
  {n:"Armenia",l:2,c:"AM"},{n:"Australia",l:1,c:"AU"},{n:"Austria",l:1,c:"AT"},{n:"Azerbaijan",l:3,c:"AZ"},
  {n:"Bahamas",l:2,c:"BS"},{n:"Bahrain",l:2,c:"BH"},{n:"Bangladesh",l:3,c:"BD"},{n:"Barbados",l:1,c:"BB"},
  {n:"Belarus",l:4,c:"BY"},{n:"Belgium",l:2,c:"BE"},{n:"Belize",l:2,c:"BZ"},{n:"Benin",l:2,c:"BJ"},
  {n:"Bhutan",l:1,c:"BT"},{n:"Bolivia",l:2,c:"BO"},{n:"Bosnia and Herzegovina",l:2,c:"BA"},
  {n:"Botswana",l:1,c:"BW"},{n:"Brazil",l:2,c:"BR"},{n:"Brunei",l:1,c:"BN"},{n:"Bulgaria",l:1,c:"BG"},
  {n:"Burkina Faso",l:4,c:"BF"},{n:"Myanmar",l:4,c:"MM"},{n:"Burundi",l:3,c:"BI"},{n:"Cabo Verde",l:1,c:"CV"},
  {n:"Cambodia",l:2,c:"KH"},{n:"Cameroon",l:2,c:"CM"},{n:"Canada",l:1,c:"CA"},{n:"Central African Republic",l:4,c:"CF"},
  {n:"Chad",l:3,c:"TD"},{n:"Chile",l:2,c:"CL"},{n:"China",l:3,c:"CN"},{n:"Colombia",l:3,c:"CO"},
  {n:"Comoros",l:2,c:"KM"},{n:"Costa Rica",l:2,c:"CR"},{n:"Cote d'Ivoire",l:2,c:"CI"},{n:"Croatia",l:1,c:"HR"},
  {n:"Cuba",l:2,c:"CU"},{n:"Cyprus",l:1,c:"CY"},{n:"Czechia",l:1,c:"CZ"},{n:"DR Congo",l:3,c:"CD"},
  {n:"Denmark",l:1,c:"DK"},{n:"Djibouti",l:2,c:"DJ"},{n:"Dominica",l:1,c:"DM"},{n:"Dominican Republic",l:2,c:"DO"},
  {n:"Ecuador",l:2,c:"EC"},{n:"Egypt",l:3,c:"EG"},{n:"El Salvador",l:3,c:"SV"},{n:"Equatorial Guinea",l:2,c:"GQ"},
  {n:"Eritrea",l:2,c:"ER"},{n:"Estonia",l:1,c:"EE"},{n:"Eswatini",l:2,c:"SZ"},{n:"Ethiopia",l:3,c:"ET"},
  {n:"Fiji",l:2,c:"FJ"},{n:"Finland",l:1,c:"FI"},{n:"France",l:2,c:"FR"},{n:"Gabon",l:2,c:"GA"},
  {n:"Georgia",l:1,c:"GE"},{n:"Germany",l:2,c:"DE"},{n:"Ghana",l:2,c:"GH"},{n:"Greece",l:1,c:"GR"},
  {n:"Grenada",l:2,c:"GD"},{n:"Guatemala",l:3,c:"GT"},{n:"Guinea",l:3,c:"GN"},{n:"Guinea-Bissau",l:3,c:"GW"},
  {n:"Guyana",l:3,c:"GY"},{n:"Haiti",l:4,c:"HT"},{n:"Honduras",l:3,c:"HN"},{n:"Hong Kong",l:2,c:"HK"},
  {n:"Hungary",l:1,c:"HU"},{n:"Iceland",l:1,c:"IS"},{n:"India",l:2,c:"IN"},{n:"Indonesia",l:2,c:"ID"},
  {n:"Iran",l:4,c:"IR"},{n:"Iraq",l:4,c:"IQ"},{n:"Ireland",l:1,c:"IE"},{n:"Israel",l:3,c:"IL"},
  {n:"Italy",l:2,c:"IT"},{n:"Jamaica",l:2,c:"JM"},{n:"Japan",l:1,c:"JP"},{n:"Jordan",l:2,c:"JO"},
  {n:"Kazakhstan",l:1,c:"KZ"},{n:"Kenya",l:2,c:"KE"},{n:"Kosovo",l:2,c:"XK"},{n:"Kuwait",l:2,c:"KW"},
  {n:"Kyrgyzstan",l:1,c:"KG"},{n:"Laos",l:2,c:"LA"},{n:"Latvia",l:1,c:"LV"},{n:"Lebanon",l:4,c:"LB"},
  {n:"Lesotho",l:2,c:"LS"},{n:"Liberia",l:2,c:"LR"},{n:"Libya",l:4,c:"LY"},{n:"Lithuania",l:1,c:"LT"},
  {n:"Luxembourg",l:1,c:"LU"},{n:"Macau",l:1,c:"MO"},{n:"Madagascar",l:2,c:"MG"},{n:"Malawi",l:2,c:"MW"},
  {n:"Malaysia",l:2,c:"MY"},{n:"Maldives",l:2,c:"MV"},{n:"Mali",l:4,c:"ML"},{n:"Malta",l:1,c:"MT"},
  {n:"Mauritania",l:3,c:"MR"},{n:"Mauritius",l:2,c:"MU"},{n:"Mexico",l:2,c:"MX"},{n:"Moldova",l:2,c:"MD"},
  {n:"Monaco",l:1,c:"MC"},{n:"Mongolia",l:1,c:"MN"},{n:"Montenegro",l:1,c:"ME"},{n:"Morocco",l:2,c:"MA"},
  {n:"Mozambique",l:2,c:"MZ"},{n:"Namibia",l:2,c:"NA"},{n:"Nepal",l:2,c:"NP"},{n:"Netherlands",l:2,c:"NL"},
  {n:"New Zealand",l:1,c:"NZ"},{n:"Nicaragua",l:3,c:"NI"},{n:"Niger",l:4,c:"NE"},{n:"Nigeria",l:3,c:"NG"},
  {n:"North Korea",l:4,c:"KP"},{n:"North Macedonia",l:1,c:"MK"},{n:"Norway",l:1,c:"NO"},{n:"Oman",l:2,c:"OM"},
  {n:"Pakistan",l:3,c:"PK"},{n:"Palau",l:1,c:"PW"},{n:"Panama",l:2,c:"PA"},{n:"Papua New Guinea",l:3,c:"PG"},
  {n:"Paraguay",l:1,c:"PY"},{n:"Peru",l:2,c:"PE"},{n:"Philippines",l:2,c:"PH"},{n:"Poland",l:1,c:"PL"},
  {n:"Portugal",l:1,c:"PT"},{n:"Qatar",l:1,c:"QA"},{n:"Romania",l:1,c:"RO"},{n:"Russia",l:4,c:"RU"},
  {n:"Rwanda",l:2,c:"RW"},{n:"Saint Kitts and Nevis",l:1,c:"KN"},{n:"Saint Lucia",l:1,c:"LC"},
  {n:"Saint Vincent",l:1,c:"VC"},{n:"Samoa",l:2,c:"WS"},{n:"Saudi Arabia",l:3,c:"SA"},
  {n:"Senegal",l:1,c:"SN"},{n:"Serbia",l:2,c:"RS"},{n:"Seychelles",l:1,c:"SC"},{n:"Sierra Leone",l:2,c:"SL"},
  {n:"Singapore",l:1,c:"SG"},{n:"Slovakia",l:1,c:"SK"},{n:"Slovenia",l:1,c:"SI"},{n:"Solomon Islands",l:2,c:"SB"},
  {n:"Somalia",l:4,c:"SO"},{n:"South Africa",l:2,c:"ZA"},{n:"South Korea",l:1,c:"KR"},{n:"South Sudan",l:4,c:"SS"},
  {n:"Spain",l:2,c:"ES"},{n:"Sri Lanka",l:2,c:"LK"},{n:"Sudan",l:4,c:"SD"},{n:"Suriname",l:1,c:"SR"},
  {n:"Sweden",l:2,c:"SE"},{n:"Switzerland",l:1,c:"CH"},{n:"Syria",l:4,c:"SY"},{n:"Taiwan",l:1,c:"TW"},
  {n:"Tajikistan",l:2,c:"TJ"},{n:"Tanzania",l:3,c:"TZ"},{n:"Thailand",l:1,c:"TH"},{n:"The Gambia",l:2,c:"GM"},
  {n:"Timor-Leste",l:2,c:"TL"},{n:"Togo",l:2,c:"TG"},{n:"Trinidad and Tobago",l:2,c:"TT"},
  {n:"Tunisia",l:2,c:"TN"},{n:"Turkey",l:2,c:"TR"},{n:"Turkmenistan",l:2,c:"TM"},{n:"Uganda",l:3,c:"UG"},
  {n:"Ukraine",l:4,c:"UA"},{n:"United Arab Emirates",l:2,c:"AE"},{n:"United Kingdom",l:2,c:"GB"},
  {n:"Uruguay",l:1,c:"UY"},{n:"Uzbekistan",l:2,c:"UZ"},{n:"Vanuatu",l:2,c:"VU"},{n:"Venezuela",l:4,c:"VE"},
  {n:"Vietnam",l:1,c:"VN"},{n:"West Bank and Gaza",l:4,c:"PS"},{n:"Yemen",l:4,c:"YE"},{n:"Zambia",l:2,c:"ZM"},
  {n:"Zimbabwe",l:2,c:"ZW"}
];

// Process embedded data
(function() {
  var levelText = {1:"Normal Precautions",2:"Increased Caution",3:"Reconsider Travel",4:"Do Not Travel"};
  var levelGrade = {1:"low",2:"med",3:"high",4:"crit"};
  
  var countries = cStateDeptAdvisories.map(function(adv) {
    var flag = "";
    if (adv.c && adv.c.length === 2) {
      flag = String.fromCodePoint(0x1F1E6 + adv.c.charCodeAt(0) - 65) + 
             String.fromCodePoint(0x1F1E6 + adv.c.charCodeAt(1) - 65);
    }
    return {
      n: adv.n,
      f: flag,
      l: adv.l,
      t: levelText[adv.l],
      g: levelGrade[adv.l],
      code: adv.c
    };
  });
  
  // Sort by level (highest first), then alphabetically
  countries.sort(function(a, b) {
    if (b.l !== a.l) return b.l - a.l;
    return a.n.localeCompare(b.n);
  });
  
  cIndex = countries;
  
  // Wait for DOM
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function() {
      renderIndex(countries);
      updateStats(countries);
    });
  } else {
    renderIndex(countries);
    updateStats(countries);
  }
})();

function renderIndex(countries) {
  var indexEl = document.getElementById("c-index");
  if (!indexEl) return;
  
  var html = "";
  for (var i = 0; i < countries.length; i++) {
    var c = countries[i];
    html += "<div class='c-row'><div class='c-rank'>"+(i+1)+"</div><div class='c-flag'>"+c.f+"</div><div class='c-info'><div class='c-name'>"+c.n+"</div><div class='c-type'>Level "+c.l+": "+c.t+"</div></div><div class='c-score'><div class='c-score-val "+c.g+"'>"+c.l+"</div></div></div>";
  }
  indexEl.innerHTML = html;
}

function updateStats(countries) {
  var level4 = 0, level3 = 0, level2 = 0, level1 = 0;
  countries.forEach(function(c) {
    if (c.l === 4) level4++;
    else if (c.l === 3) level3++;
    else if (c.l === 2) level2++;
    else level1++;
  });
  
  // Update stat boxes by ID
  var l4El = document.getElementById("c-level4");
  var l3El = document.getElementById("c-level3");
  var l2El = document.getElementById("c-level2");
  var l1El = document.getElementById("c-level1");
  
  if (l4El) l4El.textContent = level4;
  if (l3El) l3El.textContent = level3;
  if (l2El) l2El.textContent = level2;
  if (l1El) l1El.textContent = level1;
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

var currentFilter = "all";

function filterMapPoints(filterType) {
  currentFilter = filterType.toLowerCase();
  
  if (!cOriginalFeatures.length) return;
  
  var filtered;
  if (currentFilter === "all") {
    filtered = cOriginalFeatures;
  } else {
    filtered = cOriginalFeatures.filter(function(f) {
      return f.properties.type === currentFilter;
    });
  }
  
  // Reset expansion state
  cExpandedKey = null;
  if (cMap.getSource("c-lines")) {
    cMap.getSource("c-lines").setData({type:"FeatureCollection",features:[]});
  }
  if (cMap.getSource("cpts")) {
    cMap.getSource("cpts").setData({type:"FeatureCollection",features:filtered});
  }
  
  // Update count
  document.getElementById("c-map-count").textContent = filtered.length + " EVENTS";
}

var filterBtns = document.querySelectorAll(".c-fbtn");
filterBtns.forEach(function(btn) {
  btn.addEventListener("click", function() {
    filterBtns.forEach(function(b){b.classList.remove("active");});
    this.classList.add("active");
    
    var filterText = this.textContent.trim().toLowerCase();
    filterMapPoints(filterText);
  });
});
