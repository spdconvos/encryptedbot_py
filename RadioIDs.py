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
    """[summary]

    Args:
        sources (List[str]): [description]

    Returns:
        List[str]: [description]
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
            log.info(f"Found names: {names}")

    return names


def getNames(srcList: List[dict]) -> List[str]:
    sources = _getSet(srcList)
    names = _scrape(sources)
    log.info(f"Found {len(names)}/{len(sources)} names")
    return names
