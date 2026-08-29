# -*- coding: utf-8 -*-
"""
Cat cac file nhac nguon trong music/ thanh tung doan 10s (mp3).
- NBAmusic.weba            -> music/NBA Music/10s/  (prefix NBA_)
- videoplayback.weba       -> music/music1/10s/     (prefix VP1_)
- videoplayback (1).weba   -> music/music1/10s/     (prefix VP2_)
Chỉ giữ các đoạn ĐỦ 10s (bỏ đoạn lẻ cuối <10s) để reel luôn đủ 10s.
"""
import os
import subprocess

MUSIC_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music")
SEG_LEN = 10  # giây
MIN_GIU = 9.8  # chỉ giữ đoạn từ đây trở lên (gần đủ 10s)


def duration(src: str) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", src],
            capture_output=True, text=True
        ).stdout.strip()
        return float(out)
    except Exception:
        return 0.0


def cat_file(src: str, dest_dir: str, prefix: str):
    os.makedirs(dest_dir, exist_ok=True)
    dur = duration(src)
    if dur <= 0:
        print(f"  [!] Không đọc được duration: {src}")
        return 0
    so_seg, start, i = 0, 0.0, 1
    while start < dur - 0.2:
        end = start + SEG_LEN
        if end > dur:
            end = dur
        do_dai = end - start
        if do_dai >= MIN_GIU:
            out = os.path.join(dest_dir, f"{prefix}_seg{i:02d}.mp3")
            r = subprocess.run(
                ["ffmpeg", "-y", "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
                 "-i", src, "-c:a", "libmp3lame", "-q:a", "2", out],
                capture_output=True, text=True)
            if r.returncode != 0:
                print(f"  [!] Lỗi cắt {out}: {r.stderr.strip()[:150]}")
            else:
                print(f"  [+] {os.path.basename(out)}  ({do_dai:.1f}s)")
                so_seg += 1
        start, i = end, i + 1
    return so_seg


def lam_sach(folder: str):
    if os.path.isdir(folder):
        for f in os.listdir(folder):
            if f.endswith(".mp3"):
                try:
                    os.remove(os.path.join(folder, f))
                except OSError:
                    pass


print("=== BẮT ĐẦU CẮT NHẠC ===")

# Dọn 2 thư mục đích để không còn file cũ bị đè
for d in (os.path.join(MUSIC_ROOT, "NBA Music", "10s"),
          os.path.join(MUSIC_ROOT, "music1", "10s")):
    lam_sach(d)

# NBA Music
src = os.path.join(MUSIC_ROOT, "NBAmusic.weba")
if os.path.isfile(src):
    dest = os.path.join(MUSIC_ROOT, "NBA Music", "10s")
    print(f"\n[NBA Music] -> {dest}")
    print(f"  -> {cat_file(src, dest, 'NBA')} đoạn")

# music1 — 2 file videoplayback, prefix riêng
for ten, pf in [("videoplayback.weba", "VP1"), ("videoplayback (1).weba", "VP2")]:
    src = os.path.join(MUSIC_ROOT, ten)
    if os.path.isfile(src):
        dest = os.path.join(MUSIC_ROOT, "music1", "10s")
        print(f"\n[music1] {ten} -> {dest}")
        n = cat_file(src, dest, pf)
        print(f"  -> {n} đoạn")

print("\n=== HOÀN TẤT ===")
