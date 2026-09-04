# -*- coding: utf-8 -*-
"""
Lưu trữ 4 nhóm dữ liệu của tool traffic.

Hai chế độ:
- Google Sheets (gspread + service account) — KHUVEN DUNG: sửa config bằng
  điện thoại được, tool tự đọc + cập nhật status.
- Local (thư mục du_lieu_traffic/, mỗi sheet 1 file JSON) — chạy ngay không
  cần đăng ký gì, dùng để chạy thử trước khi cài Google Sheets.

Tự chọn: nếu config.json có sheets.spreadsheet_id + file credentials hợp lệ
thì dùng Google Sheets, ngược lại dùng Local.
"""

import json
import os
import re
import threading

from config import DUONG_DAN, load_config

# ---------------- Schema 4 sheet ----------------
TEN_SHEET = {
    "PAGE CONFIG": "PAGE CONFIG",
    "SOURCE CONFIG": "SOURCE CONFIG",
    "CONTENT POOL": "CONTENT POOL",
    "PAGE PERFORMANCE": "PAGE PERFORMANCE",
}

COT_PAGE_CONFIG = ["Page", "KEY", "Format", "Website", "Khung giờ đăng", "Bật/Tắt"]
COT_SOURCE_CONFIG = ["KEY", "Facebook nguồn", "Nhân vật gợi ý"]
COT_CONTENT_POOL = [
    "Content ID", "KEY", "Nhân vật/chủ đề", "Source", "Caption", "Media",
    "Link bài", "Thời gian đăng", "Cảm xúc", "Bình luận", "Chia sẻ",
    "Caption mới", "Bài báo", "Article URL", "Chủ đề", "Status", "Ghi chú",
]
COT_PAGE_PERFORMANCE = [
    "Page", "Post", "KEY", "Nhân vật/chủ đề", "Cảm xúc", "Bình luận",
    "Chia sẻ", "Điểm", "Thời gian",
]

CAC_COT = {
    "PAGE CONFIG": COT_PAGE_CONFIG,
    "SOURCE CONFIG": COT_SOURCE_CONFIG,
    "CONTENT POOL": COT_CONTENT_POOL,
    "PAGE PERFORMANCE": COT_PAGE_PERFORMANCE,
}

# Trạng thái hợp lệ của content
TRANG_THAI = ["NEW", "READY", "LOCKED", "PROCESSING", "WEB_POSTED",
              "FB_POSTED", "DONE", "ERROR", "HET_HAN"]


def _ten_file_an_toan(ten_sheet: str) -> str:
    """'CONTENT POOL' -> 'content_pool' (tên file JSON an toàn)."""
    return re.sub(r"[^a-z0-9]+", "_", ten_sheet.lower()).strip("_")


# ===================================================================
# Chế độ Local — mỗi sheet là 1 file JSON trong du_lieu_traffic/
# ===================================================================
class LocalJsonStore:
    """Lưu dạng file JSON trong thư mục du_lieu_traffic/ (chạy không cần gì)."""

    def __init__(self):
        self.thumuc = os.path.join(DUONG_DAN, "du_lieu_traffic")
        os.makedirs(self.thumuc, exist_ok=True)
        self._lock = threading.RLock()

    def _duong_dan(self, ten_sheet):
        return os.path.join(self.thumuc, _ten_file_an_toan(ten_sheet) + ".json")

    def lay_tat_ca(self, ten_sheet):
        with self._lock:
            p = self._duong_dan(ten_sheet)
            if not os.path.isfile(p):
                return []
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return []

    def them_dong(self, ten_sheet, dong: dict):
        """Thêm 1 dòng (dict theo tên cột). Header chưa có thì dùng schema."""
        with self._lock:
            danh_sach = self.lay_tat_ca(ten_sheet)
            danh_sach.append(dong)
            self._ghi(ten_sheet, danh_sach)
        return len(danh_sach)

    def cap_nhat_dong(self, ten_sheet, chi_so: int, dong: dict):
        """Ghi đè dòng theo chi_so (0-based — dòng 2 trong bảng = chi_so 0)."""
        with self._lock:
            danh_sach = self.lay_tat_ca(ten_sheet)
            while len(danh_sach) <= chi_so:
                danh_sach.append({})
            danh_sach[chi_so] = dong
            self._ghi(ten_sheet, danh_sach)

    def xoa_dong(self, ten_sheet, chi_so: int):
        """Xóa 1 dòng theo chi_so (0-based — dòng 2 trong bảng = chi_so 0)."""
        with self._lock:
            danh_sach = self.lay_tat_ca(ten_sheet)
            if 0 <= chi_so < len(danh_sach):
                del danh_sach[chi_so]
                self._ghi(ten_sheet, danh_sach)

    def tim_dong(self, ten_sheet, cot: str, gia_tri) -> (int, dict):
        """Tìm dòng đầu tiên có cot == gia_tri. Trả về (chi_so, dong) hoặc None."""
        for i, dong in enumerate(self.lay_tat_ca(ten_sheet)):
            if str(dong.get(cot, "")).strip() == str(gia_tri).strip():
                return i, dong
        return None

    def so_dong(self, ten_sheet):
        return len(self.lay_tat_ca(ten_sheet))

    def _ghi(self, ten_sheet, danh_sach):
        with open(self._duong_dan(ten_sheet), "w", encoding="utf-8") as f:
            json.dump(danh_sach, f, ensure_ascii=False, indent=2)

    def mo_ta(self):
        return f"Local: {self.thumuc}"


# ===================================================================
# Chế độ Google Sheets — gspread + service account
# ===================================================================
class GoogleSheetsStore:
    """Đọc/ghi 4 sheet Google qua gspread (service account)."""

    def __init__(self, credentials_file: str, spreadsheet_id: str):
        self.credentials_file = credentials_file
        self.spreadsheet_id = spreadsheet_id
        self._client = None
        self._sh = None
        self._ws = {}

    # ---- khởi tạo chậm: chỉ cần Google khi thực sự gọi ----
    def _ket_noi(self):
        if self._client is not None:
            return
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(
            self.credentials_file, scopes=scopes)
        self._client = gspread.authorize(creds)

    def _sheet(self, ten_sheet):
        self._ket_noi()
        if ten_sheet in self._ws:
            return self._ws[ten_sheet]
        if self._sh is None:
            self._sh = self._client.open_by_key(self.spreadsheet_id)
        try:
            ws = self._sh.worksheet(ten_sheet)
        except Exception:
            ws = self._sh.add_worksheet(title=ten_sheet, rows=1000, cols=len(CAC_COT[ten_sheet]))
            ws.update([CAC_COT[ten_sheet]], "A1")
        self._ws[ten_sheet] = ws
        return ws

    def lay_tat_ca(self, ten_sheet):
        ws = self._sheet(ten_sheet)
        du_lieu = ws.get_all_values()
        if not du_lieu:
            return []
        tieu_de = du_lieu[0]
        return [dict(zip(tieu_de, dong)) for dong in du_lieu[1:]
                if any((d or "").strip() for d in dong)]

    def them_dong(self, ten_sheet, dong: dict):
        ws = self._sheet(ten_sheet)
        du_lieu = ws.get_all_values()
        if not du_lieu:
            ws.update([CAC_COT[ten_sheet]], "A1")
            du_lieu = [CAC_COT[ten_sheet]]
        tieu_de = du_lieu[0]
        dong_moi = [dong.get(c, "") for c in tieu_de]
        ws.append_row(dong_moi, value_input_option="USER_ENTERED")
        return len(du_lieu)  # chi_so dòng vừa thêm (0-based)

    def cap_nhat_dong(self, ten_sheet, chi_so: int, dong: dict):
        ws = self._sheet(ten_sheet)
        du_lieu = ws.get_all_values()
        if not du_lieu:
            ws.update([CAC_COT[ten_sheet]], "A1")
            du_lieu = [CAC_COT[ten_sheet]]
        tieu_de = du_lieu[0]
        dong_moi = [dong.get(c, "") for c in tieu_de]
        ws.update(f"A{chi_so + 2}", [dong_moi], value_input_option="USER_ENTERED")

    def xoa_dong(self, ten_sheet, chi_so: int):
        """Xóa 1 dòng theo chi_so (0-based — dòng 2 trong sheet = chi_so 0)."""
        ws = self._sheet(ten_sheet)
        ws.delete_rows(chi_so + 2)

    def tim_dong(self, ten_sheet, cot: str, gia_tri):
        for i, dong in enumerate(self.lay_tat_ca(ten_sheet)):
            if str(dong.get(cot, "")).strip() == str(gia_tri).strip():
                return i, dong
        return None

    def so_dong(self, ten_sheet):
        return len(self.lay_tat_ca(ten_sheet))

    def mo_ta(self):
        return f"Google Sheets: {self.spreadsheet_id}"


