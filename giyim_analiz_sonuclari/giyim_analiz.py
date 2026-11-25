
import json
from io import BytesIO
from datetime import datetime
from pathlib import Path

import requests
import pandas as pd
import streamlit as st


# =========================================================
# AYARLAR
# =========================================================

SOURCE_URL = (
    "https://raw.githubusercontent.com/"
    "arturayupov/womens-fashion-catalog-open-data/"
    "main/data/products.json"
)

OUTPUT_DIR = Path("giyim_analiz_sonuclari")
OUTPUT_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 GiyimAnaliz/1.0"
}


# =========================================================
# DEĞER TEMİZLEME
# =========================================================

def clean_value(value):

    if value is None:
        return None

    if isinstance(value, dict):

        for key in [
            "name",
            "title",
            "label",
            "value",
            "displayName",
            "category",
            "brand"
        ]:
            if key in value:
                result = clean_value(value[key])

                if result:
                    return result

        return json.dumps(
            value,
            ensure_ascii=False
        )

    if isinstance(value, list):

        values = [
            clean_value(x)
            for x in value
        ]

        return ", ".join(
            str(x) for x in values if x is not None
        )

    return value


def get_value(data, *keys):

    for key in keys:

        value = data.get(key)

        if value is not None and value != "":
            return value

    return None


def parse_price(value):

    if value is None:
        return None

    if isinstance(value, dict):
        value = get_value(
            value,
            "amount",
            "value",
            "price"
        )

    if isinstance(value, list):
        return None

    try:
        return float(
            str(value).replace(",", ".").replace("$", "").strip()
        )
    except (ValueError, TypeError):
        return None


# =========================================================
# VERİ İNDİRME
# =========================================================

@st.cache_data(ttl=3600, show_spinner=False)
def download_catalog():

    response = requests.get(
        SOURCE_URL,
        headers=HEADERS,
        timeout=90
    )

    response.raise_for_status()

    return response.json()


# =========================================================
# JSON VERİSİNİ TABLOYA DÖNÜŞTÜR
# =========================================================

