import os
import json
import time
from flask import Flask, render_template_string, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select

app = Flask(__name__)

STATUS_FILE = "payment_status.json"

def load_payment_status():
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_payment_status(status_dict):
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(status_dict, f, ensure_ascii=False, indent=4)
    except:
        pass

app_data = {
    "containers": [],
    "last_updated": "Chưa quét",
    "total": 0,
    "delivered": 0,
    "pending": 0,
    "smart_unpaid": 0
}

def fetch_eport_data(bill_no="SITGHFDAU30060"):
    global app_data
    driver = None
    try:
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--remote-debugging-port=9222")

        driver = webdriver.Chrome(options=options)
        driver.get("https://eport.danangport.com/pages/tracuuedo.html")

        wait = WebDriverWait(driver, 15)
        inputs = wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "input")))
        
        if len(inputs) > 1:
            inputs[1].clear()
            inputs[1].send_keys(bill_no)

        buttons = driver.find_elements(By.TAG_NAME, "button")
        for btn in buttons:
            if "tìm kiếm" in btn.text.lower() or "search" in btn.text.lower() or "tra cứu" in btn.text.lower():
                btn.click()
                break

        time.sleep(4)

        try:
            selects = driver.find_elements(By.TAG_NAME, "select")
            for sel_elem in selects:
                try:
                    select_obj = Select(sel_elem)
                    for opt in select_obj.options:
                        txt = opt.text.strip()
                        if txt in ["200", "300", "500", "All", "Tất cả"]:
                            select_obj.select_by_visible_text(opt.text)
                            driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", sel_elem)
                            time.sleep(3)
                            break
                except:
                    continue
        except:
            pass

        extracted_data = []
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 8:
                bill_val = cols[0].text.strip()
                cont_val = cols[1].text.strip()
                
                if cont_val != '' and 'container' not in cont_val.lower() and 'số' not in bill_val.lower():
                    ngay_ra = cols[4].text.strip()
                    status_text = cols[6].text.strip() if len(cols) > 6 else ''
                    location = cols[7].text.strip() if len(cols) > 7 else ''
                    
                    is_delivered = bool(ngay_ra and ngay_ra != '') or 'Delivered' in status_text
                    
                    extracted_data.append({
                        'billNo': bill_val,
                        'containerNo': cont_val,
                        'opr': cols[2].text.strip(),
                        'dateIn': cols[3].text.strip(),
                        'dateOut': ngay_ra,
                        'status': status_text,
                        'location': location,
                        'isDelivered': is_delivered
                    })

        if driver:
            driver.quit()

        extracted_data.sort(key=lambda x: (x['location'], x['containerNo']))
        
        payment_status = load_payment_status()
        smart_unpaid_count = 0
        delivered_count = 0

        for item in extracted_data:
            cont = item['containerNo']
            location_upper = item['location'].upper()
            is_smart = "SMART" in location_upper
            
            if cont in ["TLLU4766351", "UETU7035823"]:
                payment_status[cont] = True

            is_paid = payment_status.get(cont, False)
            item['isPaid'] = is_paid

            if item['isDelivered']:
                delivered_count += 1

            if is_smart and not is_paid and not item['isDelivered']:
                smart_unpaid_count += 1

        save_payment_status(payment_status)

        app_data["containers"] = extracted_data
        app_data["total"] = len(extracted_data)
        app_data["delivered"] = delivered_count
        app_data["pending"] = len(extracted_data) - delivered_count
        app_data["smart_unpaid"] = smart_unpaid_count
        app_data["last_updated"] = time.strftime("%H:%M:%S - %d/%m/%Y")

    except Exception as e:
        if driver:
            try:
                driver.quit()
            except:
                pass
        print("Lỗi quét dữ liệu:", str(e))

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>Giám Sát Container ePort Đà Nẵng</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; font-family: Arial, sans-serif; }
        .blink-red {
            background-color: #ffcccc !important;
            animation: blinker 1s linear infinite;
            font-weight: bold;
            color: #721c24;
        }
        @keyframes blinker {
            50% { opacity: 0.4; }
        }
        .delivered-row {
            background-color: #d4edda !important;
            color: #155724;
            font-weight: bold;
        }
    </style>
