"""简易记账工具（Mini Ledger）· Flask 应用入口。

接口一览（Base URL: /api）：
    POST   /api/records               记一笔
    GET    /api/records?month=&page=&size=   流水查询（按月、倒序、分页）
    GET    /api/summary?month=       月度统计（收入 / 支出 / 结余 / 分类汇总）
    DELETE /api/records/<id>         删除记录

说明：
- 所有 SQL 使用参数化查询（? 占位），禁止字符串拼接；
- 后端独立校验，不依赖前端；
- 失败统一返回 {"error": {"code", "message"}}，不抛 HTML 错误页。
"""

import re
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, render_template, request

import db

BASE_DIR = Path(__file__).resolve().parent

# 固定分类枚举（需求文档 4.2）；按收支方向分组，便于前端联动
CATEGORIES_BY_DIRECTION = {
    "out": ["进货", "房租", "水电", "其他"],
    "in": ["销售", "其他"],
}
CATEGORIES = ["进货", "房租", "水电", "销售", "其他"]
DIRECTIONS = ["in", "out"]

# 金额：数字，大于 0，最多两位小数
AMOUNT_RE = re.compile(r"^\d+(\.\d{1,2})?$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def create_app():
    app = Flask(__name__)
    app.config["DATABASE"] = str(BASE_DIR / "ledger.db")

    db.init_app(app)

    @app.errorhandler(404)
    def not_found(_e):
        return jsonify({"error": {"code": "NOT_FOUND", "message": "接口不存在"}}), 404

    @app.errorhandler(500)
    def internal_error(_e):
        return jsonify({"error": {"code": "INTERNAL_ERROR", "message": "服务端异常"}}), 500

    # ---------- 校验辅助 ----------

    def reject(code, message, status=400):
        return jsonify({"error": {"code": code, "message": message}}), status

    def validate_record(payload):
        """校验记一笔的请求体，返回 (清洗后字段, 错误响应)。

        校验通过时错误响应为 None；否则字段为 None。
        """
        if not isinstance(payload, dict):
            return None, reject("INVALID_DIRECTION", "请求体必须为 JSON 对象")

        happened_on = (payload.get("happened_on") or "").strip()
        direction = (payload.get("direction") or "").strip()
        category = (payload.get("category") or "").strip()
        amount_raw = payload.get("amount")
        note = (payload.get("note") or "").strip()

        # 日期
        if not happened_on or not DATE_RE.match(happened_on):
            return None, reject("INVALID_DATE", "日期格式应为 YYYY-MM-DD")
        try:
            parsed_date = date.fromisoformat(happened_on)
        except ValueError:
            return None, reject("INVALID_DATE", "日期无效")
        if parsed_date > date.today():
            return None, reject("INVALID_DATE", "日期不能晚于今天")

        # 收支方向
        if direction not in DIRECTIONS:
            return None, reject("INVALID_DIRECTION", "收支方向必须为 in 或 out")

        # 分类
        if category not in CATEGORIES:
            return None, reject("INVALID_CATEGORY", "分类必须属于固定枚举")

        # 金额：允许传入字符串或数字，但必须 > 0 且最多两位小数
        amount_text = str(amount_raw).strip() if amount_raw is not None else ""
        if amount_raw is None or not AMOUNT_RE.match(amount_text):
            return None, reject("INVALID_AMOUNT", "金额必须为大于 0 的数字，最多两位小数")
        amount = round(float(amount_text), 2)
        if amount <= 0:
            return None, reject("INVALID_AMOUNT", "金额必须大于 0")

        # 备注
        if len(note) > 100:
            return None, reject("NOTE_TOO_LONG", "备注不能超过 100 字")

        cleaned = {
            "happened_on": happened_on,
            "direction": direction,
            "category": category,
            "amount": amount,
            "note": note,
        }
        return cleaned, None

    # ---------- 页面 ----------

    @app.route("/")
    def index():
        return render_template(
            "index.html",
            categories=CATEGORIES,
            categories_by_direction=CATEGORIES_BY_DIRECTION,
        )

    # ---------- 记一笔 ----------

    @app.post("/api/records")
    def create_record():
        payload = request.get_json(silent=True)
        cleaned, error = validate_record(payload)
        if error is not None:
            return error

        database = db.get_db()
        cursor = database.execute(
            """
            INSERT INTO records (happened_on, direction, category, amount, note)
            VALUES (:happened_on, :direction, :category, :amount, :note)
            """,
            cleaned,
        )
        database.commit()

        row = database.execute(
            "SELECT * FROM records WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        return jsonify(dict(row)), 201

    # ---------- 流水查询 ----------

    @app.get("/api/records")
    def list_records():
        month = (request.args.get("month") or "").strip()
        if not re.match(r"^\d{4}-\d{2}$", month):
            month = date.today().strftime("%Y-%m")

        # 分页参数非法时按默认值处理，不报错
        try:
            page = int(request.args.get("page", 1))
            size = int(request.args.get("size", 20))
        except (TypeError, ValueError):
            page, size = 1, 20
        page = max(page, 1)
        size = max(min(size, 100), 1)
        offset = (page - 1) * size

        like_pattern = f"{month}%"
        database = db.get_db()

        total = database.execute(
            "SELECT COUNT(*) AS cnt FROM records WHERE happened_on LIKE ?",
            (like_pattern,),
        ).fetchone()["cnt"]

        rows = database.execute(
            """
            SELECT id, happened_on, direction, category, amount, note
            FROM records
            WHERE happened_on LIKE ?
            ORDER BY happened_on DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (like_pattern, size, offset),
        ).fetchall()

        return jsonify(
            {
                "month": month,
                "total": total,
                "page": page,
                "size": size,
                "items": [dict(row) for row in rows],
            }
        )

    # ---------- 月度统计 ----------

    @app.get("/api/summary")
    def summary():
        month = (request.args.get("month") or "").strip()
        if not re.match(r"^\d{4}-\d{2}$", month):
            month = date.today().strftime("%Y-%m")

        like_pattern = f"{month}%"
        database = db.get_db()

        rows = database.execute(
            """
            SELECT direction, SUM(amount) AS total
            FROM records
            WHERE happened_on LIKE ?
            GROUP BY direction
            """,
            (like_pattern,),
        ).fetchall()

        income = 0.0
        expense = 0.0
        for row in rows:
            if row["direction"] == "in":
                income = round(row["total"] or 0.0, 2)
            elif row["direction"] == "out":
                expense = round(row["total"] or 0.0, 2)
        balance = round(income - expense, 2)

        category_rows = database.execute(
            """
            SELECT category, direction, SUM(amount) AS total
            FROM records
            WHERE happened_on LIKE ?
            GROUP BY category, direction
            ORDER BY direction, total DESC
            """,
            (like_pattern,),
        ).fetchall()

        by_category = [
            {
                "category": row["category"],
                "direction": row["direction"],
                "amount": round(row["total"] or 0.0, 2),
            }
            for row in category_rows
        ]

        return jsonify(
            {
                "month": month,
                "income": income,
                "expense": expense,
                "balance": balance,
                "by_category": by_category,
            }
        )

    # ---------- 删除 ----------

    @app.delete("/api/records/<int:record_id>")
    def delete_record(record_id):
        database = db.get_db()
        existing = database.execute(
            "SELECT id FROM records WHERE id = ?",
            (record_id,),
        ).fetchone()
        if existing is None:
            return reject("NOT_FOUND", "记录不存在", 404)

        database.execute("DELETE FROM records WHERE id = ?", (record_id,))
        database.commit()
        return jsonify({"deleted": 1})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
