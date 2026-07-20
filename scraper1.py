import re
import os
import sys
import json
import time
import base64
import requests
from urllib.parse import urljoin
from datetime import datetime

# ─────────────────────────────────────────────
# YAPILANDIRMA
# ─────────────────────────────────────────────
BASE_URL = "https://tvnow247.top/watch/"
OUTPUT_FILE = "tv247.m3u"
CHANNELS_FILE = "channels.txt"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://tvnow247.top/",
}

# Bilinen kanal ID'leri (yeni kanallar otomatik eklenir)
CHANNEL_IDS = {
    "abc-usa": "51",
"ahc-american-heroes-channel": "206",
"antenna-tv-usa": "283",
"a-e-usa": "302",
"amc-usa": "303",
"animal-planet": "304",
"astro-supersport-1": "123",
"astro-supersport-2": "124",
"astro-supersport-3": "125",
"astro-supersport-4": "126",
"arena-sport-1-premium": "134",
"arena-sport-2-premium": "135",
"arena-sport-3-premium": "139",
"arena-sport-1-serbia": "429",
"arena-sport-2-serbia": "430",
"arena-sport-3-serbia": "431",
"arena-sport-4-serbia": "581",
"arena-sport-1-croatia": "432",
"arena-sport-2-croatia": "433",
"arena-sport-3-croatia": "434",
"arena-sport-4-croatia": "580",
"alkass-one": "781",
"alkass-two": "782",
"alkass-three": "783",
"alkass-four": "784",
"arena-sport-1-bih": "579",
"abu-dhabi-sports-1-uae": "600",
"abu-dhabi-sports-2-uae": "601",
"abu-dhabi-sports-1-premium": "609",
"abu-dhabi-sports-2-premium": "610",
"astro-cricket": "370",
"antena-3-spain": "531",
"arena-sports-tenis-serbia": "612",
"acc-network-usa": "664",
"adult-swim": "295",
"a-sport-pk": "269",
"axn-movies-portugal": "717",
"arte-de": "725",
"axs-tv-usa": "742",
"abc-ny-usa": "766",
"azteca-7-mx": "844",
"altitude-sports": "923",
"azteca-uno-mx": "934",
"arena-sport-5-serbia": "940",
"arena-sport-6-serbia": "941",
"arena-sport-7-serbia": "942",
"arena-sport-8-serbia": "943",
"arena-sport-9-serbia": "944",
"arena-sport-10-serbia": "945",
"arte-france": "958",
"automoto-la-chaine": "961",
"atv-turkey": "1000",
"a-spor-turkey": "1011",
"bein-sports-mena-english-1": "61",
"bein-sports-mena-english-2": "90",
"bein-sports-1-arabic": "91",
"bein-sports-2-arabic": "92",
"bein-sports-3-arabic": "93",
"bein-sports-4-arabic": "94",
"bein-sports-5-arabic": "95",
"bein-sports-6-arabic": "96",
"bein-sports-7-arabic": "97",
"bein-sports-8-arabic": "98",
"bein-sports-9-arabic": "99",
"bein-sports-xtra-1": "100",
"bein-sports-max-4-france": "494",
"bein-sports-max-5-france": "495",
"bein-sports-max-6-france": "496",
"bein-sports-max-7-france": "497",
"bein-sports-max-8-france": "498",
"bein-sports-max-9-france": "499",
"bein-sports-max-10-france": "500",
"bein-sports-1-france": "116",
"bein-sports-2-france": "117",
"bein-sports-3-france": "118",
"bein-sports-1-turkey": "62",
"bein-sports-2-turkey": "63",
"bein-sports-3-turkey": "64",
"bein-sports-4-turkey": "67",
"bein-sports-hd-qatar": "578",
"bein-sports-usa": "425",
"bein-sports-en-espanol": "372",
"bein-sports-1-australia": "491",
"bein-sports-2-australia": "492",
"bein-sports-3-australia": "493",
"barca-tv-spain": "522",
"benfica-tv-pt": "380",
"boomerang": "648",
"bnt-1-bulgaria": "476",
"bnt-2-bulgaria": "477",
"bnt-3-bulgaria": "478",
"br-fernsehen-de": "737",
"btv-bulgaria": "479",
"btv-action-bulgaria": "481",
"btv-lady-bulgaria": "484",
"bbc-america": "305",
"bet-usa": "306",
"bravo-usa": "307",
"bbc-news-channel-hd": "349",
"bbc-one-uk": "356",
"bbc-two-uk": "357",
"bbc-three-uk": "358",
"bbc-four-uk": "359",
"big-ten-network-btn-usa": "397",
"bein-sports-1-malaysia": "712",
"bein-sports-2-malaysia": "713",
"bein-sports-3-malaysia": "714",
"bfm-tv-france": "957",
"bein-sports-5-turkey": "1010",
"bandsports-brasil": "275",
"canal-plus-motogp-france": "271",
"canal-plus-formula-1": "273",
"cw-pix-11-usa": "280",
"cbs-usa": "52",
"court-tv-usa": "281",
"cw-usa": "300",
"cnbc-usa": "309",
"comedy-central": "310",
"cartoon-network": "339",
"cnn-usa": "345",
"cinemax-usa": "374",
"cuatro-spain": "535",
"channel-4-uk": "354",
"channel-5-uk": "355",
"cbs-sports-network": "308",
"canal-plus-france": "121",
"canal-plus-sport-france": "122",
"canal-plus-foot-france": "463",
"canal-plus-sport360": "464",
"canal-11-portugal": "540",
"canal-plus-sport-poland": "48",
"canal-plus-sport-2-poland": "73",
"canal-plus-sport-3-poland": "259",
"canal-plus-sport-5-poland": "75",
"canal-plus-premium-poland": "566",
"canal-plus-family-poland": "567",
"canal-plus-seriale-poland": "570",
"canal-plus-sport-1-afrique": "486",
"canal-plus-sport-2-afrique": "487",
"canal-plus-sport-3-afrique": "488",
"canal-plus-sport-4-afrique": "489",
"canal-plus-sport-5-afrique": "490",
"canal-9-denmark": "805",
"combate-brasil": "89",
"cosmote-sport-1-hd": "622",
"cosmote-sport-2-hd": "623",
"cosmote-sport-3-hd": "624",
"cosmote-sport-4-hd": "625",
"cosmote-sport-5-hd": "626",
"cosmote-sport-6-hd": "627",
"cosmote-sport-7-hd": "628",
"cosmote-sport-8-hd": "629",
"cosmote-sport-9-hd": "630",
"channel-9-israel": "546",
"channel-10-israel": "547",
"channel-11-israel": "548",
"channel-12-israel": "549",
"channel-13-israel": "551",
"channel-14-israel": "552",
"c-more-first-sweden": "812",
"c-more-hits-sweden": "813",
"c-more-series-sweden": "814",
"cozi-tv-usa": "748",
"cmt-usa": "647",
"ctv-canada": "602",
"ctv-2-canada": "838",
"crime-plus-investigation-usa": "669",
"comet-usa": "696",
"cooking-channel-usa": "697",
"cleo-tv": "715",
"c-span-1": "750",
"cbsny-usa": "767",
"chicago-sports-network": "776",
"citytv": "831",
"cbc-ca": "832",
"claro-sports-mx": "933",
"canal5-mx": "936",
"c8-france": "956",
"cnews-france": "964",
"canal-plus-sport-cz": "1020",
"ct-sport-cz": "1033",
"cbs-sports-golazo": "910",
"cmtv-portugal": "790",
"cytavision-sports-1-cyprus": "911",
"cytavision-sports-2-cyprus": "912",
"cytavision-sports-3-cyprus": "913",
"cytavision-sports-4-cyprus": "914",
"cytavision-sports-5-cyprus": "915",
"cytavision-sports-6-cyprus": "916",
"cytavision-sports-7-cyprus": "917",
"dazn-1-uk": "230",
"discovery-velocity-ca": "285",
"dazn-1-bar-de": "426",
"dazn-2-bar-de": "427",
"dazn-1-spain": "445",
"dazn-2-spain": "446",
"dazn-3-spain": "447",
"dazn-4-spain": "448",
"dazn-f1-es": "537",
"dazn-laliga": "538",
"dazn-portugal-fifa-mundial-de-clubes": "918",
"dr1-denmark": "801",
"dr2-denmark": "802",
"digi-sport-1-romania": "400",
"digi-sport-2-romania": "401",
"digi-sport-3-romania": "402",
"digi-sport-4-romania": "403",
"diema-sport-bulgaria": "465",
"diema-sport-2-bulgaria": "466",
"diema-sport-3-bulgaria": "467",
"diema-bulgaria": "482",
"diema-family-bulgaria": "485",
"dubai-sports-1-uae": "604",
"dubai-sports-2-uae": "605",
"dubai-sports-3-uae": "606",
"dubai-racing-2-uae": "608",
"dstv-mzansi-magic": "786",
"dstv-m-net": "827",
"dstv-kyknet-kie": "828",
"dazn-zona-italy": "877",
"discovery-life-channel": "311",
"disney-channel": "312",
"discovery-channel": "313",
"discovery-family": "657",
"disney-xd": "314",
"destination-america": "651",
"disney-jr": "652",
"dave": "348",
"espn-usa": "44",
"espn2-usa": "45",
"espnu-usa": "316",
"espn-1-nl": "379",
"espn-2-nl": "386",
"eleven-sports-1-poland": "71",
"eleven-sports-2-poland": "72",
"eleven-sports-3-poland": "428",
"eleven-sports-1-portugal": "455",
"eleven-sports-2-portugal": "456",
"eleven-sports-3-portugal": "457",
"eleven-sports-4-portugal": "458",
"eleven-sports-5-portugal": "459",
"eurosport-1-greece": "41",
"eurosport-2-greece": "42",
"eurosport-1-poland": "57",
"eurosport-2-poland": "58",
"eurosport-1-sw": "231",
"eurosport-2-sw": "232",
"eurosport-1-nl": "233",
"eurosport-2-nl": "234",
"eurosport-1-spain": "524",
"eurosport-2-spain": "525",
"eurosport-1-italy": "878",
"eurosport-2-italy": "879",
"espn-premium-argentina": "387",
"espn-brasil": "81",
"espn2-brasil": "82",
"espn3-brasil": "83",
"espn4-brasil": "85",
"espn-argentina": "149",
"espn2-argentina": "150",
"espn-deportes": "375",
"espnews": "288",
"e-entertainment-television": "315",
"e4-channel": "363",
"espn-3-nl": "888",
"ert-1-greece": "774",
"eurosport-1-france": "772",
"eurosport-2-france": "773",
"espn3-argentina": "798",
"espn-1-mx": "925",
"espn-2-mx": "926",
"espn-3-mx": "927",
"espn-4-mx": "928",
"fuse-tv-usa": "279",
"fox-sports-1-usa": "39",
"fox-sports-2-usa": "758",
"fox-soccer-plus": "756",
"fox-cricket": "369",
"fox-deportes-usa": "643",
"fox-sports-502-au": "820",
"fox-sports-503-au": "821",
"fox-sports-504-au": "822",
"fox-sports-505-au": "823",
"fox-sports-506-au": "824",
"fox-sports-507-au": "825",
"fox-sports-1-mx": "929",
"fox-sports-2-mx": "930",
"fox-sports-3-mx": "931",
"fox-sports-argentina": "787",
"fox-sports-2-argentina": "788",
"fox-sports-3-argentina": "789",
"fox-sports-premium-mx": "830",
"filmbox-premium-poland": "568",
"fight-network": "757",
"fox-business": "297",
"fox-hd-bulgaria": "483",
"fox-usa": "54",
"fx-usa": "317",
"fxx-usa": "298",
"freeform": "301",
"fox-news": "347",
"fx-movie-channel": "381",
"fyi": "665",
"film4-uk": "688",
"fashion-tv": "744",
"fetv-family-entertainment-television": "751",
"foxny-usa": "768",
"fox-weather-channel": "775",
"fanduel-sports-network-arizona": "890",
"fanduel-sports-network-detroit": "891",
"fanduel-sports-network-florida": "892",
"fanduel-sports-network-great-lakes": "893",
"fanduel-sports-network-indiana": "894",
"fanduel-sports-network-kansas-city": "895",
"fanduel-sports-network-midwest": "896",
"fanduel-sports-network-new-orleans": "897",
"fanduel-sports-network-north": "898",
"fanduel-sports-network-ohio": "899",
"fanduel-sports-network-oklahoma": "900",
"fanduel-sports-network-socal": "902",
"fanduel-sports-network-south": "903",
"fanduel-sports-network-southeast": "904",
"fanduel-sports-network-sun": "905",
"fanduel-sports-network-west": "906",
"fanduel-sports-network-wisconsin": "907",
"france-2": "950",
"france-3": "951",
"france-4": "952",
"france-5": "953",
"gol-play-spain": "530",
"golf-channel-usa": "318",
"game-show-network": "319",
"goltv-usa": "597",
"gold-uk": "687",
"great-american-family-channel-gac": "699",
"galavision-usa": "743",
"grit-channel": "752",
"globo-sp": "760",
"globo-rio": "761",
"global-ca": "836",
"the-hallmark-channel": "320",
"hallmark-movies-and-mysteries": "296",
"heroes-and-icons-hi-usa": "282",
"hbo-usa": "321",
"hbo2-usa": "689",
"hbo-comedy-usa": "690",
"hbo-family-usa": "691",
"hbo-latino-usa": "692",
"hbo-signature-usa": "693",
"hbo-zone-usa": "694",
"hbo-poland": "569",
"history-usa": "322",
"headline-news": "323",
"hgtv": "382",
"happy-tv-serbia": "846",
"hot3-israel": "553",
"itv-1-uk": "350",
"itv-2-uk": "351",
"itv-3-uk": "352",
"itv-4-uk": "353",
"itvbe": "876",
"italia-1-italy": "854",
"investigation-discovery-id-usa": "324",
"ion-usa": "325",
"ifc-tv-usa": "656",
"kanal-4-denmark": "803",
"kanal-5-denmark": "804",
"kabel-eins-de": "731",
"laligatv-uk": "276",
"law-crime-network": "278",
"laliga-smartbank-tv": "539",
"lequipe-france": "645",
"la-sexta-spain": "534",
"liverpool-tv-lfc-tv": "826",
"logo-tv-usa": "849",
"las-estrellas": "924",
"lifetime-network": "326",
"lifetime-movies-network": "389",
"la7": "855",
"la7d": "856",
"match-football-1": "136",
"match-football-2": "137",
"match-football-3": "138",
"match-premier": "573",
"match-tv": "127",
"match-boec": "395",
"movistar-laliga": "84",
"movistar-liga-de-campeones": "435",
"movistar-deportes-4": "436",
"movistar-deportes-2": "438",
"movistar-deportes-3": "526",
"movistar-deportes-4-alt1": "527",
"movistar-golf": "528",
"motowizja": "563",
"msg": "765",
"msnbc": "327",
"magnolia-network": "299",
"m4-sports": "265",
"movistar-supercopa-de-espana": "437",
"mtv": "367",
"mtv-usa": "371",
"mutv-uk": "377",
"m6-france": "470",
"mavtv-usa": "646",
"max-sport-croatia-1": "779",
"max-sport-croatia-2": "780",
"marquee-sports-network": "770",
"max-sport-bulgaria-1": "472",
"max-sport-bulgaria-2": "473",
"max-sport-bulgaria-3": "474",
"max-sport-bulgaria-4": "475",
"mlb-network-usa": "399",
"masn-usa": "829",
"my9tv-usa": "654",
"motor-trend": "661",
"metv-usa": "662",
"mdr-de": "733",
"mundotoro-tv-spain": "749",
"monumental-sports-network": "778",
"mtv-denmark": "806",
"mgm-plus-epix-usa": "791",
"nbc10-philadelphia": "277",
"nhl-network-usa": "663",
"nfl-redzone": "667",
"nova-sport-bulgaria": "468",
"nova-sport-serbia": "582",
"nova-sports-greece-1": "631",
"nova-sports-greece-2": "632",
"nova-sports-greece-3": "633",
"nova-sports-greece-4": "634",
"nova-sports-greece-5": "635",
"nova-sports-greece-6": "636",
"nova-sports-premier-league-greece": "599",
"nova-sports-start-greece": "637",
"nova-sports-prime-greece": "638",
"nova-sports-news-greece": "639",
"nick-music": "666",
"nesn-usa": "762",
"nbc-usa": "53",
"nba-tv-usa": "404",
"nbc-sports-philadelphia": "777",
"nfl-network": "405",
"nbc-sports-bay-area": "753",
"nbc-sports-boston": "754",
"nbc-sports-california": "755",
"nbcny-usa": "769",
"nova-tv-bulgaria": "480",
"nova-s-serbia": "847",
"newsnation-usa": "292",
"national-geographic": "328",
"nick-jr": "329",
"nick": "330",
"nicktoons": "649",
"ndr": "736",
"newsmax-usa": "613",
"nat-geo-wild-usa": "745",
"noovo": "835",
"nbc-universo": "845",
"now-tv-turkey": "1003",
"nova-sport": "1021",
"nova-sport-cz-2": "1022",
"nova-sport-cz-3": "1023",
"nova-sport-cz-4": "1024",
"nova-sport-cz-5": "1025",
"nova-sport-cz-6": "1026",
"ontime-sports": "611",
"one-hd-israel-1": "541",
"one-hd-israel-2": "542",
"orange-sport-romania-1": "439",
"orange-sport-romania-2": "440",
"orange-sport-romania-3": "441",
"orange-sport-romania-4": "442",
"oprah-winfrey-network-own": "331",
"oxygen-true-crime": "332",
"outdoor-channel-usa": "848",
"oneplay-sport-cz-1": "1027",
"oneplay-sport-cz-2": "1028",
"oneplay-sport-cz-3": "1029",
"polsat-poland": "562",
"polsat-sport-poland": "47",
"polsat-sport-2": "50",
"polsat-sport-3": "129",
"polsat-news": "443",
"polsat-film": "564",
"porto-canal": "718",
"prosieben": "730",
"premier-sports-ireland-1": "771",
"ptv-sports": "450",
"pdc-tv": "43",
"premier-brasil": "88",
"prima-sport-1": "583",
"prima-sport-2": "584",
"prima-sport-3": "585",
"prima-sport-4": "586",
"paramount-network": "334",
"pop-tv": "653",
"premier-sports-ireland-2": "799",
"prima-tv": "843",
"premier-sport-cz-1": "1030",
"premier-sport-cz-2": "1031",
"premier-sport": "1032",
"pac-12-network": "287",
"pbs": "210",
"reelz-channel": "293",
"rte-1": "364",
"rte-2": "365",
"rmc-sport-1": "119",
"rmc-sport-2": "120",
"rtp-1": "719",
"rtp-2": "720",
"rtp-3": "721",
"rai-1": "850",
"rai-2": "851",
"rai-3": "852",
"rai-4": "853",
"rai-sport": "882",
"rai-premium": "858",
"real-madrid-tv": "523",
"rtl": "740",
"rds-2": "839",
"rds-2-alt1": "840",
"rds-info": "841",
"ring-bulgaria": "471",
"rtl7-netland": "390",
"racing-tv-uk": "555",
"rally-tv": "607",
"root-sports-northwest": "920",
"sky-sports-football": "35",
"sky-sports-plus": "36",
"sky-sports-action": "37",
"sky-sports-main-event": "38",
"sky-sports-tennis-2": "46",
"sky-sports-premier-league": "130",
"sky-sports-f1-1": "60",
"sky-sports-cricket": "65",
"sky-sports-golf-2": "70",
"sky-sports-de-1": "240",
"sky-sports-de-2": "241",
"sky-sports-golf-italy": "574",
"sky-sport-motogp-italy": "575",
"sky-sport-tennis-italy": "576",
"sky-sport-f1-italy": "577",
"sky-sports-news-uk": "366",
"sky-sports-mix-uk": "449",
"sky-sport-top-event-de": "556",
"sky-sport-mix-de": "557",
"sky-sport-bundesliga-1": "558",
"sky-sport-austria": "559",
"sportsnet-new-york-sny": "759",
"sky-sport-max-italy": "460",
"sky-sport-uno-italy": "461",
"sky-sport-arena-italy": "462",
"sky-sports-racing-uk": "554",
"sky-uno-italy": "881",
"sony-ten-1": "885",
"sony-ten-2": "886",
"sony-ten-3": "887",
"sky-sport-bundesliga-2": "946",
"sky-sport-bundesliga-3": "947",
"sky-sport-bundesliga-4": "948",
"sky-sport-bundesliga-3-alt1": "949",
"spectrum-sportsnet-usa": "982",
"sky-sport-nz-1": "588",
"sky-sport-nz-2": "589",
"sky-sport-nz-3": "590",
"sky-sport-nz-4": "591",
"sky-sport-nz-5": "592",
"sky-sport-nz-6": "593",
"sky-sport-nz-7": "594",
"sky-sport-nz-8": "595",
"sky-sport-nz-9": "596",
"sky-sport-select-nz": "587",
"sport-tv-portugal-1": "49",
"sport-tv-portugal-2": "74",
"sport-tv-portugal-4": "289",
"sport-tv-portugal-3": "454",
"sport-tv-portugal-5": "290",
"sport-tv-portugal-6": "291",
"sic-portugal": "722",
"sec-network-usa": "385",
"sportv-brasil-1": "78",
"sportv-brasil-2": "79",
"sportv-brasil-3": "80",
"sport-klub-serbia-1": "101",
"sport-klub-serbia-2": "102",
"sport-klub-serbia-3": "103",
"sport-klub-serbia-4": "104",
"sport-klub-hd-serbia": "453",
"sportsnet-ontario": "406",
"sportsnet-one": "411",
"sportsnet-west": "407",
"sportsnet-east": "408",
"sportsnet-360": "409",
"sportsnet-world": "410",
"supersport-grandstand": "412",
"supersport-psl": "413",
"supersport-premier-league": "414",
"supersport-laliga": "415",
"supersport-variety-1": "416",
"supersport-variety-2": "417",
"supersport-variety-3": "418",
"supersport-variety-4": "419",
"supersport-action": "420",
"supersport-rugby": "421",
"supersport-golf": "422",
"supersport-tennis": "423",
"supersport-motorsport": "424",
"supersport-football": "56",
"supersport-cricket": "368",
"supersport-maximo": "572",
"sporting-tv-portugal": "716",
"sportdigital-fussball": "571",
"spectrum-sportsnet-la": "764",
"sportdigital-germany": "640",
"sport1-germany": "641",
"s4c-uk": "670",
"sport-klub-golf-croatia": "710",
"sat1-de": "729",
"sky-cinema-premiere-uk": "671",
"sky-cinema-select-uk": "672",
"sky-cinema-hits-uk": "673",
"sky-cinema-greats-uk": "674",
"sky-cinema-animation-uk": "675",
"sky-cinema-family-uk": "676",
"sky-cinema-action-uk": "677",
"sky-cinema-comedy-uk": "678",
"sky-cinema-thriller-uk": "679",
"sky-cinema-drama-uk": "680",
"sky-cinema-sci-fi-horror-uk": "681",
"showtime-shoxbet-usa": "695",
"see-denmark": "811",
"sky-cinema-collection-italy": "859",
"sky-cinema-uno-italy": "860",
"sky-cinema-action-italy": "861",
"sky-cinema-comedy-italy": "862",
"sky-cinema-uno-24-italy": "863",
"sky-cinema-romance-italy": "864",
"sky-cinema-family-italy": "865",
"sky-cinema-due-24-italy": "866",
"sky-cinema-drama-italy": "867",
"sky-cinema-suspense": "868",
"sky-sport-24": "869",
"sky-sport-calcio": "870",
"sky-calcio-1": "871",
"sky-calcio-2": "872",
"sky-calcio-3": "873",
"sky-calcio-4": "874",
"sky-sport-basket": "875",
"sky-serie": "880",
"starzplay-criclife-1": "284",
"sky-showcase": "682",
"sky-arts": "683",
"sky-comedy": "684",
"sky-crime": "685",
"sky-history": "686",
"sky-max": "708",
"ssc-sport-1": "614",
"ssc-sport-2": "615",
"ssc-sport-3": "616",
"ssc-sport-4": "617",
"ssc-sport-5": "618",
"ssc-sport-extra-1": "619",
"ssc-sport-extra-2": "620",
"ssc-sport-extra-3": "621",
"sport-1-israel": "140",
"sport-2-israel": "141",
"sport-3-israel": "142",
"sport-4-israel": "143",
"sport-5-israel": "144",
"sport-5-plus-israel": "145",
"sport-5-live-israel": "146",
"sport-5-star-israel": "147",
"sport-5-gold-israel": "148",
"science-channel": "294",
"showtime-usa": "333",
"starz": "335",
"sky-witness-hd": "361",
"sixx-de": "732",
"sky-atlantic": "362",
"syfy-usa": "373",
"sundance-tv": "658",
"swr": "735",
"super-rtl": "738",
"sr-fernsehen": "739",
"sky-sports-golf-1": "785",
"smithsonian-channel": "603",
"sky-sports-f1-1-alt1": "274",
"sky-sports-tennis-1": "884",
"sbs6": "883",
"star-sports": "267",
"star-sports-hindi": "268",
"showtime-2": "792",
"showtime-showcase": "793",
"showtime-extreme": "794",
"showtime-family-zone": "795",
"showtime-next": "796",
"showtime-women": "797",
"space-city-home-network": "921",
"sportsnet-pittsburgh": "922",
"tnt-sports-1": "31",
"tnt-sports-2": "32",
"tnt-sports-3": "33",
"tnt-sports-4": "34",
"tsn": "111",
"tsn2": "112",
"tsn3": "113",
"tsn4": "114",
"tsn5": "115",
"tvn": "565",
"tvn24": "444",
"tvp1": "560",
"tvp2": "561",
"telecinco": "532",
"tve-la-1": "533",
"tve-la-2": "536",
"tvi": "723",
"tvi-reality": "724",
"teledeporte": "529",
"tyc-sports": "746",
"tvp-sport": "128",
"tnt-brasil": "87",
"tnt-sports-argentina": "388",
"tnt-sports-chile": "642",
"tennis-channel": "40",
"ten-sports-pk": "741",
"tudn-usa": "66",
"telemundo": "131",
"tbs-usa": "336",
"tlc": "337",
"tnt-usa": "338",
"tf1-france": "469",
"tva-sports-1": "833",
"tva-sports-2": "834",
"tvc-deportes-mx": "932",
"tudn-mx": "935",
"travel-channel": "340",
"trutv-usa": "341",
"tvland": "342",
"tcm-usa": "644",
"tmc-channel-usa": "698",
"the-food-network": "384",
"the-weather-channel": "394",
"tvp-info": "452",
"teennick": "650",
"tv-one-usa": "660",
"tv2-bornholm": "807",
"tv2-sport-x": "808",
"tv3-sport": "809",
"tv2-sport": "810",
"tv2-denmark": "817",
"tv2-zulu": "818",
"tv3-plus": "819",
"tvo-ca": "842",
"tv4-hockey": "700",
"tv3-max": "223",
"t-sports-bd": "270",
"tv4-tennis": "701",
"tv4-motor": "702",
"tv4-sport-live-4": "703",
"tv4-sport-live-4-alt1": "704",
"tv4-sport-live-4-alt2": "705",
"tv4-sport-live-4-alt3": "706",
"tv4-sportkanalen": "707",
"tv4-football-sweden": "747",
"tennis-plus-10": "709",
"tennis-plus-12": "711",
"trt-spor-tr": "889",
"usa-network": "343",
"universal-kids-usa": "668",
"univision": "132",
"unimas": "133",
"viaplay-sports-1": "451",
"viaplay-sports-2": "550",
"vamos-spain": "521",
"v-film-premiere": "815",
"v-film-family": "816",
"vodafone-sport": "260",
"v-sport-motor-sweden": "272",
"vh1-usa": "344",
"veronica-nl-netherland": "378",
"vtv-plus-uruguay": "391",
"vice-tv": "659",
"willow-cricket": "346",
"willow-xtra": "598",
"wwe-network": "376",
"win-sports-plus-colombia": "392",
"wetv-usa": "655",
"wdr-de": "734",
"ytv-ca": "286",
"yes-network-usa": "763",
"yes-movies-action-israel": "543",
"yes-movies-kids-israel": "544",
"yes-movies-comedy-israel": "545",
"yes-tv-ca": "837",
"ziggo-sport-nl-6": "393",
"ziggo-sport-nl-2": "398",
"ziggo-sport-nl-3": "919",
"ziggo-sport-nl-4": "396",
"ziggo-sport-nl-5": "383",
"ziggo-sport-nl-6-alt1": "901",
"zdf": "727",
"zdf-info": "728",
"6ter": "963",
"20-mediaset": "857",
"6eren": "800",
"5-usa": "360",
"3sat": "726",
"18-plus-18": "501",
"18-plus-18-alt1": "502",
"18-plus-18-alt2": "503",
"18-plus-18-alt3": "504",
"18-plus-18-alt4": "505",
"18-plus-18-alt5": "506",
"18-plus-18-alt6": "507",
"18-plus-18-alt7": "508",
"18-plus-18-alt8": "509",
"18-plus-18-alt9": "510",
"18-plus-18-alt10": "511",
"18-plus-18-alt11": "512",
"18-plus-18-alt12": "513",
"18-plus-18-alt13": "514",
"18-plus-18-alt14": "515",
"18-plus-18-alt15": "516",
"18-plus-18-alt16": "517",
"18-plus-18-alt17": "518",
"18-plus-18-alt18": "519",
"18-plus-18-alt19": "520",
}


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ─────────────────────────────────────────────
# TOKEN OLUŞTUR
# ─────────────────────────────────────────────
def generate_playlist_url(channel_id):
    """Channel ID'den playlist URL'si oluştur"""
    ts = int(time.time() * 1000)
    
    token_data = {
        "channelId": str(channel_id),
        "ts": ts
    }
    
    token_json = json.dumps(token_data, separators=(',', ':'))
    token_b64 = base64.b64encode(token_json.encode()).decode()
    
    return f"https://chunk.tvdaily.xyz/api/proxy/playlist?token={token_b64}"


