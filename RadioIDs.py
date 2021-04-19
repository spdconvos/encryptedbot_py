import logging
from typing import Dict, List

log = logging.getLogger(__name__)
namecache: Dict[str, str] = {}


def _getSet(srcList: List[dict]) -> List[str]:
    """Generates a list of unique sources.

    Args:
        srcList (List[dict]): The srcList to process.

    Returns:
        List[str]: Unique source IDs.
    """
    return list({src["src"] for src in srcList})


def _scrape(sources: List[str]) -> List[str]:
    """[summary]

    Args:
        sources (List[str]): [description]

    Returns:
        List[str]: [description]
    """
    names: List[str] = []
    for source in sources:
        if source in namecache.keys():
            names.append(namecache[source])
        else:
            # API stuff here, in progress. Even cache none so the API isn't battered
            name = None
            namecache[source] = name
            names.append(name)
    return [name for name in names if name is not None]


def getNames(srcList: List[dict]) -> List[str]:
    sources = _getSet(srcList)
    names = _scrape(sources)
    log.info(f"Found {len(names)}/{len(srcList)} names")
    return names
