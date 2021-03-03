import logging
import os

from datetime import datetime, timedelta
import pytz

import tweepy
from tweepy.error import TweepError

from cachetools import TTLCache

import Scraper
import Set

VERSION = "1.1.5"

log = logging.getLogger()


class Bot:
    """The twitter bot."""

    # Consts
    SINGLE_CALL_MSG = (
        "{} second encrypted call at {}. #SeattleProtestComms #ProtestCommsSeattle"
    )
    MULTI_CALL_BASE = "{} #SeattleProtestComms #ProtestCommsSeattle"
    MULTI_CALL_CALL = "{} second encrypted call at {}"
    BASE_URL = "https://api.openmhz.com/kcers1b/calls/newer?time={}&filter-type=talkgroup&filter-code=44912,45040,45112,45072,45136"
    # DEBUG URL TO GET A LOT OF API RESPONSES
    # BASE_URL = "https://api.openmhz.com/kcers1b/calls/newer?time={}&filter-type=group&filter-code=5ed813629818fe0025c8e245"

    def __init__(self) -> None:
        """Initializes the class."""
        self.callThreshold = int(os.getenv("CALL_THRESHOLD", 1))
        self.debug = os.getenv("DEBUG", "true").lower() == "true"
        self.window_minutes = int(os.getenv("WINDOW_M", 5))
        self.timezone = pytz.timezone(os.getenv("TIMEZONE", "US/Pacific"))
        # The actual look back is the length of this lookback + lag compensation. For example: 300+45=345 seconds
        self.lookback = os.getenv("LOOKBACK_S", 300)

        self.cachedTweet = None
        self.cachedTime = None
        self.cache = TTLCache(maxsize=100, ttl=self.lookback)
        self.scraper = Scraper.Instance(self.BASE_URL, self.lookback)

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

    def _getUniqueCalls(self, calls) -> list:
        """Filters the return from the scraper to only tweet unique calls.

        Works by checking if the cache already has that call ID.

        Args:
            calls (list): The complete list of calls scraped.

        Returns:
            list: A filtered list of calls.
        """
        res = []
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
            json = self.scraper.getJSON()
            calls = self._getUniqueCalls(json["calls"])
            try:
                log.info(f"Found {len(calls)} calls.")
                if len(calls) > 0:
                    self._postTweet(calls)
            except TypeError as e:
                log.exception(e)
        except KeyboardInterrupt as e:
            # Literally impossible to hit which might be an issue? Catching keyboard interrupt could happen in its own thread or something but that sounds complicated 👉👈
            self._kill()

    def _postTweet(self, calls) -> None:
        """Posts a tweet.

        Args:
            calls (list): The call objects to post about.
        """

        # Filter to make sure that calls are actually recent. There can be a weird behavior of the API returning multiple hours old calls all at once. Also filters for calls under the length threshold.
        filteredCalls = []
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

        if len(filteredCalls) == 1:
            msg = self._formatMessage(filteredCalls[0])
        elif len(filteredCalls) > 1:
            msg = self._formatMultiMessage(filteredCalls)
        else:
            # GTFO if there are no calls to post
            return

        if self.debug:
            log.debug(msg)
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
                self.cachedTweet = self.api.update_status(msg, self.cachedTweet).id
            else:
                self.cachedTweet = self.api.update_status(msg).id
            self.cachedTime = datetime.now()
        except tweepy.TweepError as e:
            log.exception(e)

    def _timeString(self, call) -> str:
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

    def _formatMessage(self, call) -> str:
        """Generate a tweet message.

        Args:
            call (dict): The call to tweet about.

        Returns:
            str: The tweet message.
        """

        return self.SINGLE_CALL_MSG.format(call["len"], self._timeString(call),)

    def _formatMultiMessage(self, calls) -> str:
        """Generate a tweet body for multiple calls in the same scan.

        Args:
            calls (list): The list of calls to format

        Returns:
            str: The tweet body for the list of calls.
        """
        callStrings = []
        for call in calls:
            callStrings.append(
                self.MULTI_CALL_CALL.format(call["len"], self._timeString(call),)
            )

        return self.MULTI_CALL_BASE.format(", ".join(callStrings))


if __name__ == "__main__":
    # Format logging
    logging.basicConfig(
        format="[%(asctime)s - %(name)s - %(lineno)3d][%(levelname)s] %(message)s",
        level=logging.INFO,
    )
    log.info(f"Version {VERSION} of EncryptedConvos")
    bot = Bot()
