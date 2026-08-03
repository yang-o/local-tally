from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from app.bootstrap import BootstrapConfig
from app.database import Database
from app.models import (
    AppSettings,
    FreePeriod,
    Lease,
    Payment,
    Project,
    ReminderItem,
    RentPeriod,
    Room,
)
from app.repositories import (
    LeaseRepository,
    PaymentRepository,
    ProjectRepository,
    RoomRepository,
    SettingsRepository,
)


class ValidationError(Exception):
    pass


def _add_months(d: date, months: int) -> date:
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, monthrange(year, month)[1])
    return date(year, month, day)


def _overlaps(a_start: date, a_end: date, b_start: date, b_end: date) -> bool:
    return a_start <= b_end and b_start <= a_end


def _fully_covers(outer_start: date, outer_end: date, inner_start: date, inner_end: date) -> bool:
    return outer_start <= inner_start and outer_end >= inner_end


def _merge_date_ranges(periods: list[tuple[date, date]]) -> list[tuple[date, date]]:
    if not periods:
        return []
    ordered = sorted(periods, key=lambda item: item[0])
    merged: list[tuple[date, date]] = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end + timedelta(days=1):
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _range_fully_covered(
    start: date, end: date, periods: list[tuple[date, date]]
) -> bool:
    if not periods or end < start:
        return False
    cursor = start
    for seg_start, seg_end in _merge_date_ranges(periods):
        if seg_end < cursor:
            continue
        if seg_start > cursor:
            return False
        if seg_end >= end:
            return True
        cursor = seg_end + timedelta(days=1)
    return cursor > end


def _range_any_overlap(
    start: date, end: date, periods: list[tuple[date, date]]
) -> bool:
    return any(_overlaps(start, end, p_start, p_end) for p_start, p_end in periods)


class SettingsService:
    def __init__(
        self, bootstrap: BootstrapConfig, db: Database | None = None
    ) -> None:
        self.bootstrap = bootstrap
        self.repo = SettingsRepository(db) if db is not None else None

    def attach_db(self, db: Database) -> None:
        self.repo = SettingsRepository(db)

    def is_ready(self) -> bool:
        return self.bootstrap.is_storage_configured() and self.repo is not None

    def get(self) -> AppSettings:
        storage = self.bootstrap.get_data_storage_path()
        remind = AppSettings()
        if self.repo is not None:
            remind = self.repo.get_settings()
        return AppSettings(
            app_name=self.bootstrap.app_name,
            data_storage_path=str(storage) if storage else "",
            storage_locked=self.bootstrap.is_storage_configured(),
            lease_expire_remind_days=remind.lease_expire_remind_days,
            rent_due_remind_days=remind.rent_due_remind_days,
        )

    def update(
        self,
        app_name: str,
        data_storage_path: str | None,
        lease_expire_remind_days: int | None = None,
        rent_due_remind_days: int | None = None,
    ) -> bool:
        """更新配置。返回是否新配置了数据存储位置。"""
        try:
            self.bootstrap.set_app_name(app_name)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        storage_just_set = False
        if self.bootstrap.is_portable():
            # 打包版存储路径由程序固定，忽略界面传入值
            pass
        elif not self.bootstrap.is_storage_configured():
            path = (data_storage_path or "").strip()
            if not path:
                raise ValidationError("请先配置数据存储位置")
            try:
                self.bootstrap.set_data_storage_path(path)
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc
            storage_just_set = True
        elif data_storage_path is not None:
            current = self.bootstrap.get_data_storage_path()
            incoming = str(Path(data_storage_path).expanduser().resolve())
            if current and incoming != str(current):
                raise ValidationError("数据存储位置已配置，不可修改")

        if self.repo is None:
            return storage_just_set

        if lease_expire_remind_days is None or rent_due_remind_days is None:
            raise ValidationError("请填写提醒天数")
        if lease_expire_remind_days < 0:
            raise ValidationError("合同到期提前提醒天数不能为负数")
        if rent_due_remind_days < 0:
            raise ValidationError("按月应收提前提醒天数不能为负数")
        self.repo.save_settings(
            AppSettings(
                lease_expire_remind_days=lease_expire_remind_days,
                rent_due_remind_days=rent_due_remind_days,
            )
        )
        return storage_just_set


class ProjectService:
    def __init__(self, db: Database) -> None:
        self.repo = ProjectRepository(db)

    def list_all(self) -> list[Project]:
        return self.repo.list_all()

    def get(self, project_id: int) -> Optional[Project]:
        return self.repo.get(project_id)

    def create(self, name: str) -> int:
        name = name.strip()
        if not name:
            raise ValidationError("项目名称不能为空")
        return self.repo.create(name)

    def update(self, project_id: int, name: str) -> None:
        name = name.strip()
        if not name:
            raise ValidationError("项目名称不能为空")
        self.repo.update(project_id, name)

    def delete(self, project_id: int) -> None:
        self.repo.delete(project_id)


