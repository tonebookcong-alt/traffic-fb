# -*- coding: utf-8 -*-
"""In nhanh nội dung pool để đối chiếu chống trùng."""
import json

rows = json.load(open(r"c:\traffic fb\du_lieu_traffic\content_pool.json", encoding="utf-8"))
print(f"== {len(rows)} dong ==")
for i, r in enumerate(rows):
    cap = r.get("Caption") or ""
    print(f"[{i}] id={r.get('Content ID')} | {r.get('Status')} | len={len(cap)}")
    print(f"     head: {cap[:100]!r}")
