import base64
import json
import re

import anthropic
import httpx
from anthropic.types import TextBlock
from datetime import datetime, UTC

from src.storage.orm_models import RentalListingORM
from src.utils.logger import logger

_client = anthropic.Anthropic()

_PROMPT = (
    "Tu regardes la photo principale d'une annonce de location d'appartement à Paris. "
    "Évalue la qualité visuelle de l'appartement de 0 à 15 points selon ces trois critères :\n"
    "- Luminosité et lumière naturelle (0-5)\n"
    "- Propreté et état général (0-5)\n"
    "- Sentiment d'espace et d'aération (0-5)\n"
    "Réponds uniquement en JSON sans markdown : "
    '{\"score\": <entier 0-15>, \"reason\": \"<une phrase courte>\"}'
)


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

        media_type = r.headers.get("content-type", "image/jpeg").split(";")[0]
        if media_type not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
            media_type = "image/jpeg"

        image_data = base64.standard_b64encode(r.content).decode("utf-8")

        result = _client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=100,
            messages=[{
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
            }],
        )

        block = result.content[0]
        if not isinstance(block, TextBlock):
            listing.image_score = None
            return
        raw = block.text.strip()
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not match:
            listing.image_score = None
            return
        data = json.loads(match.group())
        listing.image_score = float(data["score"])
        logger.info(f"[{listing.source_id}] image_score={listing.image_score}/15 — {data['reason']}")

    except Exception:
        logger.exception(f"Failed to score image for listing {listing.source_id}")
        listing.image_score = None
