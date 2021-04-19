import logging
from typing import List

import requests
from cachetools import TTLCache


log = logging.getLogger(__name__)
namecache = TTLCache(maxsize=100, ttl=60 * 60 * 12)  # 12 hours


LOOKUP_API = "https://radio-chaser.tech-bloc-sea.dev/radios/get-verbose"


def _getSet(srcList: List[dict]) -> List[str]:
    """Generates a list of unique sources.

    Args:
        srcList (List[dict]): The srcList to process.

    Returns:
        List[str]: Unique source IDs.
    """
    # Magic number 7 baby - add it to the front to match
    # the format stored in radio-chaser
    return list({"7" + src["src"] for src in srcList})


def _scrape(sources: List[str]) -> List[str]:
    """[summary]

    Args:
        sources (List[str]): [description]

    Returns:
        List[str]: [description]
    """
    names: List[str] = []
    to_lookup: List[str] = []
    for source in sources:
        if source in namecache:
            names.append(namecache[source])
        else:
            to_lookup.append(source)
    if to_lookup:
        response = requests.get(LOOKUP_API, params={"radio": to_lookup})
        data = response.json()
        log.debug(f"Data back from API: {data}")
        for source, info in data.items():
            namecache[str(source)] = info
            names.append(info)

    log.debug(f"Names found: {names}")
    return names


def getNames(srcList: List[dict]) -> List[str]:
    sources = _getSet(srcList)
    names = _scrape(sources)
    log.info(f"Found {len(names)}/{len(srcList)} names")
    return names
