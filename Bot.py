import logging
import os

from datetime import datetime, timedelta
from typing import List
import pytz

import tweepy
from tweepy.error import TweepError

import socketio
from signal import signal, SIGINT

import json

VERSION = "1.4.1"

log = logging.getLogger()


class Bot:
    """The twitter bot."""

    # Consts
    CALL_TEXT = "{} second encrypted call at {}"
    HASHTAGS = "#SeattleProtestComms #ProtestCommsSeattle"
    TWEET_PADDING = 20

    def __init__(self) -> None:
        """Initializes the class."""
        self.callThreshold = int(os.getenv("CALL_THRESHOLD", 1))
        self.debug = os.getenv("DEBUG", "true").lower() == "true"
        self.reportLatency = os.getenv("REPORT_LATENCY", "false").lower() == "true"
        self.window_minutes = int(os.getenv("WINDOW_M", 5))
        self.timezone = pytz.timezone(os.getenv("TIMEZONE", "US/Pacific"))

        self.cachedTweet: int = None
        self.cachedTime: datetime = None

        self.latency = [timedelta(seconds=0)]

        if not self.debug:
            # Does not need to be saved for later.
            # If the keys aren't in env this will still run.
            auth = tweepy.OAuthHandler(
                os.getenv("CONSUMER_KEY", ""), os.getenv("CONSUMER_SECRET", "")
            )
            auth.set_access_token(
                os.getenv("ACCESS_TOKEN_KEY", ""), os.getenv("ACCESS_TOKEN_SECRET", "")
            )
            self.api = tweepy.API(auth)
            # Test the authentication. This will gracefully fail if the keys aren't present.
            try:
                self.api.rate_limit_status()
            except TweepError as e:
                if e.api_code == 215:
                    log.error("No keys or bad keys")
                else:
                    log.error("Other API error: {}".format(e))
                exit(1)

        signal(SIGINT, self._kill)
        self._connectsio()

    def _connectsio(self) -> None:
        self.sio = socketio.Client()
        self.sio.connect("https://api.openmhz.com/", namespaces=["/"])
        self.sio.wait()

    def _startCapture(self):
        CONFIG = {
            "filterCode": "44912,45040,45112,45072,45136",
            "filterType": "talkgroup",
            "filterName": "OpenMHZ",
            "filterStarred": False,
            "shortName": "kcers1b",
        }
        # DEBUG CONFIG TO GET A LOT OF API RESPONSES
        # CONFIG = {
        #     "filterCode": "",
        #     "filterType": "all",
        #     "filterName": "OpenMHZ",
        #     "filterStarred": False,
        #     "shortName": "kcers1b"
        # }
        self.sio.emit("start", CONFIG)

    @sio.event
    def connect(self):
        self.sio.start_background_task(self._startCapture)

    def _kill(self, rec, frame) -> None:
        """This kills the c̶r̶a̶b̶  bot."""
        log.info("SIGINT or Ctrl-C hit. Exitting.")
        self.sio.emit("stop")
        self.sio.disconnect()
        exit(0)

    @sio.event
    def disconnect(self):
        log.info("Disconnected")

    @sio.on("new message")
    def _handleCall(self, data: str):
        json = json.loads(data)
        self._postTweet(json)

        if self.reportLatency:
            sum = sum(self.latency).total_seconds()
            avg = round(sum / len(self.latency), 3)
            log.info(f"Average latency for the last 100 calls: {avg} seconds")

    def _postTweet(self, call: dict):
        diff = datetime.now(pytz.utc) - datetime.strptime(
            call["time"], "%Y-%m-%dT%H:%M:%S.000%z"
        )

        if abs(diff.total_seconds()) >= 1.8e3:
            return
        elif call["len"] < self.callThreshold:
            log.debug(
                f"Call of size {call['len']} below threshold ({self.callThreshold})"
            )
            return

        if self.reportLatency:
            # Store latency
            self.latency.append(diff)
            if len(self.latency) > 100:
                self.latency.pop(0)

        msgs = self._generateTweets(call)

        if self.debug:
            msg = " | ".join(msgs)
            log.debug(f"Would have posted: {msg}")
            return

        # Check for a cached tweet, then check if the last tweet was less than the window ago. If the window has expired dereference the cached tweet.
        if (
            self.cachedTime != None
            and self.cachedTime + timedelta(minutes=self.window_minutes)
            <= datetime.now()
        ):
            self.cachedTweet = None

        try:
            if self.cachedTweet != None:
                for msg in msgs:
                    # Every time it posts the new ID gets stored so this works
                    self.cachedTweet = self.api.update_status(msg, self.cachedTweet).id
            else:
                for index, msg in enumerate(msgs):
                    if index == 0:
                        # Since there isn't a cached tweet yet we have to send a non-reply first
                        self.cachedTweet = self.api.update_status(msg).id
                    else:
                        self.cachedTweet = self.api.update_status(
                            msg, self.cachedTweet
                        ).id
            self.cachedTime = datetime.now()
        except tweepy.TweepError as e:
            log.exception(e)

    def _timeString(self, call: dict) -> str:
        """Generates a time code string for a call.
        Args:
            call (dict): The call to get time from.
        Returns:
            str: A timestamp string in I:M:S am/pm format.
        """
        # Get time from the call.
        date = datetime.strptime(call["time"], "%Y-%m-%dT%H:%M:%S.000%z")
        # Fuck I hate how computer time works
        localized = date.replace(tzinfo=pytz.utc).astimezone(self.timezone)
        normalized = self.timezone.normalize(localized)
        return normalized.strftime("%#I:%M:%S %p")

    def _chunk(self, callStrings: list) -> list:
        """Chunks tweets into an acceptable length.

        Chunking. Shamelessly stolen from `SeattleDSA/signal_scanner_bot/twitter.py` :)

        Args:
            call_strings (list): List of strings derived from calls.

        Returns:
            list: A list of tweet strings to post
        """
        tweetList: List[str] = []
        baseIndex = 0

        # Instead of spliting on words I want to split along call lines.
        subTweet: str = ""
        for index in range(len(callStrings)):
            if len(tweetList) == 0:
                subTweet = (
                    ", ".join(callStrings[baseIndex:index]) + " ... " + self.HASHTAGS
                )
            elif index < len(callStrings):
                subTweet = ", ".join(callStrings[baseIndex:index]) + " ..."
            elif index == len(callStrings):
                subTweet = ", ".join(callStrings[baseIndex:index])

            if len(subTweet) > 280 - self.TWEET_PADDING:
                lastIndex = index - 1
                tweetList.append(", ".join(callStrings[baseIndex:lastIndex]) + " ...")
                baseIndex = lastIndex

        tweetList.append(", ".join(callStrings[baseIndex:]))
        listLength = len(tweetList)
        for index in range(len(tweetList)):
            if index == 0:
                tweetList[index] += f" {self.HASHTAGS} {index + 1}/{listLength}"
            else:
                tweetList[index] += f" {index + 1}/{listLength}"

        return tweetList

    def _generateTweets(self, call: dict) -> list:
        callStrings: List[str] = []

        # First, take all of the calls and turn them into strings.
        callStrings.append(self.CALL_TEXT.format(call["len"], self._timeString(call),))

        tweet = ", ".join(callStrings) + " " + self.HASHTAGS
        # If we don't have to chunk we can just leave.
        if len(tweet) <= 280:
            return [tweet]
        else:
            tweetList = self._chunk(callStrings)

        return tweetList


if __name__ == "__main__":
    # Format logging
    logging.basicConfig(
        format="[%(asctime)s - %(name)s - %(lineno)3d][%(levelname)s] %(message)s",
        level=logging.INFO,
    )
    log.info(f"Version {VERSION} of EncryptedConvos")
    bot = Bot()
