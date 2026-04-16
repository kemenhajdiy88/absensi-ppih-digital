import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# ─────────────────────────────────────────────
# 1. KONFIGURASI HALAMAN
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Absensi PPIH",
    page_icon="🕋",
    layout="centered",
)

# ─────────────────────────────────────────────
# 2. SISTEM AUTENTIKASI PASSWORD SEDERHANA
# ─────────────────────────────────────────────
_PASSWORD = "ppih2026"  # ← Ganti password di sini


def _password_entered():
    """Callback: validasi password yang diketik pengguna."""
    if st.session_state.get("pwd_input") == _PASSWORD:
        st.session_state["authenticated"] = True
    else:
        st.session_state["authenticated"] = False
        st.session_state["pwd_wrong"] = True


def require_login() -> bool:
    """
    Tampilkan form login jika belum terautentikasi.
    Kembalikan True jika sudah login, False jika belum.
    """
    if st.session_state.get("authenticated"):
        return True

    st.markdown("## 🔐 Login Sistem Absensi PPIH")
    st.text_input(
        "Masukkan Password Akses",
        type="password",
        key="pwd_input",
        on_change=_password_entered,
        placeholder="Ketik password lalu tekan Enter…",
    )

    if st.session_state.get("pwd_wrong"):
        st.error("❌ Password salah. Silakan coba lagi.")

    return False


# ─────────────────────────────────────────────
# 3. APLIKASI UTAMA (hanya tampil setelah login)
# ─────────────────────────────────────────────
if require_login():
    st.title("🕋 Presensi Petugas PPIH")
    st.caption("Verifikasi kehadiran untuk administrasi operasional.")
    st.divider()

    # ── Koneksi Google Sheets ─────────────────
    conn = st.connection("gsheets", type=GSheetsConnection)

    # ── Ambil daftar petugas (kolom: Nama_Lengkap, Jabatan_PPIH) ─────
    try:
        df_petugas = conn.read(worksheet="daftar_petugas", ttl=0)

        # Validasi kolom wajib ada
        required_cols = {"Nama_Lengkap", "Jabatan_PPIH"}
        if not required_cols.issubset(df_petugas.columns):
            st.error(
                f"Sheet 'daftar_petugas' harus memiliki kolom: "
                f"{', '.join(required_cols)}. "
                f"Kolom yang ditemukan: {', '.join(df_petugas.columns.tolist())}"
            )
            st.stop()

        list_nama = df_petugas["Nama_Lengkap"].dropna().unique().tolist()
        list_jabatan = df_petugas["Jabatan_PPIH"].dropna().unique().tolist()

    except Exception as exc:
        st.error("⚠️ Gagal terhubung ke Google Sheets. Detail error:")
        st.exception(exc)
        st.stop()

    # ── Form Presensi ─────────────────────────
    with st.form("form_presensi", clear_on_submit=False):
        st.subheader("📋 Data Kehadiran")

        nama = st.selectbox(
            "Nama Lengkap",
            options=["-- Pilih Nama --"] + list_nama,
        )
        jabatan = st.selectbox(
            "Jabatan PPIH / Seksi",
            options=["-- Pilih Jabatan --"] + list_jabatan,
        )
        status = st.radio(
            "Status Kehadiran",
            options=["Hadir Tepat Waktu", "Hadir Terlambat", "Tugas Luar Asrama"],
            horizontal=True,
        )

        st.subheader("📸 Validasi Kehadiran")
        foto = st.camera_input("Foto Selfie di Lokasi (Wajib)")

        submit = st.form_submit_button("✅ Kirim Presensi", use_container_width=True)

    # ── Proses Pengiriman (di luar form agar st.spinner bisa tampil) ──
    if submit:
        errors = []
        if nama == "-- Pilih Nama --":
            errors.append("Nama Lengkap belum dipilih.")
        if jabatan == "-- Pilih Jabatan --":
            errors.append("Jabatan PPIH / Seksi belum dipilih.")
        if foto is None:
            errors.append("Foto selfie wajib diambil sebagai bukti kehadiran.")

        if errors:
            for err in errors:
                st.warning(f"⚠️ {err}")
        else:
            waktu_sekarang = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            new_row = pd.DataFrame([{
                "Waktu_Absen":       waktu_sekarang,
                "Nama_Lengkap":      nama,
                "Jabatan_PPIH":      jabatan,
                "Status_Kehadiran":  status,
                "Foto_Bukti":        "Terlampir",
            }])

            try:
                with st.spinner("Menyimpan data kehadiran…"):
                    existing_data = conn.read(worksheet="rekap", ttl=0)
                    # Pastikan kolom konsisten meski sheet rekap masih kosong
                    if existing_data.empty:
                        updated_df = new_row
                    else:
                        updated_df = pd.concat(
                            [existing_data, new_row], ignore_index=True
                        )
                    conn.update(worksheet="rekap", data=updated_df)

                st.success(f"✅ Alhamdulillah, presensi **{nama}** berhasil dicatat!")
                st.balloons()

            except Exception as exc:
                st.error("❌ Gagal menyimpan data. Detail error:")
                st.exception(exc)

    # ── Rekap Admin ───────────────────────────
    st.divider()
    with st.expander("📊 Lihat Rekapitulasi Kehadiran (Admin)"):
        try:
            rekap_data = conn.read(worksheet="rekap", ttl=0)
            if rekap_data.empty:
                st.info("Belum ada data kehadiran yang tercatat hari ini.")
            else:
                st.dataframe(rekap_data, use_container_width=True)
                st.caption(f"Total entri: {len(rekap_data)}")
        except Exception as exc:
            st.error("Gagal memuat rekap:")
            st.exception(exc)