class RoomService:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.repo = RoomRepository(db)
        self.lease_repo = LeaseRepository(db)
        self.settings_repo = SettingsRepository(db)

    def list_by_project(self, project_id: int) -> list[Room]:
        return self.repo.list_by_project(project_id)

    def list_all(self) -> list[Room]:
        return self.repo.list_all()

    def get(self, room_id: int) -> Optional[Room]:
        return self.repo.get(room_id)

    def create(self, project_id: int, room_no: str, area: float) -> int:
        room_no = room_no.strip()
        if not room_no:
            raise ValidationError("房间号不能为空")
        if area < 0:
            raise ValidationError("房间面积不能为负数")
        try:
            return self.repo.create(project_id, room_no, area)
        except Exception as exc:
            raise ValidationError(f"创建房间失败，可能房间号重复：{exc}") from exc

    def update(self, room_id: int, room_no: str, area: float) -> None:
        room_no = room_no.strip()
        if not room_no:
            raise ValidationError("房间号不能为空")
        if area < 0:
            raise ValidationError("房间面积不能为负数")
        try:
            self.repo.update(room_id, room_no, area)
        except Exception as exc:
            raise ValidationError(f"更新房间失败，可能房间号重复：{exc}") from exc

    def delete(self, room_id: int) -> None:
        self.repo.delete(room_id)

    def refresh_status(self, room_id: int, today: Optional[date] = None) -> None:
        today = today or date.today()
        leases = self.lease_repo.list_by_room(room_id)
        active = [l for l in leases if l.status == "生效"]
        if not active:
            self.repo.set_status(room_id, "空置")
            return

        # 取当前覆盖 today 的合同，否则取最近到期的生效合同
        current = next(
            (l for l in active if l.start_date <= today <= l.end_date),
            sorted(active, key=lambda l: l.end_date)[0],
        )
        expire_days = self.settings_repo.get_settings().lease_expire_remind_days
        days_left = (current.end_date - today).days
        if days_left < 0:
            self.repo.set_status(room_id, "已到期")
        elif days_left <= expire_days:
            self.repo.set_status(room_id, "即将到期")
        else:
            self.repo.set_status(room_id, "在租")


class LeaseService:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.repo = LeaseRepository(db)
        self.room_service = RoomService(db)

    def list_all(
        self,
        status: Optional[str] = None,
        project_id: Optional[int] = None,
    ) -> list[Lease]:
        return self.repo.list_all(status, project_id)

    def list_by_room(self, room_id: int) -> list[Lease]:
        return self.repo.list_by_room(room_id)

    def get(self, lease_id: int) -> Optional[Lease]:
        return self.repo.get(lease_id)

    def _normalize_free_periods(
        self,
        free_periods: list[tuple[date, date]] | list[FreePeriod],
        start_date: date,
        end_date: date,
    ) -> list[tuple[date, date]]:
        normalized: list[tuple[date, date]] = []
        for idx, item in enumerate(free_periods, start=1):
            if isinstance(item, FreePeriod):
                free_start, free_end = item.start_date, item.end_date
            else:
                free_start, free_end = item
            if free_end < free_start:
                raise ValidationError(f"第 {idx} 段免租期止不能早于免租期起")
            if free_start < start_date or free_end > end_date:
                raise ValidationError(f"第 {idx} 段免租期必须落在租赁期内")
            normalized.append((free_start, free_end))

        ordered = sorted(normalized, key=lambda item: item[0])
        for i in range(1, len(ordered)):
            prev_start, prev_end = ordered[i - 1]
            curr_start, curr_end = ordered[i]
            if _overlaps(prev_start, prev_end, curr_start, curr_end):
                raise ValidationError("免租期时段不能互相重叠")
        return ordered

    def _validate(
        self,
        room_id: int,
        deposit: float,
        monthly_rent: float,
        start_date: date,
        end_date: date,
        free_periods: list[tuple[date, date]] | list[FreePeriod],
        exclude_id: Optional[int] = None,
    ) -> list[tuple[date, date]]:
        if deposit < 0 or monthly_rent < 0:
            raise ValidationError("押金和月租金不能为负数")
        if end_date < start_date:
            raise ValidationError("到期时间不能早于起租时间")
        normalized = self._normalize_free_periods(free_periods, start_date, end_date)
        overlap = self.repo.find_overlap(room_id, start_date, end_date, exclude_id)
        if overlap:
            raise ValidationError(
                f"与已有生效合同时间重叠（{overlap.start_date} ~ {overlap.end_date}）"
            )
        return normalized

    def create(
        self,
        room_id: int,
        deposit: float,
        monthly_rent: float,
        start_date: date,
        end_date: date,
        free_periods: list[tuple[date, date]] | None = None,
    ) -> int:
        normalized = self._validate(
            room_id,
            deposit,
            monthly_rent,
            start_date,
            end_date,
            free_periods or [],
        )
        lease_id = self.repo.create(
            room_id, deposit, monthly_rent, start_date, end_date, normalized
        )
        self.room_service.refresh_status(room_id)
        return lease_id

    def update(
        self,
        lease_id: int,
        deposit: float,
        monthly_rent: float,
        start_date: date,
        end_date: date,
        free_periods: list[tuple[date, date]] | list[FreePeriod] | None,
        status: str,
    ) -> None:
        lease = self.repo.get(lease_id)
        if not lease:
            raise ValidationError("租赁不存在")
        if status not in {"生效", "结束"}:
            raise ValidationError("租赁状态无效")
        periods = free_periods if free_periods is not None else (lease.free_periods or [])
        if status == "生效":
            normalized = self._validate(
                lease.room_id,
                deposit,
                monthly_rent,
                start_date,
                end_date,
                periods,
                exclude_id=lease_id,
            )
        else:
            if end_date < start_date:
                raise ValidationError("到期时间不能早于起租时间")
            normalized = self._normalize_free_periods(periods, start_date, end_date)
        self.repo.update(
            lease_id,
            deposit,
            monthly_rent,
            start_date,
            end_date,
            normalized,
            status,
        )
        self.room_service.refresh_status(lease.room_id)

    def delete(self, lease_id: int) -> None:
        lease = self.repo.get(lease_id)
        if not lease:
            return
        self.repo.delete(lease_id)
        self.room_service.refresh_status(lease.room_id)


