# -*- coding: utf-8 -*-
"""
Module MEDIA — Xử lý ảnh (Pillow) cho bài đăng Facebook.
- Tải ảnh từ URL Facebook trong Content Pool
- Giữ nguyên tỷ lệ ảnh gốc (KHÔNG crop), chỉ resize cạnh dài về max_size
- Chỉnh nhẹ màu/tương phản/sáng (né FB quét trùng) + thêm viền + dán logo
- Lưu vào thư mục du_lieu_fb/<ngày_giờ>/
"""

import os
import requests
from datetime import datetime
from PIL import Image, ImageDraw, ImageEnhance, ImageOps

from config import DUONG_DAN, load_config


def tao_thu_muc_ngay_gio() -> str:
    """Tạo thư mục lưu trữ media theo phiên đăng: du_lieu_fb/YYYY-MM-DD_HH-MM/"""
    ten_folder = datetime.now().strftime("du_lieu_%Y-%m-%d_%H-%M")
    thu_muc = os.path.join(DUONG_DAN, "du_lieu_fb", ten_folder)
    os.makedirs(thu_muc, exist_ok=True)
    return thu_muc


def tai_anh(url: str, duong_dan_luu: str, timeout: int = 20) -> bool:
    """Tải ảnh từ link Facebook về đĩa."""
    if not url or not url.startswith("http"):
        return False
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
        res = requests.get(url, headers=headers, timeout=timeout)
        res.raise_for_status()
        with open(duong_dan_luu, "wb") as f:
            f.write(res.content)
        return True
    except Exception as e:
        print(f"  [!] Lỗi tải ảnh từ {url[:60]}...: {e}")
        return False


def xu_ly_anh(anh_goc_path: str, anh_dich_path: str, format_type: str = "1:1", cfg: dict = None) -> bool:
    """Giữ nguyên tỷ lệ ảnh gốc (KHÔNG crop) — chỉ resize gọn + thêm logo/viền.

    - Resize cạnh dài về `max_size` (mặc định 1080), giữ tỷ lệ, không cắt bớt gì.
    - Chỉnh nhẹ màu/tương phản/sáng (enhance_*) để né FB quét trùng nội dung.
    - Dán logo + thêm viền (solid hoặc gradient, theo `border_style`).
    `format_type` giữ để tương thích chỗ gọi cũ, nhưng không còn crop theo tỷ lệ.
    """
    cfg = cfg or (load_config().get("media") or {})
    try:
        with Image.open(anh_goc_path) as im:
            im = im.convert("RGB")
            w, h = im.size
            # Cắt bớt viền/khung sẵn có của ảnh nguồn trước khi thêm viền của mình
            crop_vien = int(float(cfg.get("crop_vien") or 4))
            if crop_vien > 0 and w > 2 * crop_vien and h > 2 * crop_vien:
                im = im.crop((crop_vien, crop_vien, w - crop_vien, h - crop_vien))
                w, h = im.size
            canh_dai = int(float(cfg.get("max_size") or 1080))
            if max(w, h) > canh_dai:
                if w >= h:
                    im = im.resize((canh_dai, int(h * canh_dai / w)), Image.Resampling.LANCZOS)
                else:
                    im = im.resize((int(w * canh_dai / h), canh_dai), Image.Resampling.LANCZOS)
            im = _tinh_chinh(im, cfg)
            im = them_logo_va_vien(im, cfg)
            im = them_vien(im, cfg)
            im.save(anh_dich_path, format="JPEG", quality=90)
            return True
    except Exception as e:
        print(f"  [!] Lỗi xử lý ảnh {anh_goc_path}: {e}")
        return False


def _vi_hex(h) -> tuple:
    """'#003C8C' -> (0, 60, 140). Trả màu đen nếu chuỗi sai."""
    try:
        s = str(h or "").strip().lstrip("#")
        if len(s) != 6:
            raise ValueError
        return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return (0, 0, 0)


def _tinh_chinh(anh: Image.Image, cfg: dict) -> Image.Image:
    """Chỉnh nhẹ tương phản/độ sáng/màu để đổi hash, mắt khó nhận."""
    c = float(cfg.get("enhance_contrast") or 1.0)
    b = float(cfg.get("enhance_brightness") or 1.0)
    s = float(cfg.get("enhance_color") or 1.0)
    if c != 1.0:
        anh = ImageEnhance.Contrast(anh).enhance(c)
    if b != 1.0:
        anh = ImageEnhance.Brightness(anh).enhance(b)
    if s != 1.0:
        anh = ImageEnhance.Color(anh).enhance(s)
    return anh


