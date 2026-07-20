from src.ingestion.sources.bienici_source import BieniciSaleSource, BieniciSource
from src.ingestion.sources.century_source import CenturySaleSource, CenturySource
from src.ingestion.sources.leboncoin_source import LeboncoinSource
from src.ingestion.sources.maison_et_appartement_source import (
    MaisonEtAppartementSaleSource,
    MaisonEtAppartementSource,
)
from src.ingestion.sources.pap_source import PapSaleSource, PapSource
from src.ingestion.sources.seloger_source import SeLogerSaleSource, SeLogerSource


def _lock_id(name: str) -> int:
    import hashlib

    return int(hashlib.sha256(f"pipeline:{name}".encode()).hexdigest()[:15], 16) % (2**62)


SOURCE_REGISTRY = {
    "pap": PapSource,
    "leboncoin": LeboncoinSource,
    "bienici": BieniciSource,
    "seloger": SeLogerSource,
    "bienici_sale": BieniciSaleSource,
    "pap_sale": PapSaleSource,
    "seloger_sale": SeLogerSaleSource,
    "century": CenturySource,
    "century_sale": CenturySaleSource,
    "maison_et_appartement": MaisonEtAppartementSource,
    "maison_et_appartement_sale": MaisonEtAppartementSaleSource,
}

FETCH_SOURCE_LOCK_IDS = {"fetch_" + name: _lock_id("fetch_" + name) for name in SOURCE_REGISTRY}

EXTRACT_SAVE_SOURCE_LOCK_IDS = {
    "extract_save_" + name: _lock_id("extract_save_" + name) for name in SOURCE_REGISTRY
}

ENRICH_LOCK_IDS = {"enrich_" + name: _lock_id("enrich_" + name) for name in SOURCE_REGISTRY}


IMAGE_SCORING_LOCK_ID = _lock_id("image_scoring")
FINAL_SCORING_LOCK_ID = _lock_id("final_scoring")
PHASH_BACKFILL_LOCK_ID = _lock_id("phash_backfill")
