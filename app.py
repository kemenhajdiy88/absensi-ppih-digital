import io
import re
import base64
import requests
import streamlit as st
import gspread
import pandas as pd
from datetime import datetime
from PIL import Image
from google.oauth2.service_account import Credentials

# ══════════════════════════════════════════════════════════════════════════════
# KONFIGURASI HALAMAN
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Sistem Absensi PPIH 2026",
    page_icon="🕋",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ══════════════════════════════════════════════════════════════════════════════
# CUSTOM CSS — Tampilan Premium & Profesional
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(
    """
    <style>
    /* ── Google Font ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* ── Dark gradient background ── */
    .stApp {
        # background: linear-gradient(135deg, #0f1b2d 0%, #162032 50%, #1a2a40 100%);
        background: #ffffff;
        min-height: 100vh;
    }

    /* ── Header Banner ── */
    .header-banner {
        # background: linear-gradient(90deg, #1a6b3c 0%, #22a15a 50%, #1a8f4e 100%);
        background: #c9a961;
        border-radius: 16px;
        padding: 26px 32px;
        margin-bottom: 28px;
        text-align: center;
        box-shadow: 0 8px 32px rgba(163,131,59,0.35);
        border: 1px solid rgba(255,255,255,0.08);
    }
    .header-banner h1 {
        color: #ffffff;
        font-size: 1.7rem;
        font-weight: 700;
        margin: 0 0 6px 0;
        letter-spacing: -0.5px;
    }
    .header-banner p { color: rgba(255,255,255,0.82); margin: 0; font-size: 0.88rem; }

    /* ── Card wrapper ── */
    .form-card {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 14px;
        padding: 28px 28px 20px;
        margin-bottom: 20px;
        backdrop-filter: blur(12px);
    }
    .section-label {
        color: #7ecba1;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1.3px;
        margin-bottom: 14px;
        display: block;
    }

    /* ── Submit button ── */
    div[data-testid="stFormSubmitButton"] > button {
        background: linear-gradient(90deg, #1a6b3c, #22a15a) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
        font-size: 1rem !important;
        padding: 14px !important;
        width: 100% !important;
        box-shadow: 0 4px 20px rgba(34,161,90,0.4) !important;
        transition: all 0.2s ease !important;
    }
    div[data-testid="stFormSubmitButton"] > button:hover {
        box-shadow: 0 6px 28px rgba(34,161,90,0.65) !important;
        transform: translateY(-1px) !important;
    }

    /* ── Widget labels ── */
    .stSelectbox label, .stRadio label,
    .stTextInput label, .stCameraInput label {
        color: #c9ddd0 !important; font-weight: 500 !important;
    }

    /* ── Expander header ── */
    .streamlit-expanderHeader {
        background: rgba(255,255,255,0.05) !important;
        border-radius: 10px !important;
        color: #7ecba1 !important;
        font-weight: 600 !important;
    }

    /* ── Footer ── */
    .footer {
        text-align: center;
        color: rgba(255,255,255,0.28);
        font-size: 0.73rem;
        padding: 20px 0 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ══════════════════════════════════════════════════════════════════════════════
# KONSTANTA & KONFIGURASI API
# ══════════════════════════════════════════════════════════════════════════════
SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

# Google Apps Script Web App URL untuk upload foto ke Google Drive
GAS_WEBAPP_URL = "https://script.google.com/macros/s/AKfycbxWXnM6xslXZ7aRhk7MTVuqyY2oyPTh8Z54ubAhsLxfLeJwf4L1FAoaWquxGteG0jCT/exec"

REQUIRED_MASTER_COLS = {"Nama_Lengkap", "Jabatan_PPIH", "Asal_Instansi", "PIN_Rahasia", "Ukuran_Pakaian_Dinas"}
REKAP_COLS = [
    "Waktu_Sistem", "Nama_Lengkap", "Jabatan_PPIH",
    "Asal_Instansi", "Jenis_Absen", "Status_Kehadiran", "Bukti_Foto",
]


# ── Pembuatan Kredensial (dibagi pakai antara Sheets & Drive) ─────────────────
@st.cache_resource(show_spinner="🔗 Memuat kredensial Google API…")
def _get_creds() -> Credentials:
    """
    Baca service account dari secrets.toml dan kembalikan objek Credentials.
    Private key dinormalisasi otomatis (\\n → newline sesungguhnya).
    """
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        return Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    except KeyError as e:
        st.error(
            f"❌ Kunci konfigurasi tidak ditemukan di secrets.toml: **{e}**. "
            "Pastikan file `.streamlit/secrets.toml` sudah diisi dengan benar."
        )
        st.stop()
    except Exception as e:
        st.error("❌ Gagal memuat kredensial Google:")
        st.exception(e)
        st.stop()


@st.cache_resource(show_spinner="🔗 Menghubungkan ke Google Sheets…")
def get_spreadsheet():
    """Buka spreadsheet menggunakan kredensial service account."""
    try:
        creds = _get_creds()
        client = gspread.authorize(creds)
        return client.open_by_url(st.secrets["spreadsheet_url"])
    except Exception as e:
        st.error("❌ Gagal terhubung ke Google Sheets:")
        st.exception(e)
        st.stop()


def ws_to_df(worksheet) -> pd.DataFrame:
    """Konversi worksheet gspread ke DataFrame pandas."""
    records = worksheet.get_all_records()
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records)


def load_data_master(spreadsheet) -> pd.DataFrame:
    """Baca tab Data_Master."""
    ws = spreadsheet.worksheet("Data_Master")
    df = ws_to_df(ws)
    if df.empty:
        st.error("⚠️ Sheet **Data_Master** kosong. Tambahkan data petugas terlebih dahulu.")
        st.stop()
    missing = REQUIRED_MASTER_COLS - set(df.columns)
    if missing:
        st.error(
            f"❌ Kolom berikut tidak ditemukan di **Data_Master**: `{', '.join(missing)}`. "
            "Periksa kembali nama kolom di Google Sheets."
        )
        st.stop()
    return df.dropna(subset=["Nama_Lengkap"])


def load_rekap_absen(spreadsheet) -> pd.DataFrame:
    """Baca tab Rekap_Absen."""
    ws = spreadsheet.worksheet("Rekap_Absen")
    df = ws_to_df(ws)
    return df


def append_rekap_absen(spreadsheet, new_row: dict) -> None:
    """Tambahkan satu baris baru ke Rekap_Absen menggunakan append_row."""
    ws = spreadsheet.worksheet("Rekap_Absen")
    row_values = [str(new_row.get(col, "")) for col in REKAP_COLS]
    ws.append_row(row_values, value_input_option="USER_ENTERED")


# ══════════════════════════════════════════════════════════════════════════════
# UTILITAS FOTO — Kompresi + Upload via Google Apps Script Web App
# ══════════════════════════════════════════════════════════════════════════════
def compress_image(raw_bytes: bytes, max_width: int = 800, quality: int = 75) -> io.BytesIO:
    """
    Kompres gambar menggunakan Pillow:
    - Konversi ke RGB (agar kompatibel dengan format JPEG)
    - Resize ke max_width px maksimum dengan mempertahankan aspek rasio
    - Simpan sebagai JPEG dengan kualitas yang ditentukan
    Mengembalikan BytesIO siap di-encode ke base64.
    """
    img = Image.open(io.BytesIO(raw_bytes))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    if img.width > max_width:
        ratio = max_width / img.width
        img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    buf.seek(0)
    return buf


def sanitize_filename(name: str) -> str:
    """Ganti karakter tidak aman untuk nama file dengan underscore."""
    return re.sub(r"[\s/:*?\"<>|]+", "_", name)


def upload_photo_via_gas(
    image_bytes: bytes,
    nama: str,
    jenis: str,
    waktu: str,
    timeout: int = 60,
) -> str:
    """
    Upload foto ke Google Drive melalui Google Apps Script Web App.

    Alur:
      1. Kompres gambar dengan Pillow (max 800px, JPEG q=75)
      2. Encode hasil kompresi ke base64 string
      3. POST payload JSON ke GAS_WEBAPP_URL
      4. GAS Web App menyimpan file ke Drive & mengembalikan URL plain-text

    Returns:
        str: Shareable Google Drive URL dari respons GAS Web App.

    Raises:
        RuntimeError: Jika request gagal atau respons tidak berisi URL valid.
    """
    # 1. Kompres
    compressed_buf = compress_image(image_bytes)

    # 2. Encode ke base64
    b64_string = base64.b64encode(compressed_buf.read()).decode("utf-8")

    # 3. Buat nama file yang aman
    filename = (
        f"{sanitize_filename(nama)}"
        f"_{sanitize_filename(jenis)}"
        f"_{sanitize_filename(waktu)}.jpg"
    )

    # 4. Kirim POST request ke GAS Web App
    payload = {
        "mimeType":   "image/jpeg",
        "fileName":   filename,
        "base64Data": b64_string,
    }
    response = requests.post(
        GAS_WEBAPP_URL,
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()   # lempar HTTPError jika status bukan 2xx

    # 5. Ekstrak URL dari respons plain-text
    drive_url = response.text.strip()
    if not drive_url.startswith("http"):
        raise RuntimeError(
            f"Respons GAS Web App tidak berisi URL valid.\nRespons: {drive_url}"
        )
    return drive_url


# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(
    """
    <div class="header-banner">
        <h1>🕋 Sistem Absensi Petugas PPIH 2026</h1>
        <p>Kementerian Haji & Umroh Daerah Istimewa Yogyakarta</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ══════════════════════════════════════════════════════════════════════════════
# LOAD DATA
# ══════════════════════════════════════════════════════════════════════════════
spreadsheet = get_spreadsheet()

try:
    df_master = load_data_master(spreadsheet)
except Exception as exc:
    st.error("⚠️ Gagal memuat Data Master dari Google Sheets.")
    st.exception(exc)
    st.stop()

list_nama = df_master["Nama_Lengkap"].unique().tolist()

# ══════════════════════════════════════════════════════════════════════════════
# FORM ABSENSI
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="form-card">', unsafe_allow_html=True)

with st.form("form_absensi", clear_on_submit=False):

    # ── Bagian 1: Data Petugas ────────────────────────────────────────────────
    st.markdown('<span class="section-label">📋 Data Petugas</span>', unsafe_allow_html=True)

    nama_pilihan = st.selectbox(
        "Nama Lengkap Petugas",
        options=["— Pilih Nama Anda —"] + list_nama,
        help="Pilih nama lengkap sesuai yang terdaftar di Data Master.",
    )

    # Tampilkan info jabatan, instansi & ukuran pakaian secara otomatis
    if nama_pilihan != "— Pilih Nama Anda —":
        row = df_master[df_master["Nama_Lengkap"] == nama_pilihan].iloc[0]
        ukuran = row.get("Ukuran_Pakaian_Dinas", "-") if "Ukuran_Pakaian_Dinas" in df_master.columns else "-"
        st.info(
            f"🏷️ **Jabatan PPIH:** {row['Jabatan_PPIH']}  \n"
            f"🏢 **Asal Instansi:** {row['Asal_Instansi']}  \n"
            f"👕 **Ukuran Pakaian Dinas:** {ukuran}"
        )
    else:
        st.info("ℹ️ Pilih nama Anda untuk melihat informasi jabatan, instansi, dan ukuran pakaian dinas.")

    st.divider()

    # ── Bagian 2: Verifikasi PIN ──────────────────────────────────────────────
    st.markdown('<span class="section-label">🔐 Verifikasi PIN</span>', unsafe_allow_html=True)

    pin_input = st.text_input(
        "PIN Rahasia (4 Digit)",
        type="password",
        max_chars=4,
        placeholder="••••",
        help="Masukkan PIN 4 digit yang telah diberikan kepada Anda.",
    )

    st.divider()

    # ── Bagian 3: Jenis & Status Kehadiran ───────────────────────────────────
    st.markdown(
        '<span class="section-label">📌 Jenis & Status Kehadiran</span>',
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        jenis_absen = st.radio(
            "Jenis Absen",
            options=["Absen Datang", "Absen Pulang"],
        )
    with col2:
        status_kehadiran = st.radio(
            "Status Kehadiran",
            options=["Hadir", "Sakit", "Izin"],
        )

    st.divider()

    # ── Bagian 4: Bukti Foto ──────────────────────────────────────────────────
    st.markdown('<span class="section-label">📸 Bukti Foto Kehadiran</span>', unsafe_allow_html=True)

    if status_kehadiran == "Hadir":
        foto = st.camera_input(
            "Ambil Foto Selfie sebagai Bukti Kehadiran *(wajib untuk status Hadir)*"
        )
    else:
        foto = None
        st.caption("📷 Foto tidak diperlukan untuk status **Sakit** atau **Izin**.")

    # ── Tombol Submit ─────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    submit = st.form_submit_button("✅  Kirim Absensi", use_container_width=True)

st.markdown("</div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# VALIDASI & PENYIMPANAN DATA
# ══════════════════════════════════════════════════════════════════════════════
if submit:
    errors = []

    # ── Validasi 1: Nama harus dipilih
    if nama_pilihan == "— Pilih Nama Anda —":
        errors.append("Nama Lengkap belum dipilih.")

    # ── Validasi 2: PIN tidak boleh kosong
    if not pin_input:
        errors.append("PIN Rahasia tidak boleh kosong.")

    # ── Validasi 3: Foto wajib jika status Hadir
    if status_kehadiran == "Hadir" and foto is None:
        errors.append("Foto selfie **wajib** diambil untuk status kehadiran **Hadir**.")

    if errors:
        for err in errors:
            st.warning(f"⚠️ {err}")
    else:
        # ── Validasi 4: Cocokkan PIN dengan Data Master
        petugas_row = df_master[df_master["Nama_Lengkap"] == nama_pilihan].iloc[0]
        pin_benar = str(petugas_row["PIN_Rahasia"]).strip()

        if str(pin_input).strip() != pin_benar:
            st.error("❌ PIN tidak valid! Absensi tidak dapat disimpan.")
        else:
            # ── Semua validasi lolos → proses foto & tulis ke Rekap_Absen ────
            waktu_sistem = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            bukti_foto   = "-"  # default untuk Sakit/Izin

            try:
                # ── LANGKAH 1: Kompres & upload foto via GAS Web App ─────────
                if foto is not None:
                    with st.spinner("📤 Mengompres dan mengupload foto ke Google Drive…"):
                        bukti_foto = upload_photo_via_gas(
                            image_bytes = foto.getvalue(),
                            nama        = nama_pilihan,
                            jenis       = jenis_absen,
                            waktu       = waktu_sistem,
                        )

                # ── LANGKAH 2: Simpan rekap ke Google Sheets ─────────────────
                new_record = {
                    "Waktu_Sistem":     waktu_sistem,
                    "Nama_Lengkap":     nama_pilihan,
                    "Jabatan_PPIH":     petugas_row["Jabatan_PPIH"],
                    "Asal_Instansi":    petugas_row["Asal_Instansi"],
                    "Jenis_Absen":      jenis_absen,
                    "Status_Kehadiran": status_kehadiran,
                    "Bukti_Foto":       bukti_foto,
                }

                with st.spinner("💾 Menyimpan data absensi ke Google Sheets…"):
                    append_rekap_absen(spreadsheet, new_record)

                # ── LANGKAH 3: Tampilkan hasil sukses ────────────────────────
                st.success(
                    f"✅ Alhamdulillah! Absensi **{nama_pilihan}** berhasil dicatat.\n\n"
                    f"📅 Waktu: `{waktu_sistem}`  |  "
                    f"📌 Jenis: `{jenis_absen}`  |  "
                    f"🟢 Status: `{status_kehadiran}`"
                )
                if foto is not None:
                    st.info(f"🖼️ Foto bukti tersimpan di Drive: [{bukti_foto}]({bukti_foto})")
                st.balloons()

            except Exception as exc:
                st.error("❌ Gagal memproses absensi. Detail error:")
                st.exception(exc)

# ══════════════════════════════════════════════════════════════════════════════
# REKAPITULASI KEHADIRAN (Admin View)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
with st.expander("📊 Rekapitulasi Kehadiran (Admin)", expanded=False):
    try:
        rekap_df = load_rekap_absen(spreadsheet)
        if rekap_df.empty:
            st.info("Belum ada data absensi yang tercatat.")
        else:
            filter_nama = st.selectbox(
                "Filter berdasarkan nama",
                options=["Semua"] + rekap_df["Nama_Lengkap"].dropna().unique().tolist(),
                key="filter_rekap",
            )
            if filter_nama != "Semua":
                rekap_df = rekap_df[rekap_df["Nama_Lengkap"] == filter_nama]

            st.dataframe(rekap_df, use_container_width=True, height=320)
            st.caption(f"🗂️ Total entri: **{len(rekap_df)}** baris")
    except Exception as exc:
        st.error("Gagal memuat rekapitulasi:")
        st.exception(exc)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="footer">© 2026 PPIH — Kementerian Agama RI &nbsp;|&nbsp; '
    'Sistem Absensi Digital v2.0</div>',
    unsafe_allow_html=True,
)
