# 📊 Facebook Scraper — Cào dữ liệu Page (text + ảnh) + Đánh giá bài tiềm năng

Công cụ tự động cào bài viết (văn bản + ảnh) từ nhiều Facebook Page công khai, xuất ra 1 file Excel kèm điểm số tương tác — và có giao diện web để theo dõi tiến trình và xem kết quả trực tiếp. Không cần biết lập trình.

---

# HƯỚNG DẪN SỬ DỤNG
Cách nhanh nhất ném link cho antigravity hoặc các AI agent khác để nó cài full.
## Bước 1. Kiểm tra môi trường Python
- Mở **Command Prompt** hoặc **PowerShell**
- Chạy lệnh: `python --version`
- Nếu thấy **Python 3.10 hoặc mới hơn** → chuyển sang Bước 2
- Nếu báo lỗi "không nhận diện": 
  1. Tải Python từ https://www.python.org/downloads/
  2. **Lưu ý:** Tích chọn "Add python.exe to PATH" khi cài
  3. Mở lại cửa sổ terminal sau khi cài xong

## Bước 2. Cài đặt các thư viện cần thiết (chỉ cần làm 1 lần)
- Di chuyển đến thư mục dự án (`c:\traffic fb`)
- Chạy lệnh: 
  ```bash
  pip install -r requirements.txt
  ```
- Chờ quá trình cài đặt hoàn thành (không có lỗi đỏ)
- **Ghi chú:** Nếu máy không có Edge/Chrome, cần chạy thêm:
  ```bash
  python -m playwright install chromium
  ```

## Bước C. Xuất cookies từ tài khoản Facebook (BẮT BUỘC)

> Facebook chặn truy cập ẩn danh — **không có cookies thì không cào được gì**.

**Cách 1 — Dùng extension (khuyên dùng, dễ nhất):**
1. Mở Chrome/Edge → vào Web Store → tìm **"cookies editor for chorme"** → Cài.
2. Mở `facebook.com` (đã đăng nhập tài khoản).
3. Bấm icon extension (góc phải trên) → **Export** → đã được sao chép sau đó **vào thư mục dự án** (`c:\traffic fb`) xóa hết xong dán nội dung đã export vào
4. Kiểm tra: file `cookies.txt` phải có nội dung (vài chục dòng trở lên).

## Bước D. Chạy giao diện web

```bash
python webui.py
```

Trình duyệt **tự mở** `http://127.0.0.1:5000`. Cửa sổ cmd giữ nguyên (đừng tắt — đó là server). Muốn thoát: bấm `Ctrl+C` trong cửa sổ cmd.

## Bước E. Cào dữ liệu (tab "Cào dữ liệu")

1. **Danh sách trang**:dán url của trang fb cần cào vào
   https://www.facebook.com/kenh14
2. **Số bài mỗi trang**: để 20 (như bạn cần) — khuyến nghị 20-30  để an toàn.
3. **Số lần cuộn**: để 10 (là mức tối thiểu). Tool **tự cuộn thêm** cho tới khi đủ số bài đã đặt — chỉ dừng sớm khi trang hết bài mới.
4. **Nghỉ (giây)**: để 3 — giảm rủi ro bị Facebook chặn.
5. **File cookies.txt**: để mặc định `cookies.txt`. Muốn chắc chắn → bấm **🔎 Kiểm tra cookies** trước: vài giây sau sẽ báo "hợp lệ ✅" hoặc yêu cầu xuất lại cookies.
6. Bấm **▶ Bắt đầu cào**.

Theo dõi **trực tiếp** ở phía dưới: bảng trạng thái (bài viết/ảnh đang tăng), nhật ký chạy, và từng bài mới hiện ngay trong bảng live. Muốn dừng giữa chừng → bấm **⏹ Dừng**.

## Bước F. Xem kết quả (tab "Kết quả")

- Toàn bộ bài viết hiển thị như trong Excel: **ảnh thu nhỏ** (bấm phóng to), nội dung (kèm **hashtag** ở cuối bài), cảm xúc, bình luận, chia sẻ, điểm, mức tiềm năng (🟩 CAO / 🟨 TRUNG_BINH / ⬜ THAP), link bài (bấm mở Facebook).
- Lọc theo trang hoặc mức tiềm năng. Bài tiềm năng nhất xếp trên cùng.
- Bấm **📥 Tải file Excel** → lưu file về máy (sheet *Tổng quan* + 1 sheet mỗi trang, có tô màu + lọc + link). Mỗi lần chạy tạo **1 file riêng** trong folder `du_lieu_exel` (tên kèm giờ chạy, ví dụ `du_lieu_2026-08-23_14-30.xlsx`) — không ghi đè lần chạy trước.

## Bước G. Các file tạo ra (trong thư mục dự án)

| File | Nội dung |
|---|---|
| `du_lieu_exel/du_lieu_<ngày-giờ>.xlsx` | **File Excel chính** — mỗi lần chạy 1 file mới trong folder `du_lieu_exel` |
| `du_lieu_images\du_lieu_<ngày-giờ>_images\` | Ảnh gốc được tải từ bài viết (mỗi lần chạy 1 folder) |
| `du_lieu_fb\du_lieu_<ngày-giờ>\goi_full_*.csv` | Dữ liệu thô CSV (mỗi批次) |
| `cookies.txt` | File cookies của bạn (được dùng để xác thực với Facebook) |
| `requirements.txt` | Danh sách các thư viện Python cần thiết |
| `webui.py` | File chạy giao diện web |
| `*.py` | Các file hỗ trợ khác (nhan_dien.py, viet_lai.py, google_sheets.py, media.py, config.py) |

---

> 💡 **Mẹo sử dụng:** 
> - Luôn kiểm tra cookies trước khi bắt đầu cào lớn
> - Bắt đầu với số lượng bài nhỏ (5-10 bài/trang) để thử
> - Theo dõi nhật ký hoạt động nếu gặp bất thường
> - Kết quả tốt nhất khi cào từ các trang công khai có hoạt động thường xuyên