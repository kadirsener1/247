#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import re
import asyncio
from pathlib import Path
from datetime import datetime, timezone, timedelta

import requests
from playwright.async_api import async_playwright, Error as PlaywrightError


# ─── MASTER KANAL LİSTESİ ─────────────────────────────────────────────────────
MASTER_CHANNELS = [
    {
        "name": "uktntsports1",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=TNT%20Sports%201&code=gb&user=cdnlivetv&plan=free",
        "group": "uk"
    },
    {
        "name": "uktntsports2",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=TNT%20Sports%202&code=gb&user=cdnlivetv&plan=free",
        "group": "uk"
    },
    {
        "name": "uktntsports3",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=TNT%20Sports%203&code=gb&user=cdnlivetv&plan=free",
        "group": "uk"
    },
    {
        "name": "uktntsports4",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=TNT%20Sports%204&code=gb&user=cdnlivetv&plan=free",
        "group": "uk"
    },
    {
        "name": "uktntsportsultimate",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=TNT%20Sports%20Ultimate&code=gb&user=cdnlivetv&plan=free",
        "group": "uk"
    },
    {
        "name": "ukskysportsmainevent",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Sky%20Sports%20Main%20Event&code=gb&user=cdnlivetv&plan=free",
        "group": "uk"
    },
    {
        "name": "ukskysportspremierleague",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Sky%20Sports%20Premier%20League&code=gb&user=cdnlivetv&plan=free",
        "group": "uk"
    },
    {
        "name": "ukskysportsfootball",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Sky%20Sports%20Football&code=gb&user=cdnlivetv&plan=free",
        "group": "uk"
    },
    {
        "name": "ukskysportsf1",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Sky%20Sports%20F1&code=gb&user=cdnlivetv&plan=free",
        "group": "uk"
    },
    {
        "name": "ukskysportscricket",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Sky%20Sports%20Cricket&code=gb&user=cdnlivetv&plan=free",
        "group": "uk"
    },
    {
        "name": "ukskysportsgolf",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Sky%20Sports%20Golf&code=gb&user=cdnlivetv&plan=free",
        "group": "uk"
    },
    {
        "name": "ukskysportsaction",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Sky%20Sports%20Action&code=gb&user=cdnlivetv&plan=free",
        "group": "uk"
    },
    {
        "name": "ukskysportsarena",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Sky%20Sports%20Arena&code=gb&user=cdnlivetv&plan=free",
        "group": "uk"
    },
    {
        "name": "ukskysportstennis",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Sky%20Sports%20Tennis&code=gb&user=cdnlivetv&plan=free",
        "group": "uk"
    },
    {
        "name": "ukskysportsmix",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Sky%20Sports%20Mix&code=gb&user=cdnlivetv&plan=free",
        "group": "uk"
    },
    {
        "name": "ukskysportsnews",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Sky%20Sports%20News&code=gb&user=cdnlivetv&plan=free",
        "group": "uk"
    },
    {
        "name": "ukskysportsracing",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Sky%20Sports%20Racing&code=gb&user=cdnlivetv&plan=free",
        "group": "uk"
    },
    {
        "name": "ukpremiersports1",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Premier%20Sports%201&code=gb&user=cdnlivetv&plan=free",
        "group": "uk"
    },
    {
        "name": "ukpremiersports2",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Premier%20Sports%202&code=gb&user=cdnlivetv&plan=free",
        "group": "uk"
    },
    {
        "name": "ukeurosport1",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Eurosport%201&code=gb&user=cdnlivetv&plan=free",
        "group": "uk"
    },
    {
        "name": "ukeurosport2",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Eurosport%202&code=gb&user=cdnlivetv&plan=free",
        "group": "uk"
    },
    {
        "name": "ukbbcone",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=BBC%20One&code=gb&user=cdnlivetv&plan=free",
        "group": "uk"
    },
    {
        "name": "ukbbctwo",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=BBC%20Two&code=gb&user=cdnlivetv&plan=free",
        "group": "uk"
    },
    {
        "name": "ukitv1",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=ITV%201&code=gb&user=cdnlivetv&plan=free",
        "group": "uk"
    },
    {
        "name": "ukchannel4",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Channel%204&code=gb&user=cdnlivetv&plan=free",
        "group": "uk"
    },
    {
        "name": "ukchannel5",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Channel%205&code=gb&user=cdnlivetv&plan=free",
        "group": "uk"
    },
    {
        "name": "trbeinsports1",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=beIN%20Sports%201&code=tr&user=cdnlivetv&plan=free",
        "group": "tr"
    },
    {
        "name": "trbeinsports2",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=beIN%20Sports%202&code=tr&user=cdnlivetv&plan=free",
        "group": "tr"
    },
    {
        "name": "trbeinsports3",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=beIN%20Sports%203&code=tr&user=cdnlivetv&plan=free",
        "group": "tr"
    },
    {
        "name": "trbeinsports4",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=beIN%20Sports%204&code=tr&user=cdnlivetv&plan=free",
        "group": "tr"
    },
    {
        "name": "trbeinsports5",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=beIN%20Sports%205&code=tr&user=cdnlivetv&plan=free",
        "group": "tr"
    },
    {
        "name": "trbeinsportsmax1",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=beIN%20Sports%20MAX%201&code=tr&user=cdnlivetv&plan=free",
        "group": "tr"
    },
    {
        "name": "trbeinsportsmax2",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=beIN%20Sports%20MAX%202&code=tr&user=cdnlivetv&plan=free",
        "group": "tr"
    },
    {
        "name": "trbeinsportshaber",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=beIN%20Sports%20Haber&code=tr&user=cdnlivetv&plan=free",
        "group": "tr"
    },
    {
        "name": "trssport",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=S%20Sport&code=tr&user=cdnlivetv&plan=free",
        "group": "tr"
    },
    {
        "name": "trssport2",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=S%20Sport%202&code=tr&user=cdnlivetv&plan=free",
        "group": "tr"
    },
    {
        "name": "trtivibuspor1",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Tivibu%20Spor%201&code=tr&user=cdnlivetv&plan=free",
        "group": "tr"
    },
    {
        "name": "trtivibuspor2",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Tivibu%20Spor%202&code=tr&user=cdnlivetv&plan=free",
        "group": "tr"
    },
    {
        "name": "trtivibuspor3",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Tivibu%20Spor%203&code=tr&user=cdnlivetv&plan=free",
        "group": "tr"
    },
    {
        "name": "trtivibuspor4",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Tivibu%20Spor%204&code=tr&user=cdnlivetv&plan=free",
        "group": "tr"
    },
    {
        "name": "trtrtspor",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=TRT%20Spor&code=tr&user=cdnlivetv&plan=free",
        "group": "tr"
    },
    {
        "name": "trtrtsporyildiz",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=TRT%20Spor%20Yildiz&code=tr&user=cdnlivetv&plan=free",
        "group": "tr"
    },
    {
        "name": "traspor",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=A%20Spor&code=tr&user=cdnlivetv&plan=free",
        "group": "tr"
    },
    {
        "name": "trtv8buçuk",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=TV8.5&code=tr&user=cdnlivetv&plan=free",
        "group": "tr"
    },
    {
        "name": "usespn",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=ESPN&code=us&user=cdnlivetv&plan=free",
        "group": "us"
    },
    {
        "name": "usespn2",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=ESPN%202&code=us&user=cdnlivetv&plan=free",
        "group": "us"
    },
    {
        "name": "usespnu",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=ESPNU&code=us&user=cdnlivetv&plan=free",
        "group": "us"
    },
    {
        "name": "usespnews",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=ESPNews&code=us&user=cdnlivetv&plan=free",
        "group": "us"
    },
    {
        "name": "usespndeportes",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=ESPN%20Deportes&code=us&user=cdnlivetv&plan=free",
        "group": "us"
    },
    {
        "name": "usfoxsports1",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Fox%20Sports%201&code=us&user=cdnlivetv&plan=free",
        "group": "us"
    },
    {
        "name": "usfoxsports2",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Fox%20Sports%202&code=us&user=cdnlivetv&plan=free",
        "group": "us"
    },
    {
        "name": "usbigtennetwork",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Big%20Ten%20Network&code=us&user=cdnlivetv&plan=free",
        "group": "us"
    },
    {
        "name": "ussecnetwork",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=SEC%20Network&code=us&user=cdnlivetv&plan=free",
        "group": "us"
    },
    {
        "name": "usaccnetwork",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=ACC%20Network&code=us&user=cdnlivetv&plan=free",
        "group": "us"
    },
    {
        "name": "uscbsportsnetwork",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=CBS%20Sports%20Network&code=us&user=cdnlivetv&plan=free",
        "group": "us"
    },
    {
        "name": "usnbcsports",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=NBC%20Sports&code=us&user=cdnlivetv&plan=free",
        "group": "us"
    },
    {
        "name": "usnbatv",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=NBA%20TV&code=us&user=cdnlivetv&plan=free",
        "group": "us"
    },
    {
        "name": "usnflnetwork",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=NFL%20Network&code=us&user=cdnlivetv&plan=free",
        "group": "us"
    },
    {
        "name": "usnhlnetwork",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=NHL%20Network&code=us&user=cdnlivetv&plan=free",
        "group": "us"
    },
    {
        "name": "usmlbnetwork",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=MLB%20Network&code=us&user=cdnlivetv&plan=free",
        "group": "us"
    },
    {
        "name": "ustennischannel",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Tennis%20Channel&code=us&user=cdnlivetv&plan=free",
        "group": "us"
    },
    {
        "name": "usgolfchannel",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Golf%20Channel&code=us&user=cdnlivetv&plan=free",
        "group": "us"
    },
    {
        "name": "uswillowtv",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Willow%20TV&code=us&user=cdnlivetv&plan=free",
        "group": "us"
    },
    {
        "name": "uswwe",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=WWE%20Network&code=us&user=cdnlivetv&plan=free",
        "group": "us"
    },
    {
        "name": "usfightnetwork",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Fight%20Network&code=us&user=cdnlivetv&plan=free",
        "group": "us"
    },
    {
        "name": "usabc",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=ABC&code=us&user=cdnlivetv&plan=free",
        "group": "us"
    },
    {
        "name": "uscbs",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=CBS&code=us&user=cdnlivetv&plan=free",
        "group": "us"
    },
    {
        "name": "usnbc",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=NBC&code=us&user=cdnlivetv&plan=free",
        "group": "us"
    },
    {
        "name": "usfox",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=FOX&code=us&user=cdnlivetv&plan=free",
        "group": "us"
    },
    {
        "name": "ususanetwork",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=USA%20Network&code=us&user=cdnlivetv&plan=free",
        "group": "us"
    },
    {
        "name": "frcanalplus",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Canal%2B&code=fr&user=cdnlivetv&plan=free",
        "group": "fr"
    },
    {
        "name": "frcanalplussport",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Canal%2B%20Sport&code=fr&user=cdnlivetv&plan=free",
        "group": "fr"
    },
    {
        "name": "frcanalplusfoot",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Canal%2B%20Foot&code=fr&user=cdnlivetv&plan=free",
        "group": "fr"
    },
    {
        "name": "frcanalplussport360",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Canal%2B%20Sport%20360&code=fr&user=cdnlivetv&plan=free",
        "group": "fr"
    },
    {
        "name": "frbeinsports1",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=beIN%20Sports%201&code=fr&user=cdnlivetv&plan=free",
        "group": "fr"
    },
    {
        "name": "frbeinsports2",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=beIN%20Sports%202&code=fr&user=cdnlivetv&plan=free",
        "group": "fr"
    },
    {
        "name": "frbeinsports3",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=beIN%20Sports%203&code=fr&user=cdnlivetv&plan=free",
        "group": "fr"
    },
    {
        "name": "frbeinsportsmax4",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=beIN%20SPORTS%20MAX%204&code=fr&user=cdnlivetv&plan=free",
        "group": "fr"
    },
    {
        "name": "frbeinsportsmax5",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=beIN%20SPORTS%20MAX%205&code=fr&user=cdnlivetv&plan=free",
        "group": "fr"
    },
    {
        "name": "frbeinsportsmax6",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=beIN%20SPORTS%20MAX%206&code=fr&user=cdnlivetv&plan=free",
        "group": "fr"
    },
    {
        "name": "frbeinsportsmax7",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=beIN%20SPORTS%20MAX%207&code=fr&user=cdnlivetv&plan=free",
        "group": "fr"
    },
    {
        "name": "frbeinsportsmax8",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=beIN%20SPORTS%20MAX%208&code=fr&user=cdnlivetv&plan=free",
        "group": "fr"
    },
    {
        "name": "frbeinsportsmax9",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=beIN%20SPORTS%20MAX%209&code=fr&user=cdnlivetv&plan=free",
        "group": "fr"
    },
    {
        "name": "frbeinsportsmax10",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=beIN%20SPORTS%20MAX%2010&code=fr&user=cdnlivetv&plan=free",
        "group": "fr"
    },
    {
        "name": "frrmcsport1",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=RMC%20Sport%201&code=fr&user=cdnlivetv&plan=free",
        "group": "fr"
    },
    {
        "name": "frrmcsport2",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=RMC%20Sport%202&code=fr&user=cdnlivetv&plan=free",
        "group": "fr"
    },
    {
        "name": "freurosport1",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Eurosport%201%20FR&code=fr&user=cdnlivetv&plan=free",
        "group": "fr"
    },
    {
        "name": "freurosport2",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Eurosport%202%20FR&code=fr&user=cdnlivetv&plan=free",
        "group": "fr"
    },
    {
        "name": "esdaznlaliga",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=DAZN%20LaLiga&code=es&user=cdnlivetv&plan=free",
        "group": "es"
    },
    {
        "name": "esdazn1",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=DAZN%201%20ES&code=es&user=cdnlivetv&plan=free",
        "group": "es"
    },
    {
        "name": "esdazn2",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=DAZN%202%20ES&code=es&user=cdnlivetv&plan=free",
        "group": "es"
    },
    {
        "name": "esdaznf1",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=DAZN%20F1&code=es&user=cdnlivetv&plan=free",
        "group": "es"
    },
    {
        "name": "esmovistarlaliga",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Movistar%20LaLiga&code=es&user=cdnlivetv&plan=free",
        "group": "es"
    },
    {
        "name": "esmovistarligadecampeones",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Movistar%20Liga%20de%20Campeones&code=es&user=cdnlivetv&plan=free",
        "group": "es"
    },
    {
        "name": "esmovistardeportes",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Movistar%20Deportes&code=es&user=cdnlivetv&plan=free",
        "group": "es"
    },
    {
        "name": "esmovistargolf",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Movistar%20Golf&code=es&user=cdnlivetv&plan=free",
        "group": "es"
    },
    {
        "name": "esmovistarplus",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Movistar%20Plus%2B&code=es&user=cdnlivetv&plan=free",
        "group": "es"
    },
    {
        "name": "deskysportbundesliga1",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Sky%20Sport%20Bundesliga%201&code=de&user=cdnlivetv&plan=free",
        "group": "de"
    },
    {
        "name": "deskysporttopevent",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Sky%20Sport%20Top%20Event&code=de&user=cdnlivetv&plan=free",
        "group": "de"
    },
    {
        "name": "deskysportpremierleague",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Sky%20Sport%20Premier%20League&code=de&user=cdnlivetv&plan=free",
        "group": "de"
    },
    {
        "name": "deskysportf1",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Sky%20Sport%20F1%20DE&code=de&user=cdnlivetv&plan=free",
        "group": "de"
    },
    {
        "name": "dedazn1",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=DAZN%201%20DE&code=de&user=cdnlivetv&plan=free",
        "group": "de"
    },
    {
        "name": "dedazn2",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=DAZN%202%20DE&code=de&user=cdnlivetv&plan=free",
        "group": "de"
    },
    {
        "name": "desport1",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Sport1&code=de&user=cdnlivetv&plan=free",
        "group": "de"
    },
    {
        "name": "defussball",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=fussball&code=de&user=cdnlivetv&plan=free",
        "group": "de"
    },
    {
        "name": "itskysportuno",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Sky%20Sport%20Uno&code=it&user=cdnlivetv&plan=free",
        "group": "it"
    },
    {
        "name": "itskysportcalcio",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Sky%20Sport%20Calcio&code=it&user=cdnlivetv&plan=free",
        "group": "it"
    },
    {
        "name": "itskysportfootball",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Sky%20Sport%20Football&code=it&user=cdnlivetv&plan=free",
        "group": "it"
    },
    {
        "name": "itskysportf1",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Sky%20Sport%20F1%20IT&code=it&user=cdnlivetv&plan=free",
        "group": "it"
    },
    {
        "name": "itskysportmotogp",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Sky%20Sport%20MotoGP&code=it&user=cdnlivetv&plan=free",
        "group": "it"
    },
    {
        "name": "itskysport24",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Sky%20Sport%2024&code=it&user=cdnlivetv&plan=free",
        "group": "it"
    },
    {
        "name": "itdazn1",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=DAZN%201%20IT&code=it&user=cdnlivetv&plan=free",
        "group": "it"
    },
    {
        "name": "catsn1",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=TSN%201&code=ca&user=cdnlivetv&plan=free",
        "group": "ca"
    },
    {
        "name": "catsn2",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=TSN%202&code=ca&user=cdnlivetv&plan=free",
        "group": "ca"
    },
    {
        "name": "catsn3",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=TSN%203&code=ca&user=cdnlivetv&plan=free",
        "group": "ca"
    },
    {
        "name": "catsn4",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=TSN%204&code=ca&user=cdnlivetv&plan=free",
        "group": "ca"
    },
    {
        "name": "catsn5",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=TSN%205&code=ca&user=cdnlivetv&plan=free",
        "group": "ca"
    },
    {
        "name": "casportsnetontario",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Sportsnet%20Ontario&code=ca&user=cdnlivetv&plan=free",
        "group": "ca"
    },
    {
        "name": "casportsnetone",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Sportsnet%20One&code=ca&user=cdnlivetv&plan=free",
        "group": "ca"
    },
    {
        "name": "casportsnet360",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Sportsnet%20360&code=ca&user=cdnlivetv&plan=free",
        "group": "ca"
    },
    {
        "name": "ptsporttv1",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Sport%20TV%201&code=pt&user=cdnlivetv&plan=free",
        "group": "pt"
    },
    {
        "name": "ptsporttv2",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Sport%20TV%202&code=pt&user=cdnlivetv&plan=free",
        "group": "pt"
    },
    {
        "name": "ptsporttv3",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Sport%20TV%203&code=pt&user=cdnlivetv&plan=free",
        "group": "pt"
    },
    {
        "name": "ptdazn1",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=DAZN%201%20PT&code=pt&user=cdnlivetv&plan=free",
        "group": "pt"
    },
    {
        "name": "ptbenficatv",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Benfica%20TV&code=pt&user=cdnlivetv&plan=free",
        "group": "pt"
    },
    {
        "name": "nlziggosportselect",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Ziggo%20Sport%20Select&code=nl&user=cdnlivetv&plan=free",
        "group": "nl"
    },
    {
        "name": "nlziggosportvoetbal",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Ziggo%20Sport%20Voetbal&code=nl&user=cdnlivetv&plan=free",
        "group": "nl"
    },
    {
        "name": "nlziggosportracing",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Ziggo%20Sport%20Racing&code=nl&user=cdnlivetv&plan=free",
        "group": "nl"
    },
    {
        "name": "nlespn1",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=ESPN%201%20NL&code=nl&user=cdnlivetv&plan=free",
        "group": "nl"
    },
    {
        "name": "nlespn2",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=ESPN%202%20NL&code=nl&user=cdnlivetv&plan=free",
        "group": "nl"
    },
    {
        "name": "aufoxleague",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Fox%20League&code=au&user=cdnlivetv&plan=free",
        "group": "au"
    },
    {
        "name": "aufoxfooty",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Fox%20Footy&code=au&user=cdnlivetv&plan=free",
        "group": "au"
    },
    {
        "name": "aufoxcricket",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Fox%20Cricket&code=au&user=cdnlivetv&plan=free",
        "group": "au"
    },
    {
        "name": "aufoxsports503",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Fox%20Sports%20503&code=au&user=cdnlivetv&plan=free",
        "group": "au"
    },
    {
        "name": "aufoxsports505",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Fox%20Sports%20505&code=au&user=cdnlivetv&plan=free",
        "group": "au"
    },
    {
        "name": "aufoxsports506",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Fox%20Sports%20506&code=au&user=cdnlivetv&plan=free",
        "group": "au"
    },
    {
        "name": "auoptussport1",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Optus%20Sport%201&code=au&user=cdnlivetv&plan=free",
        "group": "au"
    },
    {
        "name": "austansport",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Stan%20Sport&code=au&user=cdnlivetv&plan=free",
        "group": "au"
    },
    {
        "name": "arbeinsports1premium",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=beIN%20Sports%201%20Premium&code=ar&user=cdnlivetv&plan=free",
        "group": "ar"
    },
    {
        "name": "arbeinsports2premium",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=beIN%20Sports%202%20Premium&code=ar&user=cdnlivetv&plan=free",
        "group": "ar"
    },
    {
        "name": "arbeinsports3premium",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=beIN%20Sports%203%20Premium&code=ar&user=cdnlivetv&plan=free",
        "group": "ar"
    },
    {
        "name": "arbeinsportsenglish1",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=beIN%20Sports%20English%201&code=ar&user=cdnlivetv&plan=free",
        "group": "ar"
    },
    {
        "name": "arssc1",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=SSC%201&code=ar&user=cdnlivetv&plan=free",
        "group": "ar"
    },
    {
        "name": "arssc2",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=SSC%202&code=ar&user=cdnlivetv&plan=free",
        "group": "ar"
    },
    {
        "name": "arssc3",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=SSC%203&code=ar&user=cdnlivetv&plan=free",
        "group": "ar"
    },
    {
        "name": "arssc4",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=SSC%204&code=ar&user=cdnlivetv&plan=free",
        "group": "ar"
    },
    {
        "name": "arssc5",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=SSC%205&code=ar&user=cdnlivetv&plan=free",
        "group": "ar"
    },
    {
        "name": "arsscextra1",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=SSC%20Extra%201&code=ar&user=cdnlivetv&plan=free",
        "group": "ar"
    },
    {
        "name": "aralkass1",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Alkass%201&code=ar&user=cdnlivetv&plan=free",
        "group": "ar"
    },
    {
        "name": "aralkass2",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=Alkass%202&code=ar&user=cdnlivetv&plan=free",
        "group": "ar"
    },
    {
        "name": "aradextrap1",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=AD%20Sports%20Premium%201&code=ar&user=cdnlivetv&plan=free",
        "group": "ar"
    }
]

