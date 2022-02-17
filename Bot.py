import logging, os
from datetime import datetime, timedelta
from typing import List
import tweepy, json, pytz, socketio, tomli
from tweepy.errors import Unauthorized as TweepyUnauthorized
from signal import signal, SIGINT

import RadioIDs

VERSION = "3.0.0"

log = logging.getLogger()


class Bot:
    """The twitter bot."""

    def __init__(self) -> None:
        """Initializes the class."""

        # Get config
        try:
            with open("config.toml", "r") as f:
                self.config = tomli.load(f)

                # Check for necessary config keys
                for key in ["radio", "twitter"]:
                    if key not in self.config:
                        log.error(f"Missing {key} in config")
                        exit(1)

                # Fill in defaults
                self.config["general"]["timezone"] = (
                    self.config["general"]["timezone"]
                    if "timezone" in self.config["general"]
                    else "US/Pacific"
                )
                self.config["general"]["window_minutes"] = (
                    self.config["general"]["window_minutes"]
                    if "window_minutes" in self.config["general"]
                    else 5
                )
                self.config["general"]["call_threshold"] = (
                    self.config["general"]["call_threshold"]
                    if "call_threshold" in self.config["general"]
                    else 1
                )
                debug = (
                    self.config["general"]["debug"]
                    if "debug" in self.config["general"]
                    else True
                )
        except FileNotFoundError:
            log.error("No config file found. Exiting.")
            exit(1)
        except tomli.TOMLDecodeError as e:
            log.error(f"Error parsing config file: {e}")
            exit(1)

        self._cachedTweet: int = None
        self._cachedTime: datetime = None

        if not self.debug:
            # Does not need to be saved for later.
            # If the keys aren't in env this will still run.
            auth = tweepy.OAuthHandler(
                os.getenv("CONSUMER_KEY", ""), os.getenv("CONSUMER_SECRET", "")
            )
            auth.set_access_token(
                os.getenv("ACCESS_TOKEN_KEY", ""), os.getenv("ACCESS_TOKEN_SECRET", "")
            )
            self._api = tweepy.API(auth)
            # Test the authentication. This will gracefully fail if the keys aren't present.
            try:
                self._api.verify_credentials()
            except TweepyUnauthorized as e:
                log.error(f"No keys or bad keys: {e}")
                exit(1)

        # Register interput handler
        signal(SIGINT, self._kill)

    def start(self) -> None:
        """Start the bot."""
        self._connectSIO()

    def _connectSIO(self) -> None:
        """Sets up and connects the socket IO client"""
        self._sio = socketio.Client()

        # Register connect handler
        self._sio.on("connect", self._connectHandler)
        # Register disconnect handler
        self._sio.on("disconnect", self._disconnectHandler)
        # Register message handler because decorators are borked, and further using function names is borked
        self._sio.on("new message", self._callHandler)

        self._sio.connect("https://api.openmhz.com/", namespaces=["/"])
        self._sio.wait()

    def _connectHandler(self) -> None:
        """Connect event handler, sends start packet."""
        # Tell socketIO to send us data.
        self._sio.emit("start", self.config["radio"])
        log.info("Connected to socket")

    def _disconnectHandler(self) -> None:
        """Disconnect handler"""
        log.info("Disconnected")

    def _kill(self, rec, frame) -> None:
        """This kills the c̶r̶a̶b̶  bot."""
        log.info("SIGINT or Ctrl-C hit. Exitting.")
        self._sio.emit("stop")
        self._sio.disconnect()
        exit(0)

    def _callHandler(self, data) -> None:
        """Message handler

        Args:
            data (str): The call data in a str
        """
        jsonData = json.loads(data)
        self._postTweet(jsonData)

    def _postTweet(self, call: dict) -> None:
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
        elif call["len"] < self.config["general"]["call_threshold"]:
            log.debug(
                f"Call of size {call['len']} below threshold ({self.config['general']['call_threshold']})"
            )
            return

        msgs = self._generateTweets(call)

        if self.debug:
            msg = " | ".join(msgs)
            log.debug(f"Would have posted: {msg}")
            return

        # Check for a cached tweet, then check if the last tweet was less than the window ago. If the window has expired dereference the cached tweet.
        if (
            self._cachedTime is not None
            and self._cachedTime
            + timedelta(minutes=self.config["general"]["window_minutes"])
            <= datetime.now()
        ):
            self._cachedTweet = None

        try:
            if self._cachedTweet != None:
                for msg in msgs:
                    # Every time it posts the new ID gets stored so this works
                    self._cachedTweet = self._api.update_status(
                        msg, in_reply_to_status_id=self._cachedTweet
                    ).id
            else:
                for index, msg in enumerate(msgs):
                    if index == 0:
                        # Since there isn't a cached tweet yet we have to send a non-reply first
                        self._cachedTweet = self._api.update_status(msg).id
                    else:
                        self._cachedTweet = self._api.update_status(
                            msg, in_reply_to_status_id=self._cachedTweet
                        ).id
            self._cachedTime = datetime.now()
        except tweepy.TweepyException as e:
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
        localized = date.replace(tzinfo=pytz.utc).astimezone(
            self.config["general"]["timezone"]
        )
        normalized = self.config["general"]["timezone"].normalize(localized)
        return normalized.strftime("%#I:%M:%S %p")

    def _chunk(self, call: str) -> List[str]:
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
                subTweet = (
                    ", ".join(words[baseIndex:index])
                    + " ... "
                    + self.config["tweet"]["hashtags"]
                )
            elif index < len(words):
                subTweet = ", ".join(words[baseIndex:index]) + " ..."
            elif index == len(words):
                subTweet = ", ".join(words[baseIndex:index])

            if len(subTweet) > 280 - self.config["tweet"]["padding"]:
                lastIndex = index - 1
                tweetList.append(", ".join(words[baseIndex:lastIndex]) + " ...")
                baseIndex = lastIndex

        tweetList.append(", ".join(words[baseIndex:]))
        listLength = len(tweetList)
        for index in range(len(tweetList)):
            if index == 0:
                tweetList[
                    index
                ] += f' {self.config["tweet"]["hashtags"]} {index + 1}/{listLength}'
            else:
                tweetList[index] += f" {index + 1}/{listLength}"

        return tweetList

    def _generateTweets(self, call: dict) -> List[str]:
        """Generates tweet(s).

        Args:
            call (dict): The call to post about.

        Returns:
            list: A list of strings to send off to Twitter.com
        """

        info = RadioIDs.getNames(call["srcList"])
        log.info(f"{info=}")
        # First, take all of the calls and turn them into strings.
        callString = self.config["tweet"]["call"].format(
            call["len"],
            self._timeString(call),
        )

        peopleStrings: List[str] = []
        for person in info:
            if person is not None:
                peopleStrings.append(
                    self.config["tweet"]["names"].format(
                        person["badge"],
                        person["full_name"],
                    )
                )

        if peopleStrings:
            tweet = "{} ({}) {}".format(
                callString,
                "; ".join(peopleStrings),
                self.config["tweet"]["hashtags"],
            )
        else:
            tweet = "{} {}".format(
                callString,
                self.config["tweet"]["hashtags"],
            )

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
