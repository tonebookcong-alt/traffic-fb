# -*- coding: utf-8 -*-
"""
Module REEL — tạo video reel 10s từ 1 ảnh đã xử lý (dùng ffmpeg).

- Kích thước chuẩn reel dọc FB: 1080x1920 (9:16)
- Ảnh đứng yên; nếu ảnh không phải tỷ lệ dọc -> đặt ảnh GIỮA + NỀN MỜ lấp đầy
- Thời lượng: 10s
- Nếu có nhạc: chèn 1 đoạn nhạc 10s ngẫu nhiên (từ music1/10s + NBA Music/10s)
"""
import os
import random
import subprocess
from datetime import datetime

# Đường dẫn dự án (thư mục chứa file này)
DUONG_DAN = os.path.dirname(os.path.abspath(__file__))
MUSIC_MUSIC1 = os.path.join(DUONG_DAN, "music", "music1", "10s")
MUSIC_NBA = os.path.join(DUONG_DAN, "music", "NBA Music", "10s")
REEL_DIR = os.path.join(DUONG_DAN, "du_lieu_reel")

W, H = 1080, 1920
FPS = 30
GIAY = 10


def chon_nhac_ngau_nhien(root: str = None) -> str | None:
    """Chọn ngẫu nhiên 1 file nhạc 10s. Gộp cả 2 mục music1 + NBA Music."""
    duong = []
    for folder in (MUSIC_MUSIC1, MUSIC_NBA):
        if os.path.isdir(folder):
            for f in os.listdir(folder):
                if f.lower().endswith((".mp3", ".m4a", ".aac", ".weba", ".ogg", ".wav")):
                    duong.append(os.path.join(folder, f))
    if not duong:
        return None
    return random.choice(duong)


def tao_reel(anh_path: str, co_nhac: bool = True, ten_dau_ra: str = None,
             so_nhac: int = None) -> dict:
    """Tạo video reel 10s từ ảnh `anh_path`.

    - co_nhac=True: chèn 1 đoạn nhạc 10s ngẫu nhiên.
    - so_nhac: đè tên file nhạc (test) — bỏ qua nếu None.
    Trả về dict {success, video_path, nhac_path, error}.
    """
    if not anh_path or not os.path.isfile(anh_path):
        return {"success": False, "error": f"Không có ảnh: {anh_path}"}

    os.makedirs(REEL_DIR, exist_ok=True)

    if ten_dau_ra is None:
        ten_dau_ra = datetime.now().strftime("reel_%Y%m%d_%H%M%S")
    video_path = os.path.join(REEL_DIR, f"{ten_dau_ra}.mp4")

    # Lấy nguồn nhạc
    nhac_path = None
    if co_nhac:
        nhac_path = so_nhac or chon_nhac_ngau_nhien()
        if not nhac_path:
            return {"success": False, "error": "Không có file nhạc nào trong music/music1/10s hoặc music/NBA Music/10s"}

    # Lọc phức tạp ffmpeg:
    #  - bg: scale cover + blur 20 -> nền
    #  - fg: ảnh gốc giữ tỷ lệ, đặt giữa
    #  - overlay fg lên bg
    #  - nếu có nhạc: -loop 1 ảnh, thời lượng 10s, map audio
    #  - không nhạc -> video im lặng
    vf = (
        "[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
        "crop={w}:{h},boxblur=20[bg];"
        "[0:v]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]"
    ).format(w=W, h=H)

    cmd = ["ffmpeg", "-y", "-loop", "1", "-t", str(GIAY), "-i", anh_path]

    if nhac_path:
        cmd += ["-i", nhac_path]
        # dùng shortest để dừng khi nhạc hết (cả 2 đều 10s nên ~ bằng nhau)
        cmd += [
            "-filter_complex", vf,
            "-map", "[v]", "-map", "1:a",
            "-t", str(GIAY),
            "-r", str(FPS),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            video_path,
        ]
    else:
        cmd += [
            "-filter_complex", vf,
            "-map", "[v]",
            "-t", str(GIAY),
            "-r", str(FPS),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-an",
            video_path,
        ]

    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return {"success": False, "error": r.stderr.strip()[-600:], "cmd": " ".join(cmd[:8])}
    return {"success": True, "video_path": video_path, "nhac_path": nhac_path}