# ─── SİSTEM AYARLARI ──────────────────────────────────────────────────────────
OUTPUT_FILE_NAME   = "cdn.m3u"
PLAYLIST_FILE_NAME = "playlist.m3u"
PLAYLIST_URL       = "https://raw.githubusercontent.com/kadirsener1/avva/refs/heads/main/playlist.m3u"
DEBUG_FILE         = "debug_failed.json"

TIMEOUT      = 15000
FIRST_WAIT   = 3.0   # İlk yüklemede bekleme (saniye)
RELOAD_WAIT  = 3.5   # Her retry sonrası bekleme (saniye)
MAX_RETRIES  = 20    # ✅ YENİ: Maksimum yenileme denemesi (eski kodda sadece 1'di)
RETRY_WAIT   = 2.0   # ✅ YENİ: Denemeler arası ek bekleme (saniye)
MAX_CONCURRENT = 4

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8",
    "Referer": "https://cdnlivetv.tv/",
    "Origin": "https://cdnlivetv.tv",
}

BROWSER_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--mute-audio",
    "--ignore-certificate-errors",
    "--ignore-ssl-errors",
    "--disable-extensions",
    "--disable-background-networking",
    "--hide-scrollbars",
    "--autoplay-policy=no-user-gesture-required",
    "--disable-blink-features=AutomationControlled",
]