def them_vien(anh: Image.Image, cfg: dict = None) -> Image.Image:
    """Thêm viền NGOÀI cho ảnh, trả ảnh mới (to hơn). style: none | solid | gradient.

    cfg: dict "media" đọc từ config.json:
      border_style   : none | solid | gradient
      border_width   : độ dày viền (px)
      border_color   : màu viền (solid) hoặc màu ĐẬM (gradient) — hex
      border_color2  : màu GIỮA (gradient) — hex
      border_color3  : màu NHẠT (gradient) — hex
    """
    if cfg is None:
        cfg = load_config().get("media") or {}
    style = str(cfg.get("border_style") or "solid").lower()
    bw = int(float(cfg.get("border_width") or 0))
    if bw <= 0 or style == "none":
        return anh
    if style == "gradient":
        top = _vi_hex(cfg.get("border_color") or "#003C8C")
        mid = _vi_hex(cfg.get("border_color2") or top)
        bot = _vi_hex(cfg.get("border_color3") or "#FFFFFF")
    else:  # solid
        top = mid = bot = _vi_hex(cfg.get("border_color") or "#000000")

    w, h = anh.size
    base = Image.new("RGB", (w + 2 * bw, h + 2 * bw))
    draw = ImageDraw.Draw(base)
    half = max(1, bw // 2)
    for i in range(bw):
        if i < half:
            t = i / half
            c = tuple(int(top[k] * (1 - t) + mid[k] * t) for k in range(3))
        else:
            t = (i - half) / half
            c = tuple(int(mid[k] * (1 - t) + bot[k] * t) for k in range(3))
        draw.rectangle([i, i, base.width - 1 - i, base.height - 1 - i], outline=c)
    base.paste(anh, (bw, bw))
    return base


def them_logo_va_vien(anh: Image.Image, cfg: dict = None) -> Image.Image:
    """Chỉ DÁN LOGO lên ảnh (viền do them_vien xử lý riêng), trả về ảnh mới.

    cfg: dict "media" đọc từ config.json:
      logo_path     : file logo PNG (bỏ qua nếu trống/không tồn tại)
      logo_position : top_left | top_right | bottom_left | bottom_right
      logo_scale    : chiều rộng logo = tỷ lệ * chiều rộng ảnh
    Lỗi thì bỏ logo, giữ nguyên ảnh (không raise).
    """
    if cfg is None:
        cfg = load_config().get("media") or {}
    logo_path = str(cfg.get("logo_path") or "").strip()
    if logo_path and os.path.isfile(logo_path):
        try:
            logo = Image.open(logo_path).convert("RGBA")
            w, h = anh.size
            scale = float(cfg.get("logo_scale") or 0.12)
            logo_w = max(1, int(w * scale))
            logo_h = int(logo.height * (logo_w / logo.width))
            logo = logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)

            pos = str(cfg.get("logo_position") or "bottom_left").lower()
            pad = max(1, int(w * 0.03))  # cách mép 3%
            x = w - logo_w - pad if "right" in pos else pad
            y = h - logo_h - pad if "bottom" in pos else pad

            if anh.mode != "RGBA":
                anh = anh.convert("RGBA")
            anh.paste(logo, (max(0, x), max(0, y)), logo)
            anh = anh.convert("RGB")
        except Exception as e:
            print(f"  [!] Lỗi dán logo {logo_path}: {e}")
    return anh


def chuan_bi_media(bai_viet: dict, format_type: str = "1:1", thu_muc: str = None) -> str:
    """Tải và xử lý ảnh cho bài viết, trả về đường dẫn file ảnh hoàn chỉnh."""
    media_url = str(bai_viet.get("Media") or "").strip()
    content_id = str(bai_viet.get("Content ID") or "post").replace(":", "_").replace("/", "_")

    if not thu_muc:
        thu_muc = tao_thu_muc_ngay_gio()

    if not media_url or not media_url.startswith("http"):
        return ""

    anh_tho = os.path.join(thu_muc, f"{content_id}_raw.jpg")
    anh_xuly = os.path.join(thu_muc, f"{content_id}_{format_type.replace(':', 'x')}.jpg")

    if tai_anh(media_url, anh_tho):
        if xu_ly_anh(anh_tho, anh_xuly, format_type=format_type):
            return anh_xuly
        return anh_tho
    return ""


if __name__ == "__main__":
    print("Media module sẵn sàng.")
