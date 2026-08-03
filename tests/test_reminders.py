from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from app.bootstrap import BootstrapConfig
from app.database import Database
from app.services import AppServices, ValidationError


class ReminderServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.bootstrap = BootstrapConfig(root / "bootstrap.json")
        self.bootstrap.set_app_name("测试应用")
        data_dir = root / "data"
        self.bootstrap.set_data_storage_path(data_dir)
        self.db = Database(self.bootstrap.get_db_path())  # type: ignore[arg-type]
        self.services = AppServices(self.bootstrap, self.db)
        self.services.settings.update(
            app_name="测试应用",
            data_storage_path=None,
            lease_expire_remind_days=7,
            rent_due_remind_days=7,
        )
        self.project_id = self.services.projects.create("测试项目")  # type: ignore[union-attr]
        self.room_id = self.services.rooms.create(self.project_id, "A101", 50)  # type: ignore[union-attr]
        self.lease_id = self.services.leases.create(  # type: ignore[union-attr]
            room_id=self.room_id,
            deposit=2000,
            monthly_rent=3000,
            start_date=date(2026, 1, 15),
            end_date=date(2026, 8, 14),
            free_periods=[
                (date(2026, 1, 15), date(2026, 2, 14)),
                (date(2026, 5, 15), date(2026, 6, 14)),
            ],
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_generate_periods_and_multiple_free_months(self) -> None:
        lease = self.services.leases.get(self.lease_id)  # type: ignore[union-attr]
        assert lease is not None
        self.assertEqual(len(lease.free_periods or []), 2)
        periods = self.services.reminders.generate_rent_periods(lease)  # type: ignore[union-attr]
        free_starts = {p.period_start for p in periods if p.fully_free}
        self.assertIn(date(2026, 1, 15), free_starts)
        self.assertIn(date(2026, 5, 15), free_starts)
        paid_like = next(p for p in periods if p.period_start == date(2026, 2, 15))
        self.assertFalse(paid_like.fully_free)
        self.assertEqual(paid_like.amount, 3000)

    def test_reject_overlapping_free_periods(self) -> None:
        with self.assertRaises(ValidationError):
            self.services.leases.create(  # type: ignore[union-attr]
                room_id=self.room_id,
                deposit=1000,
                monthly_rent=2000,
                start_date=date(2027, 1, 1),
                end_date=date(2027, 12, 31),
                free_periods=[
                    (date(2027, 1, 1), date(2027, 2, 28)),
                    (date(2027, 2, 15), date(2027, 3, 15)),
                ],
            )

    def test_payment_clears_reminder(self) -> None:
        lease = self.services.leases.get(self.lease_id)  # type: ignore[union-attr]
        assert lease is not None
        unpaid = self.services.reminders.unpaid_periods(lease, today=date(2026, 3, 1))  # type: ignore[union-attr]
        target = next(p for p in unpaid if p.period_start == date(2026, 2, 15))
        self.services.payments.create(  # type: ignore[union-attr]
            lease_id=self.lease_id,
            period_start=target.period_start,
            period_end=target.period_end,
            amount=target.amount,
            paid_at=date(2026, 2, 16),
        )
        unpaid_after = self.services.reminders.unpaid_periods(  # type: ignore[union-attr]
            lease, today=date(2026, 3, 1)
        )
        self.assertFalse(
            any(p.period_start == date(2026, 2, 15) for p in unpaid_after)
        )

    def test_due_reminder_appears(self) -> None:
        reminders = self.services.reminders.list_reminders(today=date(2026, 2, 10))  # type: ignore[union-attr]
        kinds = {r.kind for r in reminders}
        self.assertIn("应收提醒", kinds)


class BootstrapConfigTests(unittest.TestCase):
    def test_storage_locked_after_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = BootstrapConfig(root / "bootstrap.json")
            self.assertFalse(cfg.is_storage_configured())
            cfg.set_data_storage_path(root / "data")
            self.assertTrue(cfg.is_storage_configured())
            with self.assertRaises(ValueError):
                cfg.set_data_storage_path(root / "other")

    def test_frozen_data_dir_platform_default(self) -> None:
        import sys

        from app.config import (
            get_frozen_data_dir,
            get_install_dir,
            get_platform_app_support_dir,
        )

        if sys.platform == "darwin":
            self.assertEqual(
                get_frozen_data_dir(),
                get_platform_app_support_dir() / "Tally" / "data",
            )
        else:
            self.assertEqual(get_frozen_data_dir(), get_install_dir() / "data")


if __name__ == "__main__":
    unittest.main()
