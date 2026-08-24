# -*- coding: utf-8 -*-
"""
Nhận diện NHÂN VẬT/CHỦ ĐỀ của bài viết — trọng tâm của logic chọn content.

Cách hoạt động (đã chốt với user):
- Mỗi KEY khai báo danh sách nhân vật gợi ý (cột "Nhân vật gợi ý" trong
  SOURCE CONFIG, phân tách bằng dấu phẩy).
- AI được yêu cầu: ưu tiên chọn 1 nhân vật TỪ danh sách gợi ý nếu khớp;
  không khớp thì AI được phép đề xuất tên mới ngắn gọn (không tự bịa khi
  không rõ — lúc đó trả 'Khác').

Kết quả phải ổn định: cùng 1 bài cào 2 lần phải ra cùng 1 nhân vật.
"""

from ai_client import goi_ai

HE_THONG = (
    "Bạn là bộ phận phân loại nội dung cho một công cụ quản lý trang Facebook. "
    "Nhiệm vụ: đọc caption một bài viết và xác định NHÂN VẬT HOẶC CHỦ ĐỀ chính "
    "của bài. "
    "QUY TẮC:\n"
    "1. Ưu tiên chọn một tên TỪ DANH SÁCH GỢI Ý nếu bài viết thực sự nói về "
    "nhân vật/chủ đề đó.\n"
    "2. Nếu không khớp bất kỳ gợi ý nào, đề xuất tên mới ngắn gọn (2-4 từ, "
    "không ghi chú).\n"
    "3. Không chắc chắn thì trả đúng chữ: Khác\n"
    "4. TRẢ VỀ ĐÚNG MỘT DÒNG: tên nhân vật/chủ đề. KHÔNG kèm giải thích, "
    "không dấu ngoặc kép, không dấu câu thừa."
)


def nhan_dien_nhan_vat(text: str, key: str, goi_y: list = None) -> str:
    """Trả về tên nhân vật/chủ đề của bài (chuẩn hoá: cắt khoảng trắng)."""
    goi_y_str = ", ".join(g.strip() for g in (goi_y or []) if g.strip())
    nguoi_dung = (
        f"KEY (chủ đề tổng): {key}\n"
        f"Nhân vật gợi ý: {goi_y_str if goi_y_str else 'không có'}\n\n"
        f"CAPTION BÀI VIẾT:\n{(text or '')[:2000]}\n\n"
        "Trả về tên nhân vật/chủ đề:"
    )
    ket_qua = goi_ai(HE_THONG, nguoi_dung, nhiet_do=0.2, toi_da_tu=60)
    ket_qua = (ket_qua or "").strip().strip('"').strip("'")
    # giữ lại dòng đầu tiên (AI đôi khi trả kèm dòng thừa)
    if "\n" in ket_qua:
        ket_qua = ket_qua.splitlines()[0].strip()
    return ket_qua[:60] or "Khác"


if __name__ == "__main__":
    # test nhanh: python nhan_dien.py
    import sys
    cap = sys.argv[1] if len(sys.argv) > 1 else (
        "Chiefs Fall 20-12 at Arrowhead: Patrick Mahomes took the blame after "
        "the loss, saying the offense wasn't good enough.")
    print("KEY=NFL, gợi ý=[Patrick Mahomes, Travis Kelce, Tom Brady, Josh Allen]")
    print("→", nhan_dien_nhan_vat(cap, "NFL",
                                  ["Patrick Mahomes", "Travis Kelce", "Tom Brady"]))
