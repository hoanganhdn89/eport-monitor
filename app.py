from flask import Flask, render_template_string, request, redirect, url_for
import os

app = Flask(__name__)

# Danh sách container mẫu ban đầu (anh có thể thay thế hoặc nhập mới trực tiếp trên web)
containers_list = [
    # Ví dụ: {"bill": "BILL001", "cont": "CONT1234567", "opr": "MSK", "ngay_vao": "24/10/2026", "ngay_ra": "", "trang_thai": "Đang bãi", "vi_tri": "A1-02", "smart": "Chưa TT"}
]

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>GIÁM SÁT CONTAINER ePort ĐÀ NẴNG</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    <div class="container mt-4">
        <h3 class="mb-3">🚢 GIÁM SÁT CONTAINER ePort ĐÀ NẴNG</h3>
        
        <!-- Form nhập danh sách Bill cũ -->
        <div class="card mb-4 shadow-sm">
            <div class="card-body">
                <form method="POST" action="/update_list">
                    <label for="raw_data" class="form-label fw-bold">Nhập / Dán danh sách Số Bill hoặc Số Container cũ vào đây:</label>
                    <textarea class="form-control mb-2" id="raw_data" name="raw_data" rows="3" placeholder="Dán danh sách các số Bill hoặc Container của anh vào đây, mỗi dòng một số..."></textarea>
                    <button type="submit" class="btn btn-primary">💾 Cập Nhật Danh Sách</button>
                </form>
            </div>
        </div>

        <div class="row text-white text-center mb-4">
            <div class="col-md-3"><div class="p-3 bg-secondary rounded"><h5>Tổng số Cont: {{ containers|length }}</h5></div></div>
            <div class="col-md-3"><div class="p-3 bg-success rounded"><h5>Đã gắp ra: 0</h5></div></div>
            <div class="col-md-3"><div class="p-3 bg-warning text-dark rounded"><h5>Đang chờ: 0</h5></div></div>
            <div class="col-md-3"><div class="p-3 bg-danger rounded"><h5>⚠️ SMART Chưa TT: 0</h5></div></div>
        </div>

        <table class="table table-bordered table-striped bg-white shadow-sm">
            <thead class="table-dark">
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
                <tr>
                    <td>{{ loop.index }}</td>
                    <td>{{ item.bill }}</td>
                    <td>{{ item.cont }}</td>
                    <td>{{ item.opr }}</td>
                    <td>{{ item.ngay_vao }}</td>
                    <td>{{ item.ngay_ra }}</td>
                    <td>{{ item.trang_thai }}</td>
                    <td>{{ item.vi_tri }}</td>
                    <td><span class="badge bg-danger">{{ item.smart }}</span></td>
                </tr>
                {% else %}
                <tr>
                    <td colspan="9" class="text-center text-muted">Chưa có dữ liệu. Vui lòng nhập danh sách ở khung phía trên!</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, containers=containers_list)

@app.route('/update_list', methods=['POST'])
def update_list():
    global containers_list
    raw_data = request.form.get('raw_data', '')
    lines = raw_data.splitlines()
    
    # Xử lý làm sạch và thêm dữ liệu mới vào bảng
    containers_list = []
    for line in lines:
        line = line.strip()
        if line:
            containers_list.append({
                "bill": line, # Nếu nhập số Bill hoặc Container
                "cont": "Đang cập nhật",
                "opr": "---",
                "ngay_vao": "---",
                "ngay_ra": "---",
                "trang_thai": "Đang theo dõi",
                "vi_tri": "---",
                "smart": "Chưa TT"
            })
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
