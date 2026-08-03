from __future__ import annotations

import customtkinter as ctk

from app.bootstrap import BootstrapConfig
from app.database import Database
from app.services import AppServices
from app.ui.pages.home import HomePage
from app.ui.pages.leases import LeasesPage
from app.ui.pages.payments import PaymentsPage
from app.ui.pages.projects import ProjectsPage
from app.ui.pages.rooms import RoomsPage
from app.ui.pages.settings import SettingsPage
from app.ui.utils import show_error, show_info
from app.uninstall import uninstall_portable_app


class TallyApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self.bootstrap = BootstrapConfig()
        db = None
        db_path = self.bootstrap.get_db_path()
        if db_path is not None:
            db = Database(db_path)
        self.services = AppServices(self.bootstrap, db)

        self.geometry("1180x720")
        self.minsize(980, 620)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._build_sidebar()
        self._build_pages()
        self._apply_branding()
        self._sync_nav_state()

        if self.services.is_ready:
            self.show_page("home")
        else:
            self.show_page("settings")

    def _build_sidebar(self) -> None:
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self.sidebar.grid_propagate(False)

        self.brand_label = ctk.CTkLabel(
            self.sidebar,
            text="",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        self.brand_label.pack(anchor="w", padx=20, pady=(24, 20))

        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        self._nav_items = [
            ("home", "提醒看板"),
            ("projects", "项目管理"),
            ("rooms", "房间管理"),
            ("leases", "租赁管理"),
            ("payments", "收费登记"),
            ("settings", "通用配置"),
        ]
        for key, label in self._nav_items:
            btn = ctk.CTkButton(
                self.sidebar,
                text=label,
                anchor="w",
                height=40,
                fg_color="transparent",
                text_color=("#111827", "#f9fafb"),
                hover_color=("#dbeafe", "#1e3a5f"),
                command=lambda k=key: self.show_page(k),
            )
            btn.pack(fill="x", padx=12, pady=4)
            self.nav_buttons[key] = btn

        self.data_path_label = ctk.CTkLabel(
            self.sidebar,
            text="数据：未配置",
            font=ctk.CTkFont(size=11),
            text_color="#9ca3af",
            wraplength=170,
            justify="left",
        )
        self.data_path_label.pack(side="bottom", anchor="w", padx=16, pady=16)

    def _build_pages(self) -> None:
        self.content = ctk.CTkFrame(self, fg_color=("#f3f4f6", "#111827"))
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        container = ctk.CTkFrame(self.content, fg_color="transparent")
        container.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.pages = {
            "home": HomePage(container, self.services),
            "projects": ProjectsPage(
                container, self.services, on_open_rooms=self.open_rooms_for_project
            ),
            "rooms": RoomsPage(container, self.services),
            "leases": LeasesPage(container, self.services),
            "payments": PaymentsPage(container, self.services),
            "settings": SettingsPage(
                container,
                self.services,
                on_storage_configured=self.initialize_database,
                on_app_name_changed=lambda _name: self._apply_branding(),
                on_uninstall=self.uninstall_app,
            ),
        }
        for page in self.pages.values():
            page.grid(row=0, column=0, sticky="nsew")

    def _apply_branding(self) -> None:
        name = self.bootstrap.app_name
        self.title(name)
        self.brand_label.configure(text=name)
        storage = self.bootstrap.get_data_storage_path()
        if storage is None:
            self.data_path_label.configure(text="数据：未配置")
        else:
            self.data_path_label.configure(text=f"数据：{storage}")

    def _sync_nav_state(self) -> None:
        ready = self.services.is_ready
        for key, btn in self.nav_buttons.items():
            if key == "settings":
                btn.configure(state="normal")
            else:
                btn.configure(state="normal" if ready else "disabled")

    def initialize_database(self) -> None:
        db_path = self.bootstrap.get_db_path()
        if db_path is None:
            return
        if self.services.db is None:
            self.services.attach_database(Database(db_path))
        self._apply_branding()
        self._sync_nav_state()

    def show_page(self, key: str) -> None:
        if key != "settings" and not self.services.is_ready:
            show_info("请先在「通用配置」中设置数据存储位置")
            key = "settings"

        page = self.pages[key]
        page.tkraise()
        if hasattr(page, "refresh"):
            page.refresh()
        for nav_key, btn in self.nav_buttons.items():
            if nav_key == key:
                btn.configure(fg_color=("#bfdbfe", "#1d4ed8"))
            else:
                btn.configure(fg_color="transparent")

    def open_rooms_for_project(self, project_id: int) -> None:
        if not self.services.is_ready:
            show_info("请先在「通用配置」中设置数据存储位置")
            self.show_page("settings")
            return
        self.pages["rooms"].set_project_filter(project_id)
        self.show_page("rooms")

    def uninstall_app(self) -> None:
        try:
            self.withdraw()
            self.update_idletasks()
            uninstall_portable_app()
        except Exception as exc:
            try:
                self.deiconify()
            except Exception:
                pass
            show_error(f"卸载失败：{exc}")


def run_app() -> None:
    app = TallyApp()
    app.mainloop()
