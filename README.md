# 📊 Facebook Scraper — Cào dữ liệu Page (text + ảnh) + Đánh giá bài tiềm năng

> Công cụ tự động cào bài viết (văn bản + ảnh) từ nhiều Facebook Page công khai, xuất ra 1 file Excel kèm điểm số tương tác — và có giao diện web để theo dõi tiến trình và xem kết quả trực tiếp. Không cần biết lập trình.

**Quy trình đầy đủ trong web UI (6 tab):** Cào dữ liệu → Kho bài viết → **Xử lý AI** (sinh Caption + Bài báo) → Cắt ảnh hoặc **Tạo Reel video 10s** → Xuất Excel. Hỗ trợ kết nối AI tùy chỉnh (Custom OpenAI-compatible) với nút **tự thêm model**. Xem chi tiết từng tab ở mục "HƯỚNG DẪN SỬ DỤNG GIAO DIỆN WEB" bên dưới.

---

# HƯỚNG DẪN SỬ DỤNG
Cách nhanh nhất ném link cho antigravity hoặc các AI agent khác để nó cài full cho bạn.
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

---

# HƯỚNG DẪN SỬ DỤNG GIAO DIỆN WEB (6 tab)

> Khi chạy `python webui.py`, trình duyệt mở giao diện gồm **6 tab**. Đây là toàn bộ quy trình từ cào dữ liệu → xử lý AI → cắt ảnh → tạo reel → xuất Excel.

## Tab 1: Cào Dữ Liệu
- Dán URL các trang Facebook cần cào, đặt **số bài mỗi trang**, **số lần cuộn**, **nghỉ (giây)**.
- Bấm **🔎 Kiểm tra cookies** trước, rồi bấm **▶ Bắt đầu cào**. Theo dõi tiến trình trực tiếp phía dưới.
- Sau khi cào xong, bài viết tự vào **Tab 2 — Kho Bài Viết**.

## Tab 2: Kho Bài Viết (Content Pool)
- Hiển thị toàn bộ bài đã cào, **lọc theo phiên cào**, **KEY**, **Nhân vật**, **Trạng thái**, từ khoá.
- **Tick chọn** các bài muốn xử lý → chọn **tỷ lệ ảnh** (1:1/4:5/16:9) → bấm **⚡ Xử Lý AI Hàng Loạt**.
- Tool sẽ chạy AI sinh **3 Caption + Bài báo + link** cho từng bài. Khi xong **tự chuyển sang Tab 3**.
- Muốn xử lý nhanh 1 bài: bấm **✍️ Xử Lý** ở cột Hành động.

## Tab 3: Xử Lý AI & Chỉnh Bài (danh sách + Hoàn Thành hàng loạt)
> Tab này giờ là **danh sách** các bài đã chạy AI nhưng **chưa hoàn thành** (trạng thái `PROCESSING`), hiển thị **theo phiên cào** như Tab 2.

1. Chọn **phiên cào** ở trên để xem các bài của phiên đó.
2. Mỗi bài hiện: Ảnh, **Caption cũ**, **Caption mới (bản cuối)** do AI sinh, KEY, Nhân vật, Tương tác, Thời gian, Trạng thái.
3. Muốn **chỉnh sửa/xem chi tiết** 1 bài → bấm **Xử Lý** (nút viền xanh). Giao diện chỉnh sửa hiện ra: chọn bản caption (1/2/3), sửa bài báo, link, rồi bấm **Hoàn Thành** (màu xanh) để chuyển tab đó sang bước cắt ảnh.
4. Muốn **hoàn thành nhiều bài một lần** → **tick các ô** ở cột đầu (hoặc tick ô "chọn tất cả" trên header) → bấm nút xanh **Hoàn Thành** ở trên.
   - Các bài được tick sẽ chuyển sang Tab 4 (trạng thái `SAN_SANG`). Caption giữ nguyên bản AI đã sinh. Tab 3 chỉ còn lại các bài chưa hoàn thành.

## Tab 4: Đăng Sẵn Sàng (Chờ Cắt Ảnh) — gồm Xử Lí Ảnh + Tạo Reel
> Hiện các bài đã Hoàn Thành ở Tab 3 (trạng thái `SAN_SANG`), sẵn sàng cho 2 việc: **cắt ảnh** hoặc **tạo video reel**.

- **Xử Lí Ảnh** 🟢 (nút xanh "Xử Lí Ảnh"):
  - Chọn **tỷ lệ** (1:1 vuông / 4:5 dọc FB / 16:9 ngang).
  - Tick các bài → bấm **Xử Lí Ảnh**. Tool cắt ảnh từng bài, thêm viền + logo, đặt trạng thái `HOAN_THANH`. Bài nào cắt xong tự rời khỏi đây, sang Tab 5.
