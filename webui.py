#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Giao diện web local để quan sát quá trình cào và xem kết quả.

Chạy:  python webui.py
Mở:    http://127.0.0.1:5000

- Tab 'Cào dữ liệu': nhập danh sách trang, bấm Bắt đầu — theo dõi TRỰC TIẾP
  từng bài viết, từng ảnh đang tải qua luồng sự kiện (SSE).
- Tab 'Kết quả': xem toàn bộ bài viết như trong file Excel (ảnh, cảm xúc,
  bình luận, chia sẻ, điểm tiềm năng, mức tiềm năng) + tải file Excel về.
"""

import glob
import json
import os
import queue
import threading
import webbrowser

from flask import (Flask, Response, jsonify, render_template, request,
                   send_file, send_from_directory)

import scraper

app = Flask(__name__)

# ---------------- Trạng thái chung ----------------
QUEUE_SU_KIEN = queue.Queue()
STOP_EVENT = threading.Event()
KHOA = threading.Lock()

TRANG_THAI = {
    "dang_chay": False,
    "xong": False,
    "trang_ho": [],
    "trang_hien_tai": None,
    "so_bai": 0,
    "so_anh": 0,
    "xlsx": None,
    "thong_bao": None,
}


def cap_nhat(**kw):
    with KHOA:
        TRANG_THAI.update(kw)


def emit(su_kien: dict):
    QUEUE_SU_KIEN.put(su_kien)


# ---------------- Luồng cào ----------------
def chay_scraper(trang_ho, per_page, pages, delay, cookies, no_images):
    def cb(s):
        emit(s)
        if s["loai"] == "trang_bat_dau":
            cap_nhat(trang_hien_tai=s["page"], xong=False, thong_bao=None)
        elif s["loai"] == "post":
            with KHOA:
                TRANG_THAI["so_bai"] += 1
        elif s["loai"] == "anh":
            with KHOA:
                TRANG_THAI["so_anh"] += 1

    try:
        ket_qua, xlsx_path = scraper.run_cào(
            trang_ho, pages=pages, per_page=per_page, output="du_lieu",
            no_images=no_images, cookies=cookies, delay=delay,
            callback=cb, stop_flag=STOP_EVENT,
        )
        so_bai = sum(len(p) for p in ket_qua.values())
        cap_nhat(dang_chay=False, xong=True, trang_hien_tai=None, xlsx=xlsx_path,
                 thong_bao=f"✅ Hoàn thành: {so_bai} bài viết từ {len(ket_qua)} trang")
        emit({"loai": "xong", "so_bai": so_bai, "so_trang": len(ket_qua),
              "xlsx": xlsx_path})
    except Exception as e:
        cap_nhat(dang_chay=False, xong=True,
                 thong_bao=f"❌ Lỗi: {e}")
        emit({"loai": "loi", "noi_dung": str(e)})
        emit({"loai": "xong", "so_bai": TRANG_THAI["so_bai"]})


# ---------------- Trang chính ----------------
@app.route("/")
def trang_chu():
    return render_template("index.html")


# ---------------- API: trạng thái hiện tại ----------------
@app.route("/api/trang_thai")
def api_trang_thai():
    with KHOA:
        return jsonify(TRANG_THAI)


# ---------------- API: luồng sự kiện (SSE) ----------------
@app.route("/api/su_kien")
def api_su_kien():
    def luong_su_kien():
        while True:
            try:
                su_kien = QUEUE_SU_KIEN.get(timeout=15)  # 15s heartbeat
            except queue.Empty:
                yield ": heartbeat\n\n"
                continue
            yield f"data: {json.dumps(su_kien, ensure_ascii=False)}\n\n"

    return Response(luong_su_kien(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no"})


# ---------------- API: bắt đầu / dừng cào ----------------
@app.route("/api/cao", methods=["POST"])
def api_cao():
    if TRANG_THAI["dang_chay"]:
        return jsonify({"ok": False, "loi": "Đang cào rồi — hãy đợi xong hoặc bấm Dừng."})

    trang_ho = [scraper.in_tu_page(t.strip()) for t in request.form.get("pages", "").splitlines()
                if t.strip()]
    if not trang_ho:
        return jsonify({"ok": False, "loi": "Chưa nhập trang nào."})

    per_page = int(request.form.get("per_page") or 50)
    pages = int(request.form.get("pages_scroll") or 10)
    delay = float(request.form.get("delay") or 3.0)
    cookies = request.form.get("cookies") or None
    no_images = request.form.get("no_images") == "1"

    STOP_EVENT.clear()
    cap_nhat(dang_chay=True, xong=False, trang_ho=trang_ho, trang_hien_tai=None,
             so_bai=0, so_anh=0, xlsx=None,
             thong_bao=f"Cào {len(trang_ho)} trang, tối đa {per_page} bài/trang...")
    emit({"loai": "bat_dau", "trang_ho": trang_ho, "per_page": per_page,
          "pages": pages, "delay": delay})
    emit({"loai": "log", "noi_dung": f"Bắt đầu cào: {', '.join(trang_ho)} "
                                     f"({per_page} bài/trang, delay {delay}s)"})

    threading.Thread(target=chay_scraper,
                     args=(trang_ho, per_page, pages, delay, cookies, no_images),
                     daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/dung", methods=["POST"])
def api_dung():
    if TRANG_THAI["dang_chay"]:
        STOP_EVENT.set()
        emit({"loai": "log", "noi_dung": "⏹ Đã nhận lệnh dừng — chờ dừng ở bài kế tiếp..."})
        return jsonify({"ok": True})
    return jsonify({"ok": False, "loi": "Không có tiến trình nào đang chạy."})


# ---------------- API: kiểm tra cookies trước khi cào ----------------
@app.route("/api/kiem_tra_cookies", methods=["POST"])
def api_kiem_tra_cookies():
    """Mở trình duyệt thật với cookies.txt, mở facebook.com và xem có đăng
    nhập được không. Trả về kết quả để hiển thị nút 'Kiểm tra cookies'."""
    ten_file = request.form.get("cookies") or "cookies.txt"
    if not os.path.isfile(ten_file):
        return jsonify({"ok": False,
                        "noi_dung": f"Không tìm thấy file '{ten_file}' trong thư mục dự án."})
    try:
        from cao_fb import DEFAULT_UA, doc_cookies, mo_trinh_duyet
        from playwright.sync_api import sync_playwright
        cookies = doc_cookies(ten_file)
        if not cookies:
            return jsonify({"ok": False, "noi_dung": "File trống hoặc không đọc được cookie nào — hãy xuất lại cookies."})
        with sync_playwright() as p:
            browser = mo_trinh_duyet(p, cookies)
            try:
                ctx = browser.new_context(user_agent=DEFAULT_UA, locale="vi-VN",
                                          viewport={"width": 1280, "height": 800})
                ctx.add_cookies(cookies)
                page = ctx.new_page()
                page.goto("https://www.facebook.com/", timeout=60000,
                          wait_until="domcontentloaded")
                page.wait_for_timeout(8000)
                body = page.evaluate("() => (document.body.innerText || '')")
                url = page.url
            finally:
                browser.close()
        if "login" in url.lower() or "Đăng nhập" in body or "Log in" in body:
            return jsonify({"ok": False,
                            "noi_dung": f"Đọc được {len(cookies)} cookie, nhưng Facebook KHÔNG nhận đăng nhập (cookies hết hạn hoặc bị vô hiệu). Hãy xuất lại cookies mới."})
        return jsonify({"ok": True,
                        "noi_dung": f"Đọc được {len(cookies)} cookie — hợp lệ ✅ (đã đăng nhập Facebook)."})
    except Exception as e:
        return jsonify({"ok": False, "noi_dung": f"Lỗi khi kiểm tra: {e}"})


# ---------------- API: kết quả từ các file JSON ----------------
@app.route("/api/ket_qua")
def api_ket_qua():
    """Đọc các file du_lieu_*.json / *.json chứa bài viết -> trả về theo trang."""
    ket_qua = []
    cac_file = sorted(glob.glob("*.json"),
                      key=os.path.getmtime, reverse=True)
    for f in cac_file:
        try:
            with open(f, encoding="utf-8") as fh:
                posts = json.load(fh)
        except Exception:
            continue
        if not (isinstance(posts, list) and posts and "post_id" in posts[0]):
            continue  # không phải file dữ liệu bài viết của chúng ta
        so_bai = len(posts)
        tong_cam_xuc = sum(p.get("likes") or 0 for p in posts)
        tong_bl = sum(p.get("comments") or 0 for p in posts)
        bai_top = sorted(posts, key=lambda p: p.get("diem_tiem_nang") or 0,
                         reverse=True)[:1]
        ket_qua.append({
            "file": f,
            "trang": os.path.splitext(f)[0].replace("du_lieu_", ""),
            "so_bai": so_bai,
            "tong_cam_xuc": tong_cam_xuc,
            "tong_binh_luan": tong_bl,
            "bai_top": bai_top[0] if bai_top else None,
            "posts": posts,
        })
    return jsonify(ket_qua)


# ---------------- API: tải file Excel mới nhất ----------------
@app.route("/api/xlsx")
def api_xlsx():
    cac_file = [f for f in glob.glob("*.xlsx") if os.path.isfile(f)] + \
               [f for f in glob.glob("du_lieu_exel/*.xlsx") if os.path.isfile(f)]
    if not cac_file:
        return jsonify({"loi": "Chưa có file Excel nào."}), 404
    moi_nhat = max(cac_file, key=os.path.getmtime)
    return send_file(moi_nhat, as_attachment=True, download_name=os.path.basename(moi_nhat))


# ---------------- API: ảnh đã tải ----------------
@app.route("/anh/<path:duong_dan>")
def xem_anh(duong_dan):
    """Phục vụ ảnh đã tải về (chỉ cho phép đường dẫn chứa '_images')."""
    if "_images" not in duong_dan:
        return "Không cho phép", 403
    return send_from_directory(os.getcwd(), duong_dan)


if __name__ == "__main__":
    try:
        webbrowser.open("http://127.0.0.1:5000")
    except Exception:
        pass
    print("=" * 55)
    print("  📊 Facebook Scraper — Giao diện web")
    print("  Mở trình duyệt:  http://127.0.0.1:5000")
    print("  (Nhấn Ctrl+C để thoát)")
    print("=" * 55)
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
