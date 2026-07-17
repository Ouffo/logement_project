import base64
import json
import re
from datetime import UTC, datetime
from io import BytesIO

import anthropic
import httpx
import imagehash
from anthropic.types import TextBlock
from PIL import Image

from src.storage.orm_models import RentalListingORM
from src.utils.logger import logger

_client = anthropic.Anthropic()

# Hamming distance below which two images are considered the same photo.
# Calibrated on a real duplicate listing (same apartment, cross-posted on
# two sites with different crops/resolutions): distance 14. Unrelated
# listings measured 26+. 20 sits comfortably between the two.
IMAGE_PHASH_MATCH_THRESHOLD = 20

_PROMPT = (
    "Tu regardes la photo principale d'une annonce de location d'appartement à Paris. "
    "Évalue la qualité visuelle de l'appartement de 0 à 15 points selon ces trois critères :\n"
    "- Luminosité et lumière naturelle (0-5)\n"
    "- Propreté et état général (0-5)\n"
    "- Sentiment d'espace et d'aération (0-5)\n"
    "Réponds uniquement en JSON sans markdown : "
    '{"score": <entier 0-15>, "reason": "<une phrase courte>"}'
)


def compute_image_phash(image_bytes: bytes) -> str | None:
    try:
        return str(imagehash.phash(Image.open(BytesIO(image_bytes))))
    except Exception:
        logger.exception("Failed to compute image phash")
        return None


def backfill_listing_image_phash(listing: RentalListingORM) -> bool:
    """Downloads the listing's image and fills in image_phash only, without
    the Claude scoring call — for listings that already have image_score.
    Returns whether a phash was successfully computed."""
    if not listing.image_url or not listing.image_url.startswith(("http://", "https://")):
        return False

    try:
        r = httpx.get(listing.image_url, timeout=10, follow_redirects=True)
        if r.status_code != 200:
            logger.warning(f"Image fetch failed ({r.status_code}) for {listing.source_id}")
            return False

        listing.image_phash = compute_image_phash(r.content)
        return listing.image_phash is not None

    except Exception:
        logger.exception(f"Failed to backfill image phash for listing {listing.source_id}")
        return False


def score_listing_image(listing: RentalListingORM) -> None:
    listing.image_scored_at = datetime.now(UTC)

    if not listing.image_url or not listing.image_url.startswith(("http://", "https://")):
        listing.image_score = None
        return

    try:
        r = httpx.get(listing.image_url, timeout=10, follow_redirects=True)
        if r.status_code != 200:
            logger.warning(f"Image fetch failed ({r.status_code}) for {listing.source_id}")
            listing.image_score = None
            return

        listing.image_phash = compute_image_phash(r.content)

        media_type = r.headers.get("content-type", "image/jpeg").split(";")[0]
        if media_type not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
            media_type = "image/jpeg"

        image_data = base64.standard_b64encode(r.content).decode("utf-8")

        result = _client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=100,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            },
                        },
                        {"type": "text", "text": _PROMPT},
                    ],
                }
            ],
        )

        block = result.content[0]
        if not isinstance(block, TextBlock):
            listing.image_score = None
            return
        raw = block.text.strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            listing.image_score = None
            return
        data = json.loads(match.group())
        listing.image_score = float(data["score"])
        logger.info(
            f"[{listing.source_id}] image_score={listing.image_score}/15 — {data['reason']}"
        )

    except Exception:
        logger.exception(f"Failed to score image for listing {listing.source_id}")
        listing.image_score = None
