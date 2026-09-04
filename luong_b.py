# -*- coding: utf-8 -*-
"""
LUỒNG B — XỬ LÝ NỘI DUNG VÀ XUẤT BẢN CHO WEB UI & ANTIDETECT BROWSER.
- Đọc / Lọc / Tìm kiếm kho bài viết Content Pool
- Xử lý AI đơn lẻ và Xử lý AI hàng loạt (DeepSeek sinh 3 Caption + Bài báo + Cắt ảnh)
- Lưu chỉnh sửa trực tiếp từ Web UI
- Đóng gói xuất dữ liệu sẵn sàng cho Antidetect Browser
"""

import json
import os
import time
from datetime import datetime

from config import DUONG_DAN
from google_sheets import lay_store
from content_pool import chon_content, doi_status, _goc_thoi_gian
from viet_lai import viet_3_caption, viet_bai_bao
from media import chuan_bi_media, tao_thu_muc_ngay_gio
from dang_web import dang_bai_web
from reel import duong_dan_reel
from gan_chu_de import gan_chu_de_cho_bai, gan_chu_de_cho_bai_khong_ai


def lay_danh_sach_pool(trang_thai=None, key=None, nhan_vat=None, tim_kiem=None,
                       sort_by="default", phien=None, chi_chua_xu_ly=False,
                       nhieu_trang_thai=None):
    """Lấy danh sách bài viết từ Content Pool kèm lọc và sắp xếp.

    `phien`            : chỉ lấy bài thuộc phiên cào này (giá trị `Phien_cao`).
    `chi_chua_xu_ly`   : chỉ lấy bài chưa hoàn thành (Status ∈ NEW, PROCESSING).
    `nhieu_trang_thai` : set các trạng thái được phép (VD {"PROCESSING","SAN_SANG"}).
                         Nếu truyền thì ưu tiên hơn `trang_thai`.
    """
    store = lay_store()
    danh_sach = store.lay_tat_ca("CONTENT POOL")
    ket_qua = []

    for dong in danh_sach:
        cid = str(dong.get("Content ID") or "").strip()
        if not cid:
            continue

        st = str(dong.get("Status") or "NEW").strip()
        k = str(dong.get("KEY") or "").strip()
        nv = str(dong.get("Nhân vật/chủ đề") or "Chung").strip()
        cap = str(dong.get("Caption") or "").strip()

        # Bộ lọc phiên: khớp nếu phiên nằm trong `Cac_phien_gap` (gồm cả các lần trùng);
        # row cũ chưa có nhãn này → dựa vào `Phien_cao` (phiên gốc).
        if phien:
            cac_phien = dong.get("Cac_phien_gap")
            if cac_phien is None:
                if str(dong.get("Phien_cao") or "").strip() != phien:
                    continue
            elif phien not in (cac_phien if isinstance(cac_phien, list) else [str(cac_phien)]):
                continue
        if chi_chua_xu_ly and st not in ("NEW", "PROCESSING"):
            continue
        if nhieu_trang_thai:
            if st not in nhieu_trang_thai:
                continue
        elif trang_thai and trang_thai != "ALL" and st != trang_thai:
            continue
        if key and key != "ALL" and k != key:
            continue
        if nhan_vat and nhan_vat != "ALL" and nv != nhan_vat:
            continue
        if tim_kiem:
            tk = tim_kiem.lower()
            if tk not in cap.lower() and tk not in nv.lower() and tk not in cid.lower():
                continue

        # Điểm tương tác
        try:
            cam_xuc = int(dong.get("Cảm xúc") or 0)
            binh_luan = int(dong.get("Bình luận") or 0)
            chia_se = int(dong.get("Chia sẻ") or 0)
            diem = cam_xuc + binh_luan * 2 + chia_se * 3
        except Exception:
            cam_xuc, binh_luan, chia_se, diem = 0, 0, 0, 0

        item = dict(dong)
        item["cam_xuc_num"] = cam_xuc
        item["binh_luan_num"] = binh_luan
        item["chia_se_num"] = chia_se
        item["diem_tuong_tac"] = diem
        ket_qua.append(item)

    # Sắp xếp — mặc định (default / moi) = mới nhất đăng trước (teo "Thời gian đăng")
    if sort_by == "diem":
        ket_qua.sort(key=lambda x: x["diem_tuong_tac"], reverse=True)
    elif sort_by == "like":
        ket_qua.sort(key=lambda x: x["cam_xuc_num"], reverse=True)
    elif sort_by == "cmt":
        ket_qua.sort(key=lambda x: x["binh_luan_num"], reverse=True)
    else:
        # Bài không đọc được thời gian (0) xếp cuối; mới nhất lên đầu.
        def _epoch(x):
            goc = _goc_thoi_gian(x.get("Thời gian đăng"))
            return goc.timestamp() if goc is not None else 0
        ket_qua.sort(key=_epoch, reverse=True)

    return ket_qua


