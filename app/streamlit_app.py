import hashlib
import re
import sys
from pathlib import Path

import imagehash
import pandas as pd
import streamlit as st
from sqlalchemy import or_

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from src.scoring.image_scorer import IMAGE_PHASH_MATCH_THRESHOLD  # noqa: E402
from src.storage.db import SessionLocal  # noqa: E402
from src.storage.orm_models import RentalListingORM  # noqa: E402

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

    /* Posted date */
    .listing-posted {
        font-size: 0.75rem;
        color: #9ca3af;
        margin: 0.15rem 0;
    }

    /* Hide streamlit link button default style */
    .stLinkButton a {
        display: none;
    }

    /* Mobile: stack image above info instead of side-by-side — the fixed
       240px image otherwise leaves too little width for price/specs/CTA
       on a phone in portrait. */
    @media (max-width: 520px) {
        .listing-card {
            flex-direction: column;
        }
        .listing-img {
            width: 100%;
            min-width: 100%;
            height: 200px;
        }
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
            .filter(RentalListingORM.is_active)
            .filter(~RentalListingORM.title.ilike("%cherche%"))
            .filter(
                or_(
                    RentalListingORM.description.is_(None),
                    ~RentalListingORM.description.ilike("%cherche%"),
                )
            )
            .order_by(RentalListingORM.relevance_score.desc().nullslast())
            .all()
        )
        return pd.DataFrame(
            [
                {
                    "source": listing.source,
                    "title": listing.title,
                    "is_rental": listing.is_rental,
                    "city": listing.city,
                    "postal_code": listing.postal_code,
                    "price_eur": listing.price_eur,
                    "surface_m2": listing.surface_m2,
                    "rooms": listing.rooms,
                    "bedrooms": listing.bedrooms,
                    "floor": listing.floor,
                    "is_top_floor": listing.is_top_floor,
                    "furnished": listing.furnished,
                    "parking": listing.parking,
                    "quiet": listing.quiet,
                    "score": listing.relevance_score,
                    "url": listing.url,
                    "image_url": listing.image_url,
                    "image_phash": listing.image_phash,
                    "energy_class": listing.energy_class,
                    "construction_year": listing.construction_year,
                    "posted_at": listing.posted_at,
                    "description": listing.description,
                    "collected_at": listing.collected_at,
                    "last_seen_at": listing.last_seen_at,
                }
                for listing in listings
            ]
        )
    finally:
        session.close()


def _description_fingerprint(text) -> str | None:
    if not text or not isinstance(text, str):
        return None
    normalized = re.sub(r"\s+", " ", text.lower().strip())[:200]
    return hashlib.md5(normalized.encode()).hexdigest()


def _parse_phash(value):
    if isinstance(value, str):
        try:
            return imagehash.hex_to_hash(value)
        except ValueError:
            return None
    return None


def _is_same_listing(candidate: dict, other: dict) -> bool:
    # postal_code and rooms already match by construction — see the
    # grouping in _deduplicate — so only price/surface/photo are left.
    price_a, price_b = candidate["price_eur"], other["price_eur"]
    if pd.isna(price_a) or pd.isna(price_b) or abs(price_a - price_b) > 1000:
        return False

    surface_a, surface_b = candidate["surface_m2"], other["surface_m2"]
    if pd.isna(surface_a) or pd.isna(surface_b) or abs(surface_a - surface_b) > 1:
        return False

    # Same core facts (location/price/surface/rooms) alone isn't proof it's
    # the same unit — confirm with the photo, falling back to the
    # description text for listings without a usable image hash.
    hash_a, hash_b = candidate["phash"], other["phash"]
    if hash_a is not None and hash_b is not None:
        if (hash_a - hash_b) <= IMAGE_PHASH_MATCH_THRESHOLD:
            return True

    fp_a, fp_b = candidate["fingerprint"], other["fingerprint"]
    return fp_a is not None and fp_a == fp_b


def _deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("collected_at", ascending=False).reset_index(drop=True)

    # Precompute the phash object and description fingerprint once per row
    # instead of re-parsing them on every pairwise comparison, and bucket by
    # (postal_code, rooms) — a hard requirement for a match anyway — so each
    # row is only ever compared against real candidates, not the whole set.
    records = df.to_dict("records")
    for record in records:
        record["phash"] = _parse_phash(record.get("image_phash"))
        record["fingerprint"] = _description_fingerprint(record.get("description"))

    groups: dict[tuple, list[int]] = {}
    kept_indices: list[int] = []

    for idx, record in enumerate(records):
        group_key = (record.get("postal_code"), record.get("rooms"))
        candidates = groups.setdefault(group_key, [])

        if any(_is_same_listing(record, records[c]) for c in candidates):
            continue

        kept_indices.append(idx)
        candidates.append(idx)

    return df.loc[kept_indices]