BLOCKED_RESOURCE_TYPES = {"image", "media", "font"}

# Sitedeki hata mesajları — bu metinler varsa stream gelmemiş demektir
STREAM_ERROR_TEXTS = [
    "Stream loading failed",
    "Stream Error",
    "Please refresh",
    "stream-error",
]

# ──────────────────────────────────────────────────────────────────────────────


def is_valid_stream_url(url: str) -> bool:
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return False
    invalid_chars = [" ", "{", "}", "<", ">", '"', "'", "`", ";", "(", ")",
                     "\\", "\n", "\r", "\t", "&&", "||", "import", "function"]
    if any(c in url for c in invalid_chars):
        return False
    junk_keywords = ["parser", "bundle", "webpack", "chunk", "worker", "player.min"]
    url_lower = url.lower()
    if any(k in url_lower for k in junk_keywords):
        return False
    base_path = url.split("?")[0].lower()
    if not (".m3u8" in base_path or ".mpd" in base_path):
        return False
    return True


def extract_from_html(html_text: str, base_url: str = "") -> str:
    if not html_text:
        return ""
    html_text = html_text.replace("\\/", "/").replace("\\u0026", "&")
    pattern = r'https?://[a-zA-Z0-9\-._~:/?#\[\]@!$&*+,;=%]+\.(?:m3u8|mpd)(?:\?[a-zA-Z0-9\-._~:/?#\[\]@!$&*+,;=%]*)?'
    matches = re.findall(pattern, html_text, re.IGNORECASE)
    for m in matches:
        if is_valid_stream_url(m):
            return m
    return ""


