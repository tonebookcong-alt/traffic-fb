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
    """Tách chuỗi kết quả AI thành dict 3 version."""
    ket_qua = {"version_1": "", "version_2": "", "version_3": ""}
    if not raw_text:
        return ket_qua

    m1 = re.search(r'VERSION\s*1\s*[:\n]+(.*?)(?=VERSION\s*2|$)', raw_text, re.DOTALL | re.IGNORECASE)
    m2 = re.search(r'VERSION\s*2\s*[:\n]+(.*?)(?=VERSION\s*3|$)', raw_text, re.DOTALL | re.IGNORECASE)
    m3 = re.search(r'VERSION\s*3\s*[:\n]+(.*)', raw_text, re.DOTALL | re.IGNORECASE)

    if m1:
        ket_qua["version_1"] = m1.group(1).strip()
    if m2:
        ket_qua["version_2"] = m2.group(1).strip()
    if m3:
        ket_qua["version_3"] = m3.group(1).strip()

    if not ket_qua["version_1"]:
        ket_qua["version_1"] = raw_text.strip()
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
            bai_bao = goi_ai(PROMPT_BAI_BAO_SYSTEM, prompt_user, nhiet_do=0.7, toi_da_tu=4500)
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
