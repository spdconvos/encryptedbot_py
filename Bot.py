import json
import os
from datetime import datetime, timedelta

import pytz
import tweepy

import Scraper
import Set

VERSION = "0.2.4"
print("Version %s of EncryptedConvos" % VERSION)


class Bot:
    """The twitter bot.
    """

    # Consts
    SINGLE_CALL_MSG = (
        "%s second encrypted call at %s. #SeattleProtestComms #ProtestCommsSeattle"
    )
    MULTI_CALL_BASE = "%s #SeattleProtestComms #ProtestCommsSeattle"
    MULTI_CALL_CALL = "%s second encrypted call at %s"
    TIMEZONE = pytz.timezone("US/Pacific")
    WINDOW_M = 5
    BASE_URL = "https://api.openmhz.com/kcers1b/calls/newer?time=%s&filter-type=talkgroup&filter-code=44912,45040,45112,45072,45136"
    # DEBUG URL TO GET A LOT OF API RESPONSES
    # BASE_URL = "https://api.openmhz.com/kcers1b/calls/newer?time=%s&filter-type=group&filter-code=5ed813629818fe0025c8e245"

    def __init__(self) -> None:
        """Initializes the class.
        """
        self.cachedTweet = None
        self.cachedTime = None
        self.scraper = Scraper.Instance(self.BASE_URL)
        self.callThreshold = int(os.getenv("CALL_THRESHOLD", 1))
        self.debug = os.getenv("DEBUG", "true").lower() == "true"

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
        """This kills the c̶r̶a̶b̶  bot.
        """
        self.interval.cancel()
        exit(0)

    def _check(self) -> None:
        """Checks the API and sends a tweet if needed.
        """
        try:
            print("Checking!: %s" % datetime.now())
            json = self.scraper.getJSON()
            try:
                print("Found %s calls." % len(json["calls"]))
                if len(json["calls"]) > 0:
                    self._postTweet(json["calls"])
            except TypeError as e:
                print(e)
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
            if not abs(diff.total_seconds()) >= 1.8e3 and call["len"] >= self.callThreshold:
                filteredCalls.append(call)

        msg = ""
        if len(filteredCalls) == 1:
            msg = self._formatMessage(filteredCalls[0])
        elif len(filteredCalls) > 1:
            msg = self._formatMultiMessage(filteredCalls)
        else:
            # GTFO if there are no calls to post
            return

        if self.debug:
            print("DEBUG MESSAGE:")
            print(msg)
            return

        # Check for a cached tweet, then check if the last tweet was less than the window ago. If the window has expired dereference the cached tweet.
        if (
            self.cachedTime != None
            and self.cachedTime + timedelta(minutes=self.WINDOW_M) <= datetime.now()
        ):
            self.cachedTweet = None

        try:
            if self.cachedTweet != None:
                print("    " + msg)
                self.cachedTweet = self.api.update_status(msg, self.cachedTweet).id
            else:
                print(msg)
                self.cachedTweet = self.api.update_status(msg).id
            self.cachedTime = datetime.now()
        except tweepy.TweepError as e:
            print(e)

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
        localized = date.replace(tzinfo=pytz.utc).astimezone(self.TIMEZONE)
        normalized = self.TIMEZONE.normalize(localized)
        return self.SINGLE_CALL_MSG % (
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
            localized = date.replace(tzinfo=pytz.utc).astimezone(self.TIMEZONE)
            normalized = self.TIMEZONE.normalize(localized)
            callStrings.append(
                self.MULTI_CALL_CALL
                % (call["len"], normalized.strftime("%#I:%M:%S %p"),)
            )

        return self.MULTI_CALL_BASE % ", ".join(callStrings)


if __name__ == "__main__":
    bot = Bot()