def has_stream_error(content: str) -> bool:
    """Sayfa içeriğinde stream hatası var mı kontrol et."""
    return any(err in content for err in STREAM_ERROR_TEXTS)


async def extract_from_js(page) -> str:
    try:
        val = await page.evaluate("""
            () => {
                try {
                    if (typeof jwplayer !== 'undefined' && jwplayer().getPlaylistItem) {
                        const f = jwplayer().getPlaylistItem()?.file;
                        if (f && typeof f === 'string' && f.startsWith('http')) return f;
                    }
                } catch(e){}
                try {
                    if (typeof videojs !== 'undefined') {
                        const players = videojs.getAllPlayers();
                        for (let p of players) {
                            const src = p.currentSrc ? p.currentSrc() : (p.src ? p.src() : null);
                            if (src && typeof src === 'string' && src.startsWith('http')) return src;
                        }
                    }
                } catch(e){}
                try {
                    if (typeof Hls !== 'undefined' && Hls.url && Hls.url.startsWith('http')) return Hls.url;
                } catch(e){}
                const v = document.querySelector('video');
                if (v && v.src && v.src.startsWith('http')) return v.src;
                const s = document.querySelector('video source');
                if (s && s.src && s.src.startsWith('http')) return s.src;
                return null;
            }
        """)
        if val and is_valid_stream_url(val):
            return val
    except Exception:
        pass
    return ""


