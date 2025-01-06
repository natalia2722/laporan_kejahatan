import streamlit as st
import pandas as pd
from datetime import datetime
import folium
import numpy as np
from sklearn.cluster import DBSCAN
from streamlit_folium import folium_static
from folium.plugins import HeatMap, MarkerCluster
import sqlite3
import os
from PIL import Image
import io
from streamlit_folium import st_folium


UPLOAD_FOLDER = "uploaded_files"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Inisialisasi database
def init_db():
    conn = sqlite3.connect('crime_reports.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS reports
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         nama TEXT,
         jenis_kelamin TEXT,
         telepon TEXT,
         lokasi TEXT,
         latitude REAL,
         longitude REAL,
         jenis_kejahatan TEXT,
         waktu DATETIME,
         deskripsi TEXT,
         bukti TEXT,
         timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)
    ''')
    conn.commit()
    conn.close()
    
def get_crime_clusters():
    conn = sqlite3.connect('crime_reports.db')
    
    # Get all crime reports
    df = pd.read_sql_query(
        "SELECT latitude, longitude, jenis_kejahatan FROM reports",
        conn
    )
    conn.close()
    
    if df.empty:
        return df
    
    # Initialize DBSCAN clustering
    # eps=0.0045 is approximately 500 meters in decimal degrees
    # min_samples=1 ensures all points are assigned to clusters
    clustered_data = []
    
    for crime_type in df['jenis_kejahatan'].unique():
        # Filter for current crime type
        crime_df = df[df['jenis_kejahatan'] == crime_type]
        
        if len(crime_df) > 0:
            # Prepare coordinates for clustering
            coords = crime_df[['latitude', 'longitude']].values
            
            # Apply DBSCAN clustering
            clustering = DBSCAN(
                eps=0.0045,  # ~500 meters
                min_samples=1,
                metric='haversine'
            ).fit(coords)
            
            # Add cluster labels
            crime_df['cluster'] = clustering.labels_
            
            # Calculate cluster centers and counts
            clusters = crime_df.groupby(['cluster', 'jenis_kejahatan']).agg({
                'latitude': 'mean',  # Center point of cluster
                'longitude': 'mean',  # Center point of cluster
                'jenis_kejahatan': 'count'  # Number of crimes in cluster
            }).rename(columns={'jenis_kejahatan': 'count'}).reset_index()
            
            clustered_data.append(clusters)
    
    # Combine all clustered data
    if clustered_data:
        final_clusters = pd.concat(clustered_data, ignore_index=True)
        return final_clusters
    
    return pd.DataFrame(columns=['cluster', 'jenis_kejahatan', 'latitude', 'longitude', 'count'])

def main():
    st.set_page_config(page_title="Sistem Pelaporan Kejahatan", layout="wide")
    init_db()

    # Sidebar menu
    menu = st.sidebar.selectbox(
        "Menu",
        ["Beranda", "Tentang Kami", "Tips Keamanan", "Kontak Darurat", "Peta Kejahatan", "Form Laporan", "Riwayat Laporan"]
    )

    if menu == "Beranda":
        st.title("Selamat Datang di Sistem Pelaporan Kejahatan")
        st.write("Silakan pilih menu di sidebar untuk mengakses fitur yang tersedia.")

    elif menu == "Tentang Kami":
        st.title("Tentang Kami")
        st.write("""
        Sistem Pelaporan Kejahatan adalah platform yang dikembangkan untuk memudahkan masyarakat 
        dalam melaporkan tindak kejahatan. Kami berkomitmen untuk menciptakan lingkungan yang 
        lebih aman dengan memfasilitasi pelaporan yang cepat dan efektif.
        """)

    elif menu == "Tips Keamanan":
        st.title("Tips Keamanan")
        st.subheader("Panduan Keamanan Pribadi")
        st.write("""
        1. Selalu waspada dengan lingkungan sekitar
        2. Hindari berjalan sendirian di tempat sepi
        3. Simpan nomor darurat di ponsel Anda
        4. Pastikan rumah selalu terkunci
        5. Gunakan pencahayaan yang cukup di sekitar rumah
        """)

    elif menu == "Kontak Darurat":
        st.title("Kontak Darurat")
        st.write("""
        - Polisi: 110
        - Ambulans: 118
        - Pemadam Kebakaran: 113
        - Call Center: 112
        """)

    elif menu == "Peta Kejahatan":
        st.title("Peta Daerah Rawan Kejahatan")
        

        m = folium.Map(location=[-5.1477, 119.4328], zoom_start=12) 
        
        # Get crime data from database
        crime_data = get_crime_clusters()
        
        if not crime_data.empty:
            marker_cluster = MarkerCluster().add_to(m)
            
            for idx, row in crime_data.iterrows():
                # Create marker with size based on count
                radius = min(20 * np.log(row['count'] + 1), 50)  # Logarithmic scaling
                
                folium.CircleMarker(
                    location=[row['latitude'], row['longitude']],
                    radius=radius,
                    popup=f"Jenis Kejahatan: {row['jenis_kejahatan']}<br>Jumlah Laporan: {row['count']}",
                    color='red',
                    fill=True,
                    fill_opacity=0.7,
                    tooltip=f"{row['jenis_kejahatan']}: {row['count']} kejadian"
                ).add_to(marker_cluster)
            
            # Create heatmap layer
            heat_data = [[row['latitude'], row['longitude'], row['count']] for idx, row in crime_data.iterrows()]
            HeatMap(heat_data).add_to(m)
        
        folium_static(m)

    elif menu == "Form Laporan":
        st.title("Form Laporan Kejahatan")
        
        # Create columns for the form layout
        col1, col2 = st.columns(2)
        
        # Initialize session state for location if not exists
        if 'selected_location' not in st.session_state:
            st.session_state.selected_location = None
        
        with st.form("laporan_kejahatan"):
            with col1:
                nama = st.text_input("Nama Pelapor")
                jenis_kelamin = st.selectbox("Jenis Kelamin", ["Laki-laki", "Perempuan"])
                telepon = st.text_input("Nomor Telepon")
                jenis_kejahatan = st.selectbox("Jenis Kejahatan", 
                    ["Pencurian", "Perampokan", "Penipuan", "Kekerasan", "Lainnya"])
                waktu = st.date_input("Waktu Kejadian")
                
            with col2:
                st.write("Pilih Lokasi Kejadian pada Peta (klik pada lokasi)")
                
                # Initialize the map
                m = folium.Map(location=[-5.1477, 119.4328], zoom_start=12)


                
                # Get location from map interaction
                map_data = st_folium(m, height=400, width=600)
                
                # Update selected location in session state when map is clicked
                if map_data['last_clicked'] and map_data['last_clicked'] != st.session_state.selected_location:
                    st.session_state.selected_location = map_data['last_clicked']
                    st.rerun()
                
                # Display selected location information outside the form
                if st.session_state.selected_location:
                    st.success(
                        f"Lokasi dipilih: Latitude {st.session_state.selected_location['lat']:.6f}, "
                        f"Longitude {st.session_state.selected_location['lng']:.6f}"
                    )
                
                deskripsi = st.text_area("Deskripsi Singkat")
                bukti = st.file_uploader("Unggah Bukti (Foto/Video)", 
                    type=["jpg", "jpeg", "png", "mp4"])

            if st.form_submit_button("Kirim Laporan"):
                if nama and telepon and st.session_state.selected_location and deskripsi:
                    conn = sqlite3.connect('crime_reports.db')
                    c = conn.cursor()
                    
                    bukti_path = None
                    if bukti:
                        bukti_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{bukti.name}"
                        bukti_path = os.path.join(UPLOAD_FOLDER, bukti_filename)
                        with open(bukti_path, "wb") as f:
                            f.write(bukti.getbuffer())

                    latitude = st.session_state.selected_location['lat']
                    longitude = st.session_state.selected_location['lng']
                    lokasi = f"Lat: {latitude}, Lng: {longitude}"

                    c.execute("""
                        INSERT INTO reports (nama, jenis_kelamin, telepon, lokasi, latitude, longitude,
                        jenis_kejahatan, waktu, deskripsi, bukti)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (nama, jenis_kelamin, telepon, lokasi, latitude, longitude,
                        jenis_kejahatan, waktu.strftime("%Y-%m-%d"), deskripsi, bukti_path))
                    
                    conn.commit()
                    conn.close()
                    
                    st.success("Laporan berhasil dikirim!")

                else:
                    st.error("Mohon lengkapi semua field yang wajib diisi dan pilih lokasi pada peta")

    elif menu == "Riwayat Laporan":
        st.title("Riwayat Laporan")

        conn = sqlite3.connect('crime_reports.db')
        reports = pd.read_sql_query(
            "SELECT id, nama, jenis_kejahatan, lokasi, waktu, bukti, timestamp FROM reports", 
            conn
        )
        conn.close()

        if reports.empty:  # Mengecek jika dataframe kosong
            st.write("Belum ada laporan yang tercatat.")
        else:
            for _, row in reports.iterrows():
                st.subheader(f"Laporan #{row['id']}")
                st.write(f"**Nama Pelapor:** {row['nama']}")
                st.write(f"**Jenis Kejahatan:** {row['jenis_kejahatan']}")
                st.write(f"**Lokasi Kejadian:** {row['lokasi']}")
                st.write(f"**Waktu Kejadian:** {row['waktu']}")
                st.write(f"**Dikirim Pada:** {row['timestamp']}")

                # Tampilkan bukti jika ada
                if row['bukti']:
                    file_path = row['bukti']
                    file_extension = os.path.splitext(file_path)[1].lower()

                    if file_extension in [".jpg", ".jpeg", ".png"]:
                        # Tampilkan gambar
                        image = Image.open(file_path)
                        st.image(image, caption="Bukti Foto", use_container_width=True)
                    elif file_extension == ".mp4":
                        # Tampilkan video
                        st.video(file_path)
                    else:
                        # Tampilkan tautan untuk file lain
                        st.write(f"[Unduh Bukti](./{file_path})")
                else:
                    st.write("**Tidak ada bukti yang diunggah.**")

                st.markdown("---")
    else:
        st.write("Belum ada laporan yang tercatat.")

if __name__ == "__main__":
    main()
