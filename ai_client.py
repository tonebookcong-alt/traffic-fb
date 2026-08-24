# -*- coding: utf-8 -*-
"""
Gọi AI dùng chung cho mọi bước viết/nhận diện của tool.

Chế độ theo config.json -> ai.provider:
  - mock      : KHÔNG cần key — trả kết quả giả (chạy thử toàn bộ luồng)
  - openai    : API OpenAI  (chat completions, openai-compatible)
  - anthropic : API Claude
  - gemini    : API Google Gemini

Điền key ở config.json:
  "ai": { "provider": "openai", "api_key": "sk-...", "model": "gpt-4o-mini" }
"""

import hashlib

from config import load_config

# ===================================================================
# Chế độ mock — trả kết quả giả ổn định để test luồng khi chưa có key
# ===================================================================
def _goi_mock(he_thong, nguoi_dung, nhiet_do=0.7, toi_da_tu=1500):
    """Trả lời giả theo "ý định" của prompt (nhận biết qua vài từ khoá)."""
    noi_dung = (he_thong + "\n" + nguoi_dung)
    # --- nhận diện nhân vật ---
    if "Nhân vật" in he_thong or "nhân vật" in he_thong:
        # ưu tiên từ gợi ý: dòng 'Nhân vật gợi ý: A, B, C'
        import re
        m = re.search(r"gợi ý[:\s]+([^\n]+)", nguoi_dung)
        if m and m.group(1).strip():
            ten = m.group(1).strip().split(",")[0].strip()
            if ten:
                return ten[:60]
        return "Chủ đề chung"
    # --- viết lại caption (3 bản) ---
    if "VERSION 1" in he_thong or "caption" in he_thong.lower():
        tam = re.sub(r"\s+", " ", nguoi_dung)[:300]
        return ("VERSION 1\n" + tam + " — [bản 1]\n\n"
                "VERSION 2\n" + tam + " — [bản 2]\n\n"
                "VERSION 3\n" + tam + " — [bản 3]")
    # --- viết bài báo ---
    if "1500" in he_thong or "bài viết tiếng Anh" in he_thong:
        return ("[MOCK BÀI BÁO — 1500-1700 từ] "
                "Nội dung mẫu sinh từ caption gốc, đủ 7-8 đề mục. "
                "Khi có key API thật, nội dung này sẽ là bài báo thật.")
    # --- mặc định ---
    dai = min(len(nguoi_dung) + 50, toi_da_tu)
    return nguoi_dung[:dai]


# ===================================================================
# Gọi AI thật
# ===================================================================
def _goi_openai(api_key, model, he_thong, nguoi_dung, nhiet_do, toi_da_tu):
    import requests
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model or "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": he_thong},
                {"role": "user", "content": nguoi_dung},
            ],
            "temperature": nhiet_do,
            "max_tokens": toi_da_tu,
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _goi_anthropic(api_key, model, he_thong, nguoi_dung, nhiet_do, toi_da_tu):
    import requests
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model or "claude-sonnet-4-5",
            "max_tokens": toi_da_tu,
            "temperature": nhiet_do,
            "system": he_thong,
            "messages": [{"role": "user", "content": nguoi_dung}],
        },
        timeout=180,
    )
    resp.raise_for_status()
    return "".join(b["text"] for b in resp.json()["content"] if b["type"] == "text").strip()


def _goi_gemini(api_key, model, he_thong, nguoi_dung, nhiet_do, toi_da_tu):
    import requests
    ten = model or "gemini-1.5-flash"
    resp = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{ten}:generateContent",
        params={"key": api_key},
        json={
            "system_instruction": {"parts": [{"text": he_thong}]},
            "contents": [{"parts": [{"text": nguoi_dung}]}],
            "generationConfig": {
                "temperature": nhiet_do,
                "maxOutputTokens": toi_da_tu,
            },
        },
        timeout=120,
    )
    resp.raise_for_status()
    du_lieu = resp.json()
    return du_lieu["candidates"][0]["content"]["parts"][0]["text"].strip()


def goi_ai(he_thong, nguoi_dung, nhiet_do=0.7, toi_da_tu=1500) -> str:
    """Gọi AI theo provider trong config.json. Ném lỗi rõ ràng khi thiếu key."""
    cfg = load_config()
    provider = cfg["ai"]["provider"] or "mock"
    api_key = (cfg["ai"].get("api_key") or "").strip()
    model = (cfg["ai"].get("model") or "").strip()

    if provider == "mock":
        return _goi_mock(he_thong, nguoi_dung, nhiet_do, toi_da_tu)

    if not api_key:
        raise RuntimeError(
            "config.json chưa có ai.api_key. Hoặc điền key API, hoặc để "
            "provider='mock' để chạy thử không cần key.")

    if provider == "openai":
        return _goi_openai(api_key, model, he_thong, nguoi_dung, nhiet_do, toi_da_tu)
    if provider == "anthropic":
        return _goi_anthropic(api_key, model, he_thong, nguoi_dung, nhiet_do, toi_da_tu)
    if provider == "gemini":
        return _goi_gemini(api_key, model, he_thong, nguoi_dung, nhiet_do, toi_da_tu)
    raise RuntimeError(f"ai.provider không hợp lệ: {provider} "
                       "(chỉ nhận: mock, openai, anthropic, gemini)")


if __name__ == "__main__":
    # test nhanh: python ai_client.py
    cfg = load_config()
    print(f"Provider: {cfg['ai']['provider']}")
    print(goi_ai("Bạn là trợ lý.", "Chào bạn, giới thiệu 1 câu.")[:200])
