import json
import logging
import urllib.error
import urllib.request
from datetime import datetime, timedelta

import pytz


log = logging.getLogger(__name__)


class Instance:
    """A scraping instance that stores the endpoint, and provides a scrape function."""

    def __init__(self, url: str, lookback: float) -> None:
        """Starts the scraper.

        Args:
            url (str): The API endpoint to scrape.
            lookback (float): The amount of seconds to look back.
        """
        self.url = url
        self.lookback = lookback
        self.firstCheck = self.startTimeCache = True
        self.startTime = None
        return

    def getJSON(self) -> dict:
        """Hits the endpoint and returns the result.

        Returns:
            dict: The scraped JSON.
        """
        res = None
        try:
            req = urllib.request.urlopen(self.url.format(self._timestamp()))
            # log.debug(self.BASE_URL.format(self.lastCheck))
            res = json.loads(req.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            log.exception(e)
        return res

    def _timestamp(self) -> str:
        """Generates the current time stamp in the correct format.

        Returns:
            str: The current time stamp in xyyy, where x is the whole number of seconds in unix and yyy are the first three decimal points of the time stamp.
        """
        # There's some delay in the API so you need to delay the timestamp a little.
        # With about 20 minutes of hair pulling "why is the api not returning anything!!!!" frustration I found that 45 seconds was the smallest round-ish number that got returns.
        # We also scrape back 5 minutes to check for long calls.
        time = datetime.now(pytz.utc) - timedelta(seconds=(self.lookback + 45))

        # If it's the first check cache the startup time
        if self.firstCheck:
            self.startTime = datetime.now(pytz.utc)
            self.firstCheck = False

        if self.startTimeCache:
            # If the start up time is later (greater) than the current lookbacked time would be, use the start up time instead.
            if self.startTime > (
                datetime.now(pytz.utc) - timedelta(seconds=(self.lookback + 45))
            ):
                time = self.startTime
            # If it isn't stop checking if it is
            else:
                self.startTimeCache = False

        strArray = str(time.timestamp()).split(".")
        return strArray[0] + strArray[1][:3]
