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

from dataclasses import dataclass
from datetime import datetime
from collections import deque
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from pathlib import Path
from typing import Optional

#############
# Constants #
#############

load_dotenv()

API_KEY = {"Authorization": f"Bearer {os.getenv('TOKEN')}", "Accept": "application/x-ndjson"}
BASE = "https://lichess.org"
GAME_API = BASE + "/api/games/user/{}"
LOG_PATH = f"tradeBoard.log"
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

log = logging.getLogger("tradeBoard")
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


class Day:
    datetime: "datetime"
    close: int
    open: Optional[int]
    high: int
    low: int
    volume: int

    def __init__(self, date: datetime, close: int, before: int, after: int) -> None:
        self.date = date
        self.close = close
        self.open = None
        self.high = 0
        self.low = 3999
        self.volume = 0
        self.update(before, after)

    def update(self, before: int, after: int) -> None:
        # Remember, games are fetched in reverse chronological order
        self.high = max(self.high, before, after)
        self.low = min(self.low, before, after)
        self.volume += 1
        # log.debug(f"{self.volume} games on day {self.date}")

    def finish(self, open: int) -> None:
        """Called when every games of `date` have been processed"""
        self.open = open

    def to_list(self) -> List[Union[datetime, int]]:
        assert self.open
        return [self.open, self.high, self.low, self.close, self.volume]

class LichessTradingBoard:

    def __init__(self, user: str, perf_type: str, max_games: int = 1000, update: bool = False) -> None:
        self.user = user.casefold()
        self.perf_type = perf_type
        self.max_games = max_games
        self.path = Path(f'./downloads/{self.user}/{self.perf_type}.csv')
        self.df = self.get_panda(update)
        http = requests.Session()
        http.mount("https://", ADAPTER)
        http.mount("http://", ADAPTER)
        self.http = http

    def get_panda(self, update: bool) -> "PandaFrame":
        """
        Return game statistics if already downloaded and stored.
        Otherwise return an empty `PandaFrame`
        """
        if self.path.exists() and not update:
            log.info("Existing dataframe found, using it")
            df = pd.read_csv(self.path,index_col=0, parse_dates=True)
            df.index.name = "Date"
            return df
        log.info("No dataframe found, creating it")
        df = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"], index=pd.DatetimeIndex([], name='Date'))
        log.debug(df)
        return df

    def save_df(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.df.to_csv(self.path)

    def fetch_games(self) -> None:
        buffer = deque()
        log.info(f"{self.max_games} asked, about {self.max_games // 30}s to fetch them.")
        r = self.http.get(GAME_API.format(self.user), params={"moves": False, "rated": True, "perfType": self.perf_type, "max": self.max_games, "variant": "standard"}, headers=API_KEY, stream=True)
        # reverse chronological order
        for game_raw in r.iter_lines():
            game = json.loads(game_raw.decode())
            date = datetime.combine(datetime.utcfromtimestamp(game["createdAt"] / 1000).date(), datetime.min.time())
            before, after = self.get_rating(game)
            if len(buffer) == 1 and buffer[0].date == date:
                buffer[0].update(before, after)
            else:
                log.info(f"Started computing day {date}")
                buffer.append(Day(date=date, before=before, after=after, close=after)) # Last game of the day first
            if buffer[0].date != date: # We've started a new day
                # Save the computed day, if it's not the first game we've received
                log.debug(f"Last game of {date}: {game}")
                finished_day = buffer.popleft()
                finished_day.finish(before)
                self.df.loc[finished_day.date] = finished_day.to_list()
                log.debug(self.df)
        self.df = self.df[::-1] # Put back the data in chronological order TODO fix when data is already ok, use `reindex` `sort_value`?

    def get_rating(self, game) -> None:
        """Return the rating for the player `user` before and after the game"""
        try:
            players = game["players"]
            # log.debug(players)
            if self.user in players["white"]["user"]["id"]:
                before = int(players["white"]["rating"])
                after = before + int(players["white"].get("ratingDiff", 0))
                return before, after
            before = int(players["black"]["rating"])
            after = before + int(players["black"].get("ratingDiff", 0))
        except KeyError as e:
            log.error(e)
            log.error(f"Data: {game}")
            raise Exception()
        return before, after

    def show(self, df: "Dataframe") -> None:
        mc = mpf.make_marketcolors(up='g',down='r')
        s  = mpf.make_mpf_style(marketcolors=mc)
        mpf.plot(df, type='candle', volume=True, style=s, ylabel='Rating', ylabel_lower="Games", title=f"{self.user} • {self.perf_type}")

    def run(self) -> None:
        self.fetch_games()

        self.save_df()
        df = self.df.astype(float)
        self.show(df)


########
# Main #
########

if __name__ == "__main__":
    test = LichessTradingBoard("German11", "blitz", max_games=4000, update=True)
    test.run()
