# -*- coding: utf-8 -*-
"""
Module DANG_WEB — Đăng bài báo lên Website đích qua REST API.
- Chế độ API thật:
    + Mode "blogbio" (BlogBio): form-encoded + upload ảnh qua presigned URL,
      field ảnh dùng `feature_image`, trả về `link` từ API.
    + Mode "json" (API thường): gửi JSON payload như cũ (tương thích ngược).
- Chế độ GIẢ LẬP (Mock Simulation) khi chưa có API URL:
  tự tạo URL bài báo hợp lệ và ghi log dữ liệu để kiểm tra.
"""

import json
import os
import re
import time
import requests
from datetime import datetime

from config import DUONG_DAN, load_config


def _tao_slug(text: str) -> str:
    """Tạo slug URL từ tiêu đề hoặc tên nhân vật."""
    if not text:
        return "article"
    s = text.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s).strip("-")
    return s[:60] or "article"


def _tai_len_blogbio(anh_path: str, api_token: str, base_url: str = "") -> str:
    """Upload ảnh lên BlogBio qua presigned URL, trả về fileUrl ("" nếu lỗi).

    Flow:
      1) POST /api/uploads/presigned-image-url (Bearer) -> nhận upload.url + fileUrl
      2) PUT file ảnh vào upload.url
    `base_url` = "https://host" — bỏ phần /api/posts nếu api_url trỏ thẳng vào endpoint.
    """
    if not anh_path or not api_token:
        return ""
    # Chỉ upload ảnh cục bộ; URL sẵn có (http) thì dùng luôn (nếu là ảnh của blog thì ok)
    if str(anh_path).startswith("http"):
        return anh_path
    if not os.path.isfile(anh_path):
        return ""

    base = (base_url or "").rstrip("/")
    if not base:
        # Tự suy host từ api_url nếu có
        return ""
    presign_url = base + "/api/uploads/presigned-image-url"

    ten_file = os.path.basename(anh_path) or "image.jpg"
    kich_thuoc = os.path.getsize(anh_path)
    mime = "image/jpeg"
    low = ten_file.lower()
    if low.endswith(".png"):
        mime = "image/png"
    elif low.endswith((".webp",)):
        mime = "image/webp"
    elif low.endswith((".gif",)):
        mime = "image/gif"

    try:
        # 1) Xin presigned URL
        r = requests.post(
            presign_url,
            headers={"Authorization": f"Bearer {api_token}"},
            data={
                "fileName": ten_file,
                "contentType": mime,
                "size": kich_thuoc,
                "auditContext[record_type]": "Post",
                "auditContext[action_label]": "post image",
            },
            timeout=60,
        )
        r.raise_for_status()
        d = r.json()
        upload = (d.get("data") or {}).get("upload") or {}
        file_url = (d.get("data") or {}).get("fileUrl") or ""
        up_url = upload.get("url") or ""
        if not up_url or not file_url:
            return ""

        # 2) PUT file ảnh lên presigned URL (Cloudflare R2)
        with open(anh_path, "rb") as f:
            up = requests.put(up_url, data=f, headers={"Content-Type": mime}, timeout=120)
        if up.status_code not in (200, 201, 204):
            return ""
        return file_url
    except Exception as e:
        print(f"  [!] Lỗi upload ảnh BlogBio: {e}")
        return ""


def _dang_blogbio(api_url: str, api_token: str, tieu_de: str, noi_dung: str,
                  anh_path: str = "", nhan_vat: str = "", key: str = "",
                  max_retries: int = 2) -> dict:
    """Đăng bài theo flow BlogBio: upload ảnh presigned + POST form-encoded."""
    # Suy host: api_url dạng https://host/api/posts hoặc https://host
    host = api_url
    for suf in ("/api/posts", "/api/post", "/api", "/"):
        if host.endswith(suf):
            host = host[: -len(suf)]
            break
    host = host.rstrip("/")

    # 1) Upload ảnh (nếu có) -> feature_image
    feature_image = ""
    if anh_path:
        feature_image = _tai_len_blogbio(anh_path, api_token, base_url=host)

    slug = _tao_slug(tieu_de) if tieu_de else _tao_slug(key or nhan_vat)
    if not slug:
        slug = f"bai-{int(time.time())}"
    slug = f"{slug}-{int(time.time()) % 100000}"

    tags = [key] if key else []
    if nhan_vat and nhan_vat not in tags:
        tags.append(nhan_vat)

    for lan in range(max_retries + 1):
        try:
            data = {
                "title": tieu_de or f"Story on {nhan_vat or key}",
                "content": noi_dung,
                "permalink": slug,
                "category": key or "News",
            }
            if feature_image:
                data["feature_image"] = feature_image
            if tags:
                data["tags[]"] = tags[:8]

            resp = requests.post(
                api_url,
                headers={"Authorization": f"Bearer {api_token}"},
                data=data,
                timeout=90,
            )
            resp.raise_for_status()
            d = resp.json()
            article_url = d.get("link") or d.get("url") or d.get("article_url")
            article_id = d.get("postId") or d.get("post_id") or d.get("id") or ""
            if article_url:
                return {
                    "success": True,
                    "article_url": article_url,
                    "article_id": str(article_id),
                    "message": "Đăng web thành công",
                }
            # API trả 200 nhưng không có link -> coi là lỗi
            err_msg = d.get("message") or str(d)[:200]
            if lan == max_retries:
                return {"success": False, "article_url": "", "article_id": "",
                        "message": f"API không trả link: {err_msg}"}
        except requests.HTTPError as e:
            chi_tiet = ""
            try:
                chi_tiet = str(e.response.json())[:300]
            except Exception:
                chi_tiet = str(e)
            if lan == max_retries:
                print(f"  [!] Lỗi đăng BlogBio sau {max_retries + 1} lần: {chi_tiet}")
                return {"success": False, "article_url": "", "article_id": "",
                        "message": f"Lỗi API ({e.response.status_code}): {chi_tiet}"}
        except Exception as e:
            if lan == max_retries:
                print(f"  [!] Lỗi đăng BlogBio sau {max_retries + 1} lần: {e}")
                return {"success": False, "article_url": "", "article_id": "",
                        "message": f"Lỗi kết nối: {str(e)[:200]}"}
        time.sleep(1)
    return {"success": False, "article_url": "", "article_id": "",
            "message": "Lỗi không xác định"}


