import streamlit as st
from google.cloud import storage, firestore
from io import BytesIO
from PIL import Image, ImageOps
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

# Config
GCP_PROJECT = "personal-site-466302"
BUCKET_NAME = "personal-site-bucket-1"
FOLDER_PREFIX = "images/"

# Firestore & Storage clients
storage_client = storage.Client(project=GCP_PROJECT)
firestore_client = firestore.Client(project=GCP_PROJECT, database="personal-site-md")
bucket = storage_client.bucket(BUCKET_NAME)

# Load metadata
docs = firestore_client.collection("pictures-collection").stream()
records = []
for doc in docs:
    d = doc.to_dict()
    d["filename"] = d["filename"].split("/")[-1]
    records.append(d)

df = pd.DataFrame(records)
df["date"] = pd.to_datetime(df["date"])
df.sort_values("date", inplace=True)

# World map
st.title("🗺️ Photo Map")
m = folium.Map(location=[20, 0], zoom_start=2, tiles="OpenStreetMap")
marker_cluster = MarkerCluster().add_to(m)

for _, row in df.iterrows():
    folium.Marker(
        location=[row["lat"], row["lon"]],
        tooltip=row["title"],
        popup=f"{row['title']}<br>{row['date'].strftime('%Y-%m-%d')}"
    ).add_to(marker_cluster)

# Display interactive map
st_data = st_folium(m, width=1200, height=600)

# Detect click on map
if st_data and st_data.get("last_object_clicked"):
    lat_clicked = st_data["last_object_clicked"]["lat"]
    lon_clicked = st_data["last_object_clicked"]["lng"]

    # Find nearby photos (within ~0.01 degrees)
    nearby = df[
        (df["lat"].between(lat_clicked - 0.01, lat_clicked + 0.01)) &
        (df["lon"].between(lon_clicked - 0.01, lon_clicked + 0.01))
    ]

    if not nearby.empty:
        st.subheader("📸 Photos Near This Location")
        for _, row in nearby.iterrows():
            filename = row["filename"]

            # Match filename to blob in GCS
            blob_path = next(
                (b.name for b in bucket.list_blobs(prefix=FOLDER_PREFIX) if filename in b.name), None
            )
            if blob_path:
                blob = bucket.blob(blob_path)
                img = Image.open(BytesIO(blob.download_as_bytes()))
                img = ImageOps.exif_transpose(img)

                st.image(img, caption=row["title"], use_container_width=True)
                st.markdown(f"📅 **Date**: {row['date'].strftime('%Y-%m-%d')}")
                st.markdown(f"📍 **Location**: {row['lat']}, {row['lon']}")
                st.divider()
