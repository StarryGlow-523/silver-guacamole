"""数据库连接管理。

- 使用 Flask 的 ``g`` 对象在一次请求内复用同一个连接；
- ``teardown_appcontext`` 在请求结束后关闭连接；
- 开启 WAL 模式，提升并发读写可靠性；
- 首次启动读取 ``schema.sql`` 建表（可重复执行）。
"""

import sqlite3
from pathlib import Path

from flask import current_app, g

BASE_DIR = Path(__file__).resolve().parent
SCHEMA_FILE = BASE_DIR / "schema.sql"


def get_db():
    """返回当前请求复用的 SQLite 连接（不存在则创建）。"""
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        # 让查询结果可以按列名访问
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL;")
    return g.db


def close_db(_exc=None):
    """请求结束时关闭连接。"""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """读取 schema.sql 建表；仅在应用初始化时调用一次。"""
    db = get_db()
    schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")
    db.executescript(schema_sql)
    db.commit()


def init_app(app):
    """把连接关闭钩子注册到 Flask 应用，并在启动时建表。"""
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()
