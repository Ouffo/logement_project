from src.processing.parsers import (parse_price, parse_surface)
from src.utils.logger import logger

def demo_parsing():
    price_str = "1,250 €"
    surface_str = "35 m²"

    price = parse_price(price_str)
    surface = parse_surface(surface_str)

    logger.info(f"Parsed price: {price} EUR")
    logger.info(f"Parsed surface: {surface} m²")

if __name__ == "__main__":
    demo_parsing()