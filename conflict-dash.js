var cMap = new maplibregl.Map({
  container: "c-map",
  style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
  center: [20, 15],
  zoom: 2.2,
  attributionControl: false
});

cMap.addControl(new maplibregl.AttributionControl({compact: true}), "bottom-right");

var cCentroids = {
  // A
  "afghanistan":[65.0,33.9],"afghan":[65.0,33.9],"kabul":[65.0,33.9],
  "albania":[20.2,41.2],"albanian":[20.2,41.2],"tirana":[20.2,41.2],
  "algeria":[2.6,28.0],"algerian":[2.6,28.0],"algiers":[2.6,28.0],
  "angola":[17.9,-11.2],"angolan":[17.9,-11.2],"luanda":[17.9,-11.2],
  "argentina":[-63.6,-38.4],"argentine":[-63.6,-38.4],"argentinian":[-63.6,-38.4],"buenos aires":[-63.6,-38.4],
  "armenia":[45.0,40.1],"armenian":[45.0,40.1],"yerevan":[45.0,40.1],
  "australia":[133.8,-25.3],"australian":[133.8,-25.3],"sydney":[133.8,-25.3],"melbourne":[133.8,-25.3],
  "austria":[14.6,47.5],"austrian":[14.6,47.5],"vienna":[14.6,47.5],
  "azerbaijan":[47.6,40.1],"azerbaijani":[47.6,40.1],"baku":[47.6,40.1],
  // B
  "bahrain":[50.6,26.0],"bahraini":[50.6,26.0],"manama":[50.6,26.0],
  "bangladesh":[90.4,23.7],"bangladeshi":[90.4,23.7],"dhaka":[90.4,23.7],
  "belarus":[28.0,53.7],"belarusian":[28.0,53.7],"minsk":[28.0,53.7],
  "belgium":[4.5,50.5],"belgian":[4.5,50.5],"brussels":[4.5,50.5],
  "belize":[-88.5,17.2],"belizean":[-88.5,17.2],
  "benin":[2.3,9.3],"beninese":[2.3,9.3],
  "bolivia":[-64.7,-16.3],"bolivian":[-64.7,-16.3],"la paz":[-64.7,-16.3],
  "botswana":[24.7,-22.3],"gaborone":[24.7,-22.3],
  "brazil":[-51.9,-14.2],"brazilian":[-51.9,-14.2],"brasilia":[-51.9,-14.2],"sao paulo":[-51.9,-14.2],"rio de janeiro":[-51.9,-14.2],
  "bulgaria":[25.5,42.7],"bulgarian":[25.5,42.7],"sofia":[25.5,42.7],
  "burkina faso":[-1.6,12.4],"burkinabe":[-1.6,12.4],"ouagadougou":[-1.6,12.4],
  "burundi":[29.9,-3.4],"burundian":[29.9,-3.4],"bujumbura":[29.9,-3.4],
  // C
  "cambodia":[104.9,12.6],"cambodian":[104.9,12.6],"phnom penh":[104.9,12.6],
  "cameroon":[12.4,3.9],"cameroonian":[12.4,3.9],"yaounde":[12.4,3.9],
  "canada":[-96.8,60.0],"canadian":[-96.8,60.0],"ottawa":[-96.8,60.0],"toronto":[-96.8,60.0],
  "central african republic":[20.9,6.6],"car":[20.9,6.6],"bangui":[20.9,6.6],
  "chad":[18.7,15.5],"chadian":[18.7,15.5],"ndjamena":[18.7,15.5],
  "chile":[-71.5,-35.7],"chilean":[-71.5,-35.7],"santiago":[-71.5,-35.7],
  "china":[104.2,35.9],"chinese":[104.2,35.9],"beijing":[104.2,35.9],"shanghai":[104.2,35.9],"hong kong":[104.2,35.9],"prc":[104.2,35.9],
  "colombia":[-74.3,4.1],"colombian":[-74.3,4.1],"bogota":[-74.3,4.1],
  "comoros":[43.9,-11.9],"comorian":[43.9,-11.9],
  "congo":[15.8,-0.2],"congolese":[15.8,-0.2],"brazzaville":[15.8,-0.2],
  "costa rica":[-83.8,9.7],"costa rican":[-83.8,9.7],"san jose":[-83.8,9.7],
  "croatia":[15.2,45.1],"croatian":[15.2,45.1],"zagreb":[15.2,45.1],
  "cuba":[-79.5,21.5],"cuban":[-79.5,21.5],"havana":[-79.5,21.5],
  "cyprus":[33.4,35.1],"cypriot":[33.4,35.1],"nicosia":[33.4,35.1],
  "czech republic":[15.5,49.8],"czech":[15.5,49.8],"prague":[15.5,49.8],"czechia":[15.5,49.8],
  // D
  "denmark":[9.5,56.3],"danish":[9.5,56.3],"copenhagen":[9.5,56.3],
  "djibouti":[42.6,11.8],"djiboutian":[42.6,11.8],
  "dr congo":[24.0,-2.9],"drc":[24.0,-2.9],"democratic republic of congo":[24.0,-2.9],"kinshasa":[24.0,-2.9],
  // E
  "ecuador":[-78.1,-1.8],"ecuadorian":[-78.1,-1.8],"quito":[-78.1,-1.8],
  "egypt":[30.8,26.8],"egyptian":[30.8,26.8],"cairo":[30.8,26.8],
  "el salvador":[-88.9,13.8],"salvadoran":[-88.9,13.8],"san salvador":[-88.9,13.8],
  "eritrea":[39.8,15.2],"eritrean":[39.8,15.2],"asmara":[39.8,15.2],
  "estonia":[25.0,58.6],"estonian":[25.0,58.6],"tallinn":[25.0,58.6],
  "ethiopia":[40.5,9.1],"ethiopian":[40.5,9.1],"addis ababa":[40.5,9.1],
  // F
  "fiji":[178.1,-17.7],"fijian":[178.1,-17.7],"suva":[178.1,-17.7],
  "finland":[26.0,64.0],"finnish":[26.0,64.0],"helsinki":[26.0,64.0],
  "france":[2.2,46.2],"french":[2.2,46.2],"paris":[2.2,46.2],
  // G
  "gabon":[11.6,-0.8],"gabonese":[11.6,-0.8],"libreville":[11.6,-0.8],
  "gambia":[-15.3,13.4],"gambian":[-15.3,13.4],"banjul":[-15.3,13.4],
  "georgia":[43.4,42.3],"georgian":[43.4,42.3],"tbilisi":[43.4,42.3],
  "germany":[10.5,51.2],"german":[10.5,51.2],"berlin":[10.5,51.2],
  "ghana":[-1.0,7.9],"ghanaian":[-1.0,7.9],"accra":[-1.0,7.9],
  "greece":[21.8,39.1],"greek":[21.8,39.1],"athens":[21.8,39.1],
  "guatemala":[-90.2,15.8],"guatemalan":[-90.2,15.8],
  "guinea":[-11.3,11.0],"guinean":[-11.3,11.0],"conakry":[-11.3,11.0],
  "guyana":[-59.0,5.0],"guyanese":[-59.0,5.0],"georgetown":[-59.0,5.0],
  // H
  "haiti":[-72.3,19.0],"haitian":[-72.3,19.0],"port-au-prince":[-72.3,19.0],
  "honduras":[-86.2,14.8],"honduran":[-86.2,14.8],"tegucigalpa":[-86.2,14.8],
  "hungary":[19.5,47.2],"hungarian":[19.5,47.2],"budapest":[19.5,47.2],
  "hormuz":[56.0,26.5],"strait of hormuz":[56.0,26.5],
  // I
  "iceland":[-18.7,64.9],"icelandic":[-18.7,64.9],"reykjavik":[-18.7,64.9],
  "india":[78.7,20.6],"indian":[78.7,20.6],"new delhi":[78.7,20.6],"mumbai":[78.7,20.6],"delhi":[78.7,20.6],
  "indonesia":[113.9,-0.8],"indonesian":[113.9,-0.8],"jakarta":[113.9,-0.8],
  "iran":[53.7,32.4],"iranian":[53.7,32.4],"tehran":[53.7,32.4],"persian":[53.7,32.4],
  "iraq":[43.7,33.2],"iraqi":[43.7,33.2],"baghdad":[43.7,33.2],
  "ireland":[-8.2,53.4],"irish":[-8.2,53.4],"dublin":[-8.2,53.4],
  "israel":[34.9,31.0],"israeli":[34.9,31.0],"tel aviv":[34.9,31.0],"jerusalem":[34.9,31.0],
  "italy":[12.6,42.5],"italian":[12.6,42.5],"rome":[12.6,42.5],
  // J
  "jamaica":[-77.3,18.1],"jamaican":[-77.3,18.1],"kingston":[-77.3,18.1],
  "japan":[138.3,36.2],"japanese":[138.3,36.2],"tokyo":[138.3,36.2],
  "jordan":[37.2,30.6],"jordanian":[37.2,30.6],"amman":[37.2,30.6],
  // K
  "kazakhstan":[66.9,48.0],"kazakh":[66.9,48.0],"astana":[66.9,48.0],"almaty":[66.9,48.0],
  "kenya":[37.9,0.0],"kenyan":[37.9,0.0],"nairobi":[37.9,0.0],
  "kuwait":[47.5,29.3],"kuwaiti":[47.5,29.3],
  "kyrgyzstan":[74.8,41.2],"kyrgyz":[74.8,41.2],"bishkek":[74.8,41.2],
  // L
  "laos":[103.0,18.2],"laotian":[103.0,18.2],"vientiane":[103.0,18.2],
  "latvia":[24.6,56.9],"latvian":[24.6,56.9],"riga":[24.6,56.9],
  "lebanon":[35.9,33.9],"lebanese":[35.9,33.9],"beirut":[35.9,33.9],
  "liberia":[-9.4,6.4],"liberian":[-9.4,6.4],"monrovia":[-9.4,6.4],
  "libya":[17.2,26.3],"libyan":[17.2,26.3],"tripoli":[17.2,26.3],
  "lithuania":[23.9,55.2],"lithuanian":[23.9,55.2],"vilnius":[23.9,55.2],
  "luxembourg":[6.1,49.8],"luxembourgish":[6.1,49.8],
  // M
  "madagascar":[46.9,-18.8],"malagasy":[46.9,-18.8],"antananarivo":[46.9,-18.8],
  "malawi":[34.3,-13.2],"malawian":[34.3,-13.2],"lilongwe":[34.3,-13.2],
  "malaysia":[109.7,4.2],"malaysian":[109.7,4.2],"kuala lumpur":[109.7,4.2],
  "maldives":[73.2,3.2],"maldivian":[73.2,3.2],"male":[73.2,3.2],
  "mali":[-2.0,17.6],"malian":[-2.0,17.6],"bamako":[-2.0,17.6],
  "malta":[14.4,35.9],"maltese":[14.4,35.9],"valletta":[14.4,35.9],
  "mauritania":[-10.9,20.3],"mauritanian":[-10.9,20.3],"nouakchott":[-10.9,20.3],
  "mauritius":[57.6,-20.3],"mauritian":[57.6,-20.3],
  "mexico":[-102.6,23.6],"mexican":[-102.6,23.6],"mexico city":[-102.6,23.6],
  "moldova":[28.4,47.4],"moldovan":[-28.4,47.4],"chisinau":[28.4,47.4],
  "mongolia":[103.8,46.9],"mongolian":[103.8,46.9],"ulaanbaatar":[103.8,46.9],
  "montenegro":[19.4,42.7],"montenegrin":[19.4,42.7],"podgorica":[19.4,42.7],
  "morocco":[-7.1,31.8],"moroccan":[-7.1,31.8],"rabat":[-7.1,31.8],
  "mozambique":[35.5,-18.7],"mozambican":[35.5,-18.7],"maputo":[35.5,-18.7],
  "myanmar":[95.9,17.1],"burmese":[95.9,17.1],"burma":[95.9,17.1],"yangon":[95.9,17.1],"rangoon":[95.9,17.1],"naypyidaw":[95.9,17.1],
  // N
  "namibia":[18.5,-22.0],"namibian":[18.5,-22.0],"windhoek":[18.5,-22.0],
  "nepal":[84.1,28.4],"nepali":[84.1,28.4],"nepalese":[84.1,28.4],"kathmandu":[84.1,28.4],
  "netherlands":[5.3,52.1],"dutch":[5.3,52.1],"amsterdam":[5.3,52.1],"the hague":[5.3,52.1],
  "new zealand":[172.0,-41.5],"kiwi":[172.0,-41.5],"wellington":[172.0,-41.5],"auckland":[172.0,-41.5],
  "nicaragua":[-85.2,12.9],"nicaraguan":[-85.2,12.9],"managua":[-85.2,12.9],
  "niger":[8.1,17.6],"nigerien":[8.1,17.6],"niamey":[8.1,17.6],
  "nigeria":[8.7,9.1],"nigerian":[8.7,9.1],"abuja":[8.7,9.1],"lagos":[8.7,9.1],
  "north korea":[127.5,40.3],"dprk":[127.5,40.3],"pyongyang":[127.5,40.3],
  "norway":[8.5,60.5],"norwegian":[8.5,60.5],"oslo":[8.5,60.5],
  // O
  "oman":[57.5,21.5],"omani":[57.5,21.5],"muscat":[57.5,21.5],
  // P
  "pakistan":[69.3,30.4],"pakistani":[69.3,30.4],"islamabad":[69.3,30.4],"karachi":[69.3,30.4],
  "palestine":[35.2,31.9],"palestinian":[35.2,31.9],"gaza":[35.2,31.9],"west bank":[35.2,31.9],"ramallah":[35.2,31.9],
  "panama":[-80.8,8.5],"panamanian":[-80.8,8.5],
  "papua new guinea":[143.9,-6.3],"png":[143.9,-6.3],
  "paraguay":[-58.4,-23.4],"paraguayan":[-58.4,-23.4],"asuncion":[-58.4,-23.4],
  "peru":[-75.0,-9.2],"peruvian":[-75.0,-9.2],"lima":[-75.0,-9.2],
  "philippines":[122.9,12.9],"filipino":[122.9,12.9],"philippine":[122.9,12.9],"manila":[122.9,12.9],
  "poland":[19.1,52.1],"polish":[19.1,52.1],"warsaw":[19.1,52.1],
  "portugal":[-8.2,39.4],"portuguese":[-8.2,39.4],"lisbon":[-8.2,39.4],
  // Q
  "qatar":[51.2,25.4],"qatari":[51.2,25.4],"doha":[51.2,25.4],
  // R
  "romania":[24.9,45.9],"romanian":[24.9,45.9],"bucharest":[24.9,45.9],
  "russia":[105.3,61.5],"russian":[105.3,61.5],"moscow":[105.3,61.5],"kremlin":[105.3,61.5],"st petersburg":[105.3,61.5],
  "rwanda":[29.9,-2.0],"rwandan":[29.9,-2.0],"kigali":[29.9,-2.0],
  // S
  "saudi arabia":[45.1,24.0],"saudi":[45.1,24.0],"riyadh":[45.1,24.0],
  "senegal":[-14.5,14.5],"senegalese":[-14.5,14.5],"dakar":[-14.5,14.5],
  "serbia":[21.0,44.0],"serbian":[21.0,44.0],"belgrade":[21.0,44.0],
  "sierra leone":[-11.8,8.5],"freetown":[-11.8,8.5],
  "singapore":[103.8,1.4],"singaporean":[103.8,1.4],
  "slovakia":[19.7,48.7],"slovak":[19.7,48.7],"bratislava":[19.7,48.7],
  "slovenia":[14.8,46.1],"slovenian":[14.8,46.1],"ljubljana":[14.8,46.1],
  "somalia":[46.2,6.1],"somali":[46.2,6.1],"mogadishu":[46.2,6.1],
  "south africa":[25.1,-29.0],"south african":[25.1,-29.0],"pretoria":[25.1,-29.0],"johannesburg":[25.1,-29.0],"cape town":[25.1,-29.0],
  "south korea":[127.8,35.9],"korean":[127.8,35.9],"seoul":[127.8,35.9],
  "south sudan":[31.3,6.9],"south sudanese":[31.3,6.9],"juba":[31.3,6.9],
  "spain":[-3.7,40.5],"spanish":[-3.7,40.5],"madrid":[-3.7,40.5],"barcelona":[-3.7,40.5],
  "sri lanka":[80.7,7.9],"sri lankan":[80.7,7.9],"colombo":[80.7,7.9],
  "sudan":[29.9,12.9],"sudanese":[29.9,12.9],"khartoum":[29.9,12.9],
  "sweden":[18.6,60.1],"swedish":[18.6,60.1],"stockholm":[18.6,60.1],
  "switzerland":[8.2,46.8],"swiss":[8.2,46.8],"bern":[8.2,46.8],"geneva":[8.2,46.8],"zurich":[8.2,46.8],
  "syria":[38.3,34.8],"syrian":[38.3,34.8],"damascus":[38.3,34.8],"aleppo":[38.3,34.8],
  // T
  "taiwan":[120.9,23.7],"taiwanese":[120.9,23.7],"taipei":[120.9,23.7],
  "tajikistan":[71.3,38.9],"tajik":[71.3,38.9],"dushanbe":[71.3,38.9],
  "tanzania":[34.9,-6.4],"tanzanian":[34.9,-6.4],"dar es salaam":[34.9,-6.4],"dodoma":[34.9,-6.4],
  "thailand":[101.0,15.9],"thai":[101.0,15.9],"bangkok":[101.0,15.9],
  "togo":[0.8,8.6],"togolese":[0.8,8.6],"lome":[0.8,8.6],
  "trinidad and tobago":[-61.2,10.7],"trinidadian":[-61.2,10.7],
  "tunisia":[9.0,33.9],"tunisian":[9.0,33.9],"tunis":[9.0,33.9],
  "turkey":[35.2,38.9],"turkish":[35.2,38.9],"ankara":[35.2,38.9],"istanbul":[35.2,38.9],
  "turkmenistan":[59.6,39.0],"turkmen":[59.6,39.0],"ashgabat":[59.6,39.0],
  // U
  "uganda":[32.3,1.4],"ugandan":[32.3,1.4],"kampala":[32.3,1.4],
  "ukraine":[31.2,48.4],"ukrainian":[31.2,48.4],"kyiv":[31.2,48.4],"kiev":[31.2,48.4],"kharkiv":[31.2,48.4],"odesa":[31.2,48.4],"odessa":[31.2,48.4],
  "uae":[53.8,23.4],"emirati":[53.8,23.4],"united arab emirates":[53.8,23.4],"dubai":[53.8,23.4],"abu dhabi":[53.8,23.4],
  "united kingdom":[-3.4,55.4],"british":[-3.4,55.4],"uk":[-3.4,55.4],"london":[-3.4,55.4],"britain":[-3.4,55.4],
  "united states":[-95.7,37.1],"american":[-95.7,37.1],"usa":[-95.7,37.1],"washington":[-95.7,37.1],"new york":[-95.7,37.1],
  "uruguay":[-55.8,-32.5],"uruguayan":[-55.8,-32.5],"montevideo":[-55.8,-32.5],
  "uzbekistan":[63.9,41.4],"uzbek":[63.9,41.4],"tashkent":[63.9,41.4],
  // V
  "venezuela":[-66.6,6.4],"venezuelan":[-66.6,6.4],"caracas":[-66.6,6.4],
  "vietnam":[108.3,14.1],"vietnamese":[108.3,14.1],"hanoi":[108.3,14.1],"ho chi minh":[108.3,14.1],
  // Y
  "yemen":[47.6,15.6],"yemeni":[47.6,15.6],"sanaa":[47.6,15.6],"houthi":[47.6,15.6],
  // Z
  "zambia":[27.8,-13.1],"zambian":[27.8,-13.1],"lusaka":[27.8,-13.1],
  "zimbabwe":[30.0,-19.0],"zimbabwean":[30.0,-19.0],"harare":[30.0,-19.0]
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
        console.log("DEBUG - Title:", title, "| Tags:", tags);
        var country = cDetectCountry(title, tags);
        console.log("DEBUG - Detected country:", country, "| Has centroid:", country ? !!cCentroids[country] : "N/A");
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
