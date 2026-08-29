#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cào dữ liệu Facebook Page (text + ảnh) bằng thư viện facebook-scraper.

Cách dùng (CLI):
    python scraper.py --page ten-trang --pages 5
    python scraper.py --page trangA trangB trangC --per-page 50
    python scraper.py --page ten-trang --cookies cookies.txt

Hoặc qua giao diện web:
    python webui.py   (mở http://127.0.0.1:5000)

Kết quả:
    - <output>.xlsx              : 1 file Excel chứa tất cả (sheet Tổng quan + 1 sheet/trang)
    - <output>_<trang>.json      : dữ liệu thô từng trang
    - du_lieu_images/<giờ-cào>_images/ : TẤT CẢ ảnh của lần cào (1 thư mục duy nhất
                                         theo giờ cào, nằm trong du_lieu_images/)
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime

import requests
try:
    from facebook_scraper import get_posts, set_cookies
except ImportError:
    get_posts = None
    set_cookies = None

import cao_fb  # engine cào mới: mở trình duyệt thật (Playwright + Edge/Chrome)

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def in_tu_page(page_arg: str) -> str:
    """Trích tên/ID trang từ URL hoặc tên trực tiếp.

    Xử lý cả link dạng profile.php?id=... (không bị cắt mất phần ?id=)."""
    m = re.search(r"facebook\.com/(profile\.php\?id=\d+)", page_arg)
    if m:
        return m.group(1)
    m = re.search(r"facebook\.com/([^/?]+)", page_arg)
    return m.group(1) if m else page_arg.strip("/").split("/")[-1]


def nghi_stop(giay: float, stop_flag=None):
    """Ngủ theo từng phần nhỏ (0.2s) để bấm Dừng là dừng được ngay,
    không phải đợi hết cả khoảng nghỉ."""
    if giay <= 0:
        return
    da_ngu = 0.0
    while da_ngu < giay:
        if stop_flag and stop_flag.is_set():
            return
        time.sleep(min(0.2, giay - da_ngu))
        da_ngu += 0.2


def load_cookies(path: str):
    """Đọc cookies.txt — hỗ trợ 3 định dạng:
    1. JSON (Cookie-Editor / Firefox / 'Get cookies.txt LOCALLY' dạng mới):
       [{"name": "...", "value": "...", "domain": "...", ...}]
    2. Netscape (extension cũ): tab-separated, 7 cột
    3. document.cookie từ DevTools: cac cap ten=giatri phan cach bang ';'
    """
    if not path or not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        noi_dung = f.read().strip()
    cookies = {}

    # --- 1. Định dạng JSON ---
    if noi_dung.startswith("["):
        try:
            danh_sach = json.loads(noi_dung)
            if isinstance(danh_sach, list):
                for c in danh_sach:
                    if isinstance(c, dict) and c.get("name") and c.get("value"):
                        cookies[c["name"]] = c["value"]
        except json.JSONDecodeError:
            cookies = {}  # không phải JSON hợp lệ -> thử định dạng khác

    # --- 2. Netscape hoặc document.cookie ---
    if not cookies:
        for line in noi_dung.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 7:  # dinh dang Netscape
                cookies[parts[5]] = parts[6]
            elif "=" in line:    # dinh dang document.cookie
                for cap in line.split(";"):
                    cap = cap.strip()
                    if "=" in cap:
                        k, v = cap.split("=", 1)
                        cookies[k.strip()] = v.strip()

    if cookies:
        if set_cookies:
            set_cookies(cookies)
        print(f"  [i] Đã nạp {len(cookies)} cookie từ {path}")
        # kiểm tra các cookie quan trọng để cào được
        thieu = [c for c in ("c_user", "xs", "datr") if c not in cookies]
        if thieu:
            print(f"  [!] Cảnh báo: thiếu cookie quan trọng: {', '.join(thieu)} "
                  f"— có thể vẫn không cào được")
        return cookies
    else:
        print(f"  [!] Không đọc được cookie nào từ {path}")
        return {}


def an_toan_ten_file(name: str) -> str:
    """Loại ký tự không hợp lệ trong tên file."""
    return re.sub(r'[\\/:*?"<>|]', "_", name)


def phat_su_kien(callback, su_kien: dict):
    """Gửi sự kiện cho callback (web UI) nếu có — CLI thì bỏ qua."""
    if callback:
        callback(su_kien)


def tai_anh(url: str, thumuc: str, ten_file: str) -> str | None:
    """Tải một ảnh về thư mục, trả về đường dẫn đã lưu (None nếu lỗi)."""
    try:
        resp = requests.get(url, headers={"User-Agent": DEFAULT_UA}, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"    [!] Lỗi tải ảnh {ten_file}: {e}")
        return None

    ext = ".jpg"
    ct = resp.headers.get("Content-Type", "")
    if "png" in ct:
        ext = ".png"
    elif "gif" in ct:
        ext = ".gif"
    elif "webp" in ct:
        ext = ".webp"

    path = os.path.join(thumuc, ten_file + ext)
    with open(path, "wb") as f:
        f.write(resp.content)
    return path


def xu_ly_post(post: dict, thumuc_anh: str | None, stt: int, tong: int,
               callback=None) -> dict:
    """Chuyển một post của facebook-scraper thành dict gọn, sạch và lưu ảnh."""
    post_id = post.get("post_id") or f"post_{stt}"
    text = (post.get("text") or "").strip()
    hashtags = re.findall(r"#[^\s#]+", text)

    # --- Ảnh: lấy tất cả link ảnh trong bài ---
    image_urls = list(dict.fromkeys(post.get("images") or []))

    anh_da_luu = []
    if thumuc_anh and image_urls:
        os.makedirs(thumuc_anh, exist_ok=True)
        for i, url in enumerate(image_urls):
            print(f"    [↓] Tải ảnh {i + 1}/{len(image_urls)} ...")
            # Tất cả ảnh nằm chung 1 thư mục (tên file có post_id để khỏi trùng)
            path = tai_anh(url, thumuc_anh,
                           f"{an_toan_ten_file(str(post_id))}_{i + 1}")
            if path:
                anh_da_luu.append(path)
            phat_su_kien(callback, {
                "loai": "anh", "post_id": post_id,
                "so_thu_tu": i + 1, "tong": len(image_urls),
                "duong_dan": path,
            })

    time_post = post.get("time")
    if isinstance(time_post, datetime):
        time_post = time_post.isoformat()

    print(
        f"  [✓] #{stt} | ID: {post_id} | {time_post} | "
        f"text {len(text)} ký tự | {len(image_urls)} ảnh | "
        f"{len(hashtags)} hashtag"
    )

    return {
        "post_id": post_id,
        "time": time_post,
        "text": text,
        "hashtags": hashtags,          # ví dụ: ['#PUBG', '#PUBGVN']
        "images": image_urls,          # link ảnh gốc trên Facebook
        "images_da_tai": anh_da_luu,   # đường dẫn ảnh đã tải về máy
        "post_url": post.get("post_url"),
        "likes": post.get("likes"),        # tổng số cảm xúc
        "comments": post.get("comments"),  # số bình luận
        "shares": post.get("shares"),      # số lượt chia sẻ
        "diem_tiem_nang": 0,               # điểm tương tác (tính sau)
        "muc_tiem_nang": "—",              # CAO / TRUNG_BINH / THAP (tính sau)
    }


def danh_gia_tiem_nang(posts: list):
    """Chấm điểm tương tác và xếp hạng tiềm năng cho từng bài.

    Công thức: diem = likes + comments*2 + shares*3
    (bình luận và chia sẻ nặng hơn like vì thể hiện tương tác sâu).
    Xếp hạng theo thứ hạng trong chính trang đó:
    - Top 25%  -> CAO
    - 25-60%   -> TRUNG_BINH
    - còn lại  -> THAP
    """
    if len(posts) < 5:
        return  # quá ít bài, không đủ cơ sở xếp hạng
    for p in posts:
        like = p.get("likes") or 0
        cmt = p.get("comments") or 0
        share = p.get("shares") or 0
        p["diem_tiem_nang"] = like + cmt * 2 + share * 3

    posts.sort(key=lambda p: p["diem_tiem_nang"], reverse=True)
    if not posts or posts[0]["diem_tiem_nang"] == 0:
        return  # tất cả đều 0 tương tác -> không xếp hạng

    n = len(posts)
    for i, p in enumerate(posts):
        phan_tram = (i + 1) / n
        if phan_tram <= 0.25:
            p["muc_tiem_nang"] = "CAO"
        elif phan_tram <= 0.60:
            p["muc_tiem_nang"] = "TRUNG_BINH"
        else:
            p["muc_tiem_nang"] = "THAP"


def in_top_tiem_nang(posts: list, top_n: int = 5):
    """In danh sách bài tiềm năng nhất ra màn hình."""
    print(f"\n  🏆 Top {min(top_n, len(posts))} bài TIỀM NĂNG nhất:")
    for i, p in enumerate(posts[:top_n]):
        print(
            f"    {i + 1}. [{p['muc_tiem_nang']}] điểm {p['diem_tiem_nang']} "
            f"(cảm xúc {p['likes']}, bình luận {p['comments']}, chia sẻ {p['shares']})"
        )
        if p["text"]:
            print(f"       {p['text'][:100]}{'...' if len(p['text']) > 100 else ''}")
        print(f"       {p['post_url']}")


def ghi_json(posts: list, ten_file: str):
    """Ghi file JSON lưu trữ dữ liệu thô."""
    json_path = f"{ten_file}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)
    return json_path


def ghi_excel(ket_qua: dict, ten_file: str) -> str:
    """Xuất TOÀN BỘ dữ liệu ra 1 file Excel .xlsx (engine xlsxwriter).

    - Sheet 'Tổng quan': thống kê từng trang + Top 10 bài tiềm năng nhất toàn bộ
    - 1 sheet cho mỗi trang: từng bài kèm cảm xúc, bình luận, chia sẻ,
      điểm tiềm năng (tô màu: CAO xanh lá / TRUNG_BINH vàng / THAP xám),
      đường dẫn ảnh đã tải, link bài bấm được.
    """
    import xlsxwriter

    cot = [
        ("STT", 5), ("post_id", 16), ("Thời gian", 20), ("Nội dung bài viết", 65),
        ("Cảm xúc", 11), ("Bình luận", 11), ("Chia sẻ", 10),
        ("Điểm tiềm năng", 13), ("Mức tiềm năng", 14),
        ("Ảnh đã tải (đường dẫn)", 50), ("Link bài viết", 16),
    ]

    xlsx_path = f"{ten_file}.xlsx"
    thumuc = os.path.dirname(xlsx_path)
    if thumuc:
        os.makedirs(thumuc, exist_ok=True)

    wb = xlsxwriter.Workbook(xlsx_path)

    # ---------- Các định dạng (format) ----------
    header_format = wb.add_format({
        "bold": True, "font_color": "#FFFFFF", "bg_color": "#1F4E78",
        "align": "center", "valign": "vcenter",
        "border": 1, "border_color": "#D9D9D9",
    })
    text_format = wb.add_format({
        "valign": "top", "border": 1, "border_color": "#D9D9D9",
    })
    num_format = wb.add_format({
        "valign": "top", "border": 1, "border_color": "#D9D9D9",
    })
    wrap_format = wb.add_format({
        "text_wrap": True, "valign": "top", "border": 1, "border_color": "#D9D9D9",
    })
    link_format = wb.add_format({
        "font_color": "#0563C1", "underline": 1,
        "valign": "top", "border": 1, "border_color": "#D9D9D9",
    })
    title_format = wb.add_format({"bold": True, "font_size": 14})
    bold_13 = wb.add_format({"bold": True, "font_size": 13})
    italic_gray = wb.add_format({"italic": True, "font_color": "#64748B"})
    tier_format = {
        "CAO": wb.add_format({"bg_color": "#C6EFCE", "font_color": "#006100",
                              "bold": True, "valign": "top",
                              "border": 1, "border_color": "#D9D9D9"}),
        "TRUNG_BINH": wb.add_format({"bg_color": "#FFEB9C", "font_color": "#9C6500",
                                     "bold": True, "valign": "top",
                                     "border": 1, "border_color": "#D9D9D9"}),
        "THAP": wb.add_format({"bg_color": "#F2F2F2", "font_color": "#808080",
                               "valign": "top", "border": 1, "border_color": "#D9D9D9"}),
    }

    def ke_dong_dau(ws, headers):
        """Tô header, kẻ khung, lọc tự động, đóng băng dòng đầu."""
        for c, (tieu_de, _) in enumerate(headers):
            ws.write(0, c, tieu_de, header_format)
        ws.freeze_panes(1, 0)
        ws.autofilter(0, 0, 0, len(headers) - 1)
        for c, (_, rong) in enumerate(headers):
            ws.set_column(c, c, rong)

    def ghi_mot_bai(ws, r, post):
        """Ghi 1 bài vào dòng r (0-based; dòng 0 là header)."""
        ws.write_number(r, 0, r, num_format)  # STT
        ws.write(r, 1, post.get("post_id"), text_format)
        ws.write(r, 2, post.get("time"), text_format)
        # Hashtag được ghi NGAY TRONG ô nội dung, xuống dòng phía dưới bài viết
        text = post.get("text") or ""
        hashtags = " ".join(post.get("hashtags") or [])
        noi_dung = text + ("\n\n" + hashtags if hashtags else "")
        ws.write(r, 3, noi_dung, wrap_format)
        # Chiều cao dòng theo lượng chữ — nếu không đặt, Excel chỉ hiện 1 dòng
        # đầu của mỗi bài (text vẫn đầy đủ trong ô nhưng bị ẩn).
        # Cột rộng 65 -> ~60 ký tự/dòng. Excel giới hạn dòng 409.5pt.
        so_dong = max(1, -(-len(noi_dung) // 60))
        chieu_cao = min(so_dong * 15 + 4, 409.5)
        ws.write_number(r, 4, post.get("likes") or 0, num_format)
        ws.write_number(r, 5, post.get("comments") or 0, num_format)
        ws.write_number(r, 6, post.get("shares") or 0, num_format)
        ws.write_number(r, 7, post.get("diem_tiem_nang") or 0, num_format)
        muc = post.get("muc_tiem_nang") or "—"
        if muc in tier_format:
            ws.write(r, 8, muc, tier_format[muc])
        else:
            ws.write(r, 8, muc, text_format)
        # Đường dẫn ẢNH ĐẦY ĐỦ trên máy
        # (VD: C:\traffic fb\du_lieu_images\du_lieu_2026-08-24_09-27-08_images\post_id_1.jpg)
        cac_anh = [os.path.abspath(x) for x in (post.get("images_da_tai") or [])]
        ws.write(r, 9, "\n".join(cac_anh), wrap_format)
        if cac_anh:
            # dòng cao thêm nếu nhiều ảnh
            chieu_cao = max(chieu_cao, min(len(cac_anh) * 15 + 4, 409.5))
        # Link bài viết: dán URL THẬT vào ô (bấm vẫn mở được Facebook)
        url = post.get("post_url")
        if url:
            ws.write_url(r, 10, url, link_format, url)
        else:
            ws.write(r, 10, "—", text_format)
        ws.set_row(r, chieu_cao)

    # ================= Sheet Tổng quan =================
    ws = wb.add_worksheet("Tổng quan")
    ws.write(0, 0, "TỔNG QUAN CÁC TRANG ĐÃ CÀO", title_format)

    tieu_de_tong_quan = ["Trang", "Số bài", "Tổng cảm xúc", "Tổng bình luận",
                         "Tổng chia sẻ", "Tổng điểm", "Bài hay nhất"]
    for c, td in enumerate(tieu_de_tong_quan):
        ws.write(2, c, td, header_format)
    ws.set_column(0, 0, 30)
    for col in range(1, 6):
        ws.set_column(col, col, 15)
    ws.set_column(6, 6, 45)

    r = 3
    tat_ca = []
    for page, posts in ket_qua.items():
        tong_diem = sum((p.get("diem_tiem_nang") or 0) for p in posts)
        bai_hay = posts[0] if posts and posts[0].get("post_url") else None
        ws.write(r, 0, page, text_format)
        ws.write_number(r, 1, len(posts), num_format)
        ws.write_number(r, 2, sum(p.get("likes") or 0 for p in posts), num_format)
        ws.write_number(r, 3, sum(p.get("comments") or 0 for p in posts), num_format)
        ws.write_number(r, 4, sum(p.get("shares") or 0 for p in posts), num_format)
        ws.write_number(r, 5, tong_diem, num_format)
        if bai_hay:
            ws.write_url(r, 6, bai_hay["post_url"], link_format,
                         (bai_hay.get("text") or "")[:60] or bai_hay["post_id"])
        tat_ca.extend((p | {"_trang": page}) for p in posts)
        r += 1

    r += 1
    ws.write(r, 0, "→ Cảm xúc / bình luận / chia sẻ CỦA TỪNG BÀI: mở sheet riêng của mỗi trang "
                   "(tab phía dưới, đặt tên theo trang)", italic_gray)
    r += 1
    ws.write(r, 0, "TOP 10 BÀI TIỀM NĂNG NHẤT TOÀN BỘ", bold_13)
    r += 1
    tieu_de_top = ["STT", "Trang", "post_id", "Nội dung", "Điểm", "Mức", "Link"]
    for c, td in enumerate(tieu_de_top):
        ws.write(r, c, td, header_format)
    r += 1
    for i, p in enumerate(sorted(tat_ca, key=lambda x: x.get("diem_tiem_nang") or 0, reverse=True)[:10], 1):
        ws.write_number(r, 0, i, num_format)
        ws.write(r, 1, p.get("_trang"), text_format)
        ws.write(r, 2, p.get("post_id"), text_format)
        ws.write(r, 3, (p.get("text") or "")[:100], text_format)
        ws.write_number(r, 4, p.get("diem_tiem_nang") or 0, num_format)
        muc = p.get("muc_tiem_nang") or "—"
        if muc in tier_format:
            ws.write(r, 5, muc, tier_format[muc])
        else:
            ws.write(r, 5, muc, text_format)
        if p.get("post_url"):
            ws.write_url(r, 6, p["post_url"], link_format, "Mở bài viết")
        r += 1

    # ================= Sheet từng trang =================
    for page, posts in ket_qua.items():
        ten_sheet = re.sub(r'[\\/*?:\[\]]', "_", page)[:31] or "trang"
        ws = wb.add_worksheet(ten_sheet)
        ke_dong_dau(ws, cot)
        for i, post in enumerate(posts, 1):  # dòng 1 = dòng dữ liệu đầu (0-based)
            ghi_mot_bai(ws, i, post)

    wb.close()
    return xlsx_path


def cào_mot_trang(page: str, pages_scroll: int, limit: int, thumuc_anh: str | None,
                  delay: float, callback=None, stop_flag=None,
                  cookies_playwright: list = None) -> list:
    """Cào một trang, trả về danh sách post đã xử lý.

    - Có cookies -> dùng engine mới (cao_fb): mở trình duyệt thật, cuộn, đọc DOM.
    - Không có cookies -> thử thư viện facebook-scraper cũ (thường bị FB chặn).
    """
    posts = []
    phat_su_kien(callback, {"loai": "trang_bat_dau", "page": page, "gioi_han": limit})
    try:
        if cookies_playwright:
            bai_tho = cao_fb.cào_trang(
                page, so_bai=limit or 0, so_lan_cuon=pages_scroll,
                delay=delay, cookies=cookies_playwright,
                stop_flag=stop_flag, callback=callback,
            )
            for bai in bai_tho:
                if stop_flag and stop_flag.is_set():
                    print(f"  [i] Đã dừng theo yêu cầu tại trang {page}")
                    break
                post_da_xu_ly = xu_ly_post(bai, thumuc_anh, len(posts) + 1,
                                           limit or "?", callback=callback)
                posts.append(post_da_xu_ly)
                phat_su_kien(callback, {
                    "loai": "post", "page": page, "post": post_da_xu_ly,
                    "stt": len(posts), "tong": limit or None,
                })
                if limit and len(posts) >= limit:
                    break
                nghi_stop(delay, stop_flag)
        elif get_posts:
            for post in get_posts(
                page,
                pages=pages_scroll,
                options={"posts_per_page": 200},
            ):
                if stop_flag and stop_flag.is_set():
                    print(f"  [i] Đã dừng theo yêu cầu tại trang {page}")
                    break
                post_da_xu_ly = xu_ly_post(post, thumuc_anh, len(posts) + 1,
                                           limit or "?", callback=callback)
                posts.append(post_da_xu_ly)
                phat_su_kien(callback, {
                    "loai": "post", "page": page, "post": post_da_xu_ly,
                    "stt": len(posts), "tong": limit or None,
                })
                if limit and len(posts) >= limit:
                    break
                nghi_stop(delay, stop_flag)
        else:
            raise RuntimeError(
                "Thiếu cookies và thư viện cũ. Hãy xuất cookies.txt rồi chạy lại.")
    except Exception as e:
        print(f"\n[!] Lỗi khi cào: {e}")
        phat_su_kien(callback, {"loai": "loi", "page": page, "noi_dung": str(e)})
        raise
    phat_su_kien(callback, {"loai": "trang_xong", "page": page, "so_bai": len(posts)})
    return posts


def run_cào(trang_ho: list, pages: int = 3, limit: int = 0, per_page: int = 0,
            output: str = "du_lieu", no_images: bool = False, images_dir: str = None,
            cookies: str = None, delay: float = 3.0,
            callback=None, stop_flag=None):
    """Phần lõi cào — dùng chung cho CLI (main) và Web UI.

    Trả về (ket_qua, xlsx_path) với ket_qua = {trang: [posts]}.
    Mỗi bước đều gửi sự kiện qua callback nếu có.
    """
    print(f"=== Cào {len(trang_ho)} trang: {', '.join(trang_ho)} ===")
    print(f"    {pages} lần cuộn/trang, tối đa {per_page or limit or 'không'} bài/trang")
    cookies_playwright = cao_fb.doc_cookies(cookies) if cookies else None

    # 1 lần cào = 1 giờ cào — dùng chung cho cả thư mục ảnh và tên file Excel
    thoi_gian_cao = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # TẤT CẢ ảnh của lần cào nằm trong MỘT thư mục đặt tên theo giờ cào,
    # và thư mục đó nằm BÊN TRONG du_lieu_images/
    # (VD: du_lieu_images/du_lieu_2026-08-24_09-52-42_images/)
    thumuc_anh = None if no_images else (
        images_dir or os.path.join("du_lieu_images",
                                   f"{output}_{thoi_gian_cao}_images"))

    ket_qua = {}
    for i, page in enumerate(trang_ho):
        print(f"\n----- Trang {i + 1}/{len(trang_ho)}: {page} -----")
        page_id_sach = an_toan_ten_file(in_tu_page(page))
        ten_file = output if len(trang_ho) == 1 else f"{output}_{page_id_sach}"

        posts = cào_mot_trang(page, pages, per_page or limit, thumuc_anh, delay,
                              callback=callback, stop_flag=stop_flag,
                              cookies_playwright=cookies_playwright)

        if posts:
            danh_gia_tiem_nang(posts)
            in_top_tiem_nang(posts)
        else:
            phat_su_kien(callback, {"loai": "khong_bai", "page": page})

        json_path = ghi_json(posts, ten_file)
        print(f"  ✅ {page}: {len(posts)} bài -> {json_path}")
        if thumuc_anh:
            print(f"     Ảnh: {thumuc_anh}")
        ket_qua[page] = posts

        if i < len(trang_ho) - 1 and delay > 0:
            print(f"  ... nghỉ {delay}s trước khi sang trang tiếp theo")
            nghi_stop(delay, stop_flag)

    # Mỗi lần chạy = 1 file Excel RIÊNG trong folder 'du_lieu_exel'
    # (kèm giờ phút để không ghi đè lần chạy trước — cùng giờ với thư mục ảnh)
    ten_xlsx = f"du_lieu_exel/{output}_{thoi_gian_cao}"
    xlsx_path = ghi_excel(ket_qua, ten_xlsx)

    print(f"\n=== HOÀN THÀNH: {sum(len(p) for p in ket_qua.values())} bài viết từ {len(ket_qua)} trang ===")
    for page, posts in ket_qua.items():
        print(f"  - {page}: {len(posts)} bài")
    print(f"\n📊 MỞ FILE EXCEL: {xlsx_path}")
    print("   (sheet 'Tổng quan' = thống kê + top 10 tiềm năng; 1 sheet/trang)")
    return ket_qua, xlsx_path


def main():
    parser = argparse.ArgumentParser(
        description="Cào bài viết + ảnh từ nhiều Facebook Page (trang public)."
    )
    parser.add_argument(
        "--page", nargs="+", required=True,
        help="Tên hoặc URL trang — ghi được NHIỀU trang, cách nhau bằng dấu cách",
    )
    parser.add_argument(
        "--pages", type=int, default=3,
        help="Số lần cuộn cho mỗi trang (mỗi lần ~200 bài, mặc định 3)",
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Giới hạn số bài (0 = không giới hạn)",
    )
    parser.add_argument(
        "--per-page", type=int, default=0,
        help="Giới hạn số bài cho MỖI trang (0 = dùng --limit)",
    )
    parser.add_argument(
        "--output", default="du_lieu",
        help="Tiền tố tên file đầu ra, mặc định: du_lieu (file: du_lieu_<trang>.json + du_lieu.xlsx)",
    )
    parser.add_argument(
        "--images-dir", default=None,
        help="Thư mục lưu ảnh (mặc định: du_lieu_images/<tiền tố>_<giờ-cào>_images — tất cả ảnh 1 lần cào)",
    )
    parser.add_argument(
        "--no-images", action="store_true",
        help="Không tải ảnh, chỉ lấy link ảnh",
    )
    parser.add_argument(
        "--cookies", default=None,
        help="File cookies.txt (bắt buộc vì FB chặn truy cập ẩn danh)",
    )
    parser.add_argument(
        "--delay", type=float, default=3.0,
        help="Giây nghỉ giữa mỗi lần cuộn và giữa các trang (giảm rủi ro bị chặn)",
    )
    args = parser.parse_args()

    trang_ho = [in_tu_page(p) for p in args.page]
    ket_qua, xlsx_path = run_cào(
        trang_ho, pages=args.pages, limit=args.limit, per_page=args.per_page,
        output=args.output, no_images=args.no_images, images_dir=args.images_dir,
        cookies=args.cookies, delay=args.delay,
    )

    if not any(ket_qua.values()):
        print("\n[!] Không lấy được bài nào. Facebook hiện CHẶN truy cập ẩn danh (không đăng nhập).")
        print("    Giải pháp: xuất cookies từ trình duyệt đang đăng nhập Facebook rồi chạy lại:\n")
        print("    Cách 1 - Dùng extension (dễ nhất):")
        print("        Cài 'Get cookies.txt LOCALLY' cho Chrome/Edge (miễn phí trên store),")
        print("        mở trang facebook.com -> bấm icon extension -> Export -> lưu cookies.txt")
        print("    Cách 2 - Tự copy từ DevTools:")
        print("        Mở facebook.com (đã đăng nhập) -> F12 -> Console, dán lệnh:")
        print("        copy(document.cookie) -> lưu vào cookies.txt dạng:  ten_cookie\tgia_tri  (mỗi dòng 1 cặp)\n")
        print(f"    Sau đó chạy:")
        print(f"        python scraper.py --page {' '.join(trang_ho)} --cookies cookies.txt")
        sys.exit(1)


if __name__ == "__main__":
    main()