# ─────────────────────────────────────────────
# KANAL ID BUL (Sayfadan)
# ─────────────────────────────────────────────
def find_channel_id_from_page(channel_slug):
    """
    Sayfa HTML'inden channel ID'yi çıkar
    """
    url = f"{BASE_URL}{channel_slug}/"
    session = requests.Session()
    session.headers.update(HEADERS)
    
    log(f"  Sayfa taranıyor: {url}")
    
    try:
        resp = session.get(url, timeout=30)
        html = resp.text
        
        # 1. Doğrudan sayfada ID ara
        id_patterns = [
            r'data-id=["\'](\d+)["\']',
            r'channel[_-]?id["\']?\s*[:=]\s*["\']?(\d+)',
            r'stream[_-]?id["\']?\s*[:=]\s*["\']?(\d+)',
            r'/embed/(\d+)',
            r'\?id=(\d+)',
            r'&id=(\d+)',
        ]
        
        for pattern in id_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            if matches:
                channel_id = matches[0]
                log(f"  ✓ Sayfada ID bulundu: {channel_id}")
                return channel_id
        
        # 2. iframe src'lerini kontrol et
        iframe_pattern = r'<iframe[^>]+src=["\']([^"\']+)["\']'
        iframes = re.findall(iframe_pattern, html, re.IGNORECASE)
        
        for iframe_src in iframes:
            iframe_url = urljoin(url, iframe_src)
            log(f"  iframe kontrol: {iframe_url[:80]}...")
            
            # iframe URL'sinde ID var mı?
            id_match = re.search(r'[?&]id=(\d+)', iframe_url)
            if id_match:
                channel_id = id_match.group(1)
                log(f"  ✓ iframe URL'de ID bulundu: {channel_id}")
                return channel_id
            
            # iframe içeriğini çek
            try:
                resp2 = session.get(
                    iframe_url,
                    timeout=30,
                    headers={**HEADERS, "Referer": url}
                )
                iframe_html = resp2.text
                
                # iframe içinde ID ara
                for pattern in id_patterns:
                    matches = re.findall(pattern, iframe_html, re.IGNORECASE)
                    if matches:
                        channel_id = matches[0]
                        log(f"  ✓ iframe içinde ID bulundu: {channel_id}")
                        return channel_id
                
                # iframe içinde başka iframe var mı?
                inner_iframes = re.findall(iframe_pattern, iframe_html, re.IGNORECASE)
                for inner_src in inner_iframes:
                    inner_url = urljoin(iframe_url, inner_src)
                    log(f"    iç iframe: {inner_url[:80]}...")
                    
                    id_match = re.search(r'[?&]id=(\d+)', inner_url)
                    if id_match:
                        channel_id = id_match.group(1)
                        log(f"  ✓ iç iframe'de ID bulundu: {channel_id}")
                        return channel_id
                    
                    # İç iframe içeriğini çek
                    try:
                        resp3 = session.get(
                            inner_url,
                            timeout=30,
                            headers={**HEADERS, "Referer": iframe_url}
                        )
                        inner_html = resp3.text
                        
                        for pattern in id_patterns:
                            matches = re.findall(pattern, inner_html, re.IGNORECASE)
                            if matches:
                                channel_id = matches[0]
                                log(f"  ✓ iç iframe içinde ID bulundu: {channel_id}")
                                return channel_id
                        
                        # Token URL var mı?
                        token_match = re.search(
                            r'channelId["\']?\s*[:=]\s*["\']?(\d+)',
                            inner_html,
                            re.IGNORECASE
                        )
                        if token_match:
                            return token_match.group(1)
                            
                    except Exception as e:
                        log(f"    iç iframe hatası: {e}")
                        
            except Exception as e:
                log(f"  iframe hatası: {e}")
        
        # 3. Script tag'larında ara
        script_pattern = r'<script[^>]*>(.*?)</script>'
        scripts = re.findall(script_pattern, html, re.DOTALL | re.IGNORECASE)
        
        for script in scripts:
            for pattern in id_patterns:
                matches = re.findall(pattern, script, re.IGNORECASE)
                if matches:
                    channel_id = matches[0]
                    log(f"  ✓ Script'te ID bulundu: {channel_id}")
                    return channel_id
                    
    except Exception as e:
        log(f"  Sayfa hatası: {e}")
    
    return None


