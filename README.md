# 📊 Facebook Scraper — Cào dữ liệu Page (text + ảnh) + Đánh giá bài tiềm năng

Tool cào bài viết (văn bản + ảnh) từ **nhiều** Facebook Page công khai, xuất
**1 file Excel** kèm chấm điểm tương tác — và có **giao diện web** để theo dõi
trực tiếp + xem kết quả. Không cần biết lập trình.

---

# HƯỚNG DẪN CHẠY TỪ A → Z

## Bước A. Kiểm tra Python

Mở **Command Prompt (cmd)** hoặc **PowerShell**, gõ:

```bash
python --version
```

Nếu thấy `Python 3.10` trở lên → qua **Bước B**.
Nếu báo "không nhận diện" → cài Python tại https://www.python.org/downloads/
(tích chọn **"Add python.exe to PATH"** khi cài), rồi mở lại cmd.

## Bước B. Cài đặt thư viện (chỉ 1 lần đầu)

Trong thư mục dự án (`c:\traffic fb`), chạy:

```bash
pip install -r requirements.txt
```

Đợi đến khi xong (không lỗi đỏ nào). Qua **Bước C**.

> ℹ️ Công cụ cào bằng **trình duyệt thật (Edge/Chrome có sẵn trên máy)** — không
> cần tải gì thêm. Nếu máy không có Edge/Chrome thì chạy thêm 1 lệnh để tải
> Chromium riêng:
> ```bash
> python -m playwright install chromium
> ```

## Bước C. Xuất cookies từ tài khoản Facebook (BẮT BUỘC)

> Facebook chặn truy cập ẩn danh — **không có cookies thì không cào được gì**.

**Cách 1 — Dùng extension (khuyên dùng, dễ nhất):**
1. Mở Chrome/Edge → vào Web Store → tìm **"Get cookies.txt LOCALLY"** → Cài.
2. Mở `facebook.com` (đã đăng nhập tài khoản).
3. Bấm icon extension (góc phải trên) → **Export** → lưu file tên `cookies.txt`
   **vào thư mục dự án** (`c:\traffic fb`).
4. Kiểm tra: file `cookies.txt` phải có nội dung (vài chục dòng trở lên).

**Cách 2 — DevTools (không cần cài gì):**
1. Mở `facebook.com` (đã đăng nhập) → bấm `F12` → tab **Console**.
2. Dán lệnh: `copy(document.cookie)` rồi Enter.
3. Mở Notepad → `Ctrl+V` → Lưu thành `cookies.txt` trong thư mục dự án.

> ⚠️ Cookies có hạn (vài ngày → vài tuần). Khi cào báo "không lấy được bài",
> chỉ cần xuất lại cookies mới.

## Bước D. Chạy giao diện web

```bash
python webui.py
```

Trình duyệt **tự mở** `http://127.0.0.1:5000`. Cửa sổ cmd giữ nguyên (đừng tắt —
đó là server). Muốn thoát: bấm `Ctrl+C` trong cửa sổ cmd.

## Bước E. Cào dữ liệu (tab "Cào dữ liệu")

1. **Danh sách trang**: gõ mỗi trang 1 dòng — tên hoặc URL đều được:
   ```
   vtv
   https://www.facebook.com/kenh14
   vietnamnet
   ```
2. **Số bài mỗi trang**: để 50 (như bạn cần) — khuyến nghị 50–100 để an toàn.
3. **Số lần cuộn**: để 10 (là mức tối thiểu). Tool **tự cuộn thêm** cho tới
   khi đủ số bài đã đặt — chỉ dừng sớm khi trang hết bài mới.
4. **Nghỉ (giây)**: để 3 — giảm rủi ro bị Facebook chặn.
5. **File cookies.txt**: để mặc định `cookies.txt`. Muốn chắc chắn → bấm
   **🔎 Kiểm tra cookies** trước: vài giây sau sẽ báo "hợp lệ ✅" hoặc yêu cầu
   xuất lại cookies.
6. Bấm **▶ Bắt đầu cào**.

Theo dõi **trực tiếp** ở phía dưới: bảng trạng thái (bài viết/ảnh đang tăng),
nhật ký chạy, và từng bài mới hiện ngay trong bảng live. Muốn dừng giữa chừng
→ bấm **⏹ Dừng**.

