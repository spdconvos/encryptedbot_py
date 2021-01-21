import tweepy, json, pytz, Scraper, Set
from datetime import datetime, timedelta

VERSION = "0.1.5"
print("Version %s of EncryptedConvos" % VERSION)


class Bot:
    """The twitter bot.
    """

    # Consts
    SINGLE_CALL_MSG = "[Automated post] %s second encrypted call at %s. #SeattleProtestComms #ProtestCommsSeattle"
    TIMEZONE = pytz.timezone("US/Pacific")
    WINDOW_M = 5
    BASE_URL = "https://api.openmhz.com/kcers1b/calls/newer?time=%s&filter-type=talkgroup&filter-code=44912,45040,45112,45072,45136"

    def __init__(self) -> None:
        """Initializes the class.
        """
        self.cachedTweet = None
        self.cachedTime = None
        self.scraper = Scraper.Instance(self.BASE_URL)

        with open("./secrets.json") as f:
            keys = json.load(f)
        auth = tweepy.OAuthHandler(
            consumer_key=keys["consumer_key"], consumer_secret=keys["consumer_secret"]
        )
        # If you don't already have an access token, sucks to be you
        auth.set_access_token(keys["access_token_key"], keys["access_token_secret"])
        self.api = tweepy.API(auth)

        self.interval = Set.Interval(30, self.check)

    def kill(self) -> None:
        """This kills the c̶r̶a̶b̶  bot.
        """
        self.interval.cancel()
        exit(0)

    def check(self) -> None:
        """Checks the API and sends a tweet if needed.
        """
        try:
            print("Checking!: %s" % datetime.now())
            json = self.scraper.getJSON()
            try:
                print("Found %s calls." % len(json["calls"]))
                for call in json["calls"]:
                    diff = datetime.now(pytz.utc) - datetime.strptime(
                        call["time"], "%Y-%m-%dT%H:%M:%S.000%z"
                    )
                    if not abs(diff.total_seconds()) >= 3.6e3:
                        self.post_tweet(call)
            except TypeError as e:
                print(e)
        except KeyboardInterrupt as e:
            self.kill()

    def post_tweet(self, call) -> None:
        """Posts a tweet.

        Args:
            call (dict): The call object to post about.
        """
        msg = self.format_message(call)

        # Check for a cached tweet, then check if the last tweet was less than the window ago
        if (
            self.cachedTime != None
            and self.cachedTime + timedelta(minutes=self.WINDOW_M) < datetime.now()
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

    def format_message(self, call) -> str:
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


if __name__ == "__main__":
    bot = Bot()