async def try_trigger_play(page):
    try:
        await page.mouse.click(200, 200)
    except Exception:
        pass
    try:
        await page.evaluate("""
            () => {
                document.querySelectorAll('video').forEach(v => {
                    try { v.muted = true; v.play(); } catch(e) {}
                });
                const btns = document.querySelectorAll(
                    '.jw-icon-display, .vjs-big-play-button, button[aria-label*="play" i], .play-button, #play'
                );
                btns.forEach(b => { try { b.click(); } catch(e) {} });
            }
        """)
    except Exception:
        pass


async def get_stream_url(browser, player_url: str, channel_name: str) -> str:
    stream_url = ""
    found_event = asyncio.Event()

    if not browser.is_connected():
        return ""

    context = None
    page    = None

    try:
        context = await browser.new_context(
            user_agent=HEADERS["User-Agent"],
            extra_http_headers={
                "Accept-Language": HEADERS["Accept-Language"],
                "Referer": HEADERS["Referer"],
            },
            bypass_csp=True,
            ignore_https_errors=True,
            viewport={"width": 1280, "height": 720},
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        page = await context.new_page()

        async def route_filter(route):
            req = route.request
            if is_valid_stream_url(req.url):
                await route.continue_()
            elif req.resource_type in BLOCKED_RESOURCE_TYPES:
                await route.abort()
            else:
                await route.continue_()

        await page.route("**/*", route_filter)

        async def on_request(request):
            nonlocal stream_url
            url = request.url
            if not stream_url and is_valid_stream_url(url):
                stream_url = url
                found_event.set()

        async def on_response(response):
            nonlocal stream_url
            if stream_url:
                return
            url = response.url
            if is_valid_stream_url(url):
                stream_url = url
                found_event.set()
                return
            ct = response.headers.get("content-type", "").lower()
            if "application/json" in ct:
                try:
                    text = await response.text()
                    if ".m3u8" in text or ".mpd" in text:
                        found = extract_from_html(text, url)
                        if found and is_valid_stream_url(found):
                            stream_url = found
                            found_event.set()
                except Exception:
                    pass

        page.on("request",  on_request)
        page.on("response", on_response)

        # ── İlk yükleme ──────────────────────────────────────────────────────
        try:
            await page.goto(player_url, timeout=TIMEOUT, wait_until="domcontentloaded")
        except Exception:
            pass

        await try_trigger_play(page)

        try:
            await asyncio.wait_for(found_event.wait(), timeout=FIRST_WAIT)
        except asyncio.TimeoutError:
            pass

        # ── Retry döngüsü ────────────────────────────────────────────────────
        # Sitede "Stream Error" gelince sayfa yenilemek gerekiyor.
        # Bazen 15+ deneme gerekebileceğinden MAX_RETRIES kadar deniyoruz.
        for attempt in range(1, MAX_RETRIES + 1):

            if stream_url and is_valid_stream_url(stream_url):
                break  # URL bulundu, döngüden çık

            # Sayfadaki içeriği kontrol et
            page_has_error = False
            try:
                content = await page.content()

                if has_stream_error(content):
                    # Stream Error hâlâ var — yenilemeye devam
                    page_has_error = True
                else:
                    # Hata yok → HTML'den URL çekmeyi dene
                    found = extract_from_html(content, player_url)
                    if is_valid_stream_url(found):
                        stream_url = found
                        break

                    # JS'den dene
                    js_url = await extract_from_js(page)
                    if is_valid_stream_url(js_url):
                        stream_url = js_url
                        break
            except Exception:
                page_has_error = True

            status = "Stream Error — yenileniyor" if page_has_error else "URL yok — yenileniyor"
            print(f"    🔄 [{attempt:02d}/{MAX_RETRIES}] {channel_name}: {status}")

            # Kısa bekleme + event sıfırla + yenile
            await asyncio.sleep(RETRY_WAIT)
            found_event.clear()

            try:
                await page.reload(timeout=TIMEOUT, wait_until="domcontentloaded")
                await try_trigger_play(page)
                await asyncio.wait_for(found_event.wait(), timeout=RELOAD_WAIT)
            except (asyncio.TimeoutError, Exception):
                pass

        # ── Son çare: frame taraması ──────────────────────────────────────────
        if not stream_url:
            try:
                for frame in page.frames:
                    if frame.url and frame.url != player_url:
                        try:
                            fc = await frame.content()
                            found = extract_from_html(fc, frame.url)
                            if is_valid_stream_url(found):
                                stream_url = found
                                break
                        except Exception:
                            pass
            except Exception:
                pass

    except Exception:
        pass
    finally:
        if page:
            try:
                await page.close()
            except Exception:
                pass
        if context:
            try:
                await context.close()
            except Exception:
                pass

    return stream_url if is_valid_stream_url(stream_url) else ""


async def process_all(channels: list) -> tuple:
    success    = []
    failed     = []
    semaphore  = asyncio.Semaphore(MAX_CONCURRENT)
    total      = len(channels)
    done_count = 0
    lock       = asyncio.Lock()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=BROWSER_ARGS)

        async def handle(ch):
            nonlocal done_count
            name       = str(ch.get("name",  "?")).strip()
            player_url = str(ch.get("url",   "")).strip()
            image      = str(ch.get("image", "")).strip()
            group      = str(ch.get("group", "GENEL")).strip().upper()

            if not player_url:
                async with lock:
                    done_count += 1
                    failed.append({"name": name, "player_url": "", "image": image,
                                   "group": group, "reason": "URL yok"})
                return

            async with semaphore:
                stream_url = await get_stream_url(browser, player_url, name)

            async with lock:
                done_count += 1
                prefix = f"[{done_count:03d}/{total}]"
                if stream_url and is_valid_stream_url(stream_url):
                    print(f"  ✅ {prefix} {name} → {stream_url[:65]}...")
                    success.append({
                        "name":       name,
                        "stream_url": stream_url,
                        "player_url": player_url,
                        "image":      image,
                        "group":      group,
                    })
                else:
                    print(f"  ❌ {prefix} {name} (Başarısız / Token Alınamadı)")
                    failed.append({
                        "name":       name,
                        "player_url": player_url,
                        "image":      image,
                        "group":      group,
                        "reason":     "Geçerli stream URL bulunamadı",
                    })

        await asyncio.gather(*[handle(ch) for ch in channels], return_exceptions=True)

        try:
            await browser.close()
        except Exception:
            pass

    return success, failed


