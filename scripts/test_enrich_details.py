from src.storage.repository import get_listings_to_enrich, enrich_listings
from src.storage.db import SessionLocal
from src.ingestion.sources.pap_source import PapSource
from src.ingestion.sources.bienici_source import BieniciSource
from src.ingestion.sources.leboncoin_source import LeboncoinSource



def demo_enrich_details():
    sources = {
        "pap": PapSource(),
        "leboncoin": LeboncoinSource(),
        "bienici" : BieniciSource(),
    }

    
    session = SessionLocal()

    try:
        listings_to_enrich = get_listings_to_enrich(
            session=session,
            source_name=sources["bienici"].name,
        )

        print(f"number of listing to enrich = {len(listings_to_enrich)}")

        enrich_listings(sources["bienici"], listings_to_enrich)

        session.commit()
    
    except Exception:
        session.rollback()
        raise

    finally:
        session.close()

if __name__ == "__main__":
    demo_enrich_details()