## Bước F. Xem kết quả (tab "Kết quả")

- Toàn bộ bài viết hiển thị như trong Excel: **ảnh thu nhỏ** (bấm phóng to),
  nội dung (kèm **hashtag** ở cuối bài), cảm xúc, bình luận, chia sẻ, điểm,
  mức tiềm năng (🟩 CAO / 🟨 TRUNG_BINH / ⬜ THAP), link bài (bấm mở Facebook).
- Lọc theo trang hoặc mức tiềm năng. Bài tiềm năng nhất xếp trên cùng.
- Bấm **📥 Tải file Excel** → lưu file về máy (sheet *Tổng quan* + 1 sheet
  mỗi trang, có tô màu + lọc + link). Mỗi lần chạy tạo **1 file riêng** trong
  folder `du_lieu_exel` (tên kèm giờ chạy, ví dụ `du_lieu_2026-08-23_14-30.xlsx`)
  — không ghi đè lần chạy trước.

## Bước G. Các file tạo ra (trong thư mục dự án)

| File | Nội dung |
|---|---|
| `du_lieu_exel/du_lieu_<ngày-giờ>.xlsx` | **File Excel chính** — mỗi lần chạy 1 file mới trong folder `du_lieu_exel` |
| `du_lieu_<trang>.json` | Dữ liệu thô từng trang (để lưu trữ / phân tích lại) |
| `du_lieu_images/du_lieu_<ngày-giờ>_images/` | **Tất cả ảnh của 1 lần cào** — 1 thư mục duy nhất theo giờ cào (cùng giờ với file Excel), nằm bên trong `du_lieu_images`; ảnh mỗi bài có tên bắt đầu bằng `post_id` |

## Bước H. Chạy bằng dòng lệnh (không cần web, tùy chọn)

```bash
# 1 trang, mỗi trang 50 bài
python scraper.py --page vtv --per-page 50 --cookies cookies.txt

# NHIỀU trang cùng lúc
python scraper.py --page vtv kenh14 vietnamnet --per-page 50 --cookies cookies.txt

# Thêm tùy chọn: 10 lần cuộn, nghỉ 5s, không tải ảnh
python scraper.py --page vtv --pages 10 --delay 5 --no-images --cookies cookies.txt
```

---

# Bài tiềm năng được xác định thế nào?

Mỗi bài được chấm: **điểm = cảm xúc + bình luận×2 + chia sẻ×3** (bình luận và
chia sẻ nặng hơn like vì thể hiện tương tác sâu).

Trong phạm vi từng trang, xếp hạng theo phần trăm:

| Thứ hạng | Mức tiềm năng |
|---|---|
| Top 25% | `CAO` 🔥 |
| 25–60% | `TRUNG_BINH` |
| Còn lại | `THAP` |

---

# Xử lý sự cố

| Vấn đề | Cách xử lý |
|---|---|
| "Không lấy được bài nào" | Cookies hết hạn / chưa đúng → **xuất lại cookies** (Bước C) |
| Lỗi 400/HTTPError giữa chừng | Bị chặn tạm → đợi 10–15 phút, chạy lại với `--pages` nhỏ hơn, delay lớn hơn |
| Web không mở được | Tắt server cũ rồi chạy lại `python webui.py`; kiểm tra cổng 5000 không bị chiếm |
| Trang không public | Không cào được — chỉ cào được trang công khai |
| Bị yêu cầu xác minh "human check" | Dừng ngay, đợi vài giờ; tài khoản cào bị nghi ngờ → **nên dùng tài khoản phụ** |

# Lưu ý quan trọng

- Cào bằng cookies tài khoản cá nhân có rủi ro nhỏ bị Facebook kiểm soát.
  Khuyến nghị: **dùng tài khoản phụ** (tạo riêng để cào), cào ít (50–100 bài/
  trang/lần), cách quãng thời gian giữa các lần chạy.
- Tool không chính thức (dùng backend của Facebook), có thể cần sửa nhỏ khi
  Facebook thay đổi. Nếu cần cào lâu dài với khối lượng lớn → **Graph API**
  (chính thống) — hỏi Claude để dựng bản Graph API.
