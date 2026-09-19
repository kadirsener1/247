#!/usr/bin/env python3
"""
SportsBite Scraper - m3u8 Çıkarıcı
- Track sayfalarından gerçek .m3u8 stream URL'lerini çıkarır
- TiviMate, OTT Navigator gibi uygulamalarda sorunsuz çalışır
- Stream domain otomatik bulunur
"""

import subprocess
import sys
import re
import os
import time

def install(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

try:
    import cloudscraper
except ImportError:
    install("cloudscraper")
    import cloudscraper

BASE_URL = "https://sportsbite.org"
FALLBACK_STREAM_BASE = "https://sportsbite.org"
OUTPUT_FILE = "tv247_bite.m3u"
CHANNELS_FILE = "channels_bite.txt"

# Slug -> Track ID
TRACK_IDS = {
  "abc-usa": "abc-usa", "ahc-american-heroes-channel": "ahc-american-heroes-channel", "antenna-tv-usa": "antenna-tv-usa",
    "a-e-usa": "a-e-usa", "amc-usa": "amc-usa", "animal-planet": "animal-planet",
    "astro-supersport-1": "astro-supersport-1", "astro-supersport-2": "astro-supersport-2",
    "astro-supersport-3": "astro-supersport-3", "astro-supersport-4": "astro-supersport-4",
    "arena-sport-1-premium": "arena-sport-1-premium", "arena-sport-2-premium": "arena-sport-2-premium",
    "arena-sport-3-premium": "arena-sport-3-premium", "arena-sport-1-serbia": "arena-sport-1-serbia",
    "arena-sport-2-serbia": "arena-sport-2-serbia", "arena-sport-3-serbia": "arena-sport-3-serbia",
    "arena-sport-4-serbia": "arena-sport-4-serbia", "arena-sport-1-croatia": "arena-sport-1-croatia",
    "arena-sport-2-croatia": "arena-sport-2-croatia", "arena-sport-3-croatia": "arena-sport-3-croatia",
    "arena-sport-4-croatia": "arena-sport-4-croatia", "alkass-one": "alkass-one", "alkass-two": "alkass-two",
    "alkass-three": "alkass-three", "alkass-four": "alkass-four", "arena-sport-1-bih": "arena-sport-1-bih",
    "abu-dhabi-sports-1-uae": "abu-dhabi-sports-1-uae", "abu-dhabi-sports-2-uae": "abu-dhabi-sports-2-uae",
    "abu-dhabi-sports-1-premium": "abu-dhabi-sports-1-premium", "abu-dhabi-sports-2-premium": "abu-dhabi-sports-2-premium",
    "astro-cricket": "astro-cricket", "antena-3-spain": "antena-3-spain",
    "arena-sports-tenis-serbia": "arena-sports-tenis-serbia", "acc-network-usa": "acc-network-usa",
    "adult-swim": "adult-swim", "a-sport-pk": "a-sport-pk", "axn-movies-portugal": "axn-movies-portugal",
    "arte-de": "arte-de", "axs-tv-usa": "axs-tv-usa", "abc-ny-usa": "abc-ny-usa",
    "azteca-7-mx": "azteca-7-mx", "altitude-sports": "altitude-sports", "azteca-uno-mx": "azteca-uno-mx",
    "arena-sport-5-serbia": "arena-sport-5-serbia", "arena-sport-6-serbia": "arena-sport-6-serbia",
    "arena-sport-7-serbia": "arena-sport-7-serbia", "arena-sport-8-serbia": "arena-sport-8-serbia",
    "arena-sport-9-serbia": "arena-sport-9-serbia", "arena-sport-10-serbia": "arena-sport-10-serbia",
    "arte-france": "arte-france", "automoto-la-chaine": "automoto-la-chaine",
    "atv-turkey": "atv-turkey", "a-spor-turkey": "a-spor-turkey",
    "bein-sports-mena-english-1": "bein-sports-mena-english-1", "bein-sports-mena-english-2": "bein-sports-mena-english-2",
    "bein-sports-1-arabic": "bein-sports-1-arabic", "bein-sports-2-arabic": "bein-sports-2-arabic",
    "bein-sports-3-arabic": "bein-sports-3-arabic", "bein-sports-4-arabic": "bein-sports-4-arabic",
    "bein-sports-5-arabic": "bein-sports-5-arabic", "bein-sports-6-arabic": "bein-sports-6-arabic",
    "bein-sports-7-arabic": "bein-sports-7-arabic", "bein-sports-8-arabic": "bein-sports-8-arabic",
    "bein-sports-9-arabic": "bein-sports-9-arabic", "bein-sports-xtra-1": "bein-sports-xtra-1",
    "bein-sports-max-4-france": "bein-sports-max-4-france", "bein-sports-max-5-france": "bein-sports-max-5-france",
    "bein-sports-max-6-france": "bein-sports-max-6-france", "bein-sports-max-7-france": "bein-sports-max-7-france",
    "bein-sports-max-8-france": "bein-sports-max-8-france", "bein-sports-max-9-france": "bein-sports-max-9-france",
    "bein-sports-max-10-france": "bein-sports-max-10-france", "bein-sports-1-france": "bein-sports-1-france",
    "bein-sports-2-france": "bein-sports-2-france", "bein-sports-3-france": "bein-sports-3-france",
    "bein-sports-1-turkey": "bein-sports-1-turkey", "bein-sports-2-turkey": "bein-sports-2-turkey",
    "bein-sports-3-turkey": "bein-sports-3-turkey", "bein-sports-4-turkey": "bein-sports-4-turkey",
    "bein-sports-hd-qatar": "bein-sports-hd-qatar", "bein-sports-usa": "bein-sports-usa",
    "bein-sports-en-espanol": "bein-sports-en-espanol", "bein-sports-1-australia": "bein-sports-1-australia",
    "bein-sports-2-australia": "bein-sports-2-australia", "bein-sports-3-australia": "bein-sports-3-australia",
    "barca-tv-spain": "barca-tv-spain", "benfica-tv-pt": "benfica-tv-pt", "boomerang": "boomerang",
    "bnt-1-bulgaria": "bnt-1-bulgaria", "bnt-2-bulgaria": "bnt-2-bulgaria", "bnt-3-bulgaria": "bnt-3-bulgaria",
    "br-fernsehen-de": "br-fernsehen-de", "btv-bulgaria": "btv-bulgaria", "btv-action-bulgaria": "btv-action-bulgaria",
    "btv-lady-bulgaria": "btv-lady-bulgaria", "bbc-america": "bbc-america", "bet-usa": "bet-usa",
    "bravo-usa": "bravo-usa", "bbc-news-channel-hd": "bbc-news-channel-hd", "bbc-one-uk": "bbc-one-uk",
    "bbc-two-uk": "bbc-two-uk", "bbc-three-uk": "bbc-three-uk", "bbc-four-uk": "bbc-four-uk",
    "big-ten-network-btn-usa": "big-ten-network-btn-usa", "bein-sports-1-malaysia": "bein-sports-1-malaysia",
    "bein-sports-2-malaysia": "bein-sports-2-malaysia", "bein-sports-3-malaysia": "bein-sports-3-malaysia",
    "bfm-tv-france": "bfm-tv-france", "bein-sports-5-turkey": "bein-sports-5-turkey",
    "bandsports-brasil": "bandsports-brasil", "canal-plus-motogp-france": "canal-plus-motogp-france",
    "canal-plus-formula-1": "canal-plus-formula-1", "cw-pix-11-usa": "cw-pix-11-usa", "cbs-usa": "cbs-usa",
    "court-tv-usa": "court-tv-usa", "cw-usa": "cw-usa", "cnbc-usa": "cnbc-usa",
    "comedy-central": "comedy-central", "cartoon-network": "cartoon-network", "cnn-usa": "cnn-usa",
    "cinemax-usa": "cinemax-usa", "cuatro-spain": "cuatro-spain", "channel-4-uk": "channel-4-uk",
    "channel-5-uk": "channel-5-uk", "cbs-sports-network": "cbs-sports-network",
    "canal-plus-france": "canal-plus-france", "canal-plus-sport-france": "canal-plus-sport-france",
    "canal-plus-foot-france": "canal-plus-foot-france", "canal-plus-sport360": "canal-plus-sport360",
    "canal-11-portugal": "canal-11-portugal", "canal-plus-sport-poland": "canal-plus-sport-poland",
    "canal-plus-sport-2-poland": "canal-plus-sport-2-poland", "canal-plus-sport-3-poland": "canal-plus-sport-3-poland",
    "canal-plus-sport-5-poland": "canal-plus-sport-5-poland", "canal-plus-premium-poland": "canal-plus-premium-poland",
    "canal-plus-family-poland": "canal-plus-family-poland", "canal-plus-seriale-poland": "canal-plus-seriale-poland",
    "canal-plus-sport-1-afrique": "canal-plus-sport-1-afrique", "canal-plus-sport-2-afrique": "canal-plus-sport-2-afrique",
    "canal-plus-sport-3-afrique": "canal-plus-sport-3-afrique", "canal-plus-sport-4-afrique": "canal-plus-sport-4-afrique",
    "canal-plus-sport-5-afrique": "canal-plus-sport-5-afrique", "canal-9-denmark": "canal-9-denmark",
    "combate-brasil": "combate-brasil", "cosmote-sport-1-hd": "cosmote-sport-1-hd",
    "cosmote-sport-2-hd": "cosmote-sport-2-hd", "cosmote-sport-3-hd": "cosmote-sport-3-hd",
    "cosmote-sport-4-hd": "cosmote-sport-4-hd", "cosmote-sport-5-hd": "cosmote-sport-5-hd",
    "cosmote-sport-6-hd": "cosmote-sport-6-hd", "cosmote-sport-7-hd": "cosmote-sport-7-hd",
    "cosmote-sport-8-hd": "cosmote-sport-8-hd", "cosmote-sport-9-hd": "cosmote-sport-9-hd",
    "channel-9-israel": "channel-9-israel", "channel-10-israel": "channel-10-israel",
    "channel-11-israel": "channel-11-israel", "channel-12-israel": "channel-12-israel",
    "channel-13-israel": "channel-13-israel", "channel-14-israel": "channel-14-israel",
    "c-more-first-sweden": "c-more-first-sweden", "c-more-hits-sweden": "c-more-hits-sweden",
    "c-more-series-sweden": "c-more-series-sweden", "cozi-tv-usa": "cozi-tv-usa", "cmt-usa": "cmt-usa",
    "ctv-canada": "ctv-canada", "ctv-2-canada": "ctv-2-canada",
    "crime-plus-investigation-usa": "crime-plus-investigation-usa", "comet-usa": "comet-usa",
    "cooking-channel-usa": "cooking-channel-usa", "cleo-tv": "cleo-tv", "c-span-1": "c-span-1",
    "cbsny-usa": "cbsny-usa", "chicago-sports-network": "chicago-sports-network", "citytv": "citytv",
    "cbc-ca": "cbc-ca", "claro-sports-mx": "claro-sports-mx", "canal5-mx": "canal5-mx",
    "c8-france": "c8-france", "cnews-france": "cnews-france", "canal-plus-sport-cz": "canal-plus-sport-cz",
    "ct-sport-cz": "ct-sport-cz", "cbs-sports-golazo": "cbs-sports-golazo",
    "cmtv-portugal": "cmtv-portugal", "cytavision-sports-1-cyprus": "cytavision-sports-1-cyprus",
    "cytavision-sports-2-cyprus": "cytavision-sports-2-cyprus", "cytavision-sports-3-cyprus": "cytavision-sports-3-cyprus",
    "cytavision-sports-4-cyprus": "cytavision-sports-4-cyprus", "cytavision-sports-5-cyprus": "cytavision-sports-5-cyprus",
    "cytavision-sports-6-cyprus": "cytavision-sports-6-cyprus", "cytavision-sports-7-cyprus": "cytavision-sports-7-cyprus",
    "dazn-1-uk": "dazn-1-uk", "discovery-velocity-ca": "discovery-velocity-ca",
    "dazn-1-bar-de": "dazn-1-bar-de", "dazn-2-bar-de": "dazn-2-bar-de",
    "dazn-1-spain": "dazn-1-spain", "dazn-2-spain": "dazn-2-spain", "dazn-3-spain": "dazn-3-spain",
    "dazn-4-spain": "dazn-4-spain", "dazn-f1-es": "dazn-f1-es", "dazn-laliga": "dazn-laliga",
    "dazn-portugal-fifa-mundial-de-clubes": "dazn-portugal-fifa-mundial-de-clubes",
    "dr1-denmark": "dr1-denmark", "dr2-denmark": "dr2-denmark",
    "digi-sport-1-romania": "digi-sport-1-romania", "digi-sport-2-romania": "digi-sport-2-romania",
    "digi-sport-3-romania": "digi-sport-3-romania", "digi-sport-4-romania": "digi-sport-4-romania",
    "diema-sport-bulgaria": "diema-sport-bulgaria", "diema-sport-2-bulgaria": "diema-sport-2-bulgaria",
    "diema-sport-3-bulgaria": "diema-sport-3-bulgaria", "diema-bulgaria": "diema-bulgaria",
    "diema-family-bulgaria": "diema-family-bulgaria", "dubai-sports-1-uae": "dubai-sports-1-uae",
    "dubai-sports-2-uae": "dubai-sports-2-uae", "dubai-sports-3-uae": "dubai-sports-3-uae",
    "dubai-racing-2-uae": "dubai-racing-2-uae", "dstv-mzansi-magic": "dstv-mzansi-magic",
    "dstv-m-net": "dstv-m-net", "dstv-kyknet-kie": "dstv-kyknet-kie", "dazn-zona-italy": "dazn-zona-italy",
    "discovery-life-channel": "discovery-life-channel", "disney-channel": "disney-channel",
    "discovery-channel": "discovery-channel", "discovery-family": "discovery-family", "disney-xd": "disney-xd",
    "destination-america": "destination-america", "disney-jr": "disney-jr", "dave": "dave",
    "espn-usa": "espn-usa", "espn2-usa": "espn2-usa", "espnu-usa": "espnu-usa",
    "espn-1-nl": "espn-1-nl", "espn-2-nl": "espn-2-nl",
    "eleven-sports-1-poland": "eleven-sports-1-poland", "eleven-sports-2-poland": "eleven-sports-2-poland",
    "eleven-sports-3-poland": "eleven-sports-3-poland", "eleven-sports-1-portugal": "eleven-sports-1-portugal",
    "eleven-sports-2-portugal": "eleven-sports-2-portugal", "eleven-sports-3-portugal": "eleven-sports-3-portugal",
    "eleven-sports-4-portugal": "eleven-sports-4-portugal", "eleven-sports-5-portugal": "eleven-sports-5-portugal",
    "eurosport-1-greece": "eurosport-1-greece", "eurosport-2-greece": "eurosport-2-greece",
    "eurosport-1-poland": "eurosport-1-poland", "eurosport-2-poland": "eurosport-2-poland",
    "eurosport-1-sw": "eurosport-1-sw", "eurosport-2-sw": "eurosport-2-sw",
    "eurosport-1-nl": "eurosport-1-nl", "eurosport-2-nl": "eurosport-2-nl",
    "eurosport-1-spain": "eurosport-1-spain", "eurosport-2-spain": "eurosport-2-spain",
    "eurosport-1-italy": "eurosport-1-italy", "eurosport-2-italy": "eurosport-2-italy",
    "espn-premium-argentina": "espn-premium-argentina", "espn-brasil": "espn-brasil",
    "espn2-brasil": "espn2-brasil", "espn3-brasil": "espn3-brasil", "espn4-brasil": "espn4-brasil",
    "espn-argentina": "espn-argentina", "espn2-argentina": "espn2-argentina",
    "espn-deportes": "espn-deportes", "espnews": "espnews",
    "e-entertainment-television": "e-entertainment-television", "e4-channel": "e4-channel",
    "espn-3-nl": "espn-3-nl", "ert-1-greece": "ert-1-greece",
    "eurosport-1-france": "eurosport-1-france", "eurosport-2-france": "eurosport-2-france",
    "espn3-argentina": "espn3-argentina", "espn-1-mx": "espn-1-mx", "espn-2-mx": "espn-2-mx",
    "espn-3-mx": "espn-3-mx", "espn-4-mx": "espn-4-mx", "fuse-tv-usa": "fuse-tv-usa",
    "fox-sports-1-usa": "fox-sports-1-usa", "fox-sports-2-usa": "fox-sports-2-usa",
    "fox-soccer-plus": "fox-soccer-plus", "fox-cricket": "fox-cricket",
    "fox-deportes-usa": "fox-deportes-usa", "fox-sports-502-au": "fox-sports-502-au",
    "fox-sports-503-au": "fox-sports-503-au", "fox-sports-504-au": "fox-sports-504-au",
    "fox-sports-505-au": "fox-sports-505-au", "fox-sports-506-au": "fox-sports-506-au",
    "fox-sports-507-au": "fox-sports-507-au", "fox-sports-1-mx": "fox-sports-1-mx",
    "fox-sports-2-mx": "fox-sports-2-mx", "fox-sports-3-mx": "fox-sports-3-mx",
    "fox-sports-argentina": "fox-sports-argentina", "fox-sports-2-argentina": "fox-sports-2-argentina",
    "fox-sports-3-argentina": "fox-sports-3-argentina", "fox-sports-premium-mx": "fox-sports-premium-mx",
    "filmbox-premium-poland": "filmbox-premium-poland", "fight-network": "fight-network",
    "fox-business": "fox-business", "fox-hd-bulgaria": "fox-hd-bulgaria", "fox-usa": "fox-usa",
    "fx-usa": "fx-usa", "fxx-usa": "fxx-usa", "freeform": "freeform",
    "fox-news": "fox-news", "fx-movie-channel": "fx-movie-channel", "fyi": "fyi",
    "film4-uk": "film4-uk", "fashion-tv": "fashion-tv",
    "fetv-family-entertainment-television": "fetv-family-entertainment-television", "foxny-usa": "foxny-usa",
    "fox-weather-channel": "fox-weather-channel", "fanduel-sports-network-arizona": "fanduel-sports-network-arizona",
    "fanduel-sports-network-detroit": "fanduel-sports-network-detroit",
    "fanduel-sports-network-florida": "fanduel-sports-network-florida",
    "fanduel-sports-network-great-lakes": "fanduel-sports-network-great-lakes",
    "fanduel-sports-network-indiana": "fanduel-sports-network-indiana",
    "fanduel-sports-network-kansas-city": "fanduel-sports-network-kansas-city",
    "fanduel-sports-network-midwest": "fanduel-sports-network-midwest",
    "fanduel-sports-network-new-orleans": "fanduel-sports-network-new-orleans",
    "fanduel-sports-network-north": "fanduel-sports-network-north",
    "fanduel-sports-network-ohio": "fanduel-sports-network-ohio",
    "fanduel-sports-network-oklahoma": "fanduel-sports-network-oklahoma",
    "fanduel-sports-network-socal": "fanduel-sports-network-socal",
    "fanduel-sports-network-south": "fanduel-sports-network-south",
    "fanduel-sports-network-southeast": "fanduel-sports-network-southeast",
    "fanduel-sports-network-sun": "fanduel-sports-network-sun",
    "fanduel-sports-network-west": "fanduel-sports-network-west",
    "fanduel-sports-network-wisconsin": "fanduel-sports-network-wisconsin",
    "france-2": "france-2", "france-3": "france-3", "france-4": "france-4",
    "france-5": "france-5", "gol-play-spain": "gol-play-spain", "golf-channel-usa": "golf-channel-usa",
    "game-show-network": "game-show-network", "goltv-usa": "goltv-usa", "gold-uk": "gold-uk",
    "great-american-family-channel-gac": "great-american-family-channel-gac", "galavision-usa": "galavision-usa",
    "grit-channel": "grit-channel", "globo-sp": "globo-sp", "globo-rio": "globo-rio",
    "global-ca": "global-ca", "the-hallmark-channel": "the-hallmark-channel",
    "hallmark-movies-and-mysteries": "hallmark-movies-and-mysteries",
    "heroes-and-icons-hi-usa": "heroes-and-icons-hi-usa", "hbo-usa": "hbo-usa", "hbo2-usa": "hbo2-usa",
    "hbo-comedy-usa": "hbo-comedy-usa", "hbo-family-usa": "hbo-family-usa",
    "hbo-latino-usa": "hbo-latino-usa", "hbo-signature-usa": "hbo-signature-usa",
    "hbo-zone-usa": "hbo-zone-usa", "hbo-poland": "hbo-poland", "history-usa": "history-usa",
    "headline-news": "headline-news", "hgtv": "hgtv", "happy-tv-serbia": "happy-tv-serbia",
    "hot3-israel": "hot3-israel", "itv-1-uk": "itv-1-uk", "itv-2-uk": "itv-2-uk",
    "itv-3-uk": "itv-3-uk", "itv-4-uk": "itv-4-uk", "itvbe": "itvbe",
    "italia-1-italy": "italia-1-italy", "investigation-discovery-id-usa": "investigation-discovery-id-usa",
    "ion-usa": "ion-usa", "ifc-tv-usa": "ifc-tv-usa", "kanal-4-denmark": "kanal-4-denmark",
    "kanal-5-denmark": "kanal-5-denmark", "kabel-eins-de": "kabel-eins-de",
    "laligatv-uk": "laligatv-uk", "law-crime-network": "law-crime-network",
    "laliga-smartbank-tv": "laliga-smartbank-tv", "lequipe-france": "lequipe-france",
    "la-sexta-spain": "la-sexta-spain", "liverpool-tv-lfc-tv": "liverpool-tv-lfc-tv",
    "logo-tv-usa": "logo-tv-usa", "las-estrellas": "las-estrellas",
    "lifetime-network": "lifetime-network", "lifetime-movies-network": "lifetime-movies-network",
    "la7": "la7", "la7d": "la7d", "match-football-1": "match-football-1",
    "match-football-2": "match-football-2", "match-football-3": "match-football-3",
    "match-premier": "match-premier", "match-tv": "match-tv", "match-boec": "match-boec",
    "movistar-laliga": "movistar-laliga", "movistar-liga-de-campeones": "movistar-liga-de-campeones",
    "movistar-deportes-4": "movistar-deportes-4", "movistar-deportes-2": "movistar-deportes-2",
    "movistar-deportes-3": "movistar-deportes-3", "movistar-deportes-4-alt1": "movistar-deportes-4-alt1",
    "movistar-golf": "movistar-golf", "motowizja": "motowizja", "msg": "msg",
    "msnbc": "msnbc", "magnolia-network": "magnolia-network", "m4-sports": "m4-sports",
    "movistar-supercopa-de-espana": "movistar-supercopa-de-espana", "mtv": "mtv",
    "mtv-usa": "mtv-usa", "mutv-uk": "mutv-uk", "m6-france": "m6-france",
    "mavtv-usa": "mavtv-usa", "max-sport-croatia-1": "max-sport-croatia-1",
    "max-sport-croatia-2": "max-sport-croatia-2", "marquee-sports-network": "marquee-sports-network",
    "max-sport-bulgaria-1": "max-sport-bulgaria-1", "max-sport-bulgaria-2": "max-sport-bulgaria-2",
    "max-sport-bulgaria-3": "max-sport-bulgaria-3", "max-sport-bulgaria-4": "max-sport-bulgaria-4",
    "mlb-network-usa": "mlb-network-usa", "masn-usa": "masn-usa", "my9tv-usa": "my9tv-usa",
    "motor-trend": "motor-trend", "metv-usa": "metv-usa", "mdr-de": "mdr-de",
    "mundotoro-tv-spain": "mundotoro-tv-spain", "monumental-sports-network": "monumental-sports-network",
    "mtv-denmark": "mtv-denmark", "mgm-plus-epix-usa": "mgm-plus-epix-usa",
    "nbc10-philadelphia": "nbc10-philadelphia", "nhl-network-usa": "nhl-network-usa",
    "nfl-redzone": "nfl-redzone", "nova-sport-bulgaria": "nova-sport-bulgaria",
    "nova-sport-serbia": "nova-sport-serbia", "nova-sports-greece-1": "nova-sports-greece-1",
    "nova-sports-greece-2": "nova-sports-greece-2", "nova-sports-greece-3": "nova-sports-greece-3",
    "nova-sports-greece-4": "nova-sports-greece-4", "nova-sports-greece-5": "nova-sports-greece-5",
    "nova-sports-greece-6": "nova-sports-greece-6", "nova-sports-premier-league-greece": "nova-sports-premier-league-greece",
    "nova-sports-start-greece": "nova-sports-start-greece", "nova-sports-prime-greece": "nova-sports-prime-greece",
    "nova-sports-news-greece": "nova-sports-news-greece", "nick-music": "nick-music",
    "nesn-usa": "nesn-usa", "nbc-usa": "nbc-usa", "nba-tv-usa": "nba-tv-usa",
    "nbc-sports-philadelphia": "nbc-sports-philadelphia", "nfl-network": "nfl-network",
    "nbc-sports-bay-area": "nbc-sports-bay-area", "nbc-sports-boston": "nbc-sports-boston",
    "nbc-sports-california": "nbc-sports-california", "nbcny-usa": "nbcny-usa",
    "nova-tv-bulgaria": "nova-tv-bulgaria", "nova-s-serbia": "nova-s-serbia",
    "newsnation-usa": "newsnation-usa", "national-geographic": "national-geographic",
    "nick-jr": "nick-jr", "nick": "nick", "nicktoons": "nicktoons", "ndr": "ndr",
    "newsmax-usa": "newsmax-usa", "nat-geo-wild-usa": "nat-geo-wild-usa", "noovo": "noovo",
    "nbc-universo": "nbc-universo", "now-tv-turkey": "now-tv-turkey",
    "nova-sport": "nova-sport", "nova-sport-cz-2": "nova-sport-cz-2",
    "nova-sport-cz-3": "nova-sport-cz-3", "nova-sport-cz-4": "nova-sport-cz-4",
    "nova-sport-cz-5": "nova-sport-cz-5", "nova-sport-cz-6": "nova-sport-cz-6",
    "ontime-sports": "ontime-sports", "one-hd-israel-1": "one-hd-israel-1",
    "one-hd-israel-2": "one-hd-israel-2", "orange-sport-romania-1": "orange-sport-romania-1",
    "orange-sport-romania-2": "orange-sport-romania-2", "orange-sport-romania-3": "orange-sport-romania-3",
    "orange-sport-romania-4": "orange-sport-romania-4", "oprah-winfrey-network-own": "oprah-winfrey-network-own",
    "oxygen-true-crime": "oxygen-true-crime", "outdoor-channel-usa": "outdoor-channel-usa",
    "oneplay-sport-cz-1": "oneplay-sport-cz-1", "oneplay-sport-cz-2": "oneplay-sport-cz-2",
    "oneplay-sport-cz-3": "oneplay-sport-cz-3", "polsat-poland": "polsat-poland",
    "polsat-sport-poland": "polsat-sport-poland", "polsat-sport-2": "polsat-sport-2",
    "polsat-sport-3": "polsat-sport-3", "polsat-news": "polsat-news", "polsat-film": "polsat-film",
    "porto-canal": "porto-canal", "prosieben": "prosieben",
    "premier-sports-ireland-1": "premier-sports-ireland-1", "ptv-sports": "ptv-sports",
    "pdc-tv": "pdc-tv", "premier-brasil": "premier-brasil",
    "prima-sport-1": "prima-sport-1", "prima-sport-2": "prima-sport-2",
    "prima-sport-3": "prima-sport-3", "prima-sport-4": "prima-sport-4",
    "paramount-network": "paramount-network", "pop-tv": "pop-tv",
    "premier-sports-ireland-2": "premier-sports-ireland-2", "prima-tv": "prima-tv",
    "premier-sport-cz-1": "premier-sport-cz-1", "premier-sport-cz-2": "premier-sport-cz-2",
    "premier-sport": "premier-sport", "pac-12-network": "pac-12-network", "pbs": "pbs",
    "reelz-channel": "reelz-channel", "rte-1": "rte-1", "rte-2": "rte-2",
    "rmc-sport-1": "rmc-sport-1", "rmc-sport-2": "rmc-sport-2", "rtp-1": "rtp-1",
    "rtp-2": "rtp-2", "rtp-3": "rtp-3", "rai-1": "rai-1", "rai-2": "rai-2",
    "rai-3": "rai-3", "rai-4": "rai-4", "rai-sport": "rai-sport",
    "rai-premium": "rai-premium", "real-madrid-tv": "real-madrid-tv", "rtl": "rtl",
    "rds-2": "rds-2", "rds-2-alt1": "rds-2-alt1", "rds-info": "rds-info",
    "ring-bulgaria": "ring-bulgaria", "rtl7-netland": "rtl7-netland",
    "racing-tv-uk": "racing-tv-uk", "rally-tv": "rally-tv",
    "root-sports-northwest": "root-sports-northwest",
    "sky-sports-football": "sky-sports-football", "sky-sports-plus": "sky-sports-plus",
    "sky-sports-action": "sky-sports-action", "sky-sports-main-event": "sky-sports-main-event",
    "sky-sports-tennis-2": "sky-sports-tennis-2", "sky-sports-premier-league": "sky-sports-premier-league",
    "sky-sports-f1-1": "sky-sports-f1-1", "sky-sports-cricket": "sky-sports-cricket",
    "sky-sports-golf-2": "sky-sports-golf-2", "sky-sports-de-1": "sky-sports-de-1",
    "sky-sports-de-2": "sky-sports-de-2", "sky-sports-golf-italy": "sky-sports-golf-italy",
    "sky-sport-motogp-italy": "sky-sport-motogp-italy", "sky-sport-tennis-italy": "sky-sport-tennis-italy",
    "sky-sport-f1-italy": "sky-sport-f1-italy", "sky-sports-news-uk": "sky-sports-news-uk",
    "sky-sports-mix-uk": "sky-sports-mix-uk", "sky-sport-top-event-de": "sky-sport-top-event-de",
    "sky-sport-mix-de": "sky-sport-mix-de", "sky-sport-bundesliga-1": "sky-sport-bundesliga-1",
    "sky-sport-austria": "sky-sport-austria", "sportsnet-new-york-sny": "sportsnet-new-york-sny",
    "sky-sport-max-italy": "sky-sport-max-italy", "sky-sport-uno-italy": "sky-sport-uno-italy",
    "sky-sport-arena-italy": "sky-sport-arena-italy", "sky-sports-racing-uk": "sky-sports-racing-uk",
    "sky-uno-italy": "sky-uno-italy", "sony-ten-1": "sony-ten-1", "sony-ten-2": "sony-ten-2",
    "sony-ten-3": "sony-ten-3", "sky-sport-bundesliga-2": "sky-sport-bundesliga-2",
    "sky-sport-bundesliga-3": "sky-sport-bundesliga-3", "sky-sport-bundesliga-4": "sky-sport-bundesliga-4",
    "sky-sport-bundesliga-3-alt1": "sky-sport-bundesliga-3-alt1",
    "spectrum-sportsnet-usa": "spectrum-sportsnet-usa",
    "sky-sport-nz-1": "sky-sport-nz-1", "sky-sport-nz-2": "sky-sport-nz-2",
    "sky-sport-nz-3": "sky-sport-nz-3", "sky-sport-nz-4": "sky-sport-nz-4",
    "sky-sport-nz-5": "sky-sport-nz-5", "sky-sport-nz-6": "sky-sport-nz-6",
    "sky-sport-nz-7": "sky-sport-nz-7", "sky-sport-nz-8": "sky-sport-nz-8",
    "sky-sport-nz-9": "sky-sport-nz-9", "sky-sport-select-nz": "sky-sport-select-nz",
    "sport-tv-portugal-1": "sport-tv-portugal-1", "sport-tv-portugal-2": "sport-tv-portugal-2",
    "sport-tv-portugal-4": "sport-tv-portugal-4", "sport-tv-portugal-3": "sport-tv-portugal-3",
    "sport-tv-portugal-5": "sport-tv-portugal-5", "sport-tv-portugal-6": "sport-tv-portugal-6",
    "sic-portugal": "sic-portugal", "sec-network-usa": "sec-network-usa",
    "sportv-brasil-1": "sportv-brasil-1", "sportv-brasil-2": "sportv-brasil-2",
    "sportv-brasil-3": "sportv-brasil-3", "sport-klub-serbia-1": "sport-klub-serbia-1",
    "sport-klub-serbia-2": "sport-klub-serbia-2", "sport-klub-serbia-3": "sport-klub-serbia-3",
    "sport-klub-serbia-4": "sport-klub-serbia-4", "sport-klub-hd-serbia": "sport-klub-hd-serbia",
    "sportsnet-ontario": "sportsnet-ontario", "sportsnet-one": "sportsnet-one",
    "sportsnet-west": "sportsnet-west", "sportsnet-east": "sportsnet-east",
    "sportsnet-360": "sportsnet-360", "sportsnet-world": "sportsnet-world",
    "supersport-grandstand": "supersport-grandstand", "supersport-psl": "supersport-psl",
    "supersport-premier-league": "supersport-premier-league", "supersport-laliga": "supersport-laliga",
    "supersport-variety-1": "supersport-variety-1", "supersport-variety-2": "supersport-variety-2",
    "supersport-variety-3": "supersport-variety-3", "supersport-variety-4": "supersport-variety-4",
    "supersport-action": "supersport-action", "supersport-rugby": "supersport-rugby",
    "supersport-golf": "supersport-golf", "supersport-tennis": "supersport-tennis",
    "supersport-motorsport": "supersport-motorsport", "supersport-football": "supersport-football",
    "supersport-cricket": "supersport-cricket", "supersport-maximo": "supersport-maximo",
    "sporting-tv-portugal": "sporting-tv-portugal", "sportdigital-fussball": "sportdigital-fussball",
    "spectrum-sportsnet-la": "spectrum-sportsnet-la", "sportdigital-germany": "sportdigital-germany",
    "sport1-germany": "sport1-germany", "s4c-uk": "s4c-uk",
    "sport-klub-golf-croatia": "sport-klub-golf-croatia", "sat1-de": "sat1-de",
    "sky-cinema-premiere-uk": "sky-cinema-premiere-uk", "sky-cinema-select-uk": "sky-cinema-select-uk",
    "sky-cinema-hits-uk": "sky-cinema-hits-uk", "sky-cinema-greats-uk": "sky-cinema-greats-uk",
    "sky-cinema-animation-uk": "sky-cinema-animation-uk", "sky-cinema-family-uk": "sky-cinema-family-uk",
    "sky-cinema-action-uk": "sky-cinema-action-uk", "sky-cinema-comedy-uk": "sky-cinema-comedy-uk",
    "sky-cinema-thriller-uk": "sky-cinema-thriller-uk", "sky-cinema-drama-uk": "sky-cinema-drama-uk",
    "sky-cinema-sci-fi-horror-uk": "sky-cinema-sci-fi-horror-uk",
    "showtime-shoxbet-usa": "showtime-shoxbet-usa", "see-denmark": "see-denmark",
    "sky-cinema-collection-italy": "sky-cinema-collection-italy", "sky-cinema-uno-italy": "sky-cinema-uno-italy",
    "sky-cinema-action-italy": "sky-cinema-action-italy", "sky-cinema-comedy-italy": "sky-cinema-comedy-italy",
    "sky-cinema-uno-24-italy": "sky-cinema-uno-24-italy", "sky-cinema-romance-italy": "sky-cinema-romance-italy",
    "sky-cinema-family-italy": "sky-cinema-family-italy", "sky-cinema-due-24-italy": "sky-cinema-due-24-italy",
    "sky-cinema-drama-italy": "sky-cinema-drama-italy", "sky-cinema-suspense": "sky-cinema-suspense",
    "sky-sport-24": "sky-sport-24", "sky-sport-calcio": "sky-sport-calcio",
    "sky-calcio-1": "sky-calcio-1", "sky-calcio-2": "sky-calcio-2",
    "sky-calcio-3": "sky-calcio-3", "sky-calcio-4": "sky-calcio-4",
    "sky-sport-basket": "sky-sport-basket", "sky-serie": "sky-serie",
    "starzplay-criclife-1": "starzplay-criclife-1", "sky-showcase": "sky-showcase",
    "sky-arts": "sky-arts", "sky-comedy": "sky-comedy", "sky-crime": "sky-crime",
    "sky-history": "sky-history", "sky-max": "sky-max",
    "ssc-sport-1": "ssc-sport-1", "ssc-sport-2": "ssc-sport-2", "ssc-sport-3": "ssc-sport-3",
    "ssc-sport-4": "ssc-sport-4", "ssc-sport-5": "ssc-sport-5",
    "ssc-sport-extra-1": "ssc-sport-extra-1", "ssc-sport-extra-2": "ssc-sport-extra-2",
    "ssc-sport-extra-3": "ssc-sport-extra-3", "sport-1-israel": "sport-1-israel",
    "sport-2-israel": "sport-2-israel", "sport-3-israel": "sport-3-israel",
    "sport-4-israel": "sport-4-israel", "sport-5-israel": "sport-5-israel",
    "sport-5-plus-israel": "sport-5-plus-israel", "sport-5-live-israel": "sport-5-live-israel",
    "sport-5-star-israel": "sport-5-star-israel", "sport-5-gold-israel": "sport-5-gold-israel",
    "science-channel": "science-channel", "showtime-usa": "showtime-usa", "starz": "starz",
    "sky-witness-hd": "sky-witness-hd", "sixx-de": "sixx-de", "sky-atlantic": "sky-atlantic",
    "syfy-usa": "syfy-usa", "sundance-tv": "sundance-tv", "swr": "swr",
    "super-rtl": "super-rtl", "sr-fernsehen": "sr-fernsehen",
    "sky-sports-golf-1": "sky-sports-golf-1", "smithsonian-channel": "smithsonian-channel",
    "sky-sports-f1-1-alt1": "sky-sports-f1-1-alt1", "sky-sports-tennis-1": "sky-sports-tennis-1",
    "sbs6": "sbs6", "star-sports": "star-sports", "star-sports-hindi": "star-sports-hindi",
    "showtime-2": "showtime-2", "showtime-showcase": "showtime-showcase",
    "showtime-extreme": "showtime-extreme", "showtime-family-zone": "showtime-family-zone",
    "showtime-next": "showtime-next", "showtime-women": "showtime-women",
    "space-city-home-network": "space-city-home-network", "sportsnet-pittsburgh": "sportsnet-pittsburgh",
    "tnt-sports-1": "tnt-sports-1", "tnt-sports-2": "tnt-sports-2", "tnt-sports-3": "tnt-sports-3",
    "tnt-sports-4": "tnt-sports-4", "tsn": "tsn", "tsn2": "tsn2", "tsn3": "tsn3",
    "tsn4": "tsn4", "tsn5": "tsn5", "tvn": "tvn", "tvn24": "tvn24",
    "tvp1": "tvp1", "tvp2": "tvp2", "telecinco": "telecinco",
    "tve-la-1": "tve-la-1", "tve-la-2": "tve-la-2", "tvi": "tvi",
    "tvi-reality": "tvi-reality", "teledeporte": "teledeporte", "tyc-sports": "tyc-sports",
    "tvp-sport": "tvp-sport", "tnt-brasil": "tnt-brasil",
    "tnt-sports-argentina": "tnt-sports-argentina", "tnt-sports-chile": "tnt-sports-chile",
    "tennis-channel": "tennis-channel", "ten-sports-pk": "ten-sports-pk", "tudn-usa": "tudn-usa",
    "telemundo": "telemundo", "tbs-usa": "tbs-usa", "tlc": "tlc", "tnt-usa": "tnt-usa",
    "tf1-france": "tf1-france", "tva-sports-1": "tva-sports-1", "tva-sports-2": "tva-sports-2",
    "tvc-deportes-mx": "tvc-deportes-mx", "tudn-mx": "tudn-mx", "travel-channel": "travel-channel",
    "trutv-usa": "trutv-usa", "tvland": "tvland", "tcm-usa": "tcm-usa",
    "tmc-channel-usa": "tmc-channel-usa", "the-food-network": "the-food-network",
    "the-weather-channel": "the-weather-channel", "tvp-info": "tvp-info", "teennick": "teennick",
    "tv-one-usa": "tv-one-usa", "tv2-bornholm": "tv2-bornholm", "tv2-sport-x": "tv2-sport-x",
    "tv3-sport": "tv3-sport", "tv2-sport": "tv2-sport", "tv2-denmark": "tv2-denmark",
    "tv2-zulu": "tv2-zulu", "tv3-plus": "tv3-plus", "tvo-ca": "tvo-ca",
    "tv4-hockey": "tv4-hockey", "tv3-max": "tv3-max", "t-sports-bd": "t-sports-bd",
    "tv4-tennis": "tv4-tennis", "tv4-motor": "tv4-motor",
    "tv4-sport-live-4": "tv4-sport-live-4", "tv4-sport-live-4-alt1": "tv4-sport-live-4-alt1",
    "tv4-sport-live-4-alt2": "tv4-sport-live-4-alt2", "tv4-sport-live-4-alt3": "tv4-sport-live-4-alt3",
    "tv4-sportkanalen": "tv4-sportkanalen", "tv4-football-sweden": "tv4-football-sweden",
    "tennis-plus-10": "tennis-plus-10", "tennis-plus-12": "tennis-plus-12",
    "trt-spor-tr": "trt-spor-tr", "usa-network": "usa-network",
    "universal-kids-usa": "universal-kids-usa", "univision": "univision", "unimas": "unimas",
    "viaplay-sports-1": "viaplay-sports-1", "viaplay-sports-2": "viaplay-sports-2",
    "vamos-spain": "vamos-spain", "v-film-premiere": "v-film-premiere",
    "v-film-family": "v-film-family", "vodafone-sport": "vodafone-sport",
    "v-sport-motor-sweden": "v-sport-motor-sweden", "vh1-usa": "vh1-usa",
    "veronica-nl-netherland": "veronica-nl-netherland", "vtv-plus-uruguay": "vtv-plus-uruguay",
    "vice-tv": "vice-tv", "willow-cricket": "willow-cricket", "willow-xtra": "willow-xtra",
    "wwe-network": "wwe-network", "win-sports-plus-colombia": "win-sports-plus-colombia",
    "wetv-usa": "wetv-usa", "wdr-de": "wdr-de", "ytv-ca": "ytv-ca",
    "yes-network-usa": "yes-network-usa", "yes-movies-action-israel": "yes-movies-action-israel",
    "yes-movies-kids-israel": "yes-movies-kids-israel", "yes-movies-comedy-israel": "yes-movies-comedy-israel",
    "yes-tv-ca": "yes-tv-ca", "ziggo-sport-nl-6": "ziggo-sport-nl-6",
    "ziggo-sport-nl-2": "ziggo-sport-nl-2", "ziggo-sport-nl-3": "ziggo-sport-nl-3",
    "ziggo-sport-nl-4": "ziggo-sport-nl-4", "ziggo-sport-nl-5": "ziggo-sport-nl-5",
    "ziggo-sport-nl-6-alt1": "ziggo-sport-nl-6-alt1", "zdf": "zdf", "zdf-info": "zdf-info",
    "6ter": "6ter", "20-mediaset": "20-mediaset", "6eren": "6eren",
    "5-usa": "5-usa", "3sat": "3sat",
    "18-plus-18": "18-plus-18", "18-plus-18-alt1": "18-plus-18-alt1",
    "18-plus-18-alt2": "18-plus-18-alt2", "18-plus-18-alt3": "18-plus-18-alt3",
    "18-plus-18-alt4": "18-plus-18-alt4", "18-plus-18-alt5": "18-plus-18-alt5",
    "18-plus-18-alt6": "18-plus-18-alt6", "18-plus-18-alt7": "18-plus-18-alt7",
    "18-plus-18-alt8": "18-plus-18-alt8", "18-plus-18-alt9": "18-plus-18-alt9",
    "18-plus-18-alt10": "18-plus-18-alt10", "18-plus-18-alt11": "18-plus-18-alt11",
    "18-plus-18-alt12": "18-plus-18-alt12", "18-plus-18-alt13": "18-plus-18-alt13",
    "18-plus-18-alt14": "18-plus-18-alt14", "18-plus-18-alt15": "18-plus-18-alt15",
    "18-plus-18-alt16": "18-plus-18-alt16", "18-plus-18-alt17": "18-plus-18-alt17",
    "18-plus-18-alt18": "18-plus-18-alt18", "18-plus-18-alt19": "18-plus-18-alt19",
}

def create_scraper():
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )
    scraper.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': BASE_URL + '/',
        'Origin': BASE_URL,
    })
    return scraper


