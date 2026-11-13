"""可选：向本地数据库灌入演示数据。

用法：
    python import_sample.py

说明：
- 仅用于本地演示与答辩准备；重复执行会追加数据，如需干净库可删除 ledger.db 后重启应用。
- 金额本期用 REAL（需求文档 4.3 的设计取舍）。
"""

import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "ledger.db"

SAMPLE_RECORDS = [
    # (发生日期, 方向, 分类, 金额, 备注)
    ("2026-11-02", "in", "销售", 3200.00, "上旬零售回款"),
    ("2026-11-05", "out", "进货", 1200.00, "批发市场拿货"),
    ("2026-11-08", "out", "房租", 600.00, "当月铺面租金"),
    ("2026-11-10", "out", "水电", 80.50, "水电杂费"),
    ("2026-11-13", "out", "进货", 128.50, "补货"),
]


def main():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.executescript((BASE_DIR / "schema.sql").read_text(encoding="utf-8"))
    conn.executemany(
        """
        INSERT INTO records (happened_on, direction, category, amount, note)
        VALUES (?, ?, ?, ?, ?)
        """,
        SAMPLE_RECORDS,
    )
    conn.commit()
    conn.close()
    print(f"已写入 {len(SAMPLE_RECORDS)} 条演示数据 -> {DB_FILE}")


if __name__ == "__main__":
    main()