- **Tạo Reel** 🎬 (nút xanh "Tạo Reel"):
  - Tick ô **🎵 Chọn nhạc ngẫu nhiên** (bắt buộc phải có).
  - Tick các bài → bấm **Tạo Reel**. Tool:
    1. **Cắt ảnh** giống như nút Xử Lí Ảnh;
    2. Kéo dài ảnh thành **video reel dọc 1080×1920, dài 10 giây** (ảnh đứng yên, nền mờ) với **nhạc ngẫu nhiên** 10s.
  - Video lưu trong thư mục `du_lieu_reel/` (mỗi bài 1 file `reel_<content_id>.mp4`).

> 💡 **Chú ý:** Tạo Reel cần máy có **ffmpeg** (đã được cài sẵn). Nếu sau khi Hoàn Thành mà chưa thấy bài ở Tab 4, bấm **Làm mới**.

## Tab 5: Hoàn Thành & Xuất Excel
- Xem các bài đã hoàn thành (`HOAN_THANH`) theo phiên cào.
- Bấm để **Xuất Excel** hoặc **Xuất CSV** các bài đã xử lý.

## Tab 6: Cài Đặt AI (provider + Custom + tự thêm model)
> Cấu hình nhà cung cấp AI được toàn bộ tool dùng (sinh caption, bài báo...). 4 provider mặc định: **DeepSeek**, **OpenAI**, **Anthropic (Claude)**, **Google Gemini** — hoặc **Custom**.

1. **Nhà cung cấp** — chọn 1 trong các provider, hoặc **Custom (OpenAI-compatible)**.
2. **API Key** — dán key của provider (bấm "Hiện key" để xem).
3. **Model** — điền tên model. Với **Custom**, sau khi nhập API Key + Base URL, bấm nút **"Tự thêm model"** để **tự nạp toàn bộ model của API key** vào ô Model (gõ vài chữ để chọn từ danh sách gợi ý).
4. **Base URL** (chỉ hiện khi chọn Custom) — endpoint gốc OpenAI-compatible. Ví dụ:
   - `https://openrouter.ai/api/v1`
   - `https://api.groq.com/openai/v1`
   - `https://api.deepseek.com/v1` … (bất kỳ API chuẩn OpenAI nào)
5. Bấm **🔌 Kiểm tra kết nối** để xác nhận key/model dùng được. Bấm **💾 Lưu cấu hình** để áp dụng.

> 💡 **Lưu ý khi chọn Custom:** nếu "Kiểm tra kết nối" báo lỗi kiểu *"Access restricted. Deposit required..."* nghĩa là **model đó là premium cần nạp tiền** trên provider — đổi sang model khác (ví dụ `deepseek-v4-flash`, `qwen3.8-flash`). Đây không phải lỗi sai key/URL.

---


## Bước G. Các file tạo ra (trong thư mục dự án)

| File | Nội dung |
|---|---|
| `du_lieu_exel/du_lieu_<ngày-giờ>.xlsx` | **File Excel chính** — mỗi lần chạy 1 file mới trong folder `du_lieu_exel` |
| `du_lieu_images\du_lieu_<ngày-giờ>_images\` | Ảnh gốc được tải từ bài viết (mỗi lần chạy 1 folder) |
| `du_lieu_fb\du_lieu_<ngày-giờ>\goi_full_*.csv` | Dữ liệu thô CSV (mỗi批次) |
| `du_lieu_reel\reel_<content_id>.mp4` | Video reel 10s tạo từ **Tạo Reel** ở Tab 4 (mỗi bài 1 file) |
| `music\music1\10s\` và `music\NBA Music\10s\` | Các đoạn nhạc 10s dùng để chèn vào reel (nguồn nhạc) |
| `cookies.txt` | File cookies của bạn (được dùng để xác thực với Facebook) |
| `requirements.txt` | Danh sách các thư viện Python cần thiết |
| `webui.py` | File chạy giao diện web |
| `reel.py`, `cat_nhac.py` | File hỗ trợ tạo video reel + cắt nhạc 10s (mới) |
| `*.py` | Các file hỗ trợ khác (nhan_dien.py, viet_lai.py, google_sheets.py, media.py, config.py) |

---

> 💡 **Mẹo sử dụng:** 
> - Luôn kiểm tra cookies trước khi bắt đầu cào lớn
> - Bắt đầu với số lượng bài nhỏ (5-10 bài/trang) để thử
> - Theo dõi nhật ký hoạt động nếu gặp bất thường
> - Kết quả tốt nhất khi cào từ các trang công khai có hoạt động thường xuyên