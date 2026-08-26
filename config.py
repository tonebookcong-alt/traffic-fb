# -*- coding: utf-8 -*-
"""Cấu hình chung của tool traffic — đọc từ config.json (tự tạo nếu chưa có).

Các trường:
    cookies_file          : file cookies.txt dùng để cào Facebook
    ai.provider           : 'mock' | 'openai' | 'anthropic' | 'gemini'
    ai.api_key            : key API (để trống khi dùng mock)
    ai.model              : tên model (vd gpt-4o-mini, claude-sonnet-4-5)
    sheets.credentials_file : file JSON service account của Google (bỏ trống = chế độ local)
    sheets.spreadsheet_id : ID Google Sheet (bỏ trống = chế độ local)
    luong_a.so_bai_moi_nguon : số bài cào mỗi nguồn mỗi lần chạy
    luong_a.so_lan_cuon   : số lần cuộn cho mỗi trang nguồn
    luong_a.delay         : giây nghỉ giữa các lần cuộn
    content_han_ngay      : content quá N ngày sẽ bị đánh dấu HET_HAN
"""

import json
import os

MAC_DINH = {
    "cookies_file": "cookies.txt",
    "ai": {
        "provider": "mock",
        "api_key": "",
        "model": "",
    },
    "sheets": {
        "credentials_file": "google_sheets_creds.json",
        "spreadsheet_id": "",
    },
    "luong_a": {
        "so_bai_moi_nguon": 10,
        "so_lan_cuon": 3,
        "delay": 3.0,
    },
    "content_han_ngay": 7,
    "media": {
        "logo_path": "",                # file logo PNG (trống = bỏ logo)
        "logo_position": "bottom_left",  # top_left | top_right | bottom_left | bottom_right
        "logo_scale": 0.17,             # chiều rộng logo = 17% chiều rộng ảnh
        "max_size": 1080,               # cạnh dài tối đa (giữ tỷ lệ, KHÔNG crop)
        "border_style": "gradient",     # none | solid | gradient
        "border_width": 30,             # độ dày viền (px)
        "border_color": "#003C8C",      # viền solid hoặc gradient màu đậm
        "border_color2": "#007ACC",     # gradient màu giữa
        "border_color3": "#FFFFFF",     # gradient màu nhạt
        "enhance_contrast": 1.10,       # chỉnh tương phản — né FB quét trùng
        "enhance_brightness": 1.05,     # chỉnh độ sáng
        "enhance_color": 1.22,          # chỉnh độ màu
    },
}

DUONG_DAN = os.path.dirname(os.path.abspath(__file__))


def duong_dan_config(path="config.json"):
    """Đường dẫn tuyệt đối tới file cấu hình trong thư mục dự án."""
    return os.path.join(DUONG_DAN, path)


def _gop(de, mac_dinh):
    """Gộp dict cấu hình — giữ giá trị người dùng, lấp chỗ trống bằng mặc định."""
    for k, v in mac_dinh.items():
        if k not in de:
            de[k] = v
        elif isinstance(v, dict):
            _gop(de[k], v)
    return de


def load_config(path="config.json"):
    """Đọc cấu hình; file chưa có thì tạo bằng mặc định."""
    p = duong_dan_config(path)
    if not os.path.isfile(p):
        ghi_config(MAC_DINH, path)
        return json.loads(json.dumps(MAC_DINH))
    try:
        with open(p, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except (json.JSONDecodeError, OSError):
        cfg = {}
    return _gop(cfg, json.loads(json.dumps(MAC_DINH)))


def ghi_config(cfg, path="config.json"):
    """Ghi cấu hình ra file (UTF-8, có xuống dòng cho dễ đọc)."""
    p = duong_dan_config(path)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    cfg = load_config()
    print(json.dumps(cfg, ensure_ascii=False, indent=2))
    print(f"\nĐường dẫn file cấu hình: {duong_dan_config()}")
