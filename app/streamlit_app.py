import pandas as pd
import streamlit as st

from src.storage.db import SessionLocal
from src.storage.orm_models import RentalListingORM


st.set_page_config(
    page_title="Logements Paris",
    layout="wide",
)

st.title("🏠 Logements pertinents")


def load_listings() -> pd.DataFrame:
    session = SessionLocal()

    try:
        listings = (
            session.query(RentalListingORM)
            .order_by(RentalListingORM.relevance_score.desc().nullslast())
            .all()
        )

        return pd.DataFrame(
            [
                {
                    "source": l.source,
                    "title": l.title,
                    "price_eur": l.price_eur,
                    "surface_m2": l.surface_m2,
                    "rooms": l.rooms,
                    "bedrooms": l.bedrooms,
                    "furnished": l.furnished,
                    "parking": l.parking,
                    "quiet": l.quiet,
                    "score": l.relevance_score,
                    "url": l.url,
                }
                for l in listings
            ]
        )

    finally:
        session.close()


df = load_listings()

if df.empty:
    st.warning("Aucune annonce en base pour l’instant.")
    st.stop()

col1, col2, col3 = st.columns(3)

with col1:
    max_price = st.slider(
        "Budget max",
        min_value=0,
        max_value=2000,
        value=1200,
        step=50,
    )

with col2:
    min_surface = st.slider(
        "Surface min",
        min_value=0,
        max_value=100,
        value=25,
        step=5,
    )

with col3:
    source = st.selectbox(
        "Source",
        ["Toutes"] + sorted(df["source"].dropna().unique().tolist()),
    )

filtered = df[
    (df["price_eur"] <= max_price)
    & (df["surface_m2"] >= min_surface)
]

if source != "Toutes":
    filtered = filtered[filtered["source"] == source]

st.subheader(f"{len(filtered)} annonces trouvées")

for _, row in filtered.iterrows():
    with st.container(border=True):
        st.markdown(f"### {row['title']}")

        st.write(
            f"**{row['price_eur']} €** · "
            f"{row['surface_m2']} m² · "
            f"{row['rooms'] or '?'} pièce(s)"
        )

        st.write(
            f"Source: `{row['source']}` · "
            f"Score: `{row['score']}`"
        )

        tags = []

        if row["furnished"]:
            tags.append("Meublé")
        if row["parking"]:
            tags.append("Parking")
        if row["quiet"]:
            tags.append("Calme")

        if tags:
            st.caption(" · ".join(tags))

        st.link_button("Voir l’annonce", row["url"])