# ===================================================================
# Chọn store tự động theo config
# ===================================================================
_store_dang_dung = None


def lay_store():
    """Trả về store đang dùng — Google Sheets nếu cấu hình đủ, không thì Local."""
    global _store_dang_dung
    if _store_dang_dung is not None:
        return _store_dang_dung
    cfg = load_config()
    creds = os.path.join(DUONG_DAN, cfg["sheets"]["credentials_file"])
    co_creds = os.path.isfile(creds)
    co_id = bool(cfg["sheets"]["spreadsheet_id"])
    if co_creds and co_id:
        _store_dang_dung = GoogleSheetsStore(creds, cfg["sheets"]["spreadsheet_id"])
    else:
        _store_dang_dung = LocalJsonStore()
    return _store_dang_dung


def dat_store(store):
    """Ép dùng store cụ thể (dùng trong test)."""
    global _store_dang_dung
    _store_dang_dung = store


# ===================================================================
# Lệnh --setup: in hướng dẫn + tạo spreadsheet khi đã có credentials
# ===================================================================
def huong_dan_google_sheets():
    print("=" * 62)
    print("  CÀI GOOGLE SHEETS (làm 1 lần, khoảng 5 phút)")
    print("=" * 62)
    print("""
BƯỚC 1 — Tạo project + service account:
  1. Mở https://console.cloud.google.com  (đăng nhập Google của bạn)
  2. Tạo project mới (nút chọn project trên cùng → New Project → đặt tên vd
     'traffic-fb' → Create)
  3. Bật 2 API:  Google Sheets API  và  Google Drive API
     (APIs & Services → Library → tìm từng cái → Enable)
  4. APIs & Services → Credentials → + Create Credentials →
     Service Account → đặt tên (vd 'traffic-fb') → Create → Done
  5. Bấm vào service account vừa tạo → tab Keys → Add Key → Create New Key →
     JSON → file tải về CHÍNH LÀ file credentials.

BƯỚC 2 — Đặt file credentials:
  - Đổi tên file thành:  google_sheets_creds.json
  - Bỏ vào thư mục dự án (c:\traffic fb)

BƯỚC 3 — Tạo Google Sheet:
  - Mở https://sheets.new  → đặt tên vd 'Traffic Facebook'
  - Nút Chia sẻ → dán email service account (trong file creds, dòng
    'client_email') → quyền Editor → Gửi
  - Sao chép ID từ URL:  https://docs.google.com/spreadsheets/d/<ID>/edit
    (đoạn giữa /d/ và /edit)

BƯỚC 4 — Điền vào config.json:
  - sheets.spreadsheet_id : <ID vừa sao chép>
  - ai.provider + ai.api_key : hãng AI và key của bạn

Rồi chạy lại:  python google_sheets.py --setup
sẽ TỰ TẠO 4 sheet (PAGE CONFIG, SOURCE CONFIG, CONTENT POOL,
PAGE PERFORMANCE) kèm tiêu đề cột sẵn.
""")


def tao_4_sheet(store):
    """Đảm bảo 4 sheet có sẵn với đúng tiêu đề cột (chạy được cho cả 2 chế độ).

    Chế độ Google: lay_tat_ca() tự tạo worksheet + dòng header nếu chưa có.
    Chế độ Local:  header do schema cung cấp — không cần tạo gì."""
    for ten in CAC_COT:
        store.lay_tat_ca(ten)
    print(f"  [✓] Đã chuẩn bị 4 sheet trên: {store.mo_ta()}")


if __name__ == "__main__":
    import sys

    if "--setup" in sys.argv:
        cfg = load_config()
        creds = os.path.join(DUONG_DAN, cfg["sheets"]["credentials_file"])
        if not os.path.isfile(creds) or not cfg["sheets"]["spreadsheet_id"]:
            huong_dan_google_sheets()
        else:
            try:
                store = lay_store()
                tao_4_sheet(store)
                print("  ✅ Xong! Mở Google Sheets để kiểm tra 4 sheet.")
            except Exception as e:
                print(f"  [!] Lỗi khi kết nối Google Sheets: {e}")
                print("     Kiểm tra lại credentials_file và spreadsheet_id.")
        sys.exit(0)

    # chạy thường: in ra chế độ đang dùng
    store = lay_store()
    print(f"Đang dùng chế độ: {store.mo_ta()}")
    for ten in TEN_SHEET:
        print(f"  - {ten}: {store.so_dong(ten)} dòng")
