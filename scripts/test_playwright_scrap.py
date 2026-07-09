from src.ingestion.sources.bienici_source import BieniciSource
from src.ingestion.sources.leboncoin_source import LeboncoinSource
from src.ingestion.sources.pap_source import PapSource
from src.ingestion.sources.seloger_source import SeLogerSource

sources = {
    "pap": PapSource(),
    "leboncoin": LeboncoinSource(),
    "bienici": BieniciSource(),
    "seloger": SeLogerSource(),
}

sources["seloger"].fetch_html()
