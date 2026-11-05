from flask import Flask, render_template, jsonify, request, session
import json
import os
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "doi-mat-khau-nay-tren-render-6a8")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUESTIONS_FILE = os.path.join(BASE_DIR, "questions.json")
DB_FILE = os.path.join(BASE_DIR, "quiz.db")


# ==================== DATABASE ====================

def init_db():
    """Tạo bảng nếu chưa có"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS nguoi_choi (
            ip TEXT PRIMARY KEY,
            diem INTEGER DEFAULT 0,
            tong_so INTEGER DEFAULT 0,
            thoi_gian TEXT,
            user_agent TEXT
        )
    """)
    conn.commit()
    conn.close()


def get_client_ip():
    """Lấy IP thật của client (xử lý cả khi qua proxy Render)"""
    if request.headers.get("X-Forwarded-For"):
        # Render / proxy: IP thật là phần tử đầu tiên
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    if request.headers.get("X-Real-IP"):
        return request.headers.get("X-Real-IP")
    return request.remote_addr or "unknown"


def ip_da_choi(ip):
    """Kiểm tra IP đã chơi chưa"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT diem, tong_so FROM nguoi_choi WHERE ip = ?", (ip,))
    row = c.fetchone()
    conn.close()
    return row  # None nếu chưa chơi, (diem, tong) nếu đã chơi


def luu_ket_qua(ip, diem, tong_so):
    """Lưu kết quả của IP"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO nguoi_choi (ip, diem, tong_so, thoi_gian, user_agent)
        VALUES (?, ?, ?, ?, ?)
    """, (
        ip, diem, tong_so,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        request.headers.get("User-Agent", "")[:200]
    ))
    conn.commit()
    conn.close()


# Khởi tạo DB khi import
init_db()


# ==================== HELPERS ====================

def load_questions():
    try:
        with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"tieuDe": "Đố Vui Lớp 6A8", "moTa": "", "cauHoi": []}


# ==================== ROUTES ====================

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/trang-thai")
def api_trang_thai():
    """Kiểm tra IP đã chơi chưa"""
    ip = get_client_ip()
    row = ip_da_choi(ip)
    if row:
        return jsonify({
            "daHoanThanh": True,
            "diem": row[0],
            "tongSo": row[1],
            "ip": ip
        })
    return jsonify({"daHoanThanh": False, "ip": ip})


@app.route("/api/questions")
def api_questions():
    ip = get_client_ip()
    row = ip_da_choi(ip)
    if row:
        return jsonify({
            "error": "IP của bạn đã hoàn thành bài quiz. Không thể chơi lại!",
            "daHoanThanh": True,
            "diem": row[0],
            "tongSo": row[1]
        }), 403

    # Session: chống chơi lại trong cùng phiên
    if session.get("da_hoan_thanh"):
        return jsonify({
            "error": "Bạn đã hoàn thành bài quiz.",
            "daHoanThanh": True,
            "diem": session.get("diem", 0),
            "tongSo": session.get("tongSo", 0)
        }), 403

    data = load_questions()
    safe_questions = []
    for q in data.get("cauHoi", []):
        safe_questions.append({
            "id": q.get("id"),
            "loai": q.get("loai"),
            "cauHoi": q.get("cauHoi"),
            "dapAn": q.get("dapAn", []) if q.get("loai") == "tracNghiem" else []
        })
    return jsonify({
        "tieuDe": data.get("tieuDe", "Đố Vui Lớp 6A8"),
        "moTa": data.get("moTa", ""),
        "cauHoi": safe_questions
    })


@app.route("/api/check", methods=["POST"])
def api_check():
    ip = get_client_ip()
    if ip_da_choi(ip):
        return jsonify({"error": "IP của bạn đã hoàn thành bài quiz."}), 403
    if session.get("da_hoan_thanh"):
        return jsonify({"error": "Bạn đã hoàn thành bài quiz."}), 403

    body = request.get_json(silent=True) or {}
    qid = body.get("id")
    answer = body.get("answer")

    data = load_questions()
    question = next((q for q in data.get("cauHoi", []) if q.get("id") == qid), None)
    if not question:
        return jsonify({"error": "Không tìm thấy câu hỏi"}), 404

    loai = question.get("loai")
    giaiThich = question.get("giaiThich", "")

    if loai == "tracNghiem":
        try:
            idx = int(answer)
        except (TypeError, ValueError):
            return jsonify({"correct": False, "giaiThich": giaiThich})
        correct = idx == question.get("dapAnDung")
        if correct:
            session["diem"] = session.get("diem", 0) + 1
        return jsonify({
            "correct": correct,
            "giaiThich": giaiThich,
            "dapAnDung": question.get("dapAnDung")
        })

    if loai == "tuLuan":
        def normalize(s):
            return " ".join(str(s).lower().split())
        user_ans = normalize(answer or "")
        accepted = [normalize(x) for x in question.get("dapAnDung", [])]
        correct = user_ans in accepted
        if correct:
            session["diem"] = session.get("diem", 0) + 1
        return jsonify({"correct": correct, "giaiThich": giaiThich})

    return jsonify({"correct": False, "giaiThich": giaiThich})


@app.route("/api/hoan-thanh", methods=["POST"])
def api_hoan_thanh():
    """Đánh dấu hoàn thành + LƯU IP VÀO DB"""
    ip = get_client_ip()
    data = load_questions()
    tong_so = len(data.get("cauHoi", []))
    diem = session.get("diem", 0)

    # Nếu IP đã có sẵn trong DB → không ghi đè
    if ip_da_choi(ip):
        row = ip_da_choi(ip)
        return jsonify({
            "ok": True,
            "diem": row[0],
            "tongSo": row[1],
            "ghiChu": "IP đã được ghi nhận trước đó"
        })

    luu_ket_qua(ip, diem, tong_so)
    session["da_hoan_thanh"] = True
    session["tongSo"] = tong_so

    return jsonify({
        "ok": True,
        "diem": diem,
        "tongSo": tong_so,
        "ip": ip
    })


# ==================== ADMIN (tùy chọn) ====================

@app.route("/admin/ket-qua")
def admin_ket_qua():
    """Xem danh sách IP đã chơi (bảo vệ bằng token đơn giản)"""
    token = request.args.get("token", "")
    admin_token = os.environ.get("ADMIN_TOKEN", "admin6a8")
    if token != admin_token:
        return jsonify({"error": "Sai token"}), 401

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT ip, diem, tong_so, thoi_gian FROM nguoi_choi ORDER BY thoi_gian DESC")
    rows = c.fetchall()
    conn.close()

    return jsonify({
        "tongSoNguoiChoi": len(rows),
        "danhSach": [
            {"ip": r[0], "diem": r[1], "tongSo": r[2], "thoiGian": r[3]}
            for r in rows
        ]
    })


@app.route("/admin/xoa-ip")
def admin_xoa_ip():
    """Xóa IP khỏi DB (để test hoặc reset)"""
    token = request.args.get("token", "")
    ip = request.args.get("ip", "")
    admin_token = os.environ.get("ADMIN_TOKEN", "admin6a8")
    if token != admin_token:
        return jsonify({"error": "Sai token"}), 401

    if not ip:
        return jsonify({"error": "Thiếu ip"}), 400

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM nguoi_choi WHERE ip = ?", (ip,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "daXoa": ip})


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Không tìm thấy trang"}), 404


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