class PaymentService:
    def __init__(self, db: Database) -> None:
        self.repo = PaymentRepository(db)
        self.lease_repo = LeaseRepository(db)

    def list_all(self, project_id: Optional[int] = None) -> list[Payment]:
        return self.repo.list_all(project_id)

    def list_by_lease(self, lease_id: int) -> list[Payment]:
        return self.repo.list_by_lease(lease_id)

    def get(self, payment_id: int) -> Optional[Payment]:
        return self.repo.get(payment_id)

    def _validate(
        self,
        lease_id: int,
        period_start: date,
        period_end: date,
        amount: float,
    ) -> None:
        if amount <= 0:
            raise ValidationError("缴费金额必须大于 0")
        if period_end < period_start:
            raise ValidationError("缴费对应结束时间不能早于起始时间")
        lease = self.lease_repo.get(lease_id)
        if not lease:
            raise ValidationError("租赁不存在")
        if period_start < lease.start_date or period_end > lease.end_date:
            raise ValidationError("缴费周期必须落在租赁期内")

    def create(
        self,
        lease_id: int,
        period_start: date,
        period_end: date,
        amount: float,
        paid_at: date,
        note: str = "",
    ) -> int:
        self._validate(lease_id, period_start, period_end, amount)
        return self.repo.create(
            lease_id, period_start, period_end, amount, paid_at, note.strip()
        )

    def update(
        self,
        payment_id: int,
        period_start: date,
        period_end: date,
        amount: float,
        paid_at: date,
        note: str,
    ) -> None:
        payment = self.repo.get(payment_id)
        if not payment:
            raise ValidationError("缴费记录不存在")
        self._validate(payment.lease_id, period_start, period_end, amount)
        self.repo.update(
            payment_id, period_start, period_end, amount, paid_at, note.strip()
        )

    def delete(self, payment_id: int) -> None:
        self.repo.delete(payment_id)


