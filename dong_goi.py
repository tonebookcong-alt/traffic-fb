# -*- coding: utf-8 -*-
"""
Module DONG_GOI — Xuất gói bài đã xử lý ra file CSV phân loại.

Mỗi lần chạy luồng "Cào → Viết lại → Chỉnh ảnh → Đóng gói", tool gom toàn bộ
bài đã qua xử lý (Status = WEB_POSTED / DONE) thành MỘT file CSV có đủ cột để
phân loại (KEY, Nhân vật/chủ đề, Nguồn, Caption, Link bài báo, Đường dẫn ảnh...).

Caption trong CSV được ép về 1 dòng (phẳng) để mở được ở mọi tool / Excel.
Bản caption nhiều dòng đầy đủ vẫn nằm trong thư mục du_lieu_fb/<ngày-giờ>/
dạng caption_<content_id>.txt (do luong_b xuất khi xử lý bài).
"""

import csv
import json
import os
import re
from datetime import datetime

from config import DUONG_DAN
from google_sheets import lay_store
from media import tao_thu_muc_ngay_gio

# Cột CSV xuất ra — thứ tự này cũng là header của file.
COT_CSV = [
    "Content ID", "KEY", "Nhân vật/chủ đề", "Nguồn", "Thời gian đăng",
    "Cảm xúc", "Bình luận", "Chia sẻ",
    "Caption gốc", "Caption mới", "Link bài báo", "Đường dẫn ảnh", "Status",
]

# Những trạng thái coi là "đã xử lý xong" để đưa vào gói đóng gói.
TRANG_THAI_DONG_GOI = ("WEB_POSTED", "DONE", "SAN_SANG", "HOAN_THANH")


def _doc_bo_bai() -> dict:
    """Quét toàn bộ du_lieu_fb/ lấy map {content_id: bo_bai_json}.

    Tái dùng đúng cách `luong_b.lay_danh_sach_san_sang` quét thư mục.
    """
    map_goi = {}
    fb_dir = os.path.join(DUONG_DAN, "du_lieu_fb")
    if not os.path.exists(fb_dir):
        return map_goi
    for root, _, files in os.walk(fb_dir):
        for f in files:
            if f.startswith("bo_bai_") and f.endswith(".json"):
                cid = f.replace("bo_bai_", "").replace(".json", "")
                try:
                    with open(os.path.join(root, f), "r", encoding="utf-8") as fp:
                        map_goi[cid] = json.load(fp)
                except Exception:
                    pass
    return map_goi


def lam_phang_caption(text) -> str:
    """Ép caption về 1 dòng: thay mọi dòng mới bằng 1 dấu cách, gộp space thừa."""
    if not text:
        return ""
    s = str(text)
    s = re.sub(r"\s*\n\s*", " ", s)
    s = re.sub(r"[ \t]+", " ", s).strip()
    return s


def chon_caption_xuat(goi, row) -> str:
    """Chọn đúng 1 caption để xuất (Excel/CSV).

    - Ưu tiên `caption_lua_chon` (bản người dùng đã chọn) trong gói.
    - Nếu chưa chọn → dùng `Caption mới`.
    - Nếu chuỗi vẫn là khối nhiều version (dữ liệu cũ/trường hợp lỗi) →
      tách và lấy VERSION 1 (mặc định).
    Trả về caption đã ép về 1 dòng.
    """
    from viet_lai import tach_3_version

    cap = (goi or {}).get("caption_lua_chon") or (row or {}).get("Caption mới") or ""
    cap = str(cap).strip()
    if not cap:
        return ""
    # Nếu còn lẫn nhiều version → tách lấy bản mặc định (VERSION 1)
    if re.search(r"(?:VERSION|PHI[ÊE]N BẢN)\s*[123]\b", cap, re.IGNORECASE):
        cap = tach_3_version(cap).get("version_1") or cap
    return lam_phang_caption(cap)


def tao_csv_full(store=None, danh_sach=None) -> dict:
    """Gom bài đã xử lý ra file CSV.

    - store     : store dữ liệu (mặc định lay_store()). Nếu danh_sach=None,
                  lấy TẤT CẢ bài Status ∈ (WEB_POSTED, DONE).
    - danh_sach : nếu truyền (list content_id), chỉ lấy đúng các bài đó
                  (bất kể Status) — dùng khi đóng gói theo lựa chọn.

    Trả về {"ok": True, "csv_path": ..., "so_dong": ..., "thu_muc": ...}.
    """
    store = store or lay_store()
    rows = store.lay_tat_ca("CONTENT POOL")
    map_goi = _doc_bo_bai()

    ds = []
    for row in rows:
        cid = str(row.get("Content ID") or "").strip()
        if not cid:
            continue
        st = str(row.get("Status") or "NEW").strip()
        if danh_sach:
            if cid not in danh_sach:
                continue
        else:
            if st not in TRANG_THAI_DONG_GOI:
                continue

        goi = map_goi.get(cid) or {}
        ds.append({
            "Content ID": cid,
            "KEY": row.get("KEY") or "",
            "Nhân vật/chủ đề": row.get("Nhân vật/chủ đề") or "",
            "Nguồn": row.get("Source") or "",
            "Thời gian đăng": row.get("Thời gian đăng") or "",
            "Cảm xúc": row.get("Cảm xúc") or 0,
            "Bình luận": row.get("Bình luận") or 0,
            "Chia sẻ": row.get("Chia sẻ") or 0,
            "Caption gốc": lam_phang_caption(row.get("Caption") or ""),
            "Caption mới": chon_caption_xuat(goi, row),
            "Link bài báo": goi.get("article_url") or row.get("Article URL") or "",
            "Đường dẫn ảnh": goi.get("anh_path") or row.get("Media") or "",
            "Status": st,
        })

    thu_muc = tao_thu_muc_ngay_gio()
    csv_path = os.path.join(
        thu_muc, f"goi_full_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

    # utf-8-sig: thêm BOM để Excel mở tiếng Việt không bị lỗi font.
    # newline="" + lineterminator="\n": chuẩn CSV, không kéo thêm \r.
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL, lineterminator="\n")
        w.writerow(COT_CSV)
        for r in ds:
            w.writerow([r.get(c, "") for c in COT_CSV])

    return {"ok": True, "csv_path": csv_path, "so_dong": len(ds), "thu_muc": thu_muc}


if __name__ == "__main__":
    res = tao_csv_full()
    print(json.dumps(res, ensure_ascii=False, indent=2))