# ─────────────────────────────────────────────
# DOĞRUDAN TOKEN URL BUL
# ─────────────────────────────────────────────
def find_direct_token_url(channel_slug):
    """
    Sayfada hazır token URL'si ara
    """
    url = f"{BASE_URL}{channel_slug}/"
    session = requests.Session()
    session.headers.update(HEADERS)
    
    try:
        resp = session.get(url, timeout=30)
        html = resp.text
        
        # Hazır playlist URL'si var mı?
        token_pattern = r'(https?://[^\s"\'<>]+/api/proxy/playlist\?token=[A-Za-z0-9+/=_-]+)'
        
        # Ana sayfada ara
        matches = re.findall(token_pattern, html)
        if matches:
            log(f"  ✓ Doğrudan token URL bulundu!")
            return matches[0]
        
        # iframe'lerde ara
        iframe_pattern = r'<iframe[^>]+src=["\']([^"\']+)["\']'
        iframes = re.findall(iframe_pattern, html, re.IGNORECASE)
        
        for iframe_src in iframes:
            iframe_url = urljoin(url, iframe_src)
            
            try:
                resp2 = session.get(
                    iframe_url,
                    timeout=30,
                    headers={**HEADERS, "Referer": url}
                )
                
                matches = re.findall(token_pattern, resp2.text)
                if matches:
                    log(f"  ✓ iframe'de token URL bulundu!")
                    return matches[0]
                
                # Daha derin iframe
                inner_iframes = re.findall(iframe_pattern, resp2.text, re.IGNORECASE)
                for inner_src in inner_iframes:
                    inner_url = urljoin(iframe_url, inner_src)
                    
                    try:
                        resp3 = session.get(
                            inner_url,
                            timeout=30,
                            headers={**HEADERS, "Referer": iframe_url}
                        )
                        
                        matches = re.findall(token_pattern, resp3.text)
                        if matches:
                            log(f"  ✓ iç iframe'de token URL bulundu!")
                            return matches[0]
                            
                    except:
                        pass
                        
            except:
                pass
                
    except Exception as e:
        log(f"  Hata: {e}")
    
    return None


