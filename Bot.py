import json
import logging
import os
from datetime import datetime, timedelta

import pytz
import tweepy

import Scraper
import Set

VERSION = "0.3.0"

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
        self.cachedTweet = None
        self.cachedTime = None
        self.scraper = Scraper.Instance(self.BASE_URL)

        self.callThreshold = int(os.getenv("CALL_THRESHOLD", 1))
        self.debug = os.getenv("DEBUG", "true").lower() == "true"
        self.window_minutes = int(os.getenv("WINDOW_M", 5))
        self.timezone = pytz.timezone(os.getenv("TIMEZONE", "US/Pacific"))

        if self.debug:
            log.setLevel(logging.DEBUG)

        with open("./secrets.json") as f:
            keys = json.load(f)
        auth = tweepy.OAuthHandler(
            consumer_key=keys["consumer_key"], consumer_secret=keys["consumer_secret"]
        )
        # If you don't already have an access token, sucks to be you
        auth.set_access_token(keys["access_token_key"], keys["access_token_secret"])
        self.api = tweepy.API(auth)

        self.interval = Set.Interval(30, self._check)

    def _kill(self) -> None:
        """This kills the c̶r̶a̶b̶  bot."""
        self.interval.cancel()
        exit(0)

    def _check(self) -> None:
        """Checks the API and sends a tweet if needed."""
        try:
            log.info(f"Checking!: {datetime.now()}")
            json = self.scraper.getJSON()
            try:
                log.info(f"Found {len(json['calls'])} calls.")
                if len(json["calls"]) > 0:
                    self._postTweet(json["calls"])
            except TypeError as e:
                log.exception(e)
        except KeyboardInterrupt as e:
            self._kill()

    def _postTweet(self, calls) -> None:
        """Posts a tweet.

        Args:
            calls (list): The call objects to post about.
        """

        # Filter to make sure that calls are actually recent. There can be a weird behavior of the API returning multiple hours old calls all at once.
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
                log.info("    " + msg)
                self.cachedTweet = self.api.update_status(msg, self.cachedTweet).id
            else:
                log.info(msg)
                self.cachedTweet = self.api.update_status(msg).id
            self.cachedTime = datetime.now()
        except tweepy.TweepError as e:
            log.exception(e)

    def _formatMessage(self, call) -> str:
        """Generate a tweet message.

        Args:
            call (dict): The call to tweet about.

        Returns:
            str: The tweet message.
        """
        # Get time from the call.
        date = datetime.strptime(call["time"], "%Y-%m-%dT%H:%M:%S.000%z")
        # Fuck I hate how computer time works
        localized = date.replace(tzinfo=pytz.utc).astimezone(self.timezone)
        normalized = self.timezone.normalize(localized)
        return self.SINGLE_CALL_MSG.format(
            call["len"],
            normalized.strftime("%#I:%M:%S %p"),
        )

    def _formatMultiMessage(self, calls) -> str:
        """Generate a tweet body for multiple calls in the same scan.

        Args:
            calls (list): The list of calls to format

        Returns:
            str: The tweet body for the list of calls.
        """
        callStrings = []
        for call in calls:
            # Get time from the call.
            date = datetime.strptime(call["time"], "%Y-%m-%dT%H:%M:%S.000%z")
            # Fuck I hate how computer time works
            localized = date.replace(tzinfo=pytz.utc).astimezone(self.timezone)
            normalized = self.timezone.normalize(localized)
            callStrings.append(
                self.MULTI_CALL_CALL.format(
                    call["len"], normalized.strftime("%#I:%M:%S %p")
                )
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
