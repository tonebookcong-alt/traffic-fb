#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cào Facebook Page bằng TRÌNH DUYỆT THẬT (Edge/Chrome có sẵn trên máy) qua Playwright.

Vì sao: Facebook 2026 chặn mọi truy cập "ẩn danh" bằng requests — trang chỉ render
trong trình duyệt có đăng nhập. Cách này mở đúng trang profile, cuộn để tải thêm
bài, rồi đọc dữ liệu ngay từ DOM (text, cảm xúc, bình luận, chia sẻ, ảnh).

Đầu ra: danh sách post dạng dict GIỐNG hệt định dạng cũ của scraper.py:
    post_id, time, text, images, post_url, likes, comments, shares
"""

import hashlib
import json
import re
import time
from datetime import datetime, timedelta

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# Khoảng cách (px) tối đa giữa text bài và thanh tương tác (toolbar) của CÙNG bài.
# Nếu chênh lệch lớn hơn -> chúng thuộc 2 bài khác nhau.
NGUONG_GHEP = 2500


def doc_cookies(path: str):
    """Đọc cookies.txt -> list cookies cho Playwright (giống scraper.py)."""
    if not path:
        return []
    with open(path, "r", encoding="utf-8") as f:
        noi_dung = f.read().strip()
    if not noi_dung:
        return []
    if noi_dung.startswith("["):
        try:
            ds = json.loads(noi_dung)
            if isinstance(ds, list):
                return [{"name": c["name"], "value": c["value"],
                         "domain": c.get("domain", ".facebook.com"),
                         "path": c.get("path", "/")}
                        for c in ds if isinstance(c, dict) and c.get("name")]
        except json.JSONDecodeError:
            pass
    cookies = {}
    for line in noi_dung.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            cookies[parts[5]] = parts[6]
        elif "=" in line:
            for cap in line.split(";"):
                cap = cap.strip()
                if "=" in cap:
                    k, v = cap.split("=", 1)
                    cookies[k.strip()] = v.strip()
    return [{"name": k, "value": v, "domain": ".facebook.com", "path": "/"}
            for k, v in cookies.items()]


def mo_trinh_duyet(playwright, cookies: list):
    """Mở Edge có sẵn trên máy (hoặc Chrome); lỗi thì dùng Chromium của Playwright."""
    thu = ["msedge", "chrome"]
    for kenh in thu:
        try:
            browser = playwright.chromium.launch(
                channel=kenh, headless=True,
                args=["--disable-blink-features=AutomationControlled"])
            return browser
        except Exception:
            continue
    # Không có Edge/Chrome -> cần 'playwright install chromium'
    try:
        return playwright.chromium.launch(headless=True)
    except Exception as e:
        raise RuntimeError(
            "Không mở được trình duyệt. Hãy cài Chromium cho Playwright:\n"
            "    python -m playwright install chromium\n"
            f"({e})")


def _parse_so(so_text: str) -> int:
    """'1,5K' -> 1500 ; '4.2K' -> 4200 ; '270' -> 270 ; '' -> 0"""
    if not so_text:
        return 0
    s = so_text.strip().replace(".", "").replace(",", ".").replace(" ", "")
    if not s:
        return 0
    if s[-1] in "kK":
        try:
            return int(float(s[:-1]) * 1000)
        except ValueError:
            return 0
    try:
        return int(float(s))
    except ValueError:
        return 0


def _parse_thoi_gian(label: str):
    """'Thứ bảy, 22 Tháng 8, 2026 lúc 20:02' -> datetime.
    'Hôm nay lúc 20:02' / '7 giờ' / '3 ngày' -> datetime gần đúng.
    Không hiểu được -> trả về None."""
    if not label:
        return None
    label = label.strip()
    m = re.search(r"(\d{1,2})\s+Tháng\s+(\d{1,2}),?\s+(\d{4})\s*lúc\s*(\d{1,2}):(\d{2})", label)
    if m:
        try:
            ngay, thang, nam, gio, phut = map(int, m.groups())
            return datetime(nam, thang, ngay, gio, phut)
        except ValueError:
            return None
    gio_ht = datetime.now()
    if "Hôm nay" in label:
        m = re.search(r"lúc\s*(\d{1,2}):(\d{2})", label)
        if m:
            return gio_ht.replace(hour=int(m.group(1)), minute=int(m.group(2)),
                                  second=0, microsecond=0)
    if "Hôm qua" in label:
        m = re.search(r"lúc\s*(\d{1,2}):(\d{2})", label)
        if m:
            return (gio_ht - timedelta(days=1)).replace(
                hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
    m = re.search(r"(\d+)\s*giờ", label)
    if m:
        return gio_ht - timedelta(hours=int(m.group(1)))
    m = re.search(r"(\d+)\s*ngày", label)
    if m:
        return gio_ht - timedelta(days=int(m.group(1)))
    return None


def _trich_so_lieu(toolbar_text: str):
    """'1,5K 64 4' -> (1500, 64, 4). Các số = cảm xúc, bình luận, chia sẻ."""
    cac_so = re.findall(r"\d[\d.,]*\s*[kK]?", toolbar_text)
    if not cac_so:
        return 0, 0, 0
    likes = _parse_so(cac_so[0])
    comments = _parse_so(cac_so[1]) if len(cac_so) > 1 else 0
    shares = _parse_so(cac_so[2]) if len(cac_so) > 2 else 0
    return likes, comments, shares


def _post_id_tu_link(link: str) -> str | None:
    # link trang profile: profile.php?id=...&story_fbid=123&id=...
    m = re.search(r"[?&]story_fbid=(\d+)", link)
    if m:
        return m.group(1)
    m = re.search(r"/(?:posts|reel|reels|videos|photos|photo\.php)[/\?]?([\w]+)", link)
    if m:
        return m.group(1)
    m = re.search(r"(pfbid\w+)", link)
    return m.group(1) if m else None


def lay_du_lieu_dom(page, so_bai: int) -> list:
    """Đọc toàn bộ bài viết hiện có trong DOM, trả về list dict."""
    js = """
    () => {
      const rectTop = el => Math.round(el.getBoundingClientRect().top);

      // --- 1. Text bài ---
      const previews = [];
      document.querySelectorAll('[data-ad-comet-preview]').forEach(el => {
        const top = rectTop(el);
        // ảnh media: trong block cha, bỏ avatar nhỏ và ảnh nằm trên text
        let n = el, imgs = [];
        for (let k = 0; k < 14 && n; k++) {
          n.querySelectorAll('img').forEach(img => {
            const u = img.src || '';
            if (!u.includes('fbcdn')) return;
            const w = img.naturalWidth || parseInt(img.getAttribute('width') || '0') || 0;
            if (w < 60) return;
            if (rectTop(img) < top - 80) return;
            if (imgs.indexOf(u) === -1) imgs.push(u);
          });
          n = n.parentElement;
        }
        previews.push({top, text: (el.innerText || '').trim(), imgs});
      });

      // --- 1b. Layout khác: [role="article"] bọc cả bài (không có preview).
      // Mỗi article = 1 bài hoàn chỉnh: text, ảnh, toolbar nằm bên trong.
      const articles = [];
      document.querySelectorAll('[role="article"]').forEach(el => {
        const top = rectTop(el);
        let toolbarText = '';
        el.querySelectorAll('[aria-label="Viết bình luận"]').forEach(tb => {
          let n = tb;
          for (let k = 0; k < 14 && n; k++) {
            if ((n.outerHTML || '').includes('aria-label="Thích"')) break;
            n = n.parentElement;
          }
          if (n) toolbarText = (n.innerText || '').replace(/\\s+/g, ' ').trim();
        });
        // bản sao đã GỠ toolbar để text bài không dính số liệu tương tác
        const clone = el.cloneNode(true);
        clone.querySelectorAll('[aria-label="Viết bình luận"]').forEach(tb => {
          let n = tb;
          for (let k = 0; k < 14 && n; k++) {
            if ((n.outerHTML || '').includes('aria-label="Thích"')) break;
            n = n.parentElement;
          }
          if (n) n.remove();
        });
        const imgs = [];
        el.querySelectorAll('img').forEach(img => {
          const u = img.src || '';
          if (!u.includes('fbcdn')) return;
          const w = img.naturalWidth || parseInt(img.getAttribute('width') || '0') || 0;
          if (w < 60) return;
          if (imgs.indexOf(u) === -1) imgs.push(u);
        });
        articles.push({top, text: (clone.innerText || '').trim(), imgs,
                       toolbarText});
      });

      // --- 2. Thanh tương tác (toolbar): cảm xúc / bình luận / chia sẻ ---
      const toolbars = [];
      document.querySelectorAll('[aria-label="Viết bình luận"]').forEach(tb => {
        let node = tb;
        for (let k = 0; k < 14 && node; k++) {
          if ((node.outerHTML || '').includes('aria-label="Thích"')) break;
          node = node.parentElement;
        }
        if (!node) return;
        toolbars.push({top: rectTop(node),
                       text: (node.innerText || '').replace(/\\s+/g, ' ').trim()});
      });

      // --- 3. Link bài + thời gian (riêng, ghép theo vị trí sau) ---
      const links = [];
      document.querySelectorAll('a[href*="/posts/"], a[href*="/reel"], a[href*="/reels/"], '
        + 'a[href*="/videos/"], a[href*="/photos/"], a[href*="photo.php"], '
        + 'a[href*="story_fbid"]').forEach(a => {
        let h = (a.href || '').split('?')[0];
        if (!h.startsWith('https://www.facebook.com/')) return;
        if (h.includes('/stories/')) return;
        // chỉ giữ link có ID thật (posts/pfbid…, reel/123, videos/123,
        // profile.php?id=...&story_fbid=…)
        const sau = h.split('/').pop() || '';
        const co_id = h.includes('/posts/pfbid')
          || ((h.includes('/reel/') || h.includes('/reels/')
               || h.includes('/videos/') || h.includes('/photos/')) && /\\d+/.test(sau))
          || h.includes('/photo.php?fbid=')
          || h.includes('story_fbid');
        if (!co_id) return;
        links.push({top: rectTop(a), href: a.href,
                    timeText: (a.innerText || '').trim()});
      });

      const times = [];
      document.querySelectorAll('[aria-label*="Thứ "], [aria-label*="Chủ "], '
        + '[aria-label*="Hôm nay"], [aria-label*="Hôm qua"], '
        + '[aria-label*="lúc "], [aria-label*="giờ"], [aria-label*="ngày"]').forEach(el => {
        const lb = (el.getAttribute('aria-label') || '').trim();
        if (!lb) return;
        // thẻ thời gian thường là CHÍNH anchor trỏ tới bài viết (permalink)
        times.push({top: rectTop(el), label: lb,
                    href: el.tagName === 'A' ? (el.href || '') : ''});
      });

      return {previews, toolbars, links, times, articles};
    }
    """
    du_lieu = page.evaluate(js)
    previews, toolbars = du_lieu["previews"], du_lieu["toolbars"]
    links, times = du_lieu["links"], du_lieu["times"]
    articles = du_lieu["articles"]

    # --- 4. Ghép: mỗi toolbar = 1 bài; text/link/time gần nhất phía trên ---
    def tim_gan_nhat(danh_sach, top, toi_da=NGUONG_GHEP, da_dung=None,
                     cho_phep_duoi=0):
        """Phần tử gần top nhất (trên: 0..toi_da; có thể dưới: -cho_phep_duoi..0),
        chưa bị dùng (da_dung = set index)."""
        ket_qua, khoang = None, None
        for i, phan_tu in enumerate(danh_sach):
            if da_dung is not None and i in da_dung:
                continue
            d = top - phan_tu["top"]
            if -cho_phep_duoi <= d <= toi_da:
                dd = abs(d)
                if khoang is None or dd < khoang:
                    khoang, ket_qua = dd, i
        return (danh_sach[ket_qua], ket_qua) if ket_qua is not None else (None, None)

    cac_bai = []
    dung_preview = set()
    dung_link = set()
    dung_time = set()

    if not toolbars and articles:
        # Layout B: không có thanh tương tác riêng — mỗi [role="article"] = 1 bài
        for art in articles:
            link_tt, chi_so_l = tim_gan_nhat(links, art["top"], toi_da=700,
                                             da_dung=dung_link, cho_phep_duoi=2500)
            if link_tt is not None:
                dung_link.add(chi_so_l)
            time_tt, chi_so_t = tim_gan_nhat(times, art["top"], toi_da=700,
                                             da_dung=dung_time, cho_phep_duoi=2500)
            if time_tt is not None:
                dung_time.add(chi_so_t)
            if link_tt is None and time_tt and time_tt.get("href"):
                link_tt = {"href": time_tt["href"]}
            likes, comments, shares = _trich_so_lieu(art.get("toolbarText") or "")
            post_id = _post_id_tu_link(link_tt["href"] if link_tt else "") or (
                "bai_" + hashlib.md5(
                    (art["text"][:80] or str(art["top"])).encode()).hexdigest()[:12])
            time_obj = _parse_thoi_gian(time_tt["label"] if time_tt else None)
            cac_bai.append({
                "post_id": post_id,
                "time": time_obj.isoformat() if time_obj else
                        (time_tt["label"] if time_tt else ""),
                "text": art["text"],
                "images": art["imgs"],
                "post_url": link_tt["href"] if link_tt else "",
                "likes": likes,
                "comments": comments,
                "shares": shares,
            })
        return cac_bai

    for tb in toolbars:
        bai_text, chi_so = tim_gan_nhat(previews, tb["top"])
        if bai_text is None:
            continue  # bài chưa kịp render text
        dung_preview.add(chi_so)

        # Link của bài nằm trong phần header (trên text) hoặc trong media (dưới
        # text) — tìm chưa dùng, gần nhất, ngưỡng nhỏ để không nhảy sang bài khác.
        link_tt, chi_so_l = tim_gan_nhat(links, bai_text["top"], toi_da=700,
                                         da_dung=dung_link, cho_phep_duoi=2500)
        if link_tt is None:
            link_tt, chi_so_l = tim_gan_nhat(links, tb["top"], toi_da=1200,
                                             da_dung=dung_link, cho_phep_duoi=300)
        if link_tt is not None:
            dung_link.add(chi_so_l)
        time_tt, chi_so_t = tim_gan_nhat(times, bai_text["top"], toi_da=700,
                                         da_dung=dung_time, cho_phep_duoi=2500)
        if time_tt is None:
            time_tt, chi_so_t = tim_gan_nhat(times, tb["top"], toi_da=1200,
                                             da_dung=dung_time, cho_phep_duoi=300)
        if time_tt is not None:
            dung_time.add(chi_so_t)

        # Nếu không có link riêng, thử dùng href của thẻ thời gian (permalink)
        if link_tt is None and time_tt and time_tt.get("href"):
            link_tt = {"href": time_tt["href"]}
        likes, comments, shares = _trich_so_lieu(tb["text"])
        post_id = _post_id_tu_link(link_tt["href"] if link_tt else "")
        if not post_id:
            post_id = "bai_" + hashlib.md5(
                (bai_text["text"][:80] or str(bai_text["top"])).encode()).hexdigest()[:12]
        time_obj = _parse_thoi_gian(time_tt["label"] if time_tt else None)
        cac_bai.append({
            "post_id": post_id,
            "time": time_obj.isoformat() if time_obj else
                    (time_tt["label"] if time_tt else ""),
            "text": bai_text["text"],
            "images": bai_text["imgs"],
            "post_url": link_tt["href"] if link_tt else "",
            "likes": likes,
            "comments": comments,
            "shares": shares,
        })
    return cac_bai


def cào_trang(page_name: str, so_bai: int, so_lan_cuon: int, delay: float,
              cookies: list, stop_flag=None, callback=None) -> list:
    """Cào một trang bằng trình duyệt thật, trả về danh sách bài."""
    from playwright.sync_api import sync_playwright

    def log(msg):
        print(msg)
        if callback:
            callback({"loai": "log", "noi_dung": msg})

    log(f"    [i] Mở trình duyệt để cào '{page_name}' ...")
    with sync_playwright() as p:
        browser = mo_trinh_duyet(p, cookies)
        try:
            ctx = browser.new_context(
                user_agent=DEFAULT_UA, locale="vi-VN",
                viewport={"width": 1280, "height": 900},
            )
            if cookies:
                ctx.add_cookies(cookies)
            page = ctx.new_page()
            # profile.php?id=... là link trang/profile dạng đặc biệt — không thêm "/"
            if page_name.startswith("profile.php"):
                url_trang = f"https://www.facebook.com/{page_name}"
            else:
                url_trang = f"https://www.facebook.com/{page_name}/"
            page.goto(url_trang, timeout=60000, wait_until="domcontentloaded")

            # chờ 5s đầu theo từng phần nhỏ để bấm Dừng được dừng ngay
            for _ in range(10):
                if stop_flag and stop_flag.is_set():
                    log(f"    [i] Đã dừng theo yêu cầu tại '{page_name}'")
                    return []
                page.wait_for_timeout(500)

            # Chờ tối đa 10s cho bài xuất hiện (không bỏ cuộc ngay — nhiều trang
            # tải bài chậm, nhất là profile/trang nhỏ; vòng cuộn phía dưới sẽ tự
            # xử lý tiếp nếu lúc này chưa có gì).
            for _ in range(10):
                if stop_flag and stop_flag.is_set():
                    log(f"    [i] Đã dừng theo yêu cầu tại '{page_name}'")
                    return []
                try:
                    # layout A: [data-ad-comet-preview] — layout B: [role="article"]
                    page.wait_for_selector('[data-ad-comet-preview], [role="article"], '
                                           '[aria-label="Viết bình luận"]', timeout=1000)
                    break
                except Exception:
                    continue

            # Facebook "virtualize" feed: bài đã cuộn qua sẽ bị gỡ khỏi DOM.
            # Vì vậy phải đọc bài SAU MỖI LẦN CUỘN rồi gộp dần (loại trùng theo post_id).
            cac_bai = []
            da_thay = set()
            dem_khong_tang = 0
            # Mỗi lần cuộn chỉ tải ~3-5 bài. Vì vậy nếu người dùng đặt 50 bài mà
            # chỉ cuộn 3 lần sẽ không đủ -> TỰ cuộn tiếp cho tới khi đủ so_bai
            # (giới hạn an toàn để không cuộn vô hạn khi feed vô tận).
            toi_da_lan = max(so_lan_cuon, min(60, (so_bai or 0) * 2 + 10))
            lan = 0
            while lan < toi_da_lan:
                lan += 1
                if stop_flag and stop_flag.is_set():
                    log(f"    [i] Đã dừng theo yêu cầu tại '{page_name}'")
                    break

                # mở rộng các bài dài ("Xem thêm") để lấy đủ text trước khi đọc
                try:
                    page.evaluate("""() => {
                      [...document.querySelectorAll('[role="button"]')].forEach(b => {
                        if ((b.innerText || '').trim() === 'Xem thêm') b.click();
                      });
                    }""")
                    page.wait_for_timeout(800)
                except Exception:
                    pass

                bai_moi = lay_du_lieu_dom(page, so_bai)
                them = 0
                for b in bai_moi:
                    if b["post_id"] in da_thay:
                        continue
                    # bài đôi khi được render 2 lần với post_id khác nhau
                    # (bản đầy đủ hơn sau khi bấm "Xem thêm") -> so text
                    la_trung = False
                    binh_thuong = re.sub(r"\s+", " ", b["text"] or "")
                    binh_thuong = re.sub(r"[\U0001F000-\U0001FAFF☀-➿]",
                                         "", binh_thuong)
                    for cu in cac_bai:
                        binh_cu = re.sub(r"\s+", " ", cu["text"] or "")
                        binh_cu = re.sub(r"[\U0001F000-\U0001FAFF☀-➿]",
                                         "", binh_cu)
                        if binh_thuong and binh_cu and (
                                binh_thuong[:40] == binh_cu[:40] or
                                binh_thuong in binh_cu or binh_cu in binh_thuong):
                            # giữ bản có link; nếu bản mới có link hơn thì thay
                            if not cu["post_url"] and b["post_url"]:
                                cac_bai[cac_bai.index(cu)] = b
                                da_thay.add(b["post_id"])
                                them += 1
                            la_trung = True
                            break
                    if la_trung:
                        continue
                    da_thay.add(b["post_id"])
                    cac_bai.append(b)
                    them += 1
                log(f"    [i] Lần {lan}/{toi_da_lan}: +{them} bài mới "
                    f"(tổng {len(cac_bai)})")

                if len(cac_bai) >= so_bai:
                    break
                if them == 0:
                    dem_khong_tang += 1
                    # chịu đựng 3 lần liên tiếp không có bài mới (trang tải
                    # chậm đôi khi vài lượt cuộn đầu chưa ra gì)
                    if dem_khong_tang >= 3:
                        log("    [i] Hết bài mới — dừng cuộn.")
                        break
                else:
                    dem_khong_tang = 0

                so_truoc = page.locator('[aria-label="Viết bình luận"]').count()
                page.mouse.wheel(0, 6000)
                # Chờ bài MỚI xuất hiện (số thanh tương tác TĂNG lên) — tối đa
                # delay giây. Trước đây cứ thấy bài cũ là thôi chờ, nên bài mới
                # chưa kịp tải đã đọc DOM -> tưởng "hết bài" rồi dừng sớm.
                cho = 0
                toi_da = max(delay, 4.0) * 1000
                while cho < toi_da:
                    if stop_flag and stop_flag.is_set():
                        break
                    so_ht = page.locator('[aria-label="Viết bình luận"]').count()
                    if so_ht > so_truoc:
                        break
                    page.wait_for_timeout(500)
                    cho += 500

            if not cac_bai:
                # Thực sự không lấy được bài nào — phân tích lý do để báo rõ
                body = ""
                try:
                    body = page.evaluate("() => (document.body.innerText || '')")
                except Exception:
                    pass
                if "không xem được nội dung" in body:
                    log("    [!] Trang này KHÔNG cho tài khoản cào xem nội dung "
                        "(trang giới hạn khu vực/quyền riêng tư, hoặc bị chặn).")
                elif "Không có bài viết" in body:
                    log("    [!] Trang hiển thị 'Không có bài viết' — tài khoản cào "
                        "không xem được feed của trang này (giới hạn khu vực/quyền riêng tư).")
                elif "Đăng nhập" in body or "đăng nhập" in body:
                    log("    [!] Không thấy bài viết nào — cookies có thể đã hết hạn.")
                else:
                    log("    [!] Không thấy bài viết nào — feed chưa tải xong "
                        "(mạng chậm) hoặc cookies hết hạn.")
        finally:
            browser.close()

    log(f"    [✓] Đã đọc {len(cac_bai)} bài từ trang '{page_name}'")
    return cac_bai[:so_bai] if so_bai else cac_bai