# ─────────────────────────────────────────────
# ANA STREAM BULMA FONKSİYONU
# ─────────────────────────────────────────────
def find_stream_url(channel_slug):
    """
    Kanal için stream URL'si bul
    """
    log(f"Kanal: {channel_slug}")
    
    # 1. Bilinen ID varsa doğrudan kullan
    if channel_slug in CHANNEL_IDS and CHANNEL_IDS[channel_slug]:
        channel_id = CHANNEL_IDS[channel_slug]
        log(f"  Bilinen ID: {channel_id}")
        return generate_playlist_url(channel_id)
    
    # 2. Doğrudan token URL ara
    log(f"  [1/3] Doğrudan token URL aranıyor...")
    direct_url = find_direct_token_url(channel_slug)
    if direct_url:
        return direct_url
    
    # 3. Sayfadan ID bul
    log(f"  [2/3] Sayfadan ID çıkarılıyor...")
    channel_id = find_channel_id_from_page(channel_slug)
    if channel_id:
        # Bulunan ID'yi kaydet
        CHANNEL_IDS[channel_slug] = channel_id
        return generate_playlist_url(channel_id)
    
    # 4. Slug'dan tahmin et (son çare)
    log(f"  [3/3] ID tahmin ediliyor...")
    
    # Bazı bilinen pattern'ler
    slug_guesses = {
        "atv": ["1", "101", "201"],
        "star-tv": ["2", "102", "202"],
        "show-tv": ["3", "103", "203"],
        "kanal-d": ["4", "104", "204"],
        "fox-tv": ["5", "105", "205"],
        "tv8": ["6", "106", "206"],
        "trt-1": ["10", "110", "210"],
    }
    
    for key, ids in slug_guesses.items():
        if key in channel_slug:
            for test_id in ids:
                log(f"    ID {test_id} deneniyor...")
                test_url = generate_playlist_url(test_id)
                
                # Test et
                try:
                    resp = requests.get(
                        test_url,
                        timeout=10,
                        headers=HEADERS
                    )
                    if resp.status_code == 200 and len(resp.content) > 100:
                        log(f"  ✓ Çalışan ID bulundu: {test_id}")
                        CHANNEL_IDS[channel_slug] = test_id
                        return test_url
                except:
                    pass
    
    log(f"  ✗ ID bulunamadı!")
    return None


