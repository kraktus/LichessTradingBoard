#!/usr/local/bin/python3
#coding: utf-8
# Licence: GNU AGPLv3

"""Candlestick graph from lichess rating history."""

from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import mplfinance as mpf
import os
import pandas as pd
import requests
import sys

from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from pathlib import Path

#############
# Constants #
#############

load_dotenv()

API_KEY = {"Authorization": f"Bearer {os.getenv('TOKEN')}", "Accept": "application/x-ndjson"}
BASE = "https://lichess.org"
GAME_API = BASE + "/api/games/user/{}"
LOG_PATH = f"{__name__}.log"
RETRY_STRAT = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"]
)
ADAPTER = HTTPAdapter(max_retries=RETRY_STRAT)

########
# Logs #
########

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
format_string = "%(asctime)s | %(levelname)-8s | %(message)s"

# 125000000 bytes = 12.5Mb
handler = logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=12500000, backupCount=3, encoding="utf8")
handler.setFormatter(logging.Formatter(format_string))
handler.setLevel(logging.DEBUG)
log.addHandler(handler)

handler_2 = logging.StreamHandler(sys.stdout)
handler_2.setFormatter(logging.Formatter(format_string))
handler_2.setLevel(logging.INFO)
if __debug__:
    handler_2.setLevel(logging.DEBUG)
log.addHandler(handler_2)

###########
# Classes #
###########

class LichessTradingBoard:

    def __init__(self, user: str, perf_type: str, update: bool = False) -> None:
        self.user = user
        self.perf_type = perf_type
        self.df = self.get_panda()
        http = requests.Session()
        http.mount("https://", ADAPTER)
        http.mount("http://", ADAPTER)
        self.http = http

    def get_panda(self) -> "PandaFrame":
        """
        Return game statistics if already downloaded and stored.
        Otherwise return an empty `PandaFrame`
        """
        p = Path(f'./downloads/{self.user}/{self.perf_type}.csv')
        if p.exists():
            df = pd.read_csv(p,index_col=0,parse_dates=True)
            df.index.name = "Datetime"
            return df
        df = pd.DataFrame(columns=["Datetime", "Open", "High", "Low", "Close", "Volume"])
        df.set_index('Datetime',inplace=True)
        return df

    def get_games(self) -> None:
        r = self.http.get(GAME_API.format(self.user), params={"moves": False}, headers=API_KEY, stream=True)
        # reverse chronological order
        for game_raw in r.iter_lines():
            # game = game_raw.json()
            log.debug(game_raw)
                
    def get_rating(self, game):
        """Return the rating for the player `user` before and after the game"""
        if self.user in game["players"]["white"]["user"]["name"]:
            before = int(game["white"]["rating"])
            after = before + int(game["white"]["ratingDiff"])
            return before, after
        before = int(game["black"]["rating"])
        after = before + int(game["black"]["ratingDiff"])
        return before, after

########
# Main #
########

if __name__ == "__main__":
    test = LichessTradingBoard("german11", "bullet")
    test.get_games()