def dang_bai_web(tieu_de: str, noi_dung: str, anh_path: str = "",
                 nhan_vat: str = "", key: str = "", max_retries: int = 2) -> dict:
    """Đăng bài viết lên website, trả về dict kết quả:
    {
        "success": True/False,
        "article_url": "https://...",
        "article_id": "...",
        "message": "..."
    }
    """
    cfg = load_config()
    web_cfg = cfg.get("website") or {}
    api_url = (web_cfg.get("api_url") or "").strip()
    api_token = (web_cfg.get("api_token") or "").strip()
    mode = (web_cfg.get("mode") or "json").strip().lower()

    # -------------------------------------------------------------
    # 1. CHẾ ĐỘ GIẢ LẬP (KHI CHƯA CÓ API URL THẬT)
    # -------------------------------------------------------------
    if not api_url:
        stamp = int(time.time())
        slug_nv = _tao_slug(nhan_vat) if nhan_vat else _tao_slug(key)
        slug_td = _tao_slug(tieu_de)[:40] if tieu_de else "breaking-news"
        mock_url = f"https://dailysportswire.com/articles/{slug_nv}-{slug_td}-{stamp % 10000}"

        # Ghi log bài đăng giả lập
        log_dir = os.path.join(DUONG_DAN, "du_lieu_fb")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "web_posts_simulated.json")

        record = {
            "time": datetime.now().isoformat(),
            "key": key,
            "nhan_vat": nhan_vat,
            "tieu_de": tieu_de or f"Latest update on {nhan_vat or key}",
            "noi_dung_sample": (noi_dung[:300] + "...") if noi_dung else "",
            "anh_path": anh_path,
            "mock_article_url": mock_url,
        }

        danh_sach = []
        if os.path.exists(log_file):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    danh_sach = json.load(f)
            except (json.JSONDecodeError, OSError):
                danh_sach = []
        danh_sach.append(record)
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(danh_sach, f, ensure_ascii=False, indent=2)

        print(f"  [i] [GIẢ LẬP WEB] Đã tạo Article URL: {mock_url}")
        return {
            "success": True,
            "article_url": mock_url,
            "article_id": f"mock_{stamp}",
            "message": "Đăng thành công ở chế độ giả lập (Simulation)",
        }

    # -------------------------------------------------------------
    # 2. CHẾ ĐỘ GỌI API THẬT
    # -------------------------------------------------------------
    if mode == "blogbio":
        return _dang_blogbio(api_url, api_token, tieu_de, noi_dung,
                             anh_path=anh_path, nhan_vat=nhan_vat, key=key,
                             max_retries=max_retries)

    # Mode JSON (API thường, tương thích ngược)
    headers = {
        "Authorization": f"Bearer {api_token}" if api_token else "",
        "Content-Type": "application/json",
    }
    payload = {
        "title": tieu_de or f"Story on {nhan_vat or key}",
        "content": noi_dung,
        "category": key,
        "tags": [nhan_vat, key] if nhan_vat else [key],
        "image": anh_path,
    }

    for lan in range(max_retries + 1):
        try:
            resp = requests.post(api_url, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            article_url = data.get("url") or data.get("article_url") or data.get("link")
            article_id = data.get("id") or data.get("post_id") or ""

            if article_url:
                return {
                    "success": True,
                    "article_url": article_url,
                    "article_id": article_id,
                    "message": "Đăng web thành công",
                }
        except requests.HTTPError as e:
            chi_tiet = ""
            try:
                chi_tiet = str(e.response.json())[:300]
            except Exception:
                chi_tiet = str(e)
            if lan == max_retries:
                print(f"  [!] Lỗi đăng website sau {max_retries + 1} lần: {chi_tiet}")
                return {"success": False, "article_url": "", "article_id": "",
                        "message": f"Lỗi API ({e.response.status_code}): {chi_tiet}"}
        except Exception as e:
            if lan == max_retries:
                print(f"  [!] Lỗi đăng website sau {max_retries + 1} lần: {e}")
                return {
                    "success": False,
                    "article_url": "",
                    "article_id": "",
                    "message": f"Lỗi kết nối: {str(e)[:200]}",
                }
        time.sleep(1)

    return {"success": False, "article_url": "", "article_id": "",
            "message": "Lỗi không xác định"}


if __name__ == "__main__":
    res = dang_bai_web("Kyle Busch wins at Bristol", "<p>Nội dung test.</p>",
                       anh_path="", nhan_vat="Kyle Busch", key="NASCAR")
    print(json.dumps(res, ensure_ascii=False, indent=2))
