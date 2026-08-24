# -*- coding: utf-8 -*-
"""
LUỒNG A — THU THẬP CONTENT.

Đọc SOURCE CONFIG (KEY + Facebook nguồn + nhân vật gợi ý) → cào bài mới
mỗi nguồn (cao_fb, trình duyệt thật) → chống trùng với Content Pool →
AI nhận diện nhân vật/chủ đề → lưu vào CONTENT POOL (status NEW) →
đánh dấu content hết hạn.

Chạy:  python luong_a.py
       python luong_a.py --so-bai 5 --delay 2     (tùy chỉnh cho nhanh)
"""

import argparse
import os
import sys
import time

from config import DUONG_DAN, load_config
from google_sheets import lay_store
from content_pool import chuan_hoa_text, chong_trung, them_content, danh_dau_het_han
from nhan_dien import nhan_dien_nhan_vat

sys.path.insert(0, DUONG_DAN)
import cao_fb  # noqa: E402
import scraper  # noqa: E402  (dùng load_cookies)


def _cookies_playwright():
    """Đọc cookies.txt -> list cookie cho Playwright (định dạng cao_fb cần)."""
    cfg = load_config()
    ten_file = cfg.get("cookies_file") or "cookies.txt"
    cookies_dict = scraper.load_cookies(os.path.join(DUONG_DAN, ten_file))
    if not cookies_dict:
        print(f"[!] Không đọc được cookies từ '{ten_file}' — cào sẽ thất bại.")
    return [
        {"name": k, "value": v, "domain": ".facebook.com", "path": "/"}
        for k, v in cookies_dict.items()
    ]


def _goi_y_nhan_vat(caption: str, key: str, goi_y: list):
    """Nhận diện nhân vật — có lỗi AI thì không chặn luồng, dùng 'Khác'."""
    try:
        return nhan_dien_nhan_vat(caption, key, goi_y)
    except Exception as e:
        print(f"    [!] Lỗi nhận diện nhân vật: {e}")
        return "Khác"


def chay_luong_a(so_bai=None, so_lan_cuon=None, delay=None,
                 callback=None, stop_flag=None):
    """Phần lõi Luồng A — dùng chung cho CLI và Web UI.

    Trả về (so_bai_moi, {source: so_bai_cao_duoc}).
    """
    cfg = load_config()
    so_bai = so_bai or cfg["luong_a"]["so_bai_moi_nguon"] or 10
    so_lan_cuon = so_lan_cuon or cfg["luong_a"]["so_lan_cuon"] or 3
    delay = delay if delay is not None else cfg["luong_a"]["delay"] or 3.0

    store = lay_store()
    nguon = store.lay_tat_ca("SOURCE CONFIG")
    nguon = [d for d in nguon if str(d.get("KEY") or "").strip()]

    if not nguon:
        print("[!] SOURCE CONFIG trống — chưa khai báo KEY + nguồn nào.")
        print("    (chế độ Local: sửa file du_lieu_traffic/source_config.json)")
        return 0, {}

    print(f"=== LUỒNG A: {len(nguon)} nguồn, {so_bai} bài/nguồn ===")
    cookies = _cookies_playwright()
    tong_moi = 0
    chi_tiet = {}

    for stt, dong in enumerate(nguon, 1):
        key = str(dong.get("KEY") or "").strip()
        trang = str(dong.get("Facebook nguồn") or "").strip()
        if not trang:
            continue
        goi_y = [g.strip() for g in
                 str(dong.get("Nhân vật gợi ý") or "").split(",") if g.strip()]

        print(f"\n----- [{stt}/{len(nguon)}] KEY='{key}' | nguồn: {trang} -----")
        try:
            bai_tho = cao_fb.cào_trang(
                trang, so_bai=so_bai, so_lan_cuon=so_lan_cuon, delay=delay,
                cookies=cookies, stop_flag=stop_flag, callback=callback,
            )
        except Exception as e:
            print(f"  [!] Lỗi cào '{trang}': {e}")
            continue

        # bỏ bài KHÔNG có chữ (chỉ toàn ảnh) — không viết lại caption được
        bai_tho = [b for b in bai_tho if len(chuan_hoa_text(b.get("text") or "")) >= 5]

        # chống trùng với pool hiện có
        bai_moi = chong_trung(bai_tho, store)
        print(f"  [i] {len(bai_tho)} bài có chữ, "
              f"{len(bai_moi)} bài MỚI (còn lại đã có trong pool)")

        for bai in bai_moi:
            if stop_flag and stop_flag.is_set():
                print("  [i] Đã dừng theo yêu cầu.")
                return tong_moi, chi_tiet
            text = (bai.get("text") or "").strip()
            nhan_vat = _goi_y_nhan_vat(text, key, goi_y)
            them_content(bai, key, nhan_vat, trang, store)
            tong_moi += 1
            print(f"  [✓] +{bai.get('post_id')} | {nhan_vat} | "
                  f"{text[:80]}{'...' if len(text) > 80 else ''}")

        chi_tiet[trang] = len(bai_moi)
        if stt < len(nguon) and delay > 0:
            print(f"  ... nghỉ {delay}s trước nguồn tiếp theo")
            time.sleep(delay)

    # dọn content hết hạn
    so_het_han = danh_dau_het_han(store)
    print(f"\n=== HOÀN THÀNH LUỒNG A: +{tong_moi} bài mới "
          f"({so_het_han} bài hết hạn bị loại) ===")
    return tong_moi, chi_tiet


def main():
    parser = argparse.ArgumentParser(description="Luồng A — thu thập content.")
    parser.add_argument("--so-bai", type=int, default=None, help="Số bài mỗi nguồn")
    parser.add_argument("--pages", type=int, default=None, help="Số lần cuộn")
    parser.add_argument("--delay", type=float, default=None, help="Giây nghỉ")
    args = parser.parse_args()

    try:
        chay_luong_a(so_bai=args.so_bai, so_lan_cuon=args.pages,
                     delay=args.delay)
    except KeyboardInterrupt:
        print("\n[i] Đã dừng thủ công.")


if __name__ == "__main__":
    main()