def lay_cac_phien_cao(store=None) -> list:
    """Gom bài trong Content Pool theo phiên cào (`Phien_cao`), mới nhất trước.

    Mỗi phiên trả: {phien, trang:[trang đã cào], so_bai, so_chua_xu_ly}.
    """
    store = store or lay_store()
    phien_map = {}
    for d in store.lay_tat_ca("CONTENT POOL"):
        # Phiên của bài = Cac_phien_gap (gồm cả lần trùng) nếu có, không thì phiên gốc
        cac_phien = d.get("Cac_phien_gap")
        if cac_phien is None:
            p = str(d.get("Phien_cao") or "").strip()
            ds_phien = [p] if p else []
        else:
            ds_phien = cac_phien if isinstance(cac_phien, list) else [str(cac_phien)]
        if not ds_phien:
            continue
        trang = str(d.get("Source") or "").strip()
        st = str(d.get("Status") or "NEW").strip()
        for p in ds_phien:
            p = str(p).strip()
            if not p:
                continue
            e = phien_map.setdefault(
                p, {"phien": p, "trang": set(), "so_bai": 0, "so_chua_xu_ly": 0})
            if trang:
                e["trang"].add(trang)
            e["so_bai"] += 1
            if st in ("NEW", "PROCESSING"):
                e["so_chua_xu_ly"] += 1

    ds = []
    for p, e in phien_map.items():
        ds.append({"phien": p, "trang": sorted(e["trang"]),
                   "so_bai": e["so_bai"], "so_chua_xu_ly": e["so_chua_xu_ly"]})
    ds.sort(key=lambda x: x["phien"], reverse=True)
    return ds


def lay_cac_phien_chinh_bai(store=None) -> list:
    """Gom phiên cào CHỈ gồm các bài đã chạy AI nhưng CHƯA hoàn thành (Status = PROCESSING).

    Dùng cho bộ lọc phiên ở Tab 3 (Chỉnh bài). Mỗi phiên: {phien, so_bai}.
    """
    store = store or lay_store()
    phien_map = {}
    for d in store.lay_tat_ca("CONTENT POOL"):
        st = str(d.get("Status") or "NEW").strip()
        if st != "PROCESSING":
            continue
        cac_phien = d.get("Cac_phien_gap")
        if cac_phien is None:
            p = str(d.get("Phien_cao") or "").strip()
            ds_phien = [p] if p else []
        else:
            ds_phien = cac_phien if isinstance(cac_phien, list) else [str(cac_phien)]
        if not ds_phien:
            continue
        for p in ds_phien:
            p = str(p).strip()
            if not p:
                continue
            e = phien_map.setdefault(p, {"phien": p, "so_bai": 0})
            e["so_bai"] += 1

    ds = [{"phien": p, "so_bai": e["so_bai"]} for p, e in phien_map.items()]
    ds.sort(key=lambda x: x["phien"], reverse=True)
    return ds


def lay_chi_tiet_bai(content_id: str):
    """Lấy chi tiết 1 bài viết kèm dữ liệu đã xử lý (nếu có)."""
    store = lay_store()
    tim = store.tim_dong("CONTENT POOL", "Content ID", content_id)
    if not tim:
        return None
    _, dong = tim
    
    # Kiểm tra xem có file gói lưu trong du_lieu_fb không
    fb_dir = os.path.join(DUONG_DAN, "du_lieu_fb")
    goi_fb = None
    if os.path.exists(fb_dir):
        for root, _, files in os.walk(fb_dir):
            target = f"bo_bai_{content_id}.json"
            if target in files:
                try:
                    with open(os.path.join(root, target), "r", encoding="utf-8") as f:
                        goi_fb = json.load(f)
                    break
                except Exception:
                    pass

    res = dict(dong)
    res["goi_fb"] = goi_fb
    return res