def normalize_catalog(raw):

    if isinstance(raw, dict):

        products = raw.get(
            "products",
            raw.get("data", [])
        )

    else:
        products = raw

    if not isinstance(products, list):
        raise ValueError(
            "Veri kaynağından ürün listesi alınamadı."
        )

    rows = []

    for product in products:

        if not isinstance(product, dict):
            continue

        product_id = get_value(
            product,
            "id",
            "product_id"
        )

        title = get_value(
            product,
            "title",
            "name",
            "product_name"
        )

        brand = get_value(
            product,
            "vendor",
            "brand",
            "manufacturer"
        )

        category = get_value(
            product,
            "category",
            "product_type",
            "type"
        )

        product_url = get_value(
            product,
            "url",
            "product_url"
        )

        minimum = get_value(
            product,
            "price_min_usd",
            "price_min",
            "price"
        )

        maximum = get_value(
            product,
            "price_max_usd",
            "price_max"
        )

        rating = get_value(
            product,
            "review_rating",
            "rating"
        )

        review_count = get_value(
            product,
            "review_count",
            "reviews_count"
        )

        variants = product.get(
            "variants",
            []
        )

        if isinstance(variants, dict):
            variants = list(variants.values())

        if not isinstance(variants, list):
            variants = []

        # VARYANTLI ÜRÜNLER

        if variants:

            for variant in variants:

                if not isinstance(variant, dict):
                    continue

                variant_price = get_value(
                    variant,
                    "price_usd",
                    "price",
                    "sellingPrice"
                )

                if variant_price is None:
                    variant_price = minimum

                rows.append({

                    "UrunID": clean_value(product_id),

                    "UrunAdi": clean_value(title),

                    "Marka": clean_value(brand),

                    "Kategori": clean_value(category),

                    "Varyant": clean_value(
                        get_value(
                            variant,
                            "variant_title",
                            "title",
                            "name"
                        )
                    ),

                    "UrunKodu": clean_value(
                        get_value(
                            variant,
                            "sku",
                            "barcode"
                        )
                    ),

                    "Renk": clean_value(
                        get_value(variant, "color")
                    ),

                    "Beden": clean_value(
                        get_value(variant, "size")
                    ),

                    "Fiyat_USD": parse_price(
                        variant_price
                    ),

                    "Min_Fiyat_USD": parse_price(minimum),

                    "Max_Fiyat_USD": parse_price(maximum),

                    "Stokta_Mi": clean_value(
                        get_value(
                            variant,
                            "in_stock",
                            "available"
                        )
                    ),

                    "Puan": parse_price(rating),

                    "Yorum_Sayisi": parse_price(review_count),

                    "Urun_URL": clean_value(product_url)

                })

        # VARYANT BULUNMAYAN ÜRÜNLER

        else:

            rows.append({

                "UrunID": clean_value(product_id),

                "UrunAdi": clean_value(title),

                "Marka": clean_value(brand),

                "Kategori": clean_value(category),

                "Varyant": None,

                "UrunKodu": clean_value(
                    get_value(product, "sku")
                ),

                "Renk": None,

                "Beden": None,

                "Fiyat_USD": parse_price(minimum),

                "Min_Fiyat_USD": parse_price(minimum),

                "Max_Fiyat_USD": parse_price(maximum),

                "Stokta_Mi": None,

                "Puan": parse_price(rating),

                "Yorum_Sayisi": parse_price(review_count),

                "Urun_URL": clean_value(product_url)

            })

    df = pd.DataFrame(rows)

    if df.empty:
        raise ValueError("Ürün kaydı bulunamadı.")

    # Bütün nesne değerlerini temizle

    for col in df.columns:
        df[col] = df[col].apply(clean_value)

    # Sayısal sütunlar

    numeric_columns = [
        "Fiyat_USD",
        "Min_Fiyat_USD",
        "Max_Fiyat_USD",
        "Puan",
        "Yorum_Sayisi"
    ]

    for col in numeric_columns:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    # Eksik metinleri standartlaştır

    text_columns = [
        "Marka",
        "Kategori",
        "UrunAdi",
        "UrunKodu",
        "Renk",
        "Beden"
    ]

    for col in text_columns:

        df[col] = (
            df[col]
            .fillna("Belirtilmemiş")
            .astype(str)
        )

    df["Veri_Cekim_Tarihi"] = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    return df


# =========================================================
# FİYAT ANALİZİ
# =========================================================

def create_pivots(df):

    valid = df.dropna(
        subset=["Fiyat_USD"]
    ).copy()

    if valid.empty:
        return {}

    pivots = {}

    # MARKA ANALİZİ

    pivots["Marka_Analizi"] = (
        valid.groupby(
            "Marka",
            dropna=False
        )
        .agg(
            Urun_Sayisi=("UrunID", "nunique"),
            Kayit_Sayisi=("Fiyat_USD", "count"),
            Ortalama_Fiyat=("Fiyat_USD", "mean"),
            Minimum_Fiyat=("Fiyat_USD", "min"),
            Maksimum_Fiyat=("Fiyat_USD", "max")
        )
        .reset_index()
    )

    # KATEGORİ ANALİZİ

    pivots["Kategori_Analizi"] = (
        valid.groupby(
            "Kategori",
            dropna=False
        )
        .agg(
            Urun_Sayisi=("UrunID", "nunique"),
            Kayit_Sayisi=("Fiyat_USD", "count"),
            Ortalama_Fiyat=("Fiyat_USD", "mean"),
            Minimum_Fiyat=("Fiyat_USD", "min"),
            Maksimum_Fiyat=("Fiyat_USD", "max")
        )
        .reset_index()
    )

    # ÜRÜN ANALİZİ

    pivots["Urun_Analizi"] = (
        valid.groupby(
            ["UrunAdi", "Marka"],
            dropna=False
        )
        .agg(
            Ortalama_Fiyat=("Fiyat_USD", "mean"),
            Minimum_Fiyat=("Fiyat_USD", "min"),
            Maksimum_Fiyat=("Fiyat_USD", "max"),
            Varyant_Sayisi=("UrunKodu", "count")
        )
        .reset_index()
    )

    # MARKA - KATEGORİ PIVOT

    pivots["Kategori_Marka"] = pd.pivot_table(
        valid,
        index="Kategori",
        columns="Marka",
        values="Fiyat_USD",
        aggfunc="mean"
    )

    # RENK ANALİZİ

    pivots["Renk_Analizi"] = (
        valid.groupby(
            "Renk",
            dropna=False
        )
        .agg(
            Urun_Sayisi=("UrunID", "nunique"),
            Ortalama_Fiyat=("Fiyat_USD", "mean")
        )
        .reset_index()
    )

    return pivots


