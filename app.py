from flask import Flask, render_template_string, request, redirect, url_for
import os
import time

app = Flask(__name__)

scraped_data = []

def run_eport_scraper(bill_number):
    extracted_data = []
    driver = None
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import Select

        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(options=options)
        driver.get("https://eport.danangport.vn/pages/tracuuedo.html")

        wait = WebDriverWait(driver, 20)
        
        # Sử dụng logic tìm tất cả ô input y hệt bản PyQt5 local
        inputs = wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "input")))
        if len(inputs) > 1:
            inputs[1].clear()
            inputs[1].send_keys(bill_number)
        elif len(inputs) > 0:
            inputs[0].clear()
            inputs[0].send_keys(bill_number)

        # Bấm nút tìm kiếm
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for btn in buttons:
            txt = btn.text.lower()
            if "tìm kiếm" in txt or "search" in txt or "tra cứu" in txt:
                btn.click()
                break

        time.sleep(5) # Chờ dữ liệu trả về

        # Bung tối đa danh sách bảng (200 dòng)
        try:
            selects = driver.find_elements(By.TAG_NAME, "select")
            for sel_elem in selects:
                try:
                    select_obj = Select(sel_elem)
                    for opt in select_obj.options:
                        if opt.text.strip() in ["200", "300", "500", "All", "Tất cả"]:
                            select_obj.select_by_visible_text(opt.text)
                            driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", sel_elem)
                            time.sleep(3)
                            break
                except:
                    continue
        except Exception:
            pass

        # Quét dữ liệu từ bảng kết quả
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 8:
                cont_no = cols[1].text.strip()
                date_out = cols[4].text.strip()
                status = cols[6].text.strip() if len(cols) > 6 else ''
                location = cols[7].text.strip() if len(cols) > 7 else ''

                if cont_no and cont_no not in [c['containerNo'] for c in extracted_data]:
                    is_out = bool(date_out and date_out != '') or 'Delivered' in status
                    paid_exceptions = ['TLLU4766351', 'UETU7035823']
                    is_smart = 'SMART' in location.upper() or 'SMART' in status.upper()

                    # Báo đỏ nếu hạ bãi SMART, đã gắp ra, và KHÔNG nằm trong danh sách đã thanh toán ngoại lệ
                    is_alert = bool(is_smart and is_out and cont_no not in paid_exceptions)

                    extracted_data.append({
                        'billNo': cols[0].text.strip(),
                        'containerNo': cont_no,
                        'opr': cols[2].text.strip(),
                        'dateIn': cols[3].text.strip(),
                        'dateOut': date_out,
                        'status': status,
                        'location': location,
                        'is_out': is_out,
                        'is_smart': is_smart,
                        'alert': is_alert
                    })

        driver.quit()
        extracted_data.sort(key=lambda x: (x['location'], x['containerNo']))

    except Exception as e:
        if driver:
            try:
                driver.quit()
            except:
                pass
        print(f"Lỗi quét ePort: {e}")

    return extracted_data

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
        <h3 class="mb-3 text-primary fw-bold">🚢 BỘ GIÁM SÁT CONTAINER ePort ĐÀ NẴNG (150+ CONT)</h3>
        
        <div class="card mb-4 shadow-sm">
            <div class="card-body">
                <form method="POST" action="/fetch" class="row g-3 align-items-center">
                    <div class="col-auto">
                        <label class="fw-bold">Số Bill / Số Cont:</label>
                    </div>
                    <div class="col-md-4">
                        <input type="text" name="bill" class="form-control fw-bold" value="{{ current_bill }}">
                    </div>
                    <div class="col-auto">
                        <button type="submit" class="btn btn-primary fw-bold">🔄 Quét Ngay ePort</button>
                    </div>
                    <div class="col-auto">
                        <span class="text-danger fw-bold" id="countdown">Tự động quét sau: 15:00</span>
                    </div>
                </form>
            </div>
        </div>

        <div class="row text-white text-center mb-4 g-2">
            <div class="col-md-3"><div class="p-3 bg-secondary rounded shadow-sm"><h5>Tổng số Cont: {{ containers|length }}</h5></div></div>
            <div class="col-md-3"><div class="p-3 bg-success rounded shadow-sm"><h5>✅ Đã gắp ra: {{ count_out }}</h5></div></div>
            <div class="col-md-3"><div class="p-3 bg-warning text-dark rounded shadow-sm"><h5>⏳ Đang chờ: {{ count_wait }}</h5></div></div>
            <div class="col-md-3"><div class="p-3 bg-danger rounded shadow-sm"><h5>⚠️ SMART Chưa TT (Báo Đỏ): {{ count_alert }}</h5></div></div>
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
                    <tr class="{% if item.alert %}smart-blink{% elif item.is_out %}table-success{% endif %}">
                        <td class="text-center">{{ loop.index }}</td>
                        <td>{{ item.billNo }}</td>
                        <td class="fw-bold text-primary">{{ item.containerNo }}</td>
                        <td class="text-center">{{ item.opr }}</td>
                        <td class="text-center">{{ item.dateIn }}</td>
                        <td class="text-center">{{ item.dateOut }}</td>
                        <td>{{ item.status }}</td>
                        <td>{{ item.location }}</td>
                        <td class="text-center">
                            {% if item.alert %}
                                <span class="badge-blink">⚠️ SMART CHƯA TT (CẦN GẤP)</span>
                            {% elif item.containerNo in ['TLLU4766351', 'UETU7035823'] %}
                                <span class="badge bg-info text-dark">Đã TT (Ngoại lệ)</span>
                            {% elif item.is_out %}
                                <span class="badge bg-success">Đã gắp ra / Hợp lệ</span>
                            {% else %}
                                <span class="badge bg-secondary">Đang bãi</span>
                            {% endif %}
                        </td>
                    </tr>
                    {% else %}
                    <tr>
                        <td colspan="9" class="text-center text-muted py-4">Chưa có dữ liệu. Vui lòng bấm nút "Quét Ngay ePort" để tải dữ liệu!</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <script>
        let timeLeft = 900;
        const countdownEl = document.getElementById('countdown');
        setInterval(() => {
            let m = Math.floor(timeLeft / 60);
            let s = timeLeft % 60;
            countdownEl.innerText = `Tự động quét sau: ${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
            timeLeft--;
            if (timeLeft < 0) {
                location.reload();
            }
        }, 1000);
    </script>
</body>
</html>
"""

current_bill_global = "SITGHFDAU30060"

@app.route('/')
def index():
    global scraped_data, current_bill_global
    count_out = sum(1 for c in scraped_data if c.get('is_out'))
    count_wait = len(scraped_data) - count_out
    count_alert = sum(1 for c in scraped_data if c.get('alert'))

    return render_template_string(
        HTML_TEMPLATE,
        containers=scraped_data,
        current_bill=current_bill_global,
        count_out=count_out,
        count_wait=count_wait,
        count_alert=count_alert
    )

@app.route('/fetch', methods=['POST'])
def fetch():
    global scraped_data, current_bill_global
    current_bill_global = request.form.get('bill', 'SITGHFDAU30060').strip()
    scraped_data = run_eport_scraper(current_bill_global)
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