def write_single_m3u(items: list, file_name: str = "cdn.m3u"):
    base_path = Path(__file__).parent.resolve()
    file_path = base_path / file_name
    print(f"\n📂 cdn.m3u Yazılıyor (Dosya: {file_path})")
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for ch in items:
                name   = ch["name"]
                stream = ch["stream_url"]
                group  = ch.get("group", "GENEL")
                image  = ch.get("image", "")
                f.write(f'#EXTINF:-1 tvg-id="{name}" tvg-name="{name}" tvg-logo="{image}" group-title="{group}",{name}\n')
                f.write(f"{stream}\n")
        print(f"   💾 Başarıyla Yazıldı: {file_name} ({len(items)} Kanal)")
    except Exception as e:
        print(f"   ❌ Dosya yazma hatası ({file_name}): {e}")


def get_playlist_identifiers(extinf_line: str) -> list:
    identifiers = []
    id_match = re.search(r'tvg-id="([^"]+)"', extinf_line, re.IGNORECASE)
    if id_match:
        identifiers.append(id_match.group(1).strip())
    name_match = re.search(r'tvg-name="([^"]+)"', extinf_line, re.IGNORECASE)
    if name_match:
        identifiers.append(name_match.group(1).strip())
    if "," in extinf_line:
        display_name = extinf_line.rsplit(",", 1)[-1].strip()
        identifiers.append(display_name)
    return identifiers