# =========================================================
# EXCEL OLUŞTUR
# =========================================================

def create_excel(df, pivots):

    buffer = BytesIO()

    with pd.ExcelWriter(
        buffer,
        engine="openpyxl"
    ) as writer:

        df.to_excel(
            writer,
            sheet_name="Urun_Verileri",
            index=False
        )

        for name, table in pivots.items():

            table.to_excel(
                writer,
                sheet_name=name[:31]
            )

        valid_prices = df["Fiyat_USD"].dropna()

        summary = pd.DataFrame({

            "Bilgi": [
                "Toplam kayıt",
                "Fiyatı bulunan kayıt",
                "Fiyatı bulunmayan kayıt",
                "Marka sayısı",
                "Kategori sayısı",
                "Ortalama fiyat USD",
                "En düşük fiyat USD",
                "En yüksek fiyat USD",
                "Veri çekim tarihi",
                "Veri kaynağı"
            ],

            "Deger": [

                len(df),

                df["Fiyat_USD"].notna().sum(),

                df["Fiyat_USD"].isna().sum(),

                df["Marka"].nunique(),

                df["Kategori"].nunique(),

                valid_prices.mean() if not valid_prices.empty else None,

                valid_prices.min() if not valid_prices.empty else None,

                valid_prices.max() if not valid_prices.empty else None,

                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

                SOURCE_URL

            ]

        })

        summary.to_excel(
            writer,
            sheet_name="Genel_Ozet",
            index=False
        )

    buffer.seek(0)

    return buffer.getvalue()


# =========================================================
# STREAMLIT
# =========================================================

