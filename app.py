from flask import Flask, render_template_string, request, redirect, url_for
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

app = Flask(__name__)

# Lưu danh sách kết quả sau khi quét ePort
scraped_data = []

def get_driver():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    driver = webdriver.Chrome(options=options)
    return driver

def check_eport(bill_number):
    """ Hàm chạy Selenium cào dữ liệu từ ePort Đà Nẵng dựa trên số Bill """
    results = []
    driver = None
    try:
        driver = get_driver()
        # Mở trang tra cứu ePort Đà Nẵng (Thay URL ePort thực tế của anh nếu cần)
        url = f"https://eport.danangport.vn/tra-cuu-thong-tin-container?bill={bill_number}" 
        driver.get(url)
        time.sleep(3) # Chờ trang load xong

        # Lấy thông tin các dòng container thuộc Bill
        # (Đoạn này cấu hình theo cấu trúc trang tra cứu ePort)
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        
        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 7:
                cont_num = cols[0].text.strip()
                opr = cols[1].text.strip()
                ngay_vao = cols[2].text.strip()
                ngay_ra = cols[3].text.strip()
                trang_thai = cols[4].text.strip()
                vi_tri = cols[5].text.strip()
                thanh_toan = cols[6].text.strip() # VD: Chưa TT / Đã TT

                # Kiểm tra nếu cont bãi SMART & Vừa lấy ra / Chưa thanh toán
                is_smart_alert = False
                if "SMART" in vi_tri.upper() or "SMART" in trang_thai.upper():
                    if "CHƯA" in thanh_toan.upper() or "UNPAID" in thanh_toan.upper():
                        is_smart_alert = True

                results.append({
                    "bill": bill_number,
                    "cont": cont_num,
                    "opr": opr,
                    "ngay_vao": ngay_vao,
                    "ngay_ra": ngay_ra,
                    "trang_thai": trang_thai,
                    "vi_tri": vi_tri,
                    "smart": thanh_toan if thanh_toan else "Chưa TT",
                    "alert": is_smart_alert
                })
    except Exception as e:
        print(f"Lỗi khi quét bill {bill_number}: {e}")
        # Mẫu dự phòng nếu tra cứu chưa ra dữ liệu web
        results.append({
            "bill": bill_number,
            "cont": "Không tìm thấy / Lỗi kết nối",
            "opr": "---", "ngay_vao": "---", "ngay_ra": "---",
            "trang_thai": "Lỗi quét", "vi_tri": "---",
            "smart": "Chưa TT", "alert": False
        })
    finally:
        if driver:
            driver.quit()
    return results

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>GIÁM SÁT CONTAINER ePort ĐÀ NẴNG</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        /* Hiệu ứng đỏ nhấp nháy liên tục cho Cont SMART chưa thanh toán */
        @keyframes blink-animation {
            0% { background-color: #ff4d4d; color: white; }
            50% { background-color: #8b0000; color: #yellow; }
            100% { background-color: #ff4d4d; color: white; }
        }
        .smart-blink {
            animation: blink-animation 1s infinite;
            font-weight: bold;
            font-size: 1.05rem;
        }
        .badge-blink {
            animation: blink-animation 0.8s infinite;
            padding: 6px 12px;
            border-radius: 4px;
        }
    </style>
</head>
<body class="bg-light">
    <div class="container-fluid py-4 px-4">
        <h3 class="mb-3 text-primary fw-bold">🚢 GIÁM SÁT CONTAINER ePort ĐÀ NẴNG</h3>
        
        <!-- Form nhập danh sách Số Bill -->
        <div class="card mb-4 shadow-sm">
            <div class="card-body">
                <form method="POST" action="/update_list">
                    <label for="raw_data" class="form-label fw-bold">Nhập / Dán danh sách Số Bill (Mỗi dòng 1 bill):</label>
                    <textarea class="form-control mb-2" id="raw_data" name="raw_data" rows="2" placeholder="Ví dụ: SITGHFDAU30060"></textarea>
                    <button type="submit" class="btn btn-success fw-bold">🔍 Bắt Đầu Quét & Cập Nhật ePort</button>
                </form>
            </div>
        </div>

        <!-- Thống kê tổng quan -->
        <div class="row text-white text-center mb-4 g-2">
            <div class="col-md-3"><div class="p-3 bg-secondary rounded shadow-sm"><h5>Tổng số Cont: {{ containers|length }}</h5></div></div>
            <div class="col-md-3"><div class="p-3 bg-success rounded shadow-sm"><h5>Đã gắp ra: {{ count_gap }}</h5></div></div>
            <div class="col-md-3"><div class="p-3 bg-warning text-dark rounded shadow-sm"><h5>Đang chờ: {{ count_cho }}</h5></div></div>
            <div class="col-md-3"><div class="p-3 bg-danger rounded shadow-sm"><h5>⚠️ SMART Chưa TT: {{ count_smart_alert }}</h5></div></div>
        </div>

        <!-- Bảng danh sách hiển thị -->
        <div class="table-responsive">
            <table class="table table-bordered align-middle bg-white shadow-sm">
                <thead class="table-dark text-center">
                    <tr>
                        <th>STT</th>
                        <th>Số Bill</th>
                        <th>Số Container</th>
                        <th>OPR</th>
                        <th>Ngày Vào</th>
                        <th>Ngày Ra</th>
                        <th>Trạng Thái</th>
                        <th>Vị Trí Bãi</th>
                        <th>Thanh Toán ePort</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in containers %}
                    <tr class="{% if item.alert %}smart-blink{% endif %}">
                        <td class="text-center">{{ loop.index }}</td>
                        <td class="fw-bold">{{ item.bill }}</td>
                        <td class="fw-bold text-primary">{{ item.cont }}</td>
                        <td class="text-center">{{ item.opr }}</td>
                        <td class="text-center">{{ item.ngay_vao }}</td>
                        <td class="text-center">{{ item.ngay_ra }}</td>
                        <td class="text-center">{{ item.trang_thai }}</td>
                        <td class="text-center">{{ item.vi_tri }}</td>
                        <td class="text-center">
                            {% if item.alert %}
                                <span class="badge-blink">⚠️ CẢNH BÁO SMART CHƯA TT</span>
                            {% else %}
                                <span class="badge bg-success">Đã TT / Hợp Lệ</span>
                            {% endif %}
                        </td>
                    </tr>
                    {% else %}
                    <tr>
                        <td colspan="9" class="text-center text-muted py-4">Chưa có dữ liệu. Vui lòng dán số Bill vào ô trên và bấm Quét!</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    count_gap = sum(1 for c in scraped_data if "ĐÃ GẮP" in c.get('trang_thai','').upper() or "ĐÃ RA" in c.get('trang_thai','').upper())
    count_cho = sum(1 for c in scraped_data if "ĐANG CHỜ" in c.get('trang_thai','').upper() or "ĐANG BÃI" in c.get('trang_thai','').upper())
    count_smart_alert = sum(1 for c in scraped_data
