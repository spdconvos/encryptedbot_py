import logging, os

from datetime import datetime, timedelta
from typing import List

import tweepy, json, pytz, socketio
from tweepy.error import TweepError

from signal import signal, SIGINT

import RadioIDs

VERSION = "2.1.7"

log = logging.getLogger()


class Bot:
    """The twitter bot."""

    # Consts
    CALL_TEXT = "{} second encrypted call at {}"
    NAMES_TEXT = "#{}: {}"
    HASHTAGS = "#SeattleEncryptedComms"
    TWEET_PADDING = 20
    CONFIG = {
        "filterCode": [44912, 45040, 45112, 45072, 45136],
        "filterType": "talkgroup",
        "filterName": "OpenMHZ",
        "filterStarred": False,
        "shortName": "kcers1b",
    }
    """ # DEBUG CONFIG TO GET A LOT OF API RESPONSES
    CONFIG = {
        "filterCode": "",
        "filterType": "all",
        "filterName": "OpenMHZ",
        "filterStarred": False,
        "shortName": "kcers1b",
    } """

    def __init__(self) -> None:
        """Initializes the class."""
        self.callThreshold = int(os.getenv("CALL_THRESHOLD", 1))
        self.debug = os.getenv("DEBUG", "true").lower() == "true"
        self.reportLatency = os.getenv("REPORT_LATENCY", "false").lower() == "true"
        self.window_minutes = int(os.getenv("WINDOW_M", 5))
        self.timezone = pytz.timezone(os.getenv("TIMEZONE", "US/Pacific"))

        self.cachedTweet: int = None
        self.cachedTime: datetime = None

        self.latency: List[timedelta] = []

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

        # Register interput handler
        signal(SIGINT, self._kill)

    def start(self) -> None:
        """Start the bot.
        """
        self._connectSIO()

    def _connectSIO(self) -> None:
        """Sets up and connects the socket IO client
        """
        self.sio = socketio.Client()

        # Register connect handler
        self.sio.on("connect", self._connectHandler)
        # Register disonnect handler
        self.sio.on("disconnect", self._disconnectHandler)
        # Register message handler because decorators are borked, and further using function names is borked
        self.sio.on("new message", self._callHandler)

        self.sio.connect("https://api.openmhz.com/", namespaces=["/"])
        self.sio.wait()

    def _connectHandler(self) -> None:
        """Connect event handler, sends start packet.
        """
        # Tell socketIO to send us data.
        self.sio.emit("start", self.CONFIG)
        log.info("Connected to socket")

    def _disconnectHandler(self) -> None:
        """Disconnect handler
        """
        log.info("Disconnected")

    def _kill(self, rec, frame) -> None:
        """This kills the c̶r̶a̶b̶  bot."""
        log.info("SIGINT or Ctrl-C hit. Exitting.")
        self.sio.emit("stop")
        self.sio.disconnect()
        exit(0)

    def _callHandler(self, data):
        """Message handler

        Args:
            data (str): The call data in a str
        """
        # See, here's why we needed to pass in our own reference and everything about this hurts me.
        jsonData = json.loads(data)
        self._postTweet(jsonData)

        if self.reportLatency:
            latencySum = sum(self.latency).total_seconds()
            avg = round(latencySum / len(self.latency), 3)
            log.info(f"Average latency for the last 100 calls: {avg} seconds")

    def _postTweet(self, call: dict):
        """Generates and posts a tweet

        Args:
            call (dict): The call to post about
        """
        diff = datetime.now(pytz.utc) - datetime.strptime(
            call["time"], "%Y-%m-%dT%H:%M:%S.000%z"
        )

        # Check for weird old calls
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
            self.cachedTime is not None
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

    def _chunk(self, call: str) -> list:
        """Chunks tweets into an acceptable length.

        Chunking. Shamelessly stolen from `SeattleDSA/signal_scanner_bot/twitter.py` :)

        Args:
            call (str): The call tweet.

        Returns:
            list: A list of tweet strings to post
        """
        words = call.split(" ")
        tweetList: List[str] = []
        baseIndex = 0

        subTweet: str = ""
        for index in range(len(words)):
            if len(tweetList) == 0:
                subTweet = ", ".join(words[baseIndex:index]) + " ... " + self.HASHTAGS
            elif index < len(words):
                subTweet = ", ".join(words[baseIndex:index]) + " ..."
            elif index == len(words):
                subTweet = ", ".join(words[baseIndex:index])

            if len(subTweet) > 280 - self.TWEET_PADDING:
                lastIndex = index - 1
                tweetList.append(", ".join(words[baseIndex:lastIndex]) + " ...")
                baseIndex = lastIndex

        tweetList.append(", ".join(words[baseIndex:]))
        listLength = len(tweetList)
        for index in range(len(tweetList)):
            if index == 0:
                tweetList[index] += f" {self.HASHTAGS} {index + 1}/{listLength}"
            else:
                tweetList[index] += f" {index + 1}/{listLength}"

        return tweetList

    def _generateTweets(self, call: dict) -> list:
        """Generates tweet(s).

        Args:
            call (dict): The call to post about.

        Returns:
            list: A list of strings to send off to Twitter.com
        """

        info = RadioIDs.getNames(call["srcList"])
        log.info(f"{info=}")
        # First, take all of the calls and turn them into strings.
        callString = self.CALL_TEXT.format(call["len"], self._timeString(call),)

        peopleStrings: list[str] = []
        for person in info:
            if person is not None:
                peopleStrings.append(
                    self.NAMES_TEXT.format(person["badge"], person["full_name"],)
                )

        if peopleStrings:
            tweet = "{} ({}) {}".format(
                callString, ",".join(peopleStrings), self.HASHTAGS,
            )
        else:
            tweet = "{} {}".format(callString, self.HASHTAGS,)

        # If we don't have to chunk we can just leave.
        if len(tweet) <= 280:
            return [tweet]
        else:
            tweetList = self._chunk()

        return tweetList


if __name__ == "__main__":
    # Format logging
    bot = Bot()
    level = logging.DEBUG if bot.debug else logging.INFO
    logging.basicConfig(
        format="[%(asctime)s - %(name)s - %(lineno)3d][%(levelname)s] %(message)s",
        level=level,
    )
    log.info(f"Version {VERSION} of EncryptedConvos")
    bot.start()
