from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

import pandas as pd
import streamlit as st
from src.storage.db import SessionLocal
from src.storage.orm_models import RentalListingORM


st.set_page_config(
    page_title="Logements Paris",
    layout="wide",
    page_icon="🏠",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Hide default streamlit header padding */
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 1100px;
    }

    /* Header */
    .app-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 1.5rem;
    }
    .app-logo {
        font-size: 2rem;
        font-weight: 800;
        color: #5c24a6;
        letter-spacing: -1px;
    }
    .app-logo span {
        color: #e84d8a;
    }

    /* Filters bar */
    .filter-bar {
        background: #f7f7f8;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin-bottom: 1.2rem;
    }

    /* Results count */
    .results-count {
        font-size: 0.9rem;
        color: #6b7280;
        margin-bottom: 1rem;
        font-weight: 500;
    }
    .results-count strong {
        color: #111827;
    }

    /* Listing card */
    .listing-card {
        display: flex;
        background: #ffffff;
        border-radius: 12px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08), 0 0 0 1px rgba(0,0,0,0.05);
        overflow: hidden;
        margin-bottom: 1rem;
        transition: box-shadow 0.2s;
        min-height: 160px;
    }
    .listing-card:hover {
        box-shadow: 0 4px 16px rgba(0,0,0,0.13), 0 0 0 1px rgba(0,0,0,0.07);
    }

    /* Image side */
    .listing-img {
        width: 240px;
        min-width: 240px;
        background: #e5e7eb;
        overflow: hidden;
        position: relative;
    }
    .listing-img img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
    }
    .listing-img-placeholder {
        width: 100%;
        height: 100%;
        min-height: 160px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #9ca3af;
        font-size: 2.5rem;
        background: #f3f4f6;
    }

    /* Source badge on image */
    .source-badge {
        position: absolute;
        top: 8px;
        left: 8px;
        background: rgba(0,0,0,0.55);
        color: #fff;
        font-size: 0.7rem;
        font-weight: 600;
        padding: 2px 7px;
        border-radius: 4px;
        letter-spacing: 0.3px;
        text-transform: uppercase;
    }

    /* Info side */
    .listing-info {
        flex: 1;
        padding: 1rem 1.2rem;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        gap: 0.3rem;
    }

    .listing-price {
        font-size: 1.55rem;
        font-weight: 700;
        color: #111827;
        line-height: 1.1;
    }
    .listing-price span {
        font-size: 1rem;
        font-weight: 500;
        color: #6b7280;
    }

    .listing-specs {
        font-size: 0.92rem;
        color: #374151;
        font-weight: 500;
        margin: 0.15rem 0;
    }
    .listing-specs .sep {
        color: #d1d5db;
        margin: 0 6px;
    }

    .listing-location {
        font-size: 0.83rem;
        color: #6b7280;
        margin-bottom: 0.4rem;
    }

    /* Tags */
    .listing-tags {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-top: 0.3rem;
    }
    .tag {
        font-size: 0.75rem;
        font-weight: 500;
        padding: 3px 9px;
        border-radius: 20px;
        display: inline-block;
    }
    .tag-furnished  { background: #ede9fe; color: #6d28d9; }
    .tag-parking    { background: #dbeafe; color: #1d4ed8; }
    .tag-quiet      { background: #d1fae5; color: #065f46; }

    /* Score badge */
    .score-badge {
        display: inline-block;
        background: #fef3c7;
        color: #92400e;
        font-size: 0.75rem;
        font-weight: 700;
        padding: 3px 9px;
        border-radius: 20px;
        margin-left: auto;
    }
    .score-badge.high { background: #d1fae5; color: #065f46; }
    .score-badge.mid  { background: #fef3c7; color: #92400e; }
    .score-badge.low  { background: #fee2e2; color: #991b1b; }

    /* CTA */
    .listing-footer {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-top: 0.5rem;
    }
    .cta-link {
        display: inline-block;
        background: #5c24a6;
        color: #fff !important;
        font-size: 0.82rem;
        font-weight: 600;
        padding: 7px 16px;
        border-radius: 8px;
        text-decoration: none !important;
    }
    .cta-link:hover {
        background: #4a1d84;
    }

    /* Energy class rating */
    .energy-label {
        display: flex;
        align-items: center;
        gap: 2px;
        margin-top: 0.3rem;
    }
    .energy-label-title {
        font-size: 0.72rem;
        color: #6b7280;
        font-weight: 500;
        margin-right: 4px;
        white-space: nowrap;
    }
    .energy-box {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 20px;
        height: 20px;
        border-radius: 3px;
        font-size: 0.68rem;
        font-weight: 700;
        color: rgba(255,255,255,0.75);
        opacity: 0.38;
    }
    .energy-box.active {
        width: 26px;
        height: 26px;
        font-size: 0.82rem;
        color: #fff;
        opacity: 1;
        box-shadow: 0 0 0 2px #fff, 0 0 0 3.5px rgba(0,0,0,0.25);
    }
    .energy-A  { background: #00A550; }
    .energy-B  { background: #51B747; }
    .energy-C  { background: #BAD434; color: rgba(0,0,0,0.6); }
    .energy-C.active { color: rgba(0,0,0,0.8); }
    .energy-D  { background: #FFF200; color: rgba(0,0,0,0.6); }
    .energy-D.active { color: rgba(0,0,0,0.8); }
    .energy-E  { background: #F7A600; }
    .energy-F  { background: #F15A29; }
    .energy-G  { background: #EE1D23; }

    /* Construction year badge */
    .tag-year { background: #f3f4f6; color: #374151; }

    /* Hide streamlit link button default style */
    .stLinkButton a {
        display: none;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=300)
def load_listings() -> pd.DataFrame:
    session = SessionLocal()
    try:
        listings = (
            session.query(RentalListingORM)
            .filter(RentalListingORM.is_active == True)
            .order_by(RentalListingORM.relevance_score.desc().nullslast())
            .all()
        )
        return pd.DataFrame(
            [
                {
                    "source": l.source,
                    "title": l.title,
                    "postal_code": l.postal_code,
                    "price_eur": l.price_eur,
                    "surface_m2": l.surface_m2,
                    "rooms": l.rooms,
                    "bedrooms": l.bedrooms,
                    "furnished": l.furnished,
                    "parking": l.parking,
                    "quiet": l.quiet,
                    "score": l.relevance_score,
                    "url": l.url,
                    "image_url": l.image_url,
                    "energy_class": l.energy_class,
                    "construction_year": l.construction_year,
                }
                for l in listings
            ]
        )
    finally:
        session.close()


_ENERGY_CLASSES = ["A", "B", "C", "D", "E", "F", "G"]


def render_energy_label(energy_class: str) -> str:
    ec = energy_class.upper()
    if ec not in _ENERGY_CLASSES:
        return ""
    boxes = "".join(
        f'<span class="energy-box energy-{c}{"  active" if c == ec else ""}">{c}</span>'
        for c in _ENERGY_CLASSES
    )
    return f'<div class="energy-label"><span class="energy-label-title">Classe énergie</span>{boxes}</div>'


def score_class(score):
    if score is None:
        return "mid"
    if score >= 7:
        return "high"
    if score >= 4:
        return "mid"
    return "low"


def render_card(row):
    image_url = row.get("image_url")
    has_image = pd.notna(image_url) and isinstance(image_url, str) and image_url.startswith("http")

    source = row.get("source") or ""
    price = row.get("price_eur")
    surface = row.get("surface_m2")
    rooms = row.get("rooms")
    postal = row.get("postal_code") or ""
    furnished = row.get("furnished")
    parking = row.get("parking")
    quiet = row.get("quiet")
    score = row.get("score")
    url = row.get("url") or "#"
    energy_class = row.get("energy_class")
    construction_year = row.get("construction_year")

    price_str = f"{int(price)} €" if pd.notna(price) else "— €"
    surface_str = f"{int(surface)} m²" if pd.notna(surface) else "— m²"
    rooms_str = f"{int(rooms)} pièce{'s' if rooms and rooms > 1 else ''}" if pd.notna(rooms) else "—"

    tags_html = ""
    if furnished:
        tags_html += '<span class="tag tag-furnished">Meublé</span>'
    if parking:
        tags_html += '<span class="tag tag-parking">Parking</span>'
    if quiet:
        tags_html += '<span class="tag tag-quiet">Calme</span>'
    if construction_year and pd.notna(construction_year):
        tags_html += f'<span class="tag tag-year">Construit en {int(construction_year)}</span>'

    energy_html = ""
    if energy_class and pd.notna(energy_class) and isinstance(energy_class, str):
        energy_html = render_energy_label(energy_class)

    score_html = ""
    if pd.notna(score):
        sc = score_class(score)
        score_html = f'<span class="score-badge {sc}">Score {score}/100</span>'

    if has_image:
        img_html = f'<img src="{image_url}" alt="photo" />'
    else:
        img_html = '<div class="listing-img-placeholder">🏠</div>'

    card = f"""
    <div class="listing-card">
        <div class="listing-img">
            {img_html}
            <span class="source-badge">{source}</span>
        </div>
        <div class="listing-info">
            <div>
                <div class="listing-price">{price_str} <span>/ mois</span></div>
                <div class="listing-specs">
                    {surface_str}
                    <span class="sep">·</span>
                    {rooms_str}
                </div>
                <div class="listing-location">📍 Paris {postal}</div>
                <div class="listing-tags">{tags_html}</div>{energy_html}
            </div>
            <div class="listing-footer">
                <a class="cta-link" href="{url}" target="_blank">Voir l'annonce →</a>{score_html}
            </div>
        </div>
    </div>
    """
    return card


# ── Header ──────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="app-header"><div class="app-logo">bien<span>paris</span></div></div>',
    unsafe_allow_html=True,
)

# ── Data ─────────────────────────────────────────────────────────────────────
df = load_listings()

if df.empty:
    st.warning("Aucune annonce en base pour l'instant.")
    st.stop()

# ── Filters ──────────────────────────────────────────────────────────────────
with st.container():
    c1, c2, c3 = st.columns([2, 2, 2])
    with c1:
        max_price = st.slider("Budget max (€/mois)", 0, 2000, 1200, 50)
    with c2:
        min_surface = st.slider("Surface min (m²)", 0, 100, 25, 5)
    with c3:
        source_opts = ["Toutes"] + sorted(df["source"].dropna().unique().tolist())
        source = st.selectbox("Source", source_opts)

    c4, c5, c6 = st.columns([2, 2, 2])
    with c4:
        energy_opts = ["Toutes"] + _ENERGY_CLASSES
        energy_max = st.selectbox(
            "Classe énergie (max acceptable)",
            energy_opts,
            help="Ex. : choisir D affiche les classes A, B, C et D",
        )
        include_unknown_energy = st.checkbox("Inclure annonces sans DPE", value=True)
    with c5:
        year_min = st.slider("Année de construction min", 1800, 2026, 1800, 10)
        include_unknown_year = st.checkbox("Inclure annonces sans année", value=True)

# ── Filtering ────────────────────────────────────────────────────────────────
filtered = df[(df["price_eur"] <= max_price) & (df["surface_m2"] >= min_surface)]
if source != "Toutes":
    filtered = filtered[filtered["source"] == source]

if energy_max != "Toutes":
    allowed = _ENERGY_CLASSES[: _ENERGY_CLASSES.index(energy_max) + 1]
    mask = filtered["energy_class"].isin(allowed)
    if include_unknown_energy:
        mask = mask | filtered["energy_class"].isna()
    filtered = filtered[mask]

if year_min > 1800:
    mask = (filtered["construction_year"] >= year_min).fillna(False)
    if include_unknown_year:
        mask = mask | filtered["construction_year"].isna()
    filtered = filtered[mask]

# ── Results ──────────────────────────────────────────────────────────────────
st.markdown(
    f'<div class="results-count"><strong>{len(filtered)}</strong> annonce{"s" if len(filtered) != 1 else ""} trouvée{"s" if len(filtered) != 1 else ""}</div>',
    unsafe_allow_html=True,
)

for _, row in filtered.iterrows():
    st.markdown(render_card(row), unsafe_allow_html=True)
