import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. Konfigurasi Halaman & Keamanan
st.set_page_config(page_title="Absensi PPIH", page_icon="🕋")

def check_password():
    """Returns True if the user had the correct password."""
    if "password_correct" not in st.session_state:
        st.text_input("Masukkan Password Akses", type="password", on_change=password_entered, key="password")
        return False
    return st.session_state["password_correct"]

def password_entered():
    if st.session_state["password"] == "ppih2024": # GANTI PASSWORD DISINI
        st.session_state["password_correct"] = True
    else:
        st.error("Password salah!")

if check_password():
    # 2. Judul & Tampilan
    st.title("🕋 Sistem Absensi PPIH")
    st.info("Data ini akan menjadi dasar pencairan anggaran operasional.")

    # 3. Koneksi ke Google Sheets
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Ambil daftar petugas dari sheet 'daftar_petugas'
    df_petugas = conn.read(worksheet="daftar_petugas")
    
    # 4. Form Tampilan Utama
    with st.form("absen_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            nama = st.selectbox("Pilih Nama Anda", df_petugas['Nama'].tolist())
            seksi = st.selectbox("Seksi/Ketugasan", ["Konsumsi", "Kesehatan", "Transportasi", "Bimbingan Ibadah", "Sekretariat"])
        
        with col2:
            status = st.radio("Status Kehadiran", ["Hadir Tepat Waktu", "Tugas Luar/Izin"])
            foto = st.camera_input("Ambil Foto Selfie (Bukti Hadir)")

        submit = st.form_submit_button("Kirim Absen Sekarang")

        if submit:
            if foto is not None:
                # Logika Simpan Data
                waktu_sekarang = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Menyiapkan data baru
                new_data = pd.DataFrame([{
                    "Tanggal": waktu_sekarang,
                    "Nama": nama,
                    "Seksi": seksi,
                    "Status": status,
                    "Foto_URL": "Terlampir di Sistem"
                }])
                
                # Menggabungkan data lama dengan baru
                existing_data = conn.read(worksheet="rekap")
                updated_df = pd.concat([existing_data, new_data], ignore_index=True)
                
                # Update ke Google Sheets
                conn.update(worksheet="rekap", data=updated_df)
                
                st.success(f"Terima kasih {nama}, absen Anda telah tercatat!")
                st.balloons()
            else:
                st.warning("Mohon ambil foto terlebih dahulu sebagai bukti.")

    # 5. Dashboard Rekap (Hanya untuk Admin)
    with st.expander("Lihat Rekapitulasi Hari Ini (Khusus Admin)"):
        rekap_data = conn.read(worksheet="rekap")
        st.dataframe(rekap_data)