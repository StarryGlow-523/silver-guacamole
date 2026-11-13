-- 简易记账工具 · 建表语句（与需求文档 4.1 一致）
-- 首次启动由 db.py 读取并执行；IF NOT EXISTS 保证可重复执行

CREATE TABLE IF NOT EXISTS records (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    happened_on TEXT    NOT NULL,                          -- 发生日期 YYYY-MM-DD
    direction   TEXT    NOT NULL CHECK (direction IN ('in','out')),  -- in=收入 out=支出
    category    TEXT    NOT NULL,                          -- 进货/房租/水电/销售/其他
    amount      REAL    NOT NULL CHECK (amount > 0),       -- 金额，二期改为整数分存储
    note        TEXT    DEFAULT '',                        -- 备注，可为空
    created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_records_date ON records (happened_on);
