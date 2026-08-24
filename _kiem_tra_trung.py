# -*- coding: utf-8 -*-
"""So sánh 2 bản caption cùng id bai_3a28e8381505 sau chuẩn hoá."""
import json
from content_pool import chuan_hoa_text, _la_cung_bai

rows = json.load(open(r"c:\traffic fb\du_lieu_traffic\content_pool.json", encoding="utf-8"))
ngan = [r for r in rows if r.get("Content ID") == "bai_3a28e8381505"]
dai = [r for r in rows if r.get("Content ID") == "bai_1b15fc96f645"]

a = next(r["Caption"] for r in rows if r.get("Content ID") == "bai_3a28e8381505" and len(r["Caption"]) == 111)
b = next(r["Caption"] for r in rows if r.get("Content ID") == "bai_3a28e8381505" and len(r["Caption"]) == 2229)

na, nb = chuan_hoa_text(a), chuan_hoa_text(b)
print("caption 111 ký tự:")
print(repr(a))
print()
print("111 ký tự ĐẦU của bản 2229:")
print(repr(b[:111]))
print()
print("norm 111:", repr(na))
print()
print("norm 2229 (đầu 111):", repr(nb[:111]))
print()
print("_la_cung_bai(2229, 111):", _la_cung_bai(nb, na))
print("_la_cung_bai(111, 2229):", _la_cung_bai(na, nb))
print("111 in 2229 (chuẩn hoá):", na in nb)
