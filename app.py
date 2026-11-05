from flask import Flask, render_template, jsonify, send_from_directory
import json
import os

app = Flask(__name__)

# Đường dẫn file dữ liệu
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUESTIONS_FILE = os.path.join(BASE_DIR, "questions.json")


def load_questions():
    """Đọc danh sách câu hỏi từ questions.json"""
    try:
        with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"tieuDe": "Đố Vui Lớp 6A8", "moTa": "", "cauHoi": []}
    except json.JSONDecodeError as e:
        print(f"⚠️ Lỗi đọc JSON: {e}")
        return {"tieuDe": "Đố Vui Lớp 6A8", "moTa": "", "cauHoi": []}


@app.route("/")
def home():
    """Trang chính — trả về giao diện quiz"""
    return render_template("index.html")


@app.route("/api/questions")
def api_questions():
    """API trả về danh sách câu hỏi dạng JSON"""
    data = load_questions()

    # Ẩn đáp án đúng khi gửi xuống client (chống xem trộm)
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
    """API kiểm tra đáp án — nhận id câu hỏi + câu trả lời, trả về đúng/sai"""
    from flask import request

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
        return jsonify({"correct": correct, "giaiThich": giaiThich})

    return jsonify({"correct": False, "giaiThich": giaiThich})


@app.route("/students.json")
def students_json():
    """Cho phép truy cập students.json nếu có (dùng cho trang xác minh cũ)"""
    return send_from_directory(BASE_DIR, "students.json")


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Không tìm thấy trang"}), 404


if __name__ == "__main__":
    # Chạy local: python app.py
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
