import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# Konfigurasi Tampilan
st.set_page_config(page_title="Absensi PPIH", page_icon="🕋", layout="centered")

# Sistem Password Sederhana
def check_password():
    if "password_correct" not in st.session_state:
        st.text_input("Masukkan Password Akses", type="password", on_change=password_entered, key="password")
        return False
    return st.session_state["password_correct"]

def password_entered():
    if st.session_state["password"] == "ppih2026": # Password akses
        st.session_state["password_correct"] = True
    else:
        st.error("Password salah!")

if check_password():
    st.title("🕋 Presensi Petugas PPIH")
    st.caption("Verifikasi kehadiran untuk administrasi operasional.")
    st.divider()

    # Membuka koneksi ke Google Sheets
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Menarik data master petugas
    try:
        df_petugas = conn.read(worksheet="daftar_petugas", ttl=0)
        list_nama = df_petugas['Nama_Lengkap'].dropna().tolist()
        list_jabatan = df_petugas['Jabatan_PPIH'].dropna().unique().tolist()
    except Exception as e:
        st.error("Terjadi masalah koneksi. Ini detail aslinya:")
        st.write(e) # Ini akan memunculkan pesan dari sistem
        st.stop()

    # Form Absensi Utama
    with st.form("form_presensi", clear_on_submit=True):
        st.subheader("Data Kehadiran")
        
        nama = st.selectbox("Cari Nama Lengkap Anda", ["-- Pilih Nama --"] + list_nama)
        jabatan = st.selectbox("Pilih Jabatan PPIH / Seksi", ["-- Pilih Jabatan --"] + list_jabatan)
        status = st.radio("Status Hadir", ["Hadir Tepat Waktu", "Hadir Terlambat", "Tugas Luar Asrama"])
        
        st.subheader("Validasi")
        foto = st.camera_input("Foto Selfie di Lokasi (Wajib)")

        submit = st.form_submit_button("Kirim Presensi")

        if submit:
            if nama == "-- Pilih Nama --" or jabatan == "-- Pilih Jabatan --":
                st.warning("Mohon pilih Nama dan Jabatan terlebih dahulu.")
            elif foto is None:
                st.warning("Mohon ambil foto selfie sebagai bukti kehadiran.")
            else:
                # Menyiapkan data untuk dikirim ke tab 'rekap'
                waktu_sekarang = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                new_data = pd.DataFrame([{
                    "Waktu_Absen": waktu_sekarang,
                    "Nama_Lengkap": nama,
                    "Jabatan_PPIH": jabatan,
                    "Status_Kehadiran": status,
                    "Foto_Bukti": "Terlampir"
                }])
                
                # Proses menyimpan data
                with st.spinner("Menyimpan data kehadiran..."):
                    existing_data = conn.read(worksheet="rekap", ttl=0)
                    updated_df = pd.concat([existing_data, new_data], ignore_index=True)
                    conn.update(worksheet="rekap", data=updated_df)
                
                st.success(f"Alhamdulillah, presensi {nama} berhasil dicatat!")