st.set_page_config(
    page_title="Giyim Büyük Veri Analizi",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Giyim Sektörü Büyük Veri Analiz Sistemi")

st.write(
    "Açık moda kataloğundan ürün kayıtlarını indirir, "
    "fiyatları analiz eder ve Excel PivotTable dosyaları oluşturur."
)

st.caption(
    "Kaynak: Livostyle açık moda kataloğu | Para birimi: USD"
)

if st.button(
    "İnternetten Ürünleri İndir",
    type="primary"
):

    try:

        with st.spinner("Ürün kataloğu indiriliyor..."):

            raw = download_catalog()

            df = normalize_catalog(raw)

        st.session_state["giyim_df"] = df

        st.success(
            f"{len(df):,} ürün/varyant kaydı alındı."
        )

    except Exception as error:

        st.error(
            f"Veri indirme hatası: {error}"
        )


# =========================================================
# ANALİZ EKRANI
# =========================================================

if "giyim_df" in st.session_state:

    df = st.session_state["giyim_df"].copy()

    st.divider()

    st.subheader("Genel Durum")

    valid_prices = df["Fiyat_USD"].dropna()

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Toplam kayıt",
        f"{len(df):,}"
    )

    c2.metric(
        "Marka sayısı",
        f"{df['Marka'].nunique():,}"
    )

    c3.metric(
        "Kategori sayısı",
        f"{df['Kategori'].nunique():,}"
    )

    c4.metric(
        "Ortalama fiyat",
        f"${valid_prices.mean():,.2f}"
        if not valid_prices.empty
        else "Veri yok"
    )

    st.divider()

    st.subheader("Ürün Filtreleme")

    brands = sorted(
        df["Marka"].dropna().astype(str).unique().tolist()
    )

    categories = sorted(
        df["Kategori"].dropna().astype(str).unique().tolist()
    )

    selected_brands = st.multiselect(
        "Marka seç",
        brands,
        default=brands
    )

    selected_categories = st.multiselect(
        "Kategori seç",
        categories,
        default=categories
    )

    filtered = df[
        df["Marka"].isin(selected_brands)
        & df["Kategori"].isin(selected_categories)
    ].copy()

    st.write(
        f"Filtrelenmiş kayıt sayısı: {len(filtered):,}"
    )

    st.dataframe(
        filtered,
        use_container_width=True,
        height=400
    )

    st.divider()

    st.subheader("PivotTable Analizleri")

    pivots = create_pivots(filtered)

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Marka",
        "Kategori",
        "Ürün",
        "Renk",
        "Grafikler"
    ])

    with tab1:

        if "Marka_Analizi" in pivots:

            st.dataframe(
                pivots["Marka_Analizi"],
                use_container_width=True
            )

        else:
            st.info("Marka analizi için fiyat verisi yok.")

    with tab2:

        if "Kategori_Analizi" in pivots:

            st.dataframe(
                pivots["Kategori_Analizi"],
                use_container_width=True
            )

        else:
            st.info("Kategori analizi için fiyat verisi yok.")

    with tab3:

        if "Urun_Analizi" in pivots:

            st.dataframe(
                pivots["Urun_Analizi"],
                use_container_width=True
            )

        else:
            st.info("Ürün analizi için fiyat verisi yok.")

    with tab4:

        if "Renk_Analizi" in pivots:

            st.dataframe(
                pivots["Renk_Analizi"],
                use_container_width=True
            )

        else:
            st.info("Renk analizi için fiyat verisi yok.")

    with tab5:

        if not filtered.empty:

            chart_data = (
                filtered.dropna(
                    subset=["Fiyat_USD"]
                )
                .groupby("Kategori")["Fiyat_USD"]
                .mean()
                .sort_values(ascending=False)
            )

            if not chart_data.empty:
                st.bar_chart(chart_data)

            else:
                st.info("Grafik için fiyat verisi bulunamadı.")

    st.divider()

    st.subheader("CSV ve Excel Çıktıları")

    csv_data = filtered.to_csv(
        index=False
    ).encode("utf-8-sig")

    st.download_button(
        "CSV İndir",
        csv_data,
        "giyim_urun_verileri.csv",
        "text/csv"
    )

    excel_data = create_excel(
        filtered,
        pivots
    )

    st.download_button(
        "Pivot Analizli Excel İndir",
        excel_data,
        "giyim_pivot_analizi.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    if st.button("Bilgisayara Kaydet"):

        csv_path = OUTPUT_DIR / "giyim_urun_verileri.csv"

        filtered.to_csv(
            csv_path,
            index=False,
            encoding="utf-8-sig"
        )

        excel_path = OUTPUT_DIR / "giyim_pivot_analizi.xlsx"

        excel_path.write_bytes(excel_data)

        st.success(
            f"Dosyalar kaydedildi: {OUTPUT_DIR.resolve()}"
        )

else:

    st.info(
        "Başlamak için 'İnternetten Ürünleri İndir' "
        "butonuna bas."
    )

st.divider()

st.caption(
    "Bu açık katalog ABD kaynaklıdır. "
    "Türkiye'deki mağazaların canlı fiyatlarını temsil etmez. "
    "Katalogdaki fiyatlar kaynakta yer aldığı şekliyle aktarılır."
)
