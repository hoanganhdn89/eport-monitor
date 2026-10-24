from flask import Flask, render_template_string, request, redirect, url_for
import os
import time

app = Flask(__name__)

# Lưu dữ liệu sau khi quét
scraped_data = []

def check_eport(bill_number):
    """Hàm quét ePort Đà Nẵng"""
    results = []
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By

        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')

        driver = webdriver.Chrome(options=options)
        
        # Mở trang ePort
        url = f"https://eport.danangport.vn/tra-cuu-thong-tin-container?bill={bill_number}"
        driver.get(url)
        time.sleep(3)

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
                thanh_toan = cols[6].text.strip()

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
        driver.quit()
    except Exception as e:
        print(f"Lỗi khi quét {bill_number}: {e}")
        # Dữ liệu dự phòng nếu chưa cào được
        results.append({
            "bill": bill_number,
            "cont": "Cần cào lại / Lỗi kết nối",
            "opr": "---", "ngay_vao": "---", "ngay_ra": "---",
            "trang_thai": "Đang theo dõi", "vi_tri": "Bãi SMART",
            "smart": "Chưa TT", "alert": True
        })
    return results

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>GIÁM SÁT CONTAINER ePort ĐÀ NẴNG</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        @keyframes blink-animation {
            0% { background-color: #ff4d4d; color: white; }
            50% { background-color: #8b0000; color: #ffff00; }
            100% { background-color: #ff4d4d; color: white; }
        }
        .smart-blink {
            animation: blink-animation 1s infinite;
            font-weight: bold;
        }
        .badge-blink {
            animation: blink-animation 0.8s infinite;
            padding: 6px 12px;
            border-radius: 4px;
            display: inline-block;
        }
    </style>
</head>
<body class="bg-light">
    <div class="container-fluid py-4 px-4">
        <h3 class="mb-3 text-primary fw-bold">🚢 GIÁM SÁT CONTAINER ePort ĐÀ NẴNG</h3>
        
        <div class="card mb-4 shadow-sm">
            <div class="card-body">
                <form method="POST" action="/update_list">
                    <label for="raw_data" class="form-label fw-bold">Nhập / Dán danh sách Số Bill (Mỗi dòng 1 bill):</label>
                    <textarea class="form-control mb-2" id="raw_data" name="raw_data" rows="2" placeholder="Ví dụ: SITGHFDAU30060"></textarea>
                    <button type="submit" class="btn btn-success fw-bold">🔍 Bắt Đầu Quét & Cập Nhật ePort</button>
                </form>
            </div>
        </div>

        <div class="row text-white text-center mb-4 g-2">
            <div class="col-md-3"><div class="p-3 bg-secondary rounded shadow-sm"><h5>Tổng số Cont: {{ containers|length }}</h5></div></div>
            <div class="col-md-3"><div class="p-3 bg-success rounded shadow-sm"><h5>Đã gắp ra: {{ count_gap }}</h5></div></div>
            <div class="col-md-3"><div class="p-3 bg-warning text-dark rounded shadow-sm"><h5>Đang chờ: {{ count_cho }}</h5></div></div>
            <div class="col-md-3"><div class="p-3 bg-danger rounded shadow-sm"><h5>⚠️ SMART Chưa TT: {{ count_smart_alert }}</h5></div></div>
        </div>

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