@st.cache_data(ttl=300)
def get_mode_listings(is_rental_mode: bool) -> tuple[pd.DataFrame, "pd.Timestamp | None"]:
    df = load_listings()
    df = df[df["is_rental"] == is_rental_mode].reset_index(drop=True)

    if df.empty:
        return df, None

    last_update = df["last_seen_at"].dropna().max()

    df = _deduplicate(df)
    df = df.sort_values("score", ascending=False, na_position="last").drop(
        columns=["description", "collected_at", "last_seen_at"]
    )
    return df, last_update


_ENERGY_CLASSES = ["A", "B", "C", "D", "E", "F", "G"]


def render_energy_label(energy_class: str) -> str:
    ec = energy_class.upper()
    if ec not in _ENERGY_CLASSES:
        return ""
    boxes = "".join(
        f'<span class="energy-box energy-{c}{"  active" if c == ec else ""}">{c}</span>'
        for c in _ENERGY_CLASSES
    )
    return f"""
    <div class="energy-label">
    <span class="energy-label-title">
    Classe énergie</span>{boxes}</div>
    """


def _display_source(source: str) -> str:
    return source.removesuffix("_sale") if isinstance(source, str) else source


def _arrondissement_label(postal_code: str) -> str:
    if isinstance(postal_code, str) and postal_code.startswith("75") and len(postal_code) == 5:
        return f"{int(postal_code[3:])}e"
    return postal_code


def _resolve_toggle_all_selection(selection: list[str], prev: list[str]) -> list[str]:
    added = [v for v in selection if v not in prev]

    if "Tous" in added:
        # "Tous" was just checked alongside others -> it wins, drop the rest.
        return ["Tous"]
    if selection and "Tous" in selection:
        # A specific option was just checked while "Tous" was still on -> a
        # specific pick always overrides "Tous".
        return [v for v in selection if v != "Tous"]
    if not selection:
        # Nothing left checked -> fall back to "Tous" rather than an empty,
        # confusing filter state.
        return ["Tous"]
    return selection


def _make_toggle_all_on_change(key: str):
    def _on_change():
        selection = st.session_state.get(key, [])
        prev = st.session_state.get(f"_{key}_prev", ["Tous"])
        resolved = _resolve_toggle_all_selection(selection, prev)
        st.session_state[key] = resolved
        st.session_state[f"_{key}_prev"] = resolved

    return _on_change


