from __future__ import annotations

import customtkinter as ctk

from app.services import AppServices
from app.ui.utils import format_money
from app.ui.widgets import DataTable


def _days_display(days_delta: int) -> tuple[str, str]:
    """返回 (展示文案, 行标签)。"""
    if days_delta < 0:
        return f"逾期 {abs(days_delta)} 天", "overdue"
    if days_delta == 0:
        return "今天到期", "today"
    if days_delta <= 3:
        return f"剩余 {days_delta} 天", "urgent"
    # 已进入提醒窗口但仍有一定余量：黄色警示，不用绿色
    return f"剩余 {days_delta} 天", "upcoming"


class HomePage(ctk.CTkFrame):
    def __init__(self, master, services: AppServices, **kwargs) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self.services = services
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header, text="提醒看板", font=ctk.CTkFont(size=22, weight="bold")
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(header, text="刷新", width=80, command=self.refresh).grid(
            row=0, column=1, sticky="e"
        )

        self.summary = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=14), text_color="#4b5563", anchor="w"
        )
        self.summary.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        self.table = DataTable(
            self,
            columns=[
                ("days", "天数", 140),
                ("kind", "类型", 110),
                ("project", "项目", 140),
                ("room", "房间", 90),
                ("period", "周期/合同", 180),
                ("amount", "金额", 90),
                ("detail", "说明", 260),
            ],
            column_anchors={
                "days": "center",
                "kind": "center",
                "project": "w",
                "room": "center",
                "period": "center",
                "amount": "e",
                "detail": "w",
            },
            rowheight=38,
            style_prefix="TallyReminder",
            emphasis_columns=("days",),
        )
        self.table.grid(row=2, column=0, sticky="nsew")
        self._configure_day_tags()

    def _configure_day_tags(self) -> None:
        tree = self.table.tree
        # 逾期：红
        tree.tag_configure(
            "overdue",
            foreground="#b91c1c",
            background="#fef2f2",
            font=("PingFang SC", 15, "bold"),
        )
        # 今天：琥珀
        tree.tag_configure(
            "today",
            foreground="#b45309",
            background="#fffbeb",
            font=("PingFang SC", 15, "bold"),
        )
        # ≤3 天：橙
        tree.tag_configure(
            "urgent",
            foreground="#c2410c",
            background="#fff7ed",
            font=("PingFang SC", 15, "bold"),
        )
        # 提醒窗口内其余：黄（警示，非绿）
        tree.tag_configure(
            "upcoming",
            foreground="#a16207",
            background="#fefce8",
            font=("PingFang SC", 15, "bold"),
        )

    def refresh(self) -> None:
        if not self.services.is_ready or self.services.reminders is None:
            return
        items = self.services.reminders.list_reminders()
        overdue = sum(1 for i in items if i.kind == "已逾期")
        due = sum(1 for i in items if i.kind == "应收提醒")
        expire = sum(1 for i in items if i.kind in {"合同即将到期", "合同已到期"})
        self.summary.configure(
            text=f"共 {len(items)} 条提醒｜已逾期 {overdue}｜应收提醒 {due}｜合同到期相关 {expire}"
        )
        rows = []
        iids = []
        tags = []
        for idx, item in enumerate(items):
            period = ""
            if item.period_start and item.period_end:
                period = f"{item.period_start} ~ {item.period_end}"
            days_text, tag = _days_display(item.days_delta)
            rows.append(
                (
                    days_text,
                    item.kind,
                    item.project_name,
                    item.room_no,
                    period,
                    format_money(item.amount),
                    item.detail,
                )
            )
            iids.append(str(idx))
            tags.append(tag)
        self.table.set_rows(rows, iids, tags=tags)
