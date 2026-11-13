/* 简易记账工具 · 前端逻辑（原生 JS，fetch 调用同源接口）
 * 安全：渲染用户输入一律使用 textContent，不使用 innerHTML。
 */

(function () {
    "use strict";

    var state = {
        year: 0,
        month: 0, // 1-12
        submitting: false,
    };

    var $form = document.getElementById("recordForm");
    var $date = document.getElementById("fieldDate");
    var $direction = document.getElementById("fieldDirection");
    var $category = document.getElementById("fieldCategory");
    var $amount = document.getElementById("fieldAmount");
    var $note = document.getElementById("fieldNote");
    var $formError = document.getElementById("formError");
    var $submitBtn = document.getElementById("submitBtn");
    var $list = document.getElementById("recordList");
    var $emptyTip = document.getElementById("emptyTip");
    var $monthLabel = document.getElementById("monthLabel");
    var $income = document.getElementById("summaryIncome");
    var $expense = document.getElementById("summaryExpense");
    var $balance = document.getElementById("summaryBalance");
    var $toast = document.getElementById("toast");
    var $hint = document.getElementById("categoryHint");

    // 分类按收支方向分组（与后端 CATEGORIES_BY_DIRECTION 对齐）
    var CATEGORIES_BY_DIRECTION = {
        out: ["进货", "房租", "水电", "其他"],
        in: ["销售", "其他"],
    };
    var HINT_BY_DIRECTION = {
        out: "支出：进货 / 房租 / 水电 / 其他",
        in: "收入：销售 / 其他",
    };

    // ---------- 工具 ----------

    function todayStr() {
        var d = new Date();
        var m = String(d.getMonth() + 1).padStart(2, "0");
        var day = String(d.getDate()).padStart(2, "0");
        return d.getFullYear() + "-" + m + "-" + day;
    }

    function monthKey(year, month) {
        return year + "-" + String(month).padStart(2, "0");
    }

    function formatMoney(value) {
        return Number(value).toFixed(2);
    }

    function showToast(message) {
        $toast.textContent = message;
        $toast.hidden = false;
        window.clearTimeout(showToast._timer);
        showToast._timer = window.setTimeout(function () {
            $toast.hidden = true;
        }, 2400);
    }

    function showFormError(message) {
        $formError.textContent = message || "";
        $formError.hidden = !message;
    }

    function parseError(data) {
        if (data && data.error && data.error.message) {
            return data.error.message;
        }
        return "请求失败，请重试";
    }

    // ---------- 数据请求 ----------

    function fetchSummary() {
        var key = monthKey(state.year, state.month);
        return fetch("/api/summary?month=" + encodeURIComponent(key))
            .then(function (res) {
                return res.json();
            })
            .then(function (data) {
                $income.textContent = formatMoney(data.income);
                $expense.textContent = formatMoney(data.expense);
                $balance.textContent = formatMoney(data.balance);
            })
            .catch(function () {
                showToast("统计加载失败，请重试");
            });
    }

    function fetchRecords() {
        var key = monthKey(state.year, state.month);
        return fetch("/api/records?month=" + encodeURIComponent(key))
            .then(function (res) {
                return res.json();
            })
            .then(function (data) {
                renderRecords(data.items || []);
            })
            .catch(function () {
                showToast("流水加载失败，请重试");
            });
    }

    function refreshAll() {
        $monthLabel.textContent = state.year + "年" + state.month + "月";
        return Promise.all([fetchSummary(), fetchRecords()]);
    }

    // ---------- 渲染 ----------

    function renderRecords(items) {
        $list.textContent = "";
        $emptyTip.hidden = items.length > 0;

        items.forEach(function (item) {
            var li = document.createElement("li");
            li.className = "record-item";

            var dateSpan = document.createElement("span");
            dateSpan.className = "record-date";
            dateSpan.textContent = item.happened_on.slice(5); // MM-DD

            var main = document.createElement("div");
            main.className = "record-main";
            var cat = document.createElement("span");
            cat.className = "record-category";
            cat.textContent = item.category;
            main.appendChild(cat);
            if (item.note) {
                var note = document.createElement("span");
                note.className = "record-note";
                note.textContent = item.note;
                main.appendChild(note);
            }

            var amount = document.createElement("span");
            amount.className = "record-amount " + item.direction;
            var sign = item.direction === "in" ? "+" : "-";
            amount.textContent = sign + formatMoney(item.amount);

            var del = document.createElement("button");
            del.type = "button";
            del.className = "btn-delete";
            del.textContent = "删除";
            del.addEventListener("click", function () {
                handleDelete(item.id);
            });

            li.appendChild(dateSpan);
            li.appendChild(main);
            li.appendChild(amount);
            li.appendChild(del);
            $list.appendChild(li);
        });
    }

    // ---------- 交互 ----------

    function validateForm() {
        var amountText = $amount.value.trim();
        if (!/^\d+(\.\d{1,2})?$/.test(amountText)) {
            return "金额必须为大于 0 的数字，最多两位小数";
        }
        if (Number(amountText) <= 0) {
            return "金额必须大于 0";
        }
        if (!$date.value) {
            return "请选择日期";
        }
        if ($date.value > todayStr()) {
            return "日期不能晚于今天";
        }
        return "";
    }

    function handleSubmit(event) {
        event.preventDefault();
        if (state.submitting) {
            return;
        }

        var error = validateForm();
        if (error) {
            showFormError(error);
            return;
        }
        showFormError("");

        var payload = {
            happened_on: $date.value,
            direction: $direction.value,
            category: $category.value,
            amount: Number($amount.value.trim()),
            note: $note.value.trim(),
        };

        state.submitting = true;
        $submitBtn.disabled = true;
        $submitBtn.textContent = "保存中…";

        fetch("/api/records", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        })
            .then(function (res) {
                return res.json().then(function (data) {
                    return { ok: res.ok, data: data };
                });
            })
            .then(function (result) {
                if (!result.ok) {
                    showFormError(parseError(result.data));
                    showToast(parseError(result.data));
                    return;
                }
                $form.reset();
                $date.value = todayStr();
                showToast("已记一笔");
                refreshAll();
            })
            .catch(function () {
                showFormError("保存失败，请重试");
                showToast("保存失败，请重试");
            })
            .finally(function () {
                state.submitting = false;
                $submitBtn.disabled = false;
                $submitBtn.textContent = "记一笔";
            });
    }

    function handleDelete(id) {
        if (!window.confirm("确定删除这笔记录吗？")) {
            return;
        }
        fetch("/api/records/" + id, { method: "DELETE" })
            .then(function (res) {
                return res.json().then(function (data) {
                    return { ok: res.ok, data: data };
                });
            })
            .then(function (result) {
                if (!result.ok) {
                    showToast(parseError(result.data));
                    return;
                }
                showToast("已删除");
                refreshAll();
            })
            .catch(function () {
                showToast("删除失败，请重试");
            });
    }

    function shiftMonth(delta) {
        var d = new Date(state.year, state.month - 1 + delta, 1);
        state.year = d.getFullYear();
        state.month = d.getMonth() + 1;
        refreshAll();
    }

    // 按收支方向联动分类下拉，并更新提示
    function syncCategory() {
        var direction = $direction.value;
        var cats = CATEGORIES_BY_DIRECTION[direction] || [];
        $category.textContent = "";
        cats.forEach(function (cat) {
            var opt = document.createElement("option");
            opt.value = cat;
            opt.textContent = cat;
            $category.appendChild(opt);
        });
        $hint.textContent = HINT_BY_DIRECTION[direction] || "";
    }

    // ---------- 初始化 ----------

    function init() {
        var now = new Date();
        state.year = now.getFullYear();
        state.month = now.getMonth() + 1;

        $date.value = todayStr();
        $form.addEventListener("submit", handleSubmit);
        $direction.addEventListener("change", syncCategory);
        syncCategory();
        document.getElementById("prevMonth").addEventListener("click", function () {
            shiftMonth(-1);
        });
        document.getElementById("nextMonth").addEventListener("click", function () {
            shiftMonth(1);
        });

        refreshAll();
    }

    document.addEventListener("DOMContentLoaded", init);
})();