_on_arrondissement_change = _make_toggle_all_on_change("arr_filter")
_on_floor_change = _make_toggle_all_on_change("floor_filter")


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

    source = _display_source(row.get("source") or "")
    is_rental_row = row.get("is_rental", True)
    price = row.get("price_eur")
    surface = row.get("surface_m2")
    rooms = row.get("rooms")
    city = row.get("city") or "Paris"
    postal = row.get("postal_code") or ""
    furnished = row.get("furnished")
    parking = row.get("parking")
    quiet = row.get("quiet")
    score = row.get("score")
    url = row.get("url") or "#"
    energy_class = row.get("energy_class")
    construction_year = row.get("construction_year")
    posted_at = row.get("posted_at")

    price_str = f"{int(price):,}".replace(",", " ") + " €" if pd.notna(price) else "— €"
    price_suffix = " <span>/ mois</span>" if is_rental_row else ""
    surface_str = f"{int(surface)} m²" if pd.notna(surface) else "— m²"
    rooms_str = (
        f"{int(rooms)} pièce{'s' if rooms and rooms > 1 else ''}" if pd.notna(rooms) else "—"
    )

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

    posted_html = ""
    if posted_at is not None and pd.notna(posted_at):
        try:
            date_str = pd.Timestamp(posted_at).strftime("%d/%m/%Y")
            posted_html = f'<div class="listing-posted">Publiée le {date_str}</div>'
        except Exception:
            pass

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
                <div class="listing-price">{price_str}{price_suffix}</div>
                <div class="listing-specs">
                    {surface_str}
                    <span class="sep">·</span>
                    {rooms_str}
                </div>
                <div class="listing-location">📍 {city} {postal}</div>
                {posted_html}
                <div class="listing-tags">{tags_html}</div>{energy_html}
            </div>
            <div class="listing-footer">
                <a class="cta-link" href="{url}" target="_blank">Voir l'annonce →</a>{score_html}
            </div>
        </div>
    </div>
    """
    return "\n".join(line for line in card.splitlines() if line.strip())


# ── Header ──────────────────────────────────────────────────────────────────
_h1, _h2 = st.columns([3, 2])
with _h1:
    st.markdown(
        '<div class="app-header"><div class="app-logo">bien<span>paris</span></div></div>',
        unsafe_allow_html=True,
    )

# ── Data ─────────────────────────────────────────────────────────────────────
_all_listings = load_listings()

if _all_listings.empty:
    st.warning("Aucune annonce en base pour l'instant.")
    st.stop()

# ── Mode toggle (location / achat) ────────────────────────────────────────────
mode = st.radio("Mode", ["Location", "Achat"], horizontal=True, label_visibility="collapsed")
is_rental_mode = mode == "Location"

with st.spinner("Chargement des annonces..."):
    df, _last_update = get_mode_listings(is_rental_mode)

if df.empty:
    st.info(f"Aucune annonce en {'location' if is_rental_mode else 'achat'} pour l'instant.")
    st.stop()

# ── Last update timestamp ─────────────────────────────────────────────────────
with _h2:
    if pd.notna(_last_update):
        _last_update_str = pd.Timestamp(_last_update).strftime("%d/%m/%Y à %H:%M")
        st.markdown(
            f"""
            <div style="text-align:right;color:#9ca3af;font-size:0.8rem;padding-top:1.1rem;">
            Dernière mise à jour : {_last_update_str}</div>
            """,
            unsafe_allow_html=True,
        )

# ── Filters ──────────────────────────────────────────────────────────────────
with st.container():
    c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
    with c1:
        if is_rental_mode:
            max_price = st.slider("Budget max (€/mois)", 0, 2000, 1200, 50)
        else:
            max_price = st.slider("Budget max (€)", 0, 1_000_000, 650_000, 10_000)
    with c2:
        if is_rental_mode:
            min_surface = st.slider("Surface min (m²)", 0, 100, 25, 5)
        else:
            min_surface = st.slider("Surface min (m²)", 0, 200, 50, 5)
    with c3:
        source_opts = ["Toutes"] + sorted({_display_source(s) for s in df["source"].dropna()})
        source = st.selectbox("Source", source_opts)
    label_to_postal = {_arrondissement_label(pc): pc for pc in df["postal_code"].dropna().unique()}
    with c4:
        if is_rental_mode:
            city_opts = ["Tous"] + sorted(df["city"].dropna().unique().tolist())
            city_filter = st.selectbox("Lieu", city_opts)
            arrondissement_filter = ["Tous"]
        else:
            arr_opts = ["Tous"] + sorted(
                label_to_postal, key=lambda label: int(re.sub(r"\D", "", label) or 0)
            )
            arrondissement_filter = st.multiselect(
                "Arrondissement",
                arr_opts,
                default=["Tous"],
                key="arr_filter",
                on_change=_on_arrondissement_change,
            )
            city_filter = "Tous"

    c5, c6, c7, c8 = st.columns([2, 2, 2, 2])
    with c5:
        energy_opts = ["Toutes"] + _ENERGY_CLASSES
        energy_max = st.selectbox(
            "Classe énergie (max acceptable)",
            energy_opts,
            help="Ex. : choisir D affiche les classes A, B, C et D",
        )
        include_unknown_energy = st.checkbox("Inclure annonces sans DPE", value=True)
    with c6:
        year_min = st.slider("Année de construction min", 1800, 2026, 1800, 10)
        include_unknown_year = st.checkbox("Inclure annonces sans année", value=True)
    with c7:
        sort_by_date = st.toggle("Afficher par ordre récent", value=False)
    with c8:
        if is_rental_mode:
            floor_filter = ["Tous"]
        else:
            floor_values = sorted({int(f) for f in df["floor"].dropna().unique()})
            floor_opts = ["Tous", "Dernier étage"] + [str(v) for v in floor_values]
            floor_filter = st.multiselect(
                "Étage",
                floor_opts,
                default=["Tous"],
                key="floor_filter",
                on_change=_on_floor_change,
            )

# ── Filtering ────────────────────────────────────────────────────────────────
filtered = df[(df["price_eur"] <= max_price) & (df["surface_m2"] >= min_surface)]
if source != "Toutes":
    filtered = filtered[filtered["source"].apply(_display_source) == source]

if city_filter != "Tous":
    filtered = filtered[filtered["city"] == city_filter]

if not is_rental_mode and arrondissement_filter and "Tous" not in arrondissement_filter:
    selected_postals = [
        label_to_postal[label] for label in arrondissement_filter if label in label_to_postal
    ]
    filtered = filtered[filtered["postal_code"].isin(selected_postals)]

if not is_rental_mode and floor_filter and "Tous" not in floor_filter:
    mask = pd.Series(False, index=filtered.index)
    if "Dernier étage" in floor_filter:
        mask = mask | filtered["is_top_floor"].fillna(False)
    numeric_floors = [int(v) for v in floor_filter if v != "Dernier étage"]
    if numeric_floors:
        mask = mask | filtered["floor"].isin(numeric_floors)
    filtered = filtered[mask]

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

# ── Sort ─────────────────────────────────────────────────────────────────────
if sort_by_date:
    filtered = filtered.sort_values("posted_at", ascending=False, na_position="last")

# ── Results ──────────────────────────────────────────────────────────────────
st.markdown(
    f"""
    <div class="results-count">
    <strong>{len(filtered)}</strong> 
    annonce{"s" if len(filtered) != 1 else ""} 
    trouvée{"s" if len(filtered) != 1 else ""}
    </div>
    """,
    unsafe_allow_html=True,
)

for _, row in filtered.iterrows():
    st.markdown(render_card(row), unsafe_allow_html=True)