# ─────────────────────────────────────────────
# KANAL LİSTESİ
# ─────────────────────────────────────────────
def load_channels():
    """channels.txt'den kanal listesi yükle"""
    channels = []
    
    if os.path.exists(CHANNELS_FILE):
        with open(CHANNELS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split('|')
                slug = parts[0].strip()
                name = parts[1].strip() if len(parts) > 1 else slug.replace('-', ' ').title()
                channels.append({'slug': slug, 'name': name})
    else:
        channels = [
            {'slug': 'bein-sports-1-turkey', 'name': 'beIN Sports 1'},
        ]
    
    return channels


def generate_m3u(results):
    """M3U dosyası oluştur"""
    lines = ['#EXTM3U']
    lines.append(f'# Updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")}')
    lines.append('')
    
    for ch in results:
        if ch.get('url'):
            lines.append(
                f'#EXTINF:-1 tvg-id="{ch["slug"]}" '
                f'tvg-name="{ch["name"]}" '
                f'group-title="TV247",{ch["name"]}'
            )
            lines.append(ch['url'])
            lines.append('')
    
    content = '\n'.join(lines)
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    
    log(f"\n✓ {OUTPUT_FILE} oluşturuldu")
    return content


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    log("=" * 50)
    log("TV247 M3U Generator")
    log("=" * 50)
    
    channels = load_channels()
    log(f"\n{len(channels)} kanal işlenecek\n")
    
    results = []
    
    for i, ch in enumerate(channels):
        log(f"\n[{i+1}/{len(channels)}] {ch['name']}")
        log("-" * 40)
        
        stream_url = find_stream_url(ch['slug'])
        
        results.append({
            'slug': ch['slug'],
            'name': ch['name'],
            'url': stream_url
        })
        
        if stream_url:
            log(f"✓ {stream_url[:80]}...")
        else:
            log(f"✗ Bulunamadı")
        
        time.sleep(1)
    
    # M3U oluştur
    log("\n" + "=" * 50)
    content = generate_m3u(results)
    print(f"\n{content}")
    
    # Özet
    found = sum(1 for r in results if r.get('url'))
    log(f"\nSONUÇ: {found}/{len(results)} kanal bulundu")
    
    # Bulunan ID'leri göster
    log("\nBulunan Kanal ID'leri:")
    for slug, cid in CHANNEL_IDS.items():
        if cid:
            log(f"  {slug}: {cid}")
    
    return 0 if found > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