def get_local_or_remote_playlist() -> str:
    local_file = Path(__file__).parent.resolve() / PLAYLIST_FILE_NAME
    if local_file.exists():
        try:
            content = local_file.read_text(encoding="utf-8")
            if content.strip():
                print(f"   📂 Lokal '{PLAYLIST_FILE_NAME}' dosyası başarıyla okundu.")
                return content
        except Exception:
            pass
    print(f"   🌐 Lokal dosya bulunamadı, uzak adresten indiriliyor: {PLAYLIST_URL}")
    try:
        r = requests.get(PLAYLIST_URL, timeout=15)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"   ❌ Uzak playlist indirilemedi: {e}")
        return ""


def update_playlist_m3u(success_channels: list, content: str):
    if not content:
        print("   ⚠️ Güncellenecek playlist.m3u içeriği bulunamadı!")
        return

    print(f"\n🔄 Playlist Senkronizasyonu Başlatıldı...")

    channel_map = {}
    for ch in success_channels:
        ch_name = ch["name"].strip()
        channel_map[ch_name]            = ch["stream_url"]
        channel_map[ch_name.lower()]    = ch["stream_url"]

    lines         = content.splitlines()
    new_lines     = []
    updated_count = 0
    total_channels = 0

    i = 0
    while i < len(lines):
        line    = lines[i]
        stripped = line.strip()

        if stripped.startswith("#EXTINF"):
            total_channels += 1
            new_lines.append(line)
            identifiers = get_playlist_identifiers(stripped)

            j = i + 1
            url_line_index = -1
            while j < len(lines):
                next_line = lines[j].strip()
                if not next_line:
                    j += 1
                    continue
                if next_line.startswith("#EXTINF") or next_line.startswith("#EXTM3U"):
                    break
                if next_line.startswith("http://") or next_line.startswith("https://"):
                    url_line_index = j
                    break
                j += 1

            matched_stream = None
            matched_id     = ""
            for ident in identifiers:
                if ident in channel_map:
                    matched_stream = channel_map[ident]
                    matched_id     = ident
                    break
                elif ident.lower() in channel_map:
                    matched_stream = channel_map[ident.lower()]
                    matched_id     = ident
                    break

            if matched_stream:
                new_lines.append(matched_stream)
                updated_count += 1
                print(f"   ✨ Eşleşti ve Güncellendi: {matched_id}")
                i = (url_line_index + 1) if url_line_index != -1 else (i + 1)
            else:
                if url_line_index != -1:
                    for k in range(i + 1, url_line_index + 1):
                        new_lines.append(lines[k])
                    i = url_line_index + 1
                else:
                    i += 1
        else:
            new_lines.append(line)
            i += 1

    file_path = Path(__file__).parent.resolve() / PLAYLIST_FILE_NAME
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(new_lines) + "\n")
        print(f"\n   💾 {PLAYLIST_FILE_NAME} başarıyla kaydedildi!")
        print(f"   📊 Toplam Kanal: {total_channels} | Güncellenen: {updated_count}")
    except Exception as e:
        print(f"   ❌ playlist.m3u kaydedilemedi: {e}")


