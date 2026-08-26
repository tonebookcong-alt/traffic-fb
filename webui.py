#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GIAO DIỆN WEB UI QUẢN LÝ TOÀN DIỆN TOOL TRAFFIC FACEBOOK (4 TAB).

Chạy:  python webui.py
Mở:    http://127.0.0.1:5000

- Tab 1: 📥 CÀO DỮ LIỆU (Playwright, Cookies, Realtime SSE)
- Tab 2: 📋 KHO BÀI VIẾT / CONTENT POOL (Lọc, Checkbox Chọn tất cả, Xử lý hàng loạt)
- Tab 3: ✍️ XỬ LÝ AI & ẢNH (DeepSeek 3 Caption viral, Sửa trực tiếp, Bài báo 1500-1700 từ, Crop ảnh)
- Tab 4: 📦 BÀI SẴN SÀNG ĐĂNG (Copy 1-click cho Antidetect Browser, Mở Folder máy tính)
"""

import glob
import json
import os
import queue
import subprocess
import threading
import time
import webbrowser
from datetime import datetime

from flask import (Flask, Response, jsonify, render_template, request,
                   send_file, send_from_directory)

from config import DUONG_DAN, load_config, ghi_config
from google_sheets import lay_store
import scraper
import luong_b
import dong_goi
from viet_lai import viet_3_caption, viet_bai_bao
from media import chuan_bi_media, xu_ly_anh
from ai_client import kiem_tra_api_key

app = Flask(__name__)


@app.after_request
def chong_cache_api(resp):
    """Chặn trình duyệt cache response API — tránh WebUI hiển thị dữ liệu CŨ
    (caption dính "Chiefs Dynasty Fans…") sau khi file đã được sửa."""
    if request.path.startswith("/api/") or resp.mimetype == "application/json":
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
    return resp


# ---------------- Trạng thái chung Luồng Cào ----------------
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

# ---------------- Trạng thái Xử lý Hàng loạt ----------------
BATCH_STATUS = {
    "dang_chay": False,
    "tong_so": 0,
    "da_xong": 0,
    "dang_xu_ly": "",
    "loi": [],
    "hoan_thanh": False,
}

# ---------------- Trạng thái Cắt ảnh (Tab 4) ----------------
ANH_STATUS = {
    "dang_chay": False,
    "tong_so": 0,
    "da_xong": 0,
    "dang_xu_ly": "",
    "loi": [],
    "hoan_thanh": False,
}


def cap_nhat(**kw):
    with KHOA:
        TRANG_THAI.update(kw)


def emit(su_kien: dict):
    QUEUE_SU_KIEN.put(su_kien)


def _nap_vao_pool(ket_qua, store):
    """Nạp các bài cào được vào Content Pool — dùng chung cho luồng cào và luồng full."""
    from content_pool import chong_trung, them_content, chuan_hoa_text
    from nhan_dien import nhan_dien_nhan_vat
    phien = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # 1 lần cào = 1 phiên
    tong_nap = 0
    for trang, ds_bai in ket_qua.items():
        if not ds_bai:
            continue
        bai_co_chu = [b for b in ds_bai if len(chuan_hoa_text(b.get("text") or "")) >= 5]
        bai_moi = chong_trung(bai_co_chu, store, phien=phien)
        for b in bai_moi:
            txt = (b.get("text") or "").strip()
            try:
                nv = nhan_dien_nhan_vat(txt, "Facebook", [])
            except Exception:
                nv = "Chung"
            them_content(b, "Facebook", nv, trang, store, phien=phien)
            tong_nap += 1
    return tong_nap


# ===================================================================
# 1. API TAB 1: CÀO DỮ LIỆU (SCRAPER)
# ===================================================================
def chay_scraper(trang_ho, per_page, pages, delay, cookies, no_images):
    def cb(s):
        emit(s)
        if s.get("loai") == "trang_bat_dau":
            cap_nhat(trang_hien_tai=s.get("page"), xong=False, thong_bao=None)
        elif s.get("loai") == "post":
            with KHOA:
                TRANG_THAI["so_bai"] += 1
        elif s.get("loai") == "anh":
            with KHOA:
                TRANG_THAI["so_anh"] += 1
        elif s.get("loai") == "log":
            emit({"loai": "log", "noi_dung": s.get("noi_dung")})

    try:
        emit({"loai": "log", "noi_dung": f"🚀 Bắt đầu cào {len(trang_ho)} trang..."})
        ket_qua, xlsx_path = scraper.run_cào(
            trang_ho, pages=pages, per_page=per_page, output="du_lieu",
            no_images=no_images, cookies=cookies, delay=delay,
            callback=cb, stop_flag=STOP_EVENT,
        )
        so_bai = sum(len(p) for p in ket_qua.values())

        # Tự động nạp các bài cào được vào Content Pool (Tab 2)
        store = lay_store()
        tong_nap_pool = _nap_vao_pool(ket_qua, store)

        thong_bao_xong = f"✅ Hoàn thành: Cào được {so_bai} bài viết (+{tong_nap_pool} bài mới đã nạp vào Kho bài Tab 2)"
        cap_nhat(dang_chay=False, xong=True, trang_hien_tai=None, xlsx=xlsx_path,
                 thong_bao=thong_bao_xong)
        emit({"loai": "xong", "so_bai": so_bai, "so_trang": len(ket_qua), "xlsx": xlsx_path, "nap_pool": tong_nap_pool})
        emit({"loai": "log", "noi_dung": f"\n🎉 {thong_bao_xong}"})
        emit({"loai": "log", "noi_dung": f"📊 File Excel đã tạo tại: {xlsx_path}"})
    except Exception as e:
        cap_nhat(dang_chay=False, xong=True, thong_bao=f"❌ Lỗi: {e}")
        emit({"loai": "loi", "noi_dung": str(e)})
        emit({"loai": "log", "noi_dung": f"❌ Lỗi trong quá trình cào: {e}"})
        emit({"loai": "xong", "so_bai": TRANG_THAI["so_bai"]})


def chay_ca_luong(trang_ho, per_page, pages, delay, cookies, no_images, format_type):
    """Luồng FULL: Cào → nạp pool → viết lại (AI) từng bài mới → chỉnh ảnh → đóng gói CSV."""
    def cb(s):
        emit(s)
        if s.get("loai") == "trang_bat_dau":
            cap_nhat(trang_hien_tai=s.get("page"), xong=False, thong_bao=None)
        elif s.get("loai") == "post":
            with KHOA:
                TRANG_THAI["so_bai"] += 1
        elif s.get("loai") == "anh":
            with KHOA:
                TRANG_THAI["so_anh"] += 1
        elif s.get("loai") == "log":
            emit({"loai": "log", "noi_dung": s.get("noi_dung")})

    try:
        store = lay_store()
        # Nhớ các bài ĐÃ có trước khi cào → chỉ xử lý các bài MỚI vừa nạp
        truoc = {str(d.get("Content ID") or "").strip()
                 for d in store.lay_tat_ca("CONTENT POOL")}

        emit({"loai": "log", "noi_dung": f"⚡ CHẠY CẢ LUỒNG — cào {len(trang_ho)} trang..."})
        ket_qua, xlsx_path = scraper.run_cào(
            trang_ho, pages=pages, per_page=per_page, output="du_lieu",
            no_images=no_images, cookies=cookies, delay=delay,
            callback=cb, stop_flag=STOP_EVENT,
        )
        so_cao = sum(len(p) for p in ket_qua.values())
        nap = _nap_vao_pool(ket_qua, store)
        emit({"loai": "log", "noi_dung": f"✅ Cào xong: {so_cao} bài (+{nap} bài mới nạp kho)."})

        # Bài MỚI vừa nạp: Content ID chưa có trong `truoc`
        sau = {str(d.get("Content ID") or "").strip()
               for d in store.lay_tat_ca("CONTENT POOL")}
        bai_moi_ids = [c for c in sau if c and c not in truoc]

        emit({"loai": "log", "noi_dung": f"✍️ Viết lại + chỉnh ảnh {len(bai_moi_ids)} bài mới..."})
        ok = 0
        for i, cid in enumerate(bai_moi_ids, 1):
            emit({"loai": "log", "noi_dung": f"[{i}/{len(bai_moi_ids)}] Đang xử lý {cid}..."})
            try:
                res = luong_b.xu_ly_ai_mot_bai(cid, format_type=format_type)
                if res.get("success"):
                    ok += 1
            except Exception as e:
                emit({"loai": "log", "noi_dung": f"  [!] Lỗi {cid}: {e}"})

        # Bài ĐÃ xử lý (WEB_POSTED/DONE) nhưng mất file ảnh/bo_bai (folder cũ bị xóa)
        # → dựng lại ảnh (logo+viền) KHÔNG chạy lại AI, để CSV có đường dẫn ảnh.
        goi_co = set(dong_goi._doc_bo_bai().keys())
        thieu_anh = [
            str(d.get("Content ID") or "").strip()
            for d in store.lay_tat_ca("CONTENT POOL")
            if str(d.get("Status") or "").strip() in ("WEB_POSTED", "DONE")
            and str(d.get("Content ID") or "").strip()
            and str(d.get("Content ID") or "").strip() not in goi_co
        ]
        if thieu_anh:
            emit({"loai": "log", "noi_dung": f"🖼️ Dựng lại ảnh cho {len(thieu_anh)} bài mất file ảnh..."})
            for i, cid in enumerate(thieu_anh, 1):
                emit({"loai": "log", "noi_dung": f"[{i}/{len(thieu_anh)}] Dựng ảnh lại {cid}..."})
                try:
                    luong_b.xu_ly_anh_bo_bai(cid, format_type=format_type)
                except Exception as e:
                    emit({"loai": "log", "noi_dung": f"  [!] Lỗi dựng ảnh {cid}: {e}"})

        # Đóng gói CSV toàn bộ bài đã xử lý
        emit({"loai": "log", "noi_dung": "📄 Đang đóng gói CSV..."})
        res_csv = dong_goi.tao_csv_full(store)
        csv_path = res_csv.get("csv_path") or ""
        so_csv = res_csv.get("so_dong") or 0

        thong_bao = (f"🏁 XONG LUỒNG: cào {so_cao}, xử lý {ok}/{len(bai_moi_ids)}, "
                     f"CSV {so_csv} bài tại {csv_path}")
        cap_nhat(dang_chay=False, xong=True, trang_hien_tai=None,
                 xlsx=xlsx_path, thong_bao=thong_bao)
        emit({"loai": "xong", "so_bai": so_cao, "nap_pool": nap,
              "xlsx": xlsx_path, "csv": csv_path, "thong_bao": thong_bao})
        emit({"loai": "log", "noi_dung": f"\n🎉 {thong_bao}"})
    except Exception as e:
        import traceback
        traceback.print_exc()
        cap_nhat(dang_chay=False, xong=True, thong_bao=f"❌ Lỗi luồng: {e}")
        emit({"loai": "loi", "noi_dung": str(e)})
        emit({"loai": "xong", "so_bai": TRANG_THAI["so_bai"]})


@app.route("/")
def trang_chu():
    return render_template("index.html")


@app.route("/api/trang_thai")
def api_trang_thai():
    with KHOA:
        return jsonify(TRANG_THAI)


@app.route("/api/su_kien")
def api_su_kien():
    def generator():
        while True:
            try:
                su_kien = QUEUE_SU_KIEN.get(timeout=20)
                yield f"data: {json.dumps(su_kien, ensure_ascii=False)}\n\n"
            except queue.Empty:
                yield ": keep-alive\n\n"
    return Response(generator(), mimetype="text/event-stream")


@app.route("/api/bat_dau", methods=["POST"])
def api_bat_dau():
    with KHOA:
        if TRANG_THAI["dang_chay"]:
            return jsonify({"ok": False, "loi": "Đang cào dữ liệu, vui lòng đợi!"}), 400

    data = request.json or {}
    trang_raw = data.get("trang", "")
    trang_ho = [t.strip() for t in trang_raw.splitlines() if t.strip()]
    if not trang_ho:
        return jsonify({"ok": False, "loi": "Danh sách trang rỗng"}), 400

    per_page = int(data.get("per_page") or 50)
    pages = int(data.get("pages") or 10)
    delay = float(data.get("delay") or 3.0)
    cookies = data.get("cookies", "cookies.txt").strip() or "cookies.txt"
    no_images = bool(data.get("no_images", False))

    STOP_EVENT.clear()
    while not QUEUE_SU_KIEN.empty():
        try:
            QUEUE_SU_KIEN.get_nowait()
        except queue.Empty:
            break

    cap_nhat(dang_chay=True, xong=False, trang_ho=trang_ho, trang_hien_tai=trang_ho[0],
             so_bai=0, so_anh=0, xlsx=None, thong_bao="Đang khởi động cào dữ liệu...")

    t = threading.Thread(
        target=chay_scraper,
        args=(trang_ho, per_page, pages, delay, cookies, no_images),
        daemon=True,
    )
    t.start()
    return jsonify({"ok": True, "so_trang": len(trang_ho)})


@app.route("/api/dung", methods=["POST"])
def api_dung():
    STOP_EVENT.set()
    cap_nhat(dang_chay=False, thong_bao="Đã gửi yêu cầu dừng...")
    emit({"loai": "thong_bao", "noi_dung": "Đang dừng theo yêu cầu người dùng..."})
    return jsonify({"ok": True})


@app.route("/api/chay_ca_luong", methods=["POST"])
def api_chay_ca_luong():
    """Luồng FULL: cào → viết lại → chỉnh ảnh → đóng gói CSV."""
    with KHOA:
        if TRANG_THAI["dang_chay"]:
            return jsonify({"ok": False, "loi": "Đang có tiến trình chạy, vui lòng đợi!"}), 400

    data = request.json or {}
    trang_raw = data.get("trang", "")
    trang_ho = [t.strip() for t in trang_raw.splitlines() if t.strip()]
    if not trang_ho:
        return jsonify({"ok": False, "loi": "Danh sách trang rỗng"}), 400

    per_page = int(data.get("per_page") or 10)
    pages = int(data.get("pages") or 3)
    delay = float(data.get("delay") or 3.0)
    cookies = data.get("cookies", "cookies.txt").strip() or "cookies.txt"
    no_images = bool(data.get("no_images", False))
    format_type = (data.get("format_type") or "1:1").strip() or "1:1"

    STOP_EVENT.clear()
    while not QUEUE_SU_KIEN.empty():
        try:
            QUEUE_SU_KIEN.get_nowait()
        except queue.Empty:
            break

    cap_nhat(dang_chay=True, xong=False, trang_ho=trang_ho, trang_hien_tai=trang_ho[0],
             so_bai=0, so_anh=0, xlsx=None, thong_bao="Đang chạy luồng đầy đủ...")

    t = threading.Thread(
        target=chay_ca_luong,
        args=(trang_ho, per_page, pages, delay, cookies, no_images, format_type),
        daemon=True,
    )
    t.start()
    return jsonify({"ok": True, "trang": len(trang_ho)})


@app.route("/api/xuat_csv", methods=["POST"])
def api_xuat_csv():
    """Đóng gói các bài đã xử lý ra file CSV (gửi ids để lọc, không thì lấy TẤT CẢ WEB_POSTED/DONE)."""
    data = request.json or {}
    ids = data.get("ids") or None
    res = dong_goi.tao_csv_full(danh_sach=ids)
    if not res.get("ok"):
        return jsonify({"ok": False, "loi": "Không thể xuất CSV"}), 500
    return jsonify({"ok": True, "csv_path": res.get("csv_path"),
                    "so_dong": res.get("so_dong"), "thu_muc": res.get("thu_muc")})


@app.route("/api/tai_csv")
def api_tai_csv():
    f = request.args.get("file")
    if not f:
        folder = os.path.join(DUONG_DAN, "du_lieu_fb")
        danh_sach = sorted(
            glob.glob(os.path.join(folder, "**", "goi_full_*.csv"), recursive=True),
            key=os.path.getmtime, reverse=True)
        if danh_sach:
            f = danh_sach[0]
    if f and os.path.isfile(f):
        return send_file(f, as_attachment=True, download_name=os.path.basename(f))
    return jsonify({"ok": False, "loi": "Không tìm thấy file CSV"}), 404


@app.route("/api/kiem_tra_cookies", methods=["POST"])
def api_kiem_tra_cookies():
    ten_file = (request.json or {}).get("file", "cookies.txt").strip() or "cookies.txt"
    duong_dan = os.path.join(DUONG_DAN, ten_file)
    if not os.path.isfile(duong_dan):
        return jsonify({"ok": False, "loi": f"Không tìm thấy file '{ten_file}'"})
    try:
        cookies = scraper.load_cookies(duong_dan)
        if not cookies:
            return jsonify({"ok": False, "loi": "File cookies rỗng"})
        return jsonify({"ok": True, "so_luong": len(cookies), "thong_bao": f"Hợp lệ ({len(cookies)} cookies)"})
    except Exception as e:
        return jsonify({"ok": False, "loi": str(e)})


@app.route("/api/tai_xlsx")
def api_tai_xlsx():
    f = request.args.get("file")
    if not f:
        folder = os.path.join(DUONG_DAN, "du_lieu_exel")
        danh_sach = sorted(glob.glob(os.path.join(folder, "du_lieu_*.xlsx")), key=os.path.getmtime, reverse=True)
        if danh_sach:
            f = danh_sach[0]
    if f and os.path.isfile(f):
        return send_file(f, as_attachment=True, download_name=os.path.basename(f))
    return jsonify({"ok": False, "loi": "Không tìm thấy file Excel"}), 404


# ===================================================================
# 2. API TAB 2: KHO BÀI VIẾT (CONTENT POOL)
# ===================================================================
@app.route("/api/pool", methods=["GET"])
def api_lay_pool():
    st = request.args.get("trang_thai")
    key = request.args.get("key")
    nv = request.args.get("nhan_vat")
    search = request.args.get("search")
    sort_by = request.args.get("sort_by", "default")
    phien = request.args.get("phien")
    chi_chua = request.args.get("chi_chua_xu_ly") == "1"
    danh_sach = luong_b.lay_danh_sach_pool(
        trang_thai=st, key=key, nhan_vat=nv, tim_kiem=search, sort_by=sort_by,
        phien=phien, chi_chua_xu_ly=chi_chua)
    return jsonify({"ok": True, "tong_so": len(danh_sach), "data": danh_sach})


@app.route("/api/pool/phien", methods=["GET"])
def api_lay_pool_phien():
    """Danh sách các phiên cào (thời gian cào) để chọn trong Tab Kho Bài Viết."""
    ds = luong_b.lay_cac_phien_cao()
    return jsonify({"ok": True, "data": ds})


@app.route("/api/pool/filters", methods=["GET"])
def api_lay_pool_filters():
    store = lay_store()
    danh_sach = store.lay_tat_ca("CONTENT POOL")
    keys = sorted(list({str(d.get("KEY") or "").strip() for d in danh_sach if str(d.get("KEY") or "").strip()}))
    nvs = sorted(list({str(d.get("Nhân vật/chủ đề") or "").strip() for d in danh_sach if str(d.get("Nhân vật/chủ đề") or "").strip()}))
    statuses = ["NEW", "PROCESSING", "SAN_SANG", "HOAN_THANH", "WEB_POSTED", "DONE", "ERROR", "HET_HAN"]
    return jsonify({"ok": True, "keys": keys, "nhan_vats": nvs, "statuses": statuses})


@app.route("/api/pool/xoa", methods=["POST"])
def api_pool_xoa():
    """Xóa 1 hoặc nhiều bài khỏi Content Pool theo Content ID."""
    data = request.json or {}
    ids = data.get("ids") or []
    if not ids:
        cid = (data.get("content_id") or "").strip()
        if cid:
            ids = [cid]
    if not ids:
        return jsonify({"ok": False, "loi": "Danh sách ID rỗng"}), 400

    store = lay_store()
    da_xoa = 0
    for cid in ids:
        tim = store.tim_dong("CONTENT POOL", "Content ID", str(cid))
        if tim:
            chi_so, _ = tim
            store.xoa_dong("CONTENT POOL", chi_so)
            da_xoa += 1
    return jsonify({"ok": True, "da_xoa": da_xoa})


# ===================================================================
# 3. API TAB 3: XỬ LÝ AI & ẢNH (DEEPSEEK + PILLOW)
# ===================================================================
@app.route("/api/pool/chi_tiet/<path:content_id>", methods=["GET"])
def api_chi_tiet_bai(content_id):
    bai = luong_b.lay_chi_tiet_bai(content_id)
    if not bai:
        return jsonify({"ok": False, "loi": "Không tìm thấy bài viết"}), 404
    return jsonify({"ok": True, "data": bai})


@app.route("/api/xu_ly_ai/<path:content_id>", methods=["POST"])
def api_xu_ly_ai_don_le(content_id):
    """Tab 3: sinh nội dung (3 Caption + Bài báo + link) — KHÔNG cắt ảnh."""
    format_type = (request.json or {}).get("format_type", "1:1")
    res = luong_b.xuat_noi_dung_ai_bai(content_id, format_type=format_type)
    if res.get("success"):
        return jsonify({"ok": True, "data": res.get("data"), "folder": res.get("folder")})
    return jsonify({"ok": False, "loi": res.get("message")}), 500


def _worker_batch(ids, format_type):
    global BATCH_STATUS
    BATCH_STATUS["dang_chay"] = True
    BATCH_STATUS["tong_so"] = len(ids)
    BATCH_STATUS["da_xong"] = 0
    BATCH_STATUS["loi"] = []
    BATCH_STATUS["hoan_thanh"] = False

    for cid in ids:
        BATCH_STATUS["dang_xu_ly"] = cid
        try:
            res = luong_b.xuat_noi_dung_ai_bai(cid, format_type=format_type)
            if not res.get("success"):
                BATCH_STATUS["loi"].append({"id": cid, "err": res.get("message")})
        except Exception as e:
            BATCH_STATUS["loi"].append({"id": cid, "err": str(e)})
        BATCH_STATUS["da_xong"] += 1

    BATCH_STATUS["dang_chay"] = False
    BATCH_STATUS["hoan_thanh"] = True
    BATCH_STATUS["dang_xu_ly"] = ""


@app.route("/api/xu_ly_hang_loat", methods=["POST"])
def api_xu_ly_hang_loat():
    global BATCH_STATUS
    if BATCH_STATUS["dang_chay"]:
        return jsonify({"ok": False, "loi": "Đang có tiến trình xử lý hàng loạt chạy ngầm"}), 400

    data = request.json or {}
    ids = data.get("ids") or []
    format_type = data.get("format_type", "1:1")

    if not ids:
        return jsonify({"ok": False, "loi": "Danh sách ID rỗng"}), 400

    t = threading.Thread(target=_worker_batch, args=(ids, format_type), daemon=True)
    t.start()
    return jsonify({"ok": True, "tong_so": len(ids), "message": f"Bắt đầu xử lý {len(ids)} bài viết"})


@app.route("/api/tien_do_hang_loat", methods=["GET"])
def api_tien_do_hang_loat():
    return jsonify(BATCH_STATUS)


def _worker_anh(ids, format_type):
    """Cắt ảnh từng bài trong nền (Tab 4) — dùng cho thread riêng."""
    global ANH_STATUS
    ANH_STATUS["dang_chay"] = True
    ANH_STATUS["tong_so"] = len(ids)
    ANH_STATUS["da_xong"] = 0
    ANH_STATUS["loi"] = []
    ANH_STATUS["hoan_thanh"] = False

    for cid in ids:
        ANH_STATUS["dang_xu_ly"] = cid
        try:
            res = luong_b.xu_ly_anh_hoan_thanh_mot_bai(cid, format_type=format_type)
            if not res.get("success"):
                ANH_STATUS["loi"].append({"id": cid, "err": res.get("message")})
        except Exception as e:
            ANH_STATUS["loi"].append({"id": cid, "err": str(e)})
        ANH_STATUS["da_xong"] += 1

    ANH_STATUS["dang_chay"] = False
    ANH_STATUS["hoan_thanh"] = True
    ANH_STATUS["dang_xu_ly"] = ""


@app.route("/api/xu_ly_anh", methods=["POST"])
def api_xu_ly_anh():
    """Tab 4: nhận ids + format_type → chạy nền cắt ảnh từng bài."""
    global ANH_STATUS
    if ANH_STATUS["dang_chay"]:
        return jsonify({"ok": False, "loi": "Đang có tiến trình cắt ảnh chạy ngầm"}), 400

    data = request.json or {}
    ids = data.get("ids") or []
    format_type = data.get("format_type", "1:1")
    if not ids:
        return jsonify({"ok": False, "loi": "Danh sách ID rỗng"}), 400

    t = threading.Thread(target=_worker_anh, args=(ids, format_type), daemon=True)
    t.start()
    return jsonify({"ok": True, "tong_so": len(ids), "message": f"Bắt đầu cắt ảnh {len(ids)} bài"})


@app.route("/api/tien_do_anh", methods=["GET"])
def api_tien_do_anh():
    return jsonify(ANH_STATUS)


@app.route("/api/luu_chinh_sua", methods=["POST"])
def api_luu_chinh_sua():
    data = request.json or {}
    cid = data.get("content_id")
    if not cid:
        return jsonify({"ok": False, "loi": "Thiếu content_id"}), 400
    res = luong_b.luu_chinh_sua_bai(cid, data)
    return jsonify({"ok": res.get("success"), "message": res.get("message")})


@app.route("/api/viet_lai_caption/<path:content_id>", methods=["POST"])
def api_viet_lai_caption(content_id):
    bai = luong_b.lay_chi_tiet_bai(content_id)
    if not bai:
        return jsonify({"ok": False, "loi": "Không tìm thấy bài"}), 404
    caption_goc = bai.get("Caption") or ""
    try:
        caps = viet_3_caption(caption_goc)
        return jsonify({"ok": True, "data": caps})
    except Exception as e:
        return jsonify({"ok": False, "loi": str(e)}), 500


@app.route("/api/viet_lai_bai_bao/<path:content_id>", methods=["POST"])
def api_viet_lai_bai_bao(content_id):
    bai = luong_b.lay_chi_tiet_bai(content_id)
    if not bai:
        return jsonify({"ok": False, "loi": "Không tìm thấy bài"}), 404
    caption_goc = bai.get("Caption") or ""
    key = bai.get("KEY") or ""
    nv = bai.get("Nhân vật/chủ đề") or ""
    try:
        bb = viet_bai_bao(caption_goc, nhan_vat=nv, key=key)
        return jsonify({"ok": True, "bai_bao": bb})
    except Exception as e:
        return jsonify({"ok": False, "loi": str(e)}), 500


# ===================================================================
# 4. API TAB 4: BÀI SẴN SÀNG ĐĂNG (ANTIDETECT BROWSER)
# ===================================================================
@app.route("/api/san_sang", methods=["GET"])
def api_lay_san_sang():
    danh_sach = luong_b.lay_danh_sach_san_sang()
    return jsonify({"ok": True, "tong_so": len(danh_sach), "data": danh_sach})


@app.route("/api/hoan_thanh", methods=["GET"])
def api_lay_hoan_thanh():
    """Tab 5: danh sách bài đã cắt ảnh xong (Status = HOAN_THANH).

    `phien` (query) : chỉ lấy bài thuộc phiên cào này; bỏ trống = tất cả các phiên.
    """
    phien = request.args.get("phien") or None
    danh_sach = luong_b.lay_danh_sach_hoan_thanh(phien=phien)
    return jsonify({"ok": True, "tong_so": len(danh_sach), "data": danh_sach})


@app.route("/api/hoan_thanh/phien", methods=["GET"])
def api_lay_phien_hoan_thanh():
    """Tab 5: danh sách phiên cào có chứa bài HOAN_THANH để chọn lọc."""
    ds = luong_b.lay_cac_phien_hoan_thanh()
    return jsonify({"ok": True, "data": ds})


@app.route("/api/xuat_excel_tab5", methods=["POST"])
def api_xuat_excel_tab5():
    """Tab 5: xuất file Excel các bài HOAN_THANH (ids rỗng = lấy tất cả)."""
    data = request.json or {}
    ids = data.get("ids") or None
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
    except Exception as e:
        return jsonify({"ok": False, "loi": f"Thiếu openpyxl: {e}"}), 500

    danh_sach = luong_b.lay_danh_sach_hoan_thanh()
    if ids:
        danh_sach = [d for d in danh_sach if str(d.get("Content ID") or "") in set(str(i) for i in ids)]
    if not danh_sach:
        return jsonify({"ok": False, "loi": "Không có bài nào để xuất"}), 400

    cot = dong_goi.COT_CSV
    thu_muc = os.path.join(DUONG_DAN, "du_lieu_exel")
    os.makedirs(thu_muc, exist_ok=True)
    xlsx_path = os.path.join(
        thu_muc, f"hoan_thanh_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")

    wb = Workbook()
    ws = wb.active
    ws.title = "Hoan Thanh"
    ws.append(["STT"] + cot)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for i, r in enumerate(danh_sach, start=1):
        goi = r.get("goi_fb") or {}
        row = [
            r.get("Content ID") or "",
            r.get("KEY") or "",
            r.get("Nhân vật/chủ đề") or "",
            r.get("Source") or "",
            r.get("Thời gian đăng") or "",
            r.get("Cảm xúc") or 0,
            r.get("Bình luận") or 0,
            r.get("Chia sẻ") or 0,
            dong_goi.lam_phang_caption(r.get("Caption") or ""),
            dong_goi.lam_phang_caption(goi.get("caption_lua_chon") or r.get("Caption mới") or ""),
            goi.get("article_url") or r.get("Article URL") or "",
            goi.get("anh_path") or r.get("Media") or "",
            r.get("Status") or "",
        ]
        ws.append([i] + list(row))

    for col in ws.columns:
        width = min(max(len(str(c.value)) for c in col) + 4, 60)
        ws.column_dimensions[col[0].column_letter].width = width

    wb.save(xlsx_path)
    return jsonify({"ok": True, "xlsx_path": xlsx_path, "so_dong": len(danh_sach), "file": xlsx_path})


@app.route("/api/xac_nhan_da_dang", methods=["POST"])
def api_xac_nhan_da_dang():
    cid = (request.json or {}).get("content_id")
    if not cid:
        return jsonify({"ok": False, "loi": "Thiếu content_id"}), 400
    luong_b.danh_dau_da_dang_fb(cid)
    return jsonify({"ok": True, "message": f"Đã đánh dấu bài {cid} hoàn tất (DONE)"})


@app.route("/api/mo_thu_muc", methods=["POST"])
def api_mo_thu_muc():
    folder = (request.json or {}).get("folder")
    if not folder or not os.path.exists(folder):
        folder = os.path.join(DUONG_DAN, "du_lieu_fb")
    try:
        if os.name == "nt":
            os.startfile(folder)
        else:
            subprocess.Popen(["xdg-open", folder])
        return jsonify({"ok": True, "folder": folder})
    except Exception as e:
        return jsonify({"ok": False, "loi": str(e)})


# ===================================================================
# 7. API TAB 6: CẤU HÌNH AI
# ===================================================================
@app.route("/api/cau_hinh", methods=["GET"])
def api_lay_cau_hinh():
    """Trả về cấu hình AI hiện tại (provider, api_key, model)."""
    cfg = load_config()
    return jsonify({
        "ok": True,
        "provider": cfg["ai"]["provider"],
        "api_key": cfg["ai"]["api_key"],
        "model": cfg["ai"]["model"],
    })


@app.route("/api/luu_cau_hinh", methods=["POST"])
def api_luu_cau_hinh():
    """Lưu cấu hình AI vào config.json."""
    data = request.json or {}
    cfg = load_config()
    cfg["ai"]["provider"] = (data.get("provider") or cfg["ai"]["provider"]).strip()
    cfg["ai"]["api_key"] = (data.get("api_key") or cfg["ai"]["api_key"]).strip()
    cfg["ai"]["model"] = (data.get("model") or cfg["ai"]["model"]).strip()
    try:
        ghi_config(cfg)
        return jsonify({"ok": True, "message": "Đã lưu cấu hình AI thành công."})
    except Exception as e:
        return jsonify({"ok": False, "loi": f"Lỗi ghi cấu hình: {e}"}), 500


@app.route("/api/kiem_tra_ai", methods=["POST"])
def api_kiem_tra_ai():
    """Kiểm tra kết nối API (provider, api_key, model từ body)."""
    data = request.json or {}
    provider = data.get("provider") or ""
    api_key = data.get("api_key") or ""
    model = data.get("model") or ""
    ket_qua = kiem_tra_api_key(provider, api_key, model)
    if ket_qua["ok"]:
        return jsonify({"ok": True, "message": ket_qua["message"]})
    return jsonify({"ok": False, "loi": ket_qua["message"]}), 400


# Phục vụ file media ảnh local
@app.route("/media/<path:filename>")
def serve_media(filename):
    # Cho phép tải ảnh từ du_lieu_fb hoặc du_lieu_images
    duong_dan_fb = os.path.join(DUONG_DAN, "du_lieu_fb")
    duong_dan_img = os.path.join(DUONG_DAN, "du_lieu_images")
    if os.path.exists(os.path.join(duong_dan_fb, filename)):
        return send_from_directory(duong_dan_fb, filename)
    if os.path.exists(os.path.join(duong_dan_img, filename)):
        return send_from_directory(duong_dan_img, filename)
    return send_from_directory(DUONG_DAN, filename)


if __name__ == "__main__":
    print("=" * 60)
    print("🚀 GIAO DIỆN WEB UI TOOL TRAFFIC FACEBOOK (4 TAB)")
    print("👉 Mở trình duyệt tại: http://127.0.0.1:5000")
    print("=" * 60)
    webbrowser.open("http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
