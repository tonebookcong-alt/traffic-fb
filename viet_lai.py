# -*- coding: utf-8 -*-
"""
Module VIET_LAI — Viết lại Caption (3 phiên bản) + Viết bài báo 1500-1700 từ.
Tuân thủ tuyệt đối prompt và quy tắc nghiệp vụ trong yeucau.txt.
"""

import re
from ai_client import goi_ai

with open("yeucau.txt", "r", encoding="utf-8") as f:
    _full_doc = f.read()

_idx_cap = _full_doc.find("PROMPT VI\u1ebeT L\u1ea0I CAPTION")
_idx_cap_end = _full_doc.find("Promt vi\u1ebft l\u1ea1i b\u00e0i b\u00e1o:")
PROMPT_CAPTION_SYSTEM = _full_doc[_idx_cap:_idx_cap_end].strip()

_idx_bb = _full_doc.find("\u0110\u1eccC \u0110\u00daNG B\u00c0I VI\u1ebeT T\u00d4I \u0110\u01afA SAU \u0110\u00c2Y:")
PROMPT_BAI_BAO_SYSTEM = _full_doc[_idx_bb:].strip()


def tach_3_version(raw_text: str) -> dict:
    """Tách chuỗi kết quả AI thành dict 3 version.

    Nhận linh hoạt nhiều định dạng nhãn: `VERSION 1`, `**VERSION 1**`,
    `VERSION 1:`, `Phiên bản 1 -`, ... (không phân biệt hoa/thường).
    """
    ket_qua = {"version_1": "", "version_2": "", "version_3": ""}
    if not raw_text:
        return ket_qua

    # Tìm vị trí các nhãn VERSION/PHIÊN BẢN <số> (bất kể trang trí xung quanh)
    mau = re.compile(r'(?:VERSION|PHI[ÊE]N BẢN)\s*([123])\b', re.IGNORECASE)
    vi_tri = [(m.start(), m.end(), int(m.group(1))) for m in mau.finditer(raw_text)]

    if not vi_tri:
        ket_qua["version_1"] = raw_text.strip()
        return ket_qua

    # Nội dung mỗi version = từ sau nhãn tới nhãn kế tiếp (theo thứ tự xuất hiện)
    for idx, (start, end, so) in enumerate(vi_tri):
        ket = vi_tri[idx + 1][0] if idx + 1 < len(vi_tri) else len(raw_text)
        s = re.sub(r"^[\s*:;\-–—.]+", "", raw_text[end:ket])
        # Bỏ trang trí đóng ở cuối (vd **\n\n) trước khi tới nhãn kế tiếp
        s = re.sub(r"[\s*\n]+$", "", s).strip()
        if 1 <= so <= 3:
            ket_qua[f"version_{so}"] = s

    # Đảm bảo luôn có version_1 (mặc định): nếu không tìm thấy nhãn 1, dùng phần đầu
    if not ket_qua["version_1"]:
        # Lấy phần trước nhãn đầu tiên nếu có, không thì toàn bộ chuỗi
        bat_dau = raw_text[: vi_tri[0][0]].strip()
        ket_qua["version_1"] = bat_dau or raw_text.strip()
    return ket_qua


def viet_3_caption(caption_goc: str, max_retries: int = 2) -> dict:
    """Gọi AI viết lại 3 phiên bản caption tiếng Anh viral."""
    prompt_user = f"CAPTION GỐC:\n{caption_goc.strip()}"
    for lan in range(max_retries + 1):
        try:
            raw = goi_ai(PROMPT_CAPTION_SYSTEM, prompt_user, nhiet_do=0.8, toi_da_tu=1200)
            res = tach_3_version(raw)
            if res.get("version_1"):
                return res
        except Exception as e:
            if lan == max_retries:
                raise e
    return tach_3_version("")


def viet_bai_bao(caption_goc: str, nhan_vat: str = "", key: str = "", max_retries: int = 2) -> str:
    """Gọi AI viết bài báo 1500-1700 từ tiếng Anh chuẩn SEO theo phong cách storytelling."""
    prompt_user = (
        f"CHỦ ĐỀ CHÍNH (KEY): {key}\n"
        f"NHÂN VẬT / ĐỐI TƯỢNG TRỌNG TÂM: {nhan_vat}\n\n"
        f"NỘI DUNG TÓM TẮT BAN ĐẦU:\n{caption_goc.strip()}\n\n"
        "Hãy viết bài báo đầy đủ 1500-1700 từ theo các yêu cầu đề mục và chính sách đã nêu."
    )
    for lan in range(max_retries + 1):
        try:
            bai_bao = goi_ai(PROMPT_BAI_BAO_SYSTEM, prompt_user, nhiet_do=0.7, toi_da_tu=3000)
            if bai_bao and len(bai_bao.strip()) > 200:
                return bai_bao.strip()
        except Exception as e:
            if lan == max_retries:
                raise e
    return ""


if __name__ == "__main__":
    sample = "Kyle Busch suffered a devastating engine failure during lap 145 at Daytona."
    print("Test viet_3_caption...")
    res = viet_3_caption(sample)
    print("V1:", res["version_1"][:100])