def _doc_bo_bai_mot(content_id):
    """Đọc file bo_bai_<content_id>.json trong du_lieu_fb/ (nếu còn)."""
    fb_dir = os.path.join(DUONG_DAN, "du_lieu_fb")
    if not os.path.exists(fb_dir):
        return None
    target = f"bo_bai_{content_id}.json"
    for root, _, files in os.walk(fb_dir):
        if target in files:
            try:
                with open(os.path.join(root, target), "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
    return None


def xu_ly_anh_bo_bai(content_id: str, format_type: str = "1:1") -> dict:
    """Dựng lại ẢNH + bo_bai cho bài ĐÃ xử lý nhưng mất file ảnh/bo_bai.

    KHÔNG chạy lại AI (giữ caption/bài báo/link cũ nếu còn) — chỉ tải chỉnh ảnh
    (logo + viền) rồi ghi đè bo_bai_<content_id>.json để CSV không bị trống cột ảnh.
    """
    store = lay_store()
    tim = store.tim_dong("CONTENT POOL", "Content ID", content_id)
    if not tim:
        return {"success": False, "message": f"Không tìm thấy bài {content_id}"}
    _, dong = tim
    thu_muc = tao_thu_muc_ngay_gio()

    goi_cu = _doc_bo_bai_mot(content_id) or {}
    cap_lua = goi_cu.get("caption_lua_chon") or dong.get("Caption mới") or ""
    cap_v2 = goi_cu.get("caption_version_2") or ""
    cap_v3 = goi_cu.get("caption_version_3") or ""
    bai_bao = goi_cu.get("bai_bao") or dong.get("Bài báo") or ""
    article_url = goi_cu.get("article_url") or dong.get("Article URL") or ""

    try:
        anh_path = chuan_bi_media(dong, format_type=format_type, thu_muc=thu_muc)
    except Exception as e:
        return {"success": False, "message": str(e)}

    goi_fb = {
        "content_id": content_id,
        "key": dong.get("KEY") or "",
        "nhan_vat": dong.get("Nhân vật/chủ đề") or "",
        "thoi_gian_tao": datetime.now().isoformat(),
        "article_url": article_url,
        "anh_path": anh_path,
        "caption_lua_chon": cap_lua,
        "caption_version_1": cap_lua,
        "caption_version_2": cap_v2,
        "caption_version_3": cap_v3,
        "bai_bao": bai_bao,
        "folder": thu_muc,
    }
    file_goi = os.path.join(thu_muc, f"bo_bai_{content_id}.json")
    with open(file_goi, "w", encoding="utf-8") as f:
        json.dump(goi_fb, f, ensure_ascii=False, indent=2)

    file_cap = os.path.join(thu_muc, f"caption_{content_id}.txt")
    with open(file_cap, "w", encoding="utf-8") as f:
        f.write(f"=== LINK BÀI BÁO (COMMENT ĐẦU TIÊN) ===\n{article_url}\n\n")
        f.write(f"=== VERSION 1 (MẶC ĐỊNH) ===\n{cap_lua}\n\n")
        if cap_v2:
            f.write(f"=== VERSION 2 ===\n{cap_v2}\n\n")
        if cap_v3:
            f.write(f"=== VERSION 3 ===\n{cap_v3}\n\n")

    return {"success": True, "data": goi_fb, "anh_path": anh_path, "folder": thu_muc}


def xu_ly_ai_mot_bai(content_id: str, format_type: str = "1:1", callback=None) -> dict:
    """Chạy AI sinh 3 Caption + Bài báo + Xử lý ảnh cho 1 bài viết."""
    store = lay_store()
    tim = store.tim_dong("CONTENT POOL", "Content ID", content_id)
    if not tim:
        return {"success": False, "message": f"Không tìm thấy bài {content_id}"}
    
    chi_so, dong = tim
    cid = dong.get("Content ID")
    key = dong.get("KEY") or "Chung"
    nhan_vat = dong.get("Nhân vật/chủ đề") or "Chung"
    caption_goc = dong.get("Caption") or ""

    if callback:
        callback({"status": "processing", "step": "lock", "message": f"Bắt đầu xử lý {cid}"})

    doi_status(cid, "PROCESSING", ghi_chu="Đang xử lý AI trên Web UI", store=store)
    thu_muc = tao_thu_muc_ngay_gio()

    try:
        # 1. AI Sinh 3 Caption
        if callback:
            callback({"status": "processing", "step": "caption", "message": "Đang gọi DeepSeek sinh 3 Caption viral..."})
        caps = viet_3_caption(caption_goc)
        cap_v1 = caps.get("version_1") or ""
        cap_v2 = caps.get("version_2") or ""
        cap_v3 = caps.get("version_3") or ""

        # 2. AI Viết bài báo
        if callback:
            callback({"status": "processing", "step": "article", "message": "Đang gọi DeepSeek viết bài báo 1500-1700 từ..."})
        bai_bao = viet_bai_bao(caption_goc, nhan_vat=nhan_vat, key=key)

        # 3. Xử lý ảnh
        if callback:
            callback({"status": "processing", "step": "media", "message": "Đang tải và crop ảnh chuẩn tỷ lệ..."})
        anh_path = chuan_bi_media(dong, format_type=format_type, thu_muc=thu_muc)

        # 4. Giả lập đăng Web
        if callback:
            callback({"status": "processing", "step": "web", "message": "Đang sinh link bài báo Website..."})
        tieu_de = f"Exclusive: {nhan_vat} — The Untold Story" if nhan_vat != "Khác" else f"Insight: {key} Update"
        res_web = dang_bai_web(tieu_de=tieu_de, noi_dung=bai_bao, anh_path=anh_path, nhan_vat=nhan_vat, key=key)
        article_url = res_web.get("article_url") or ""

        # Gán chủ đề: ưu tiên KEY khớp, không khớp thì gọi AI
        chu_de = gan_chu_de_cho_bai(key, caption_goc or bai_bao)

        # 5. Lưu gói bài đăng
        goi_fb = {
            "content_id": cid,
            "key": key,
            "nhan_vat": nhan_vat,
            "chu_de": chu_de,
            "thoi_gian_tao": datetime.now().isoformat(),
            "article_url": article_url,
            "anh_path": anh_path,
            "caption_lua_chon": cap_v1,
            "caption_version_1": cap_v1,
            "caption_version_2": cap_v2,
            "caption_version_3": cap_v3,
            "bai_bao": bai_bao,
            "folder": thu_muc,
        }

        file_goi = os.path.join(thu_muc, f"bo_bai_{cid}.json")
        with open(file_goi, "w", encoding="utf-8") as f:
            json.dump(goi_fb, f, ensure_ascii=False, indent=2)

        file_cap = os.path.join(thu_muc, f"caption_{cid}.txt")
        with open(file_cap, "w", encoding="utf-8") as f:
            f.write(f"=== LINK BÀI BÁO (COMMENT ĐẦU TIÊN) ===\n{article_url}\n\n")
            f.write(f"=== VERSION 1 (MẶC ĐỊNH) ===\n{cap_v1}\n\n")
            f.write(f"=== VERSION 2 ===\n{cap_v2}\n\n")
            f.write(f"=== VERSION 3 ===\n{cap_v3}\n\n")

        # 6. Cập nhật Content Pool chuẩn xác theo chi_so
        tim_lai = store.tim_dong("CONTENT POOL", "Content ID", cid)
        if tim_lai:
            idx, row = tim_lai
            row["Caption mới"] = cap_v1
            row["Bài báo"] = bai_bao[:500] + "... [xem chi tiết trong thư mục]"
            row["Article URL"] = article_url
            row["Chủ đề"] = chu_de
            row["Status"] = "WEB_POSTED"
            row["Ghi chú"] = f"Đã sẵn sàng tại {os.path.basename(thu_muc)}"
            store.cap_nhat_dong("CONTENT POOL", idx, row)

        if callback:
            callback({"status": "done", "step": "done", "message": f"Hoàn thành xuất sắc bài {cid}!"})

        return {"success": True, "data": goi_fb, "folder": thu_muc}

    except Exception as e:
        doi_status(cid, "ERROR", ghi_chu=f"Lỗi AI: {str(e)[:100]}", store=store)
        if callback:
            callback({"status": "error", "step": "error", "message": f"Lỗi bài {cid}: {e}"})
        return {"success": False, "message": str(e)}


def xuat_noi_dung_ai_bai(content_id: str, format_type: str = "1:1", callback=None) -> dict:
    """Tách bước AI (Tab 3): chỉ sinh 3 Caption + Bài báo + link bài báo mock.

    KHÔNG cắt ảnh (`chuan_bi_media`) và KHÔNG đặt Status = WEB_POSTED — bài vẫn ở
    PROCESSING, chờ user bấm "Hoàn thành" (→ SAN_SANG) rồi cắt ảnh ở Tab 4 (→ HOAN_THANH).
    """
    store = lay_store()
    tim = store.tim_dong("CONTENT POOL", "Content ID", content_id)
    if not tim:
        return {"success": False, "message": f"Không tìm thấy bài {content_id}"}

    chi_so, dong = tim
    cid = dong.get("Content ID")
    key = dong.get("KEY") or "Chung"
    nhan_vat = dong.get("Nhân vật/chủ đề") or "Chung"
    caption_goc = dong.get("Caption") or ""

    if callback:
        callback({"status": "processing", "step": "lock", "message": f"Bắt đầu xử lý {cid}"})

    doi_status(cid, "PROCESSING", ghi_chu="Đang sinh nội dung trên Web UI", store=store)
    thu_muc = tao_thu_muc_ngay_gio()

    try:
        if callback:
            callback({"status": "processing", "step": "caption", "message": "Đang gọi DeepSeek sinh 3 Caption viral..."})
        caps = viet_3_caption(caption_goc)
        cap_v1 = caps.get("version_1") or ""
        cap_v2 = caps.get("version_2") or ""
        cap_v3 = caps.get("version_3") or ""

        if callback:
            callback({"status": "processing", "step": "article", "message": "Đang gọi DeepSeek viết bài báo 1500-1700 từ..."})
        bai_bao = viet_bai_bao(caption_goc, nhan_vat=nhan_vat, key=key)

        if callback:
            callback({"status": "processing", "step": "web", "message": "Đang sinh link bài báo Website..."})
        tieu_de = f"Exclusive: {nhan_vat} — The Untold Story" if nhan_vat != "Khác" else f"Insight: {key} Update"
        # Lấy ảnh ĐẦU TIÊN (Media có thể là chuỗi nhiều ảnh cách nhau "; ") — ảnh làm thumbnail bài báo
        anh_goc = str(dong.get("Media") or "").strip().split(";")[0].strip()[:300]
        res_web = dang_bai_web(tieu_de=tieu_de, noi_dung=bai_bao, anh_path=anh_goc, nhan_vat=nhan_vat, key=key)
        article_url = res_web.get("article_url") or ""

        # Gán chủ đề: ưu tiên KEY khớp, không khớp thì gọi AI
        chu_de = gan_chu_de_cho_bai(key, caption_goc or bai_bao)

        goi_fb = {
            "content_id": cid,
            "key": key,
            "nhan_vat": nhan_vat,
            "chu_de": chu_de,
            "thoi_gian_tao": datetime.now().isoformat(),
            "article_url": article_url,
            "anh_path": "",
            "caption_lua_chon": cap_v1,
            "caption_version_1": cap_v1,
            "caption_version_2": cap_v2,
            "caption_version_3": cap_v3,
            "bai_bao": bai_bao,
            "folder": thu_muc,
        }

        file_goi = os.path.join(thu_muc, f"bo_bai_{cid}.json")
        with open(file_goi, "w", encoding="utf-8") as f:
            json.dump(goi_fb, f, ensure_ascii=False, indent=2)

        file_cap = os.path.join(thu_muc, f"caption_{cid}.txt")
        with open(file_cap, "w", encoding="utf-8") as f:
            f.write(f"=== LINK BÀI BÁO (COMMENT ĐẦU TIÊN) ===\n{article_url}\n\n")
            f.write(f"=== VERSION 1 (MẶC ĐỊNH) ===\n{cap_v1}\n\n")
            f.write(f"=== VERSION 2 ===\n{cap_v2}\n\n")
            f.write(f"=== VERSION 3 ===\n{cap_v3}\n\n")

        tim_lai = store.tim_dong("CONTENT POOL", "Content ID", cid)
        if tim_lai:
            idx, row = tim_lai
            row["Caption mới"] = cap_v1
            row["Bài báo"] = bai_bao[:500] + "... [xem chi tiết trong thư mục]"
            row["Article URL"] = article_url
            row["Chủ đề"] = chu_de
            store.cap_nhat_dong("CONTENT POOL", idx, row)

        if callback:
            callback({"status": "done", "step": "done", "message": f"Đã sinh nội dung bài {cid}! Bấm Hoàn thành để chuyển sang bước cắt ảnh."})

        return {"success": True, "data": goi_fb, "folder": thu_muc}

    except Exception as e:
        doi_status(cid, "ERROR", ghi_chu=f"Lỗi AI: {str(e)[:100]}", store=store)
        if callback:
            callback({"status": "error", "step": "error", "message": f"Lỗi bài {cid}: {e}"})
        return {"success": False, "message": str(e)}


def luu_chinh_sua_bai(content_id: str, du_lieu_sua: dict) -> dict:
    """Lưu nội dung chỉnh sửa trực tiếp (Caption, Bài báo, Bản được chọn) từ Web UI."""
    store = lay_store()
    tim = store.tim_dong("CONTENT POOL", "Content ID", content_id)
    if not tim:
        return {"success": False, "message": "Không tìm thấy bài viết"}
    
    idx, row = tim
    cap_chon = du_lieu_sua.get("caption_lua_chon") or ""
    cap_v1 = du_lieu_sua.get("caption_version_1") or ""
    cap_v2 = du_lieu_sua.get("caption_version_2") or ""
    cap_v3 = du_lieu_sua.get("caption_version_3") or ""
    bai_bao = du_lieu_sua.get("bai_bao") or ""
    article_url = du_lieu_sua.get("article_url") or row.get("Article URL") or ""

    # Cập nhật row trong store
    row["Caption mới"] = cap_chon or cap_v1
    if bai_bao:
        row["Bài báo"] = bai_bao[:500] + "... [xem chi tiết trong thư mục]"
    row["Article URL"] = article_url
    row["Status"] = "SAN_SANG"
    store.cap_nhat_dong("CONTENT POOL", idx, row)

    # Cập nhật file bo_bai trong du_lieu_fb
    fb_dir = os.path.join(DUONG_DAN, "du_lieu_fb")
    if os.path.exists(fb_dir):
        for root, _, files in os.walk(fb_dir):
            target = f"bo_bai_{content_id}.json"
            if target in files:
                fpath = os.path.join(root, target)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        goi = json.load(f)
                    goi["caption_lua_chon"] = cap_chon
                    goi["caption_version_1"] = cap_v1
                    goi["caption_version_2"] = cap_v2
                    goi["caption_version_3"] = cap_v3
                    goi["bai_bao"] = bai_bao
                    goi["article_url"] = article_url
                    with open(fpath, "w", encoding="utf-8") as f:
                        json.dump(goi, f, ensure_ascii=False, indent=2)

                    # Cập nhật cả file txt
                    txt_path = os.path.join(root, f"caption_{content_id}.txt")
                    with open(txt_path, "w", encoding="utf-8") as f:
                        f.write(f"=== LINK BÀI BÁO (COMMENT ĐẦU TIÊN) ===\n{article_url}\n\n")
                        f.write(f"=== CAPTION ĐÃ CHỌN ĐĂNG ===\n{cap_chon}\n\n")
                        f.write(f"=== VERSION 1 ===\n{cap_v1}\n\n")
                        f.write(f"=== VERSION 2 ===\n{cap_v2}\n\n")
                        f.write(f"=== VERSION 3 ===\n{cap_v3}\n\n")
                    break
                except Exception as e:
                    print(f"[!] Lỗi cập nhật file gói: {e}")

    return {"success": True, "message": "Đã lưu chỉnh sửa thành công"}


def hoan_thanh_hang_loat(danh_sach_id: list, ghi_chu: str = "Đã hoàn thành hàng loạt (Tab 3)") -> dict:
    """Hoàn thành nhiều bài một lần: đặt Status = SAN_SANG, giữ caption AI đã sinh sẵn.

    Trả về {success, so_thanh_cong, so_loi, loi:[{id, err}]}.
    """
    store = lay_store()
    so_thanh_cong = 0
    loi = []
    for cid in danh_sach_id:
        cid = str(cid or "").strip()
        if not cid:
            loi.append({"id": cid, "err": "ID rỗng"})
            continue
        tim = store.tim_dong("CONTENT POOL", "Content ID", cid)
        if not tim:
            loi.append({"id": cid, "err": "Không tìm thấy bài"})
            continue
        idx, row = tim
        st = str(row.get("Status") or "").strip()
        if st == "HOAN_THANH":
            loi.append({"id": cid, "err": "Đã hoàn thành (HOAN_THANH)"})
            continue
        # Giữ caption sẵn có; nếu trống mới dùng caption gốc làm nền
        if not str(row.get("Caption mới") or "").strip():
            row["Caption mới"] = str(row.get("Caption") or "").strip()
        row["Status"] = "SAN_SANG"
        if ghi_chu:
            row["Ghi chú"] = ghi_chu
        store.cap_nhat_dong("CONTENT POOL", idx, row)
        so_thanh_cong += 1
    return {"success": True, "so_thanh_cong": so_thanh_cong, "so_loi": len(loi), "loi": loi}


def xu_ly_anh_hoan_thanh_mot_bai(content_id: str, format_type: str = "1:1", co_logo: bool = True) -> dict:
    """Bước cắt ảnh (Tab 4): tải + crop ảnh chuẩn tỷ lệ rồi đặt Status = HOAN_THANH.

    `co_logo=True` → dán logo lên ảnh (dùng cho nút Tạo Ảnh).
    `co_logo=False` → không dán logo (dùng cho ảnh reel).
    Cắt ảnh vào CHÍNH thư mục chứa `bo_bai_<id>.json` (nếu tìm thấy) để gói bài nằm cùng chỗ.
    """
    store = lay_store()
    tim = store.tim_dong("CONTENT POOL", "Content ID", content_id)
    if not tim:
        return {"success": False, "message": f"Không tìm thấy bài {content_id}"}
    _, dong = tim

    # 1) Xác định thư mục gói bài (nếu có), không thì tạo mới
    thu_muc = None
    fb_dir = os.path.join(DUONG_DAN, "du_lieu_fb")
    if os.path.exists(fb_dir):
        for root, _, files in os.walk(fb_dir):
            if f"bo_bai_{content_id}.json" in files:
                thu_muc = root
                break
    if not thu_muc:
        thu_muc = tao_thu_muc_ngay_gio()

    try:
        anh_path = chuan_bi_media(dong, format_type=format_type, thu_muc=thu_muc,
                                  co_logo=co_logo)
        if not anh_path:
            # Không tải được ảnh — vẫn đánh dấu xong để không kẹt ở tab4
            anh_path = dong.get("Media") or ""

        # 2) Cập nhật `anh_path`/`folder` vào bo_bai_<id>.json
        if os.path.exists(fb_dir):
            for root, _, files in os.walk(fb_dir):
                if f"bo_bai_{content_id}.json" in files:
                    fp = os.path.join(root, f"bo_bai_{content_id}.json")
                    try:
                        with open(fp, "r", encoding="utf-8") as f:
                            goi = json.load(f)
                        goi["anh_path"] = anh_path
                        goi["folder"] = thu_muc
                        with open(fp, "w", encoding="utf-8") as f:
                            json.dump(goi, f, ensure_ascii=False, indent=2)
                    except Exception:
                        pass
                    break

        doi_status(content_id, "HOAN_THANH", ghi_chu=f"Đã cắt ảnh ({format_type})", store=store)
        return {"success": True, "data": {"content_id": content_id, "anh_path": anh_path}}

    except Exception as e:
        doi_status(content_id, "ERROR", ghi_chu=f"Lỗi cắt ảnh: {str(e)[:100]}", store=store)
        return {"success": False, "message": str(e)}


def xu_ly_anh_reel_mot_bai(content_id: str, format_type: str = "1:1") -> dict:
    """Tạo ẢNH REEL riêng (KHÔNG logo) trong du_lieu_reel/anh_reel/.

    Không đụng vào ảnh chính (có logo) đã lưu trong bo_bai — nên nếu bạn đã bấm
    "Tạo Ảnh" trước, ảnh đăng FB vẫn giữ logo; video reel dùng ảnh không logo.
    """
    store = lay_store()
    tim = store.tim_dong("CONTENT POOL", "Content ID", content_id)
    if not tim:
        return {"success": False, "message": f"Không tìm thấy bài {content_id}"}
    _, dong = tim
    thu_muc_reel = os.path.join(DUONG_DAN, "du_lieu_reel", "anh_reel")
    os.makedirs(thu_muc_reel, exist_ok=True)
    try:
        anh_reel = chuan_bi_media(dong, format_type=format_type, thu_muc=thu_muc_reel,
                                  co_logo=False)
        if not anh_reel:
            anh_reel = dong.get("Media") or ""
        return {"success": True, "data": {"content_id": content_id, "anh_path": anh_reel}}
    except Exception as e:
        return {"success": False, "message": str(e)}


def _lay_danh_sach_theo_status(*statuses, phien=None) -> list:
    """Gom bài trong Content Pool có Status thuộc `statuses`, kèm dữ liệu bo_bai (ảnh, caption, link).

    `phien` : chỉ lấy bài thuộc phiên cào này (giá trị `Phien_cao`, hoặc `Cac_phien_gap` nếu có).
    """
    store = lay_store()
    danh_sach = store.lay_tat_ca("CONTENT POOL")
    ket_qua = []

    fb_dir = os.path.join(DUONG_DAN, "du_lieu_fb")
    map_goi = {}
    if os.path.exists(fb_dir):
        for root, _, files in os.walk(fb_dir):
            for f in files:
                if f.startswith("bo_bai_") and f.endswith(".json"):
                    cid = f.replace("bo_bai_", "").replace(".json", "")
                    try:
                        with open(os.path.join(root, f), "r", encoding="utf-8") as fp:
                            map_goi[cid] = json.load(fp)
                    except Exception:
                        pass

    for row in danh_sach:
        st = str(row.get("Status") or "").strip()
        cid = str(row.get("Content ID") or "").strip()
        if st not in statuses:
            continue
        if phien:
            cac_phien = row.get("Cac_phien_gap")
            if cac_phien is None:
                if str(row.get("Phien_cao") or "").strip() != phien:
                    continue
            elif phien not in (cac_phien if isinstance(cac_phien, list) else [str(cac_phien)]):
                continue
        if st in statuses:
            item = dict(row)
            goi = map_goi.get(cid) or {}
            item["goi_fb"] = goi
            item["anh_path"] = goi.get("anh_path") or ""
            item["reel_path"] = duong_dan_reel(cid)
            item["chu_de"] = (goi.get("chu_de") or row.get("Chủ đề") or "").strip()
            item["caption_lua_chon"] = goi.get("caption_lua_chon") or row.get("Caption mới") or ""
            item["article_url"] = goi.get("article_url") or row.get("Article URL") or ""
            item["folder"] = goi.get("folder") or ""
            ket_qua.append(item)

    return ket_qua


def lay_danh_sach_san_sang():
    """Tab 4: bài đã bấm Hoàn thành ở Tab 3 (Status = SAN_SANG) — chờ cắt ảnh."""
    return _lay_danh_sach_theo_status("SAN_SANG")


def lay_danh_sach_hoan_thanh(phien=None):
    """Tab 5: bài đã cắt ảnh xong (Status = HOAN_THANH) — đầy đủ để rà lại & xuất Excel.

    `phien` : chỉ lấy bài thuộc phiên cào này (None = tất cả các phiên).
    """
    return _lay_danh_sach_theo_status("HOAN_THANH", phien=phien)


def lay_cac_phien_hoan_thanh(store=None) -> list:
    """Phiên cào cho Tab 5: gom các phiên có chứa bài HOAN_THANH, mới nhất trước.

    Mỗi phiên trả: {phien, trang:[trang đã cào], so_bai}.
    """
    store = store or lay_store()
    phien_map = {}
    for d in store.lay_tat_ca("CONTENT POOL"):
        if str(d.get("Status") or "").strip() != "HOAN_THANH":
            continue
        cac_phien = d.get("Cac_phien_gap")
        if cac_phien is None:
            p = str(d.get("Phien_cao") or "").strip()
            ds_phien = [p] if p else []
        else:
            ds_phien = cac_phien if isinstance(cac_phien, list) else [str(cac_phien)]
        if not ds_phien:
            continue
        trang = str(d.get("Source") or "").strip()
        for p in ds_phien:
            p = str(p).strip()
            if not p:
                continue
            e = phien_map.setdefault(
                p, {"phien": p, "trang": set(), "so_bai": 0})
            if trang:
                e["trang"].add(trang)
            e["so_bai"] += 1

    ds = []
    for p, e in phien_map.items():
        ds.append({"phien": p, "trang": sorted(e["trang"]),
                   "so_bai": e["so_bai"]})
    ds.sort(key=lambda x: x["phien"], reverse=True)
    return ds


def danh_dau_da_dang_fb(content_id: str):
    """Đánh dấu bài viết đã đăng xong lên Facebook -> DONE."""
    store = lay_store()
    return doi_status(content_id, "DONE", ghi_chu="Đã đăng Facebook hoàn tất qua Antidetect", store=store)
