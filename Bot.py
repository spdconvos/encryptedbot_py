import logging
import os

from datetime import datetime, timedelta
from typing import List
import pytz

import tweepy
from tweepy.error import TweepError

from cachetools import TTLCache

import Scraper
import Set

VERSION = "1.3.2"

log = logging.getLogger()


class Bot:
    """The twitter bot."""

    # Consts
    CALL_TEXT = "{} second encrypted call at {}"
    HASHTAGS = "#SeattleProtestComms #ProtestCommsSeattle"

    BASE_URL = "https://api.openmhz.com/kcers1b/calls/newer?time={}&filter-type=talkgroup&filter-code=44912,45040,45112,45072,45136"
    # DEBUG URL TO GET A LOT OF API RESPONSES
    # BASE_URL = "https://api.openmhz.com/kcers1b/calls/newer?time={}&filter-type=group&filter-code=5ed813629818fe0025c8e245"

    def __init__(self) -> None:
        """Initializes the class."""
        self.callThreshold = int(os.getenv("CALL_THRESHOLD", 1))
        self.debug = os.getenv("DEBUG", "true").lower() == "true"
        self.reportLatency = os.getenv("REPORT_LATENCY", "false").lower() == "true"
        self.window_minutes = int(os.getenv("WINDOW_M", 5))
        self.timezone = pytz.timezone(os.getenv("TIMEZONE", "US/Pacific"))
        # The actual look back is the length of this lookback + lag compensation. For example: 300+45=345 seconds
        self.lookback = os.getenv("LOOKBACK_S", 300)

        self.cachedTweet: int = None
        self.cachedTime: datetime = None
        self.cache = TTLCache(maxsize=100, ttl=self.lookback)
        self.scraper = Scraper.Instance(self.BASE_URL, self.lookback)

        self.latency = [timedelta(seconds=0)]

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

        self.interval = Set.Interval(30, self._check)

    def _kill(self) -> None:
        """This kills the c̶r̶a̶b̶  bot."""
        self.interval.cancel()
        exit(0)

    def _getUniqueCalls(self, calls: dict) -> list:
        """Filters the return from the scraper to only tweet unique calls.
        Works by checking if the cache already has that call ID.
        Args:
            calls (list): The complete list of calls scraped.
        Returns:
            list: A filtered list of calls.
        """
        res: List[dict] = []
        for call in calls:
            # If the call is already in the cache skip.
            if call["_id"] in self.cache.keys():
                continue
            # If it isn't, cache it and return it.
            else:
                # Might want to actually store somthing? Who knows.
                self.cache.update({call["_id"]: 0})
                res.append(call)
        return res

    def _check(self) -> None:
        """Checks the API and sends a tweet if needed."""
        try:
            log.info(f"Checking!: {datetime.now()}")
            try:
                json = self.scraper.getJSON()
                calls = self._getUniqueCalls(json["calls"])
                log.info(f"Found {len(calls)} calls.")
                if len(calls) > 0:
                    self._postTweet(calls)
            except TypeError as e:
                if json == None:
                    # We already have an error message from the scraper
                    return
                log.exception(e)
                return
        except KeyboardInterrupt as e:
            # Literally impossible to hit which might be an issue? Catching keyboard interrupt could happen in its own thread or something but that sounds complicated 👉👈
            self._kill()

        if self.reportLatency:
            sum = sum(self.latency).total_seconds()
            avg = round(sum / len(self.latency), 3)
            log.info(f"Average latency for the last 100 calls: {avg} seconds")

    def _postTweet(self, calls: list) -> None:
        """Posts a tweet.
        Args:
            calls (list): The call objects to post about.
        """

        # Filter to make sure that calls are actually recent. There can be a weird behavior of the API returning multiple hours old calls all at once. Also filters for calls under the length threshold.
        filteredCalls: List[dict] = []
        for call in calls:
            diff = datetime.now(pytz.utc) - datetime.strptime(
                call["time"], "%Y-%m-%dT%H:%M:%S.000%z"
            )
            if not abs(diff.total_seconds()) >= 1.8e3:
                if call["len"] < self.callThreshold:
                    log.debug(
                        f"Call of size {call['len']} below threshold ({self.callThreshold})"
                    )
                    continue
                filteredCalls.append(call)

                if self.reportLatency:
                    # Store latency
                    self.latency.append(diff)
                    if len(self.latency) > 100:
                        self.latency.pop(0)

        if len(filteredCalls) >= 1:
            msgs = self._formatMessage(filteredCalls)
        else:
            # GTFO if there are no calls to post
            return

        if self.debug:
            log.debug(f"Would have posted: {msgs}")
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

    def _formatMessage(self, calls) -> list:
        """Generates tweet messages.
        Args:
            call (list): The calls to tweet about.
        Returns:
            list: The tweet messages, hopefully right around the character limit.
        """
        msgs = []
        temp_msg = ""
        # This feels really clunky. There's gotta be a better way to chunk.
        for call in calls:
            temp_msg += (
                self.CALL_TEXT.format(call["len"], self._timeString(call),) + ", "
            )
            # Check for a range of lengths, this could go horribly wrong if the message goes over 280 characters but idk how to do this better.
            if (len(temp_msg) + len(self.HASHTAGS)) >= 260 and (
                len(temp_msg) + len(self.HASHTAGS)
            ) <= 280:
                temp_msg = temp_msg[:-2] + " " + self.HASHTAGS
                msgs.append(temp_msg)
                temp_msg = ""

        return msgs


if __name__ == "__main__":
    # Format logging
    logging.basicConfig(
        format="[%(asctime)s - %(name)s - %(lineno)3d][%(levelname)s] %(message)s",
        level=logging.INFO,
    )
    log.info(f"Version {VERSION} of EncryptedConvos")
    bot = Bot()
