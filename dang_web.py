# -*- coding: utf-8 -*-
"""
Module DANG_WEB — Đăng bài báo lên Website đích qua REST API.
- Hỗ trợ chế độ API thật (khi có URL + Token)
- Hỗ trợ chế độ GIẢ LẬP (Mock Simulation) khi chưa có tài liệu API:
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
            except Exception:
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
        except Exception as e:
            if lan == max_retries:
                print(f"  [!] Lỗi đăng website sau {max_retries + 1} lần: {e}")
                return {
                    "success": False,
                    "article_url": "",
                    "article_id": "",
                    "message": str(e),
                }
            time.sleep(2)

    return {"success": False, "article_url": "", "article_id": "", "message": "Không phản hồi"}


if __name__ == "__main__":
    res = dang_bai_web("Kyle Busch engine failure", "Full story content...", "", "Kyle Busch", "NASCAR")
    print("Kết quả test đăng web:", res)
