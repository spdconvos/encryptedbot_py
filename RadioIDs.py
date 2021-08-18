import logging
from typing import List
import requests
from cachetools import TTLCache

log = logging.getLogger(__name__)
namecache: TTLCache = TTLCache(maxsize=100, ttl=12 * 3.6e3)  # 12 hours

LOOKUP_URL = "https://radio-chaser.tech-bloc-sea.dev/radios/get-verbose"


def _getSet(srcList: List[dict]) -> List[str]:
    """Generates a list of unique sources.

    Args:
        srcList (List[dict]): The srcList to process.

    Returns:
        List[str]: Unique source IDs.
    """
    return list({"7" + src["src"] for src in srcList})


def _scrape(sources: List[str]) -> List[str]:
    """Scrapes the api end point and returns a list of names.

    Args:
        sources (List[str]): A list of ID strings from a call.

    Returns:
        List[str]: A list of names gotten from the IDs provided
    """
    names: List[str] = []
    toLookup: List[str] = []
    for source in sources:
        if source in namecache.keys():
            names.append(namecache[source])
        else:
            toLookup.append(source)

    if toLookup:
        response = requests.get(LOOKUP_URL, params={"radio": toLookup})
        data = response.json()
        log.debug(f"Data back from API: {data}")
        for source, info in data.items():
            namecache[str(source)] = info
            names.append(info)
    if names:
        log.info(f"Found names: {names}")

    return names


def getNames(srcList: List[dict]) -> List[str]:
    """Gets the names corresponds to the provided radio IDs.

    Args:
        srcList (List[dict]): List of radio ID entries from the OpenMHZ API.

    Returns:
        List[str]: The list of names that corresponds to the srcList, if such a list exists.
    """
    sources = _getSet(srcList)
    names = _scrape(sources)
    log.info(f"Found {len(names)}/{len(sources)} names")
    return names