def find_stream_base(scraper):
    """Ana sayfadan stream domain'ini otomatik bul"""
    print("[*] Stream domain aranıyor...")
    try:
        resp = scraper.get(BASE_URL, timeout=30)
        html = resp.text

        preconnect_urls = re.findall(
            r'<link[^>]+(?:preconnect|dns-prefetch)[^>]+href="(https?://[^"]+)"',
            html, re.IGNORECASE
        )
        skip = ['google', 'facebook', 'wsrv.nl', 'ibb.co', 'adsterra',
                'piano', 'goog', 'cr7siuu']
        candidates = []
        for url in preconnect_urls:
            url_clean = url.rstrip('/')
            if not any(s in url_clean.lower() for s in skip):
                candidates.append(url_clean)

        if candidates:
            print(f"  Adaylar: {candidates}")
            for candidate in candidates:
                test_url = f"{candidate}/247/360"
                try:
                    test = scraper.head(test_url, timeout=5, allow_redirects=True)
                    if test.status_code == 200:
                        print(f"  ✅ Domain bulundu: {candidate}")
                        return candidate
                except:
                    pass

        js_match = re.search(r'src="(/assets/index-[^"]+\.js)"', html)
        if js_match:
            js_url = BASE_URL + js_match.group(1)
            try:
                js_resp = scraper.get(js_url, timeout=20)
                domains = re.findall(
                    r'(https?://[a-zA-Z0-9\-\.]+\.[a-z]{2,})/ch\d+/', js_resp.text
                )
                if domains:
                    print(f"  ✅ JS'den domain: {domains[0]}")
                    return domains[0].rstrip('/')
            except:
                pass
    except Exception as e:
        print(f"  ⚠ Hata: {e}")

    print(f"  ⚠ Fallback: {FALLBACK_STREAM_BASE}")
    return FALLBACK_STREAM_BASE