def print_report(channels: list, success: list, failed: list):
    turkey_tz = timezone(timedelta(hours=3))
    now = datetime.now(turkey_tz).strftime("%d.%m.%Y %H:%M:%S")
    print(f"\n{'═'*65}")
    print(f"📊 SONUÇ RAPORU")
    print(f"{'═'*65}")
    print(f"  📺 Taranan kanal sayısı  : {len(channels)}")
    print(f"  ✅ Başarıyla çözülen     : {len(success)}")
    print(f"  ❌ Başarısız olan        : {len(failed)}")
    print(f"  📁 cdn.m3u               : Güncellendi ({len(success)} kanal)")
    print(f"  📁 playlist.m3u          : Senkronize Edildi")
    print(f"  🕐 Güncelleme zamanı     : {now}")
    print(f"{'═'*65}\n")


async def main():
    print("═" * 65)
    print("   📺 CDN LIVE TV — ÇOKLU LİSTE GÜNCELLEME SİSTEMİ")
    print("═" * 65 + "\n")

    playlist_content = get_local_or_remote_playlist()

    print(f"🚀 Taranacak Kanal Sayısı : {len(MASTER_CHANNELS)}")
    print(f"⚡ Eşzamanlı Sekme        : {MAX_CONCURRENT}")
    print(f"🔁 Max Retry / Kanal      : {MAX_RETRIES}\n")

    success, failed = await process_all(MASTER_CHANNELS)

    write_single_m3u(success, OUTPUT_FILE_NAME)

    if success:
        update_playlist_m3u(success, playlist_content)

    with open(DEBUG_FILE, "w", encoding="utf-8") as f:
        json.dump(failed, f, ensure_ascii=False, indent=2)

    print_report(MASTER_CHANNELS, success, failed)


if __name__ == "__main__":
    asyncio.run(main())