class ReminderService:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.lease_repo = LeaseRepository(db)
        self.payment_repo = PaymentRepository(db)
        self.settings_repo = SettingsRepository(db)

    def generate_rent_periods(self, lease: Lease) -> list[RentPeriod]:
        periods: list[RentPeriod] = []
        cursor = lease.start_date
        index = 0
        while cursor <= lease.end_date:
            next_start = _add_months(lease.start_date, index + 1)
            period_end = min(next_start - timedelta(days=1), lease.end_date)
            if period_end < cursor:
                break

            free_ranges = [
                (p.start_date, p.end_date) for p in (lease.free_periods or [])
            ]
            fully_free = _range_fully_covered(cursor, period_end, free_ranges)
            partial_free = (not fully_free) and _range_any_overlap(
                cursor, period_end, free_ranges
            )

            amount = 0.0 if fully_free else float(lease.monthly_rent)
            periods.append(
                RentPeriod(
                    lease_id=lease.id,
                    period_start=cursor,
                    period_end=period_end,
                    amount=amount,
                    fully_free=fully_free,
                    partial_free=partial_free,
                )
            )
            index += 1
            cursor = next_start
        return periods

    def is_period_paid(self, lease_id: int, period: RentPeriod) -> bool:
        payments = self.payment_repo.list_by_lease(lease_id)
        for pay in payments:
            if (
                pay.period_start == period.period_start
                and pay.period_end == period.period_end
            ):
                return True
            if _fully_covers(
                pay.period_start, pay.period_end, period.period_start, period.period_end
            ):
                return True
        return False

    def unpaid_periods(self, lease: Lease, today: Optional[date] = None) -> list[RentPeriod]:
        today = today or date.today()
        result: list[RentPeriod] = []
        for period in self.generate_rent_periods(lease):
            if period.fully_free or period.amount <= 0:
                continue
            # 只关心已进入提醒窗口或已开始的周期（避免列出遥远未来）
            if period.period_start > today + timedelta(days=366):
                continue
            if not self.is_period_paid(lease.id, period):
                result.append(period)
        return result

    def list_reminders(self, today: Optional[date] = None) -> list[ReminderItem]:
        today = today or date.today()
        reminders: list[ReminderItem] = []
        leases = self.lease_repo.list_all(status="生效")
        settings = self.settings_repo.get_settings()
        expire_days = settings.lease_expire_remind_days
        rent_days = settings.rent_due_remind_days

        for lease in leases:
            project_name = lease.project_name

            # 合同到期提醒
            days_to_end = (lease.end_date - today).days
            if 0 <= days_to_end <= expire_days:
                reminders.append(
                    ReminderItem(
                        kind="合同即将到期",
                        project_id=lease.project_id,
                        project_name=project_name,
                        room_id=lease.room_id,
                        room_no=lease.room_no,
                        lease_id=lease.id,
                        period_start=lease.start_date,
                        period_end=lease.end_date,
                        amount=lease.monthly_rent,
                        days_delta=days_to_end,
                        detail=f"合同将于 {lease.end_date.isoformat()} 到期",
                    )
                )
            elif days_to_end < 0:
                reminders.append(
                    ReminderItem(
                        kind="合同已到期",
                        project_id=lease.project_id,
                        project_name=project_name,
                        room_id=lease.room_id,
                        room_no=lease.room_no,
                        lease_id=lease.id,
                        period_start=lease.start_date,
                        period_end=lease.end_date,
                        amount=lease.monthly_rent,
                        days_delta=days_to_end,
                        detail=f"合同已于 {lease.end_date.isoformat()} 到期",
                    )
                )

            # 按月应收提醒
            for period in self.unpaid_periods(lease, today):
                remind_from = period.period_start - timedelta(days=rent_days)
                if today < remind_from:
                    continue
                days_delta = (period.period_start - today).days
                if days_delta < 0:
                    kind = "已逾期"
                    detail = (
                        f"应收期 {period.period_start} ~ {period.period_end} "
                        f"已逾期 {abs(days_delta)} 天"
                    )
                else:
                    kind = "应收提醒"
                    detail = (
                        f"应收期 {period.period_start} ~ {period.period_end}"
                        + ("（含免租区间）" if period.partial_free else "")
                    )
                reminders.append(
                    ReminderItem(
                        kind=kind,
                        project_id=lease.project_id,
                        project_name=project_name,
                        room_id=lease.room_id,
                        room_no=lease.room_no,
                        lease_id=lease.id,
                        period_start=period.period_start,
                        period_end=period.period_end,
                        amount=period.amount,
                        days_delta=days_delta,
                        detail=detail,
                    )
                )

        kind_order = {"已逾期": 0, "应收提醒": 1, "合同已到期": 2, "合同即将到期": 3}
        reminders.sort(key=lambda r: (kind_order.get(r.kind, 9), r.days_delta, r.project_name))
        return reminders


class AppServices:
    def __init__(
        self, bootstrap: BootstrapConfig, db: Database | None = None
    ) -> None:
        self.bootstrap = bootstrap
        self.db = db
        self.settings = SettingsService(bootstrap, db)
        self.projects: ProjectService | None = None
        self.rooms: RoomService | None = None
        self.leases: LeaseService | None = None
        self.payments: PaymentService | None = None
        self.reminders: ReminderService | None = None
        if db is not None:
            self._init_domain_services(db)

    @property
    def is_ready(self) -> bool:
        return self.db is not None and self.bootstrap.is_storage_configured()

    def attach_database(self, db: Database) -> None:
        self.db = db
        self.settings.attach_db(db)
        self._init_domain_services(db)

    def _init_domain_services(self, db: Database) -> None:
        self.projects = ProjectService(db)
        self.rooms = RoomService(db)
        self.leases = LeaseService(db)
        self.payments = PaymentService(db)
        self.reminders = ReminderService(db)

    def require_ready(self) -> None:
        if not self.is_ready:
            raise ValidationError("请先在「通用配置」中设置数据存储位置")