def load_channels_txt():
    """channels_bite.txt dosyasından slug -> (name, group) eşlemesi"""
    info = {}
    if not os.path.exists(CHANNELS_FILE):
        print(f"  ⚠ {CHANNELS_FILE} bulunamadı")
        return info
    with open(CHANNELS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split('|')
            if len(parts) >= 3:
                info[parts[0].strip()] = {
                    'name': parts[1].strip(),
                    'group': parts[2].strip()
                }
    print(f"  ✅ {len(info)} kanal bilgisi yüklendi")
    return info


def slug_to_name(slug):
    name = slug.replace('-', ' ').title()
    for old, new in {'Usa':'USA','Uk':'UK','Tv':'TV','Hd':'HD','Espn':'ESPN',
                     'Nba':'NBA','Nfl':'NFL','Nhl':'NHL','Bbc':'BBC','Hbo':'HBO',
                     'Cnn':'CNN','Tnt':'TNT','Ssc':'SSC','Bein':'beIN'}.items():
        name = name.replace(old, new)
    return name


def extract_m3u8_from_track(scraper, track_url, stream_base):
    """
    Track sayfasına girip gerçek .m3u8 URL'sini çıkar.
    Track sayfası bir HTML player, içinde m3u8 gömülü.
    """
    try:
        resp = scraper.get(track_url, timeout=10, headers={
            'Referer': stream_base + '/',
        })
        if resp.status_code != 200:
            return None

        html = resp.text

        # m3u8 URL'lerini ara (en yaygın pattern'ler)
        m3u8_patterns = [
            r'(https?://[^\s"\'<>\\]+\.m3u8[^\s"\'<>\\]*)',
            r'source\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
            r'file\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
            r'src\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
            r'url\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
            r'Clappr\.Player[^}]*source\s*:\s*["\']([^"\']+)["\']',
            r'Hls\.loadSource\s*\(\s*["\']([^"\']+)["\']',
            r'hlsUrl\s*[=:]\s*["\']([^"\']+)["\']',
            r'playbackUrl\s*[=:]\s*["\']([^"\']+)["\']',
            r'video_url\s*[=:]\s*["\']([^"\']+)["\']',
            r'hls\s*[=:]\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
            r'atob\s*\(\s*["\']([A-Za-z0-9+/=]+)["\']',
        ]

        for pat in m3u8_patterns:
            matches = re.findall(pat, html, re.IGNORECASE)
            for match in matches:
                url = match.strip()
                # base64 decode denemesi
                if 'atob' in pat:
                    try:
                        import base64
                        url = base64.b64decode(url).decode('utf-8', errors='ignore')
                    except:
                        continue
                if '.m3u8' in url and url.startswith('http'):
                    return url

        return None

    except Exception:
        return None


def main():
    print("=" * 60)
    print("SportsBite Scraper - m3u8 Çıkarıcı")
    print(f"Toplam {len(TRACK_IDS)} kanal")
    print("=" * 60)

    scraper = create_scraper()

    # 1. Domain bul
    stream_base = find_stream_base(scraper)
    print(f"[*] Stream domain: {stream_base}\n")

    # 2. channels.txt yükle
    print("[*] Kanal bilgileri yükleniyor...")
    channel_info = load_channels_txt()

    # 3. Önce birkaç kanaldan m3u8 çıkarmayı dene
    print("\n[*] m3u8 URL çıkarma deneniyor (ilk 5 kanal)...")
    test_slugs = list(TRACK_IDS.keys())[:5]
    m3u8_found = 0
    m3u8_cache = {}

    for slug in test_slugs:
        track_id = TRACK_IDS[slug]
        track_url = f"{stream_base}/247/{track_id}"
        m3u8_url = extract_m3u8_from_track(scraper, track_url, stream_base)
        if m3u8_url:
            m3u8_found += 1
            m3u8_cache[slug] = m3u8_url
            print(f"  ✅ {slug}: {m3u8_url[:80]}...")
        else:
            print(f"  ❌ {slug}: m3u8 bulunamadı")
        time.sleep(0.3)

    # m3u8 bulunabiliyorsa tüm kanallar için çıkar
    use_m3u8 = m3u8_found > 0
    if use_m3u8:
        print(f"\n[*] m3u8 modu aktif! Tüm kanallar taranıyor...")
        total = len(TRACK_IDS)
        done = 0
        for slug, track_id in TRACK_IDS.items():
            done += 1
            if slug in m3u8_cache:
                continue
            track_url = f"{stream_base}/ch1/track/{track_id}"
            m3u8_url = extract_m3u8_from_track(scraper, track_url, stream_base)
            if m3u8_url:
                m3u8_cache[slug] = m3u8_url
            if done % 50 == 0:
                print(f"  ... {done}/{total} tarandı ({len(m3u8_cache)} m3u8 bulundu)")
            time.sleep(0.2)
        print(f"  Toplam {len(m3u8_cache)} m3u8 bulundu")
    else:
        print("\n[*] m3u8 bulunamadı, track URL'leri kullanılacak")

    # 4. M3U dosyası oluştur
    print(f"\n[*] M3U dosyası oluşturuluyor...")
    count = 0
    m3u8_count = 0

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n\n')

        for slug, track_id in TRACK_IDS.items():
            if slug in channel_info:
                name = channel_info[slug]['name']
                group = channel_info[slug]['group']
            else:
                name = slug_to_name(slug)
                group = "Other"

            # m3u8 varsa onu kullan, yoksa track URL
            if slug in m3u8_cache:
                url = m3u8_cache[slug]
                m3u8_count += 1
            else:
                url = f"{stream_base}/247/{track_id}"

            f.write(f'#EXTINF:-1 group-title="{group}" tvg-name="{name}",{name}\n')
            f.write(f'#EXTVLCOPT:http-referrer={stream_base}/\n')
            f.write(f'#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\n')

            # m3u8 URL'leri için Origin header ekle
            if '.m3u8' in url:
                f.write(f'#EXTVLCOPT:http-origin={stream_base}\n')

            f.write(f'{url}\n\n')
            count += 1

    print(f"\n{'='*60}")
    print(f"✅ {OUTPUT_FILE} oluşturuldu!")
    print(f"  📋 Toplam kanal: {count}")
    print(f"  🎬 m3u8 stream:  {m3u8_count}")
    print(f"  📺 Track URL:    {count - m3u8_count}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
