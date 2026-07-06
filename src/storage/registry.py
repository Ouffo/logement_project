from src.ingestion.sources.pap_source import PapSource
from src.ingestion.sources.leboncoin_source import LeboncoinSource
from src.ingestion.sources.bienici_source import BieniciSource
from src.ingestion.sources.seloger_source import SeLogerSource

def _lock_id(name: str) -> int:
    import hashlib
    return int(hashlib.sha256(f"pipeline:{name}".encode()).hexdigest()[:15], 16) % (2 ** 62)

SOURCE_REGISTRY = {
    "pap": PapSource,
    "leboncoin": LeboncoinSource,
    "bienici": BieniciSource,
    "seloger": SeLogerSource,
}

FETCH_SOURCE_LOCK_IDS = {
    "fetch_"+name: _lock_id("fetch_"+name)
    for name in SOURCE_REGISTRY
}

EXTRACT_SAVE_SOURCE_LOCK_IDS = {
    "extract_save_"+name: _lock_id("extract_save_"+name)
    for name in SOURCE_REGISTRY
}

ENRICH_LOCK_IDS = {
    "enrich_"+name: _lock_id("enrich_"+name)
    for name in SOURCE_REGISTRY
}


IMAGE_SCORING_LOCK_ID = _lock_id("image_scoring")
FINAL_SCORING_LOCK_ID = _lock_id("final_scoring")