</head>
<body>
<div class="container-fluid py-4">
    <div class="row mb-3">
        <div class="col-md-6">
            <h3>🚢 GIÁM SÁT CONTAINER ePort ĐÀ NẴNG (150+ CONT)</h3>
            <p class="text-muted mb-0">Cập nhật lần cuối: <span id="last-updated">{{ last_updated }}</span></p>
        </div>
        <div class="col-md-6 text-end">
            <button class="btn btn-primary fw-bold" onclick="triggerFetch()">🔄 Làm Mới & Quét Ngay</button>
        </div>
    </div>

    <div class="row mb-3">
        <div class="col-md-3">
            <div class="card text-white bg-secondary p-2">
                <h5>Tổng số Cont: <span id="lbl-total">{{ total }}</span></h5>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card text-white bg-success p-2">
                <h5>Đã gắp ra: <span id="lbl-delivered">{{ delivered }}</span></h5>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card text-white bg-warning p-2">
                <h5>Đang chờ: <span id="lbl-pending">{{ pending }}</span></h5>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card text-white bg-danger p-2">
                <h5>⚠️ SMART Chưa TT: <span id="lbl-smart-unpaid">{{ smart_unpaid }}</span></h5>
            </div>
        </div>
    </div>

    <div class="card shadow-sm">
        <div class="card-body p-0">
            <div class="table-responsive" style="max-height: 650px;">
                <table class="table table-bordered table-striped mb-0 text-center align-middle">
                    <thead class="table-dark sticky-top">
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
                    <tbody id="table-body">
                        {% for item in containers %}
                        {% set is_smart = "SMART" in item.location.upper() %}
                        {% set needs_payment = is_smart and not item.isPaid and not item.isDelivered %}
                        <tr class="{% if item.isDelivered %}delivered-row{% elif needs_payment %}blink-red{% endif %}">
                            <td>{{ loop.index }}</td>
                            <td>{{ item.billNo }}</td>
                            <td class="fw-bold">{{ item.containerNo }}</td>
                            <td>{{ item.opr }}</td>
                            <td>{{ item.dateIn }}</td>
                            <td>{{ item.dateOut }}</td>
                            <td>{{ item.status }}</td>
                            <td>{{ item.location }}</td>
                            <td>
                                {% if item.isDelivered %}
                                    <span class="badge bg-success">Đã Gắp Ra</span>
                                {% elif item.isPaid %}
                                    <button class="btn btn-sm btn-success fw-bold" onclick="togglePayment('{{ item.containerNo }}', false)">✅ Đã Thanh Toán (Click hoàn tác)</button>
                                {% else %}
                                    <button class="btn btn-sm btn-danger fw-bold" onclick="togglePayment('{{ item.containerNo }}', true)">⏳ Chưa TT (Click hoàn thành)</button>
                                {% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>

<script>
function togglePayment(containerNo, status) {
    fetch('/update_payment', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ containerNo: containerNo, isPaid: status })
    })
    .then(response => response.json())
    .then(data => {
        if(data.success) {
            location.reload();
        }
    });
}

function triggerFetch() {
    alert("Đang yêu cầu quét mới dữ liệu ePort trên mây, vui lòng đợi 5-10 giây rồi bấm OK để xem kết quả!");
    fetch('/fetch_data', { method: 'POST' })
    .then(res => res.json())
    .then(data => {
        location.reload();
    });
}

setTimeout(function(){
   window.location.reload();
}, 60000);
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, **app_data)

@app.route('/update_payment', methods=['POST'])
def update_payment():
    data = request.json
    cont_no = data.get('containerNo')
    is_paid = data.get('isPaid')
    
    payment_status = load_payment_status()
    payment_status[cont_no] = is_paid
    save_payment_status(payment_status)
    
    for item in app_data["containers"]:
        if item['containerNo'] == cont_no:
            item['isPaid'] = is_paid
            
    smart_unpaid_count = 0
    for item in app_data["containers"]:
        is_smart = "SMART" in item['location'].upper()
        if is_smart and not item['isPaid'] and not item['isDelivered']:
            smart_unpaid_count += 1
    app_data["smart_unpaid"] = smart_unpaid_count

    return jsonify(success=True)

@app.route('/fetch_data', methods=['POST'])
def background_fetch():
    fetch_eport_data()
    return jsonify(success=True)

if __name__ == '__main__':
    print("Đang quét dữ liệu lần đầu...")
    fetch_eport_data()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)