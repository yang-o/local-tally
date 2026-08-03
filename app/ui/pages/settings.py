from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk

from app.config import frozen_storage_hint, is_frozen
from app.services import AppServices, ValidationError
from app.ui.utils import ask_directory, ask_yes_no, parse_int, show_error, show_info


class SettingsPage(ctk.CTkFrame):
    def __init__(
        self,
        master,
        services: AppServices,
        on_storage_configured: Optional[Callable[[], None]] = None,
        on_app_name_changed: Optional[Callable[[str], None]] = None,
        on_uninstall: Optional[Callable[[], None]] = None,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self.services = services
        self.on_storage_configured = on_storage_configured
        self.on_app_name_changed = on_app_name_changed
        self.on_uninstall = on_uninstall
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ctk.CTkLabel(
            header, text="通用配置", font=ctk.CTkFont(size=22, weight="bold")
        ).pack(anchor="w")
        self.subtitle = ctk.CTkLabel(
            header,
            text="请先配置数据存储位置，配置后才能使用其他功能",
            font=ctk.CTkFont(size=13),
            text_color="#6b7280",
        )
        self.subtitle.pack(anchor="w", pady=(4, 0))

        # 可滚动区域，避免默认窗口高度下底部按钮被遮挡
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=1, column=0, sticky="nsew")
        self.scroll.grid_columnconfigure(0, weight=1)

        card = ctk.CTkFrame(self.scroll)
        card.grid(row=0, column=0, sticky="ew")
        card.grid_columnconfigure(1, weight=1)

        row = 0
        ctk.CTkLabel(
            card, text="基础设置", font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=row, column=0, columnspan=3, sticky="w", padx=20, pady=(20, 12))

        row = 1
        ctk.CTkLabel(card, text="应用名称", anchor="w", width=180).grid(
            row=row, column=0, sticky="w", padx=20, pady=10
        )
        self.app_name_var = ctk.StringVar(value="")
        self.app_name_entry = ctk.CTkEntry(card, textvariable=self.app_name_var)
        self.app_name_entry.grid(
            row=row, column=1, columnspan=2, sticky="ew", padx=(0, 20), pady=10
        )

        row = 2
        ctk.CTkLabel(card, text="数据存储位置", anchor="w", width=180).grid(
            row=row, column=0, sticky="w", padx=20, pady=10
        )
        self.storage_var = ctk.StringVar(value="")
        self.storage_entry = ctk.CTkEntry(card, textvariable=self.storage_var)
        self.storage_entry.grid(row=row, column=1, sticky="ew", padx=(0, 8), pady=10)
        self.browse_btn = ctk.CTkButton(
            card, text="选择文件夹", width=100, command=self.browse_storage
        )
        self.browse_btn.grid(row=row, column=2, sticky="e", padx=(0, 20), pady=10)

        row = 3
        self.storage_hint = ctk.CTkLabel(
            card,
            text="选择后保存即锁定，之后不可修改",
            font=ctk.CTkFont(size=12),
            text_color="#6b7280",
            anchor="w",
        )
        self.storage_hint.grid(
            row=row, column=0, columnspan=3, sticky="w", padx=20, pady=(0, 8)
        )

        row = 4
        ctk.CTkLabel(
            card, text="提醒设置", font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=row, column=0, columnspan=3, sticky="w", padx=20, pady=(16, 12))

        row = 5
        ctk.CTkLabel(card, text="合同到期提前提醒天数", anchor="w", width=180).grid(
            row=row, column=0, sticky="w", padx=20, pady=10
        )
        self.expire_var = ctk.StringVar(value="7")
        self.expire_entry = ctk.CTkEntry(
            card, textvariable=self.expire_var, width=160, placeholder_text="例如 7"
        )
        self.expire_entry.grid(row=row, column=1, sticky="w", padx=(0, 20), pady=10)

        row = 6
        ctk.CTkLabel(
            card,
            text="合同到期日前多少天开始提醒",
            font=ctk.CTkFont(size=12),
            text_color="#6b7280",
            anchor="w",
        ).grid(row=row, column=0, columnspan=3, sticky="w", padx=20, pady=(0, 8))

        row = 7
        ctk.CTkLabel(card, text="按月应收提前提醒天数", anchor="w", width=180).grid(
            row=row, column=0, sticky="w", padx=20, pady=10
        )
        self.rent_var = ctk.StringVar(value="7")
        self.rent_entry = ctk.CTkEntry(
            card, textvariable=self.rent_var, width=160, placeholder_text="例如 7"
        )
        self.rent_entry.grid(row=row, column=1, sticky="w", padx=(0, 20), pady=10)

        row = 8
        ctk.CTkLabel(
            card,
            text="应收起始日前多少天开始提醒",
            font=ctk.CTkFont(size=12),
            text_color="#6b7280",
            anchor="w",
        ).grid(row=row, column=0, columnspan=3, sticky="w", padx=20, pady=(0, 8))

        row = 9
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=row, column=0, columnspan=3, sticky="ew", padx=20, pady=(8, 20))
        ctk.CTkButton(actions, text="保存配置", width=110, command=self.save).pack(
            side="right"
        )

        # 打包版卸载区（放在滚动区域内，保证可完整看到）
        self.uninstall_card = ctk.CTkFrame(self.scroll)
        self.uninstall_card.grid(row=1, column=0, sticky="ew", pady=(16, 12))
        self.uninstall_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self.uninstall_card,
            text="卸载",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 8))
        ctk.CTkLabel(
            self.uninstall_card,
            text="卸载将删除程序目录、本地数据与配置，且不可恢复",
            font=ctk.CTkFont(size=12),
            text_color="#6b7280",
            anchor="w",
        ).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 12))
        ctk.CTkButton(
            self.uninstall_card,
            text="卸载应用",
            width=120,
            fg_color="#b91c1c",
            hover_color="#991b1b",
            command=self.uninstall,
        ).grid(row=2, column=0, sticky="e", padx=20, pady=(0, 16))

        if not is_frozen():
            self.uninstall_card.grid_remove()

    def browse_storage(self) -> None:
        if is_frozen() or self.services.bootstrap.is_portable():
            show_info(frozen_storage_hint())
            return
        if self.services.bootstrap.is_storage_configured():
            show_info("数据存储位置已配置，不可修改")
            return
        selected = ask_directory(title="选择数据存储文件夹", parent=self)
        if selected:
            self.storage_var.set(selected)

    def uninstall(self) -> None:
        if not is_frozen():
            show_info("开发运行模式不提供卸载")
            return
        if not ask_yes_no("确认卸载？将删除程序文件与全部本地数据，且不可恢复。"):
            return
        if not ask_yes_no("再次确认：真的要卸载并清空数据吗？"):
            return
        if self.on_uninstall:
            self.on_uninstall()

    def _set_remind_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.expire_entry.configure(state=state)
        self.rent_entry.configure(state=state)

    def _set_storage_entry_readonly(self, readonly: bool) -> None:
        """不可修改时置灰路径框，可修改时恢复可编辑样式。"""
        if readonly:
            self.storage_entry.configure(
                state="disabled",
                fg_color=("#e5e7eb", "#374151"),
                text_color=("#6b7280", "#9ca3af"),
                border_color=("#d1d5db", "#4b5563"),
            )
        else:
            self.storage_entry.configure(
                state="normal",
                fg_color=("#f9fafb", "#343638"),
                text_color=("#111827", "#DCE4EE"),
                border_color=("#979DA2", "#565B5E"),
            )

    def _set_storage_locked_ui(self, locked: bool) -> None:
        portable = is_frozen() or self.services.bootstrap.is_portable()
        if portable:
            self._set_storage_entry_readonly(True)
            self.browse_btn.grid_remove()
            self.storage_entry.grid_configure(columnspan=2, padx=(0, 20))
            self.storage_hint.configure(text=frozen_storage_hint())
            self.subtitle.configure(text="应用于全部项目的提醒与系统参数")
            self.uninstall_card.grid()
            return

        self.browse_btn.grid()
        self.storage_entry.grid_configure(columnspan=1, padx=(0, 8))
        self.uninstall_card.grid_remove()
        if locked:
            self._set_storage_entry_readonly(True)
            self.browse_btn.configure(state="disabled")
            self.storage_hint.configure(text="数据存储位置已锁定，不可修改")
            self.subtitle.configure(text="应用于全部项目的提醒与系统参数")
        else:
            self._set_storage_entry_readonly(False)
            self.browse_btn.configure(state="normal")
            self.storage_hint.configure(text="选择后保存即锁定，之后不可修改")
            self.subtitle.configure(
                text="请先配置数据存储位置，配置后才能使用其他功能"
            )

    def refresh(self) -> None:
        settings = self.services.settings.get()
        self.app_name_var.set(settings.app_name)
        # 先切到可写再写入路径，避免 disabled 状态下显示不更新
        self.storage_entry.configure(state="normal")
        self.storage_var.set(settings.data_storage_path)
        self.expire_var.set(str(settings.lease_expire_remind_days))
        self.rent_var.set(str(settings.rent_due_remind_days))
        self._set_storage_locked_ui(settings.storage_locked)
        self._set_remind_enabled(self.services.is_ready)

    def save(self) -> None:
        try:
            app_name = self.app_name_var.get().strip()
            storage_path = self.storage_var.get().strip()
            was_ready = self.services.is_ready
            portable = is_frozen() or self.services.bootstrap.is_portable()

            expire = None
            rent = None
            if was_ready or self.services.bootstrap.is_storage_configured() or portable:
                expire = parse_int(self.expire_var.get(), "合同到期提前提醒天数")
                rent = parse_int(self.rent_var.get(), "按月应收提前提醒天数")
            elif self.expire_var.get().strip() or self.rent_var.get().strip():
                expire = parse_int(self.expire_var.get() or "7", "合同到期提前提醒天数")
                rent = parse_int(self.rent_var.get() or "7", "按月应收提前提醒天数")

            storage_just_set = self.services.settings.update(
                app_name=app_name,
                data_storage_path=None if (was_ready or portable) else storage_path,
                lease_expire_remind_days=expire if (was_ready or portable) else None,
                rent_due_remind_days=rent if (was_ready or portable) else None,
            )

            if storage_just_set and self.on_storage_configured:
                self.on_storage_configured()

            if self.services.is_ready and expire is not None and rent is not None:
                self.services.settings.update(
                    app_name=app_name,
                    data_storage_path=None,
                    lease_expire_remind_days=expire,
                    rent_due_remind_days=rent,
                )

            if self.on_app_name_changed:
                self.on_app_name_changed(self.services.bootstrap.app_name)

            show_info("配置已保存")
            self.refresh()
        except (ValidationError, ValueError) as exc:
            show_error(str(exc))
