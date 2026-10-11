import sqlite3
from dataclasses import replace
from decimal import Decimal as D

import pytest
from conftest import event

from stock_portfolio.ledger.codec import dumps, event_from_json
from stock_portfolio.ledger.repository import IdentityConflict, LedgerRepository, StaleRevision


def apply(repo, *events, void=(), reason="Synthetic change"):
    return repo.apply_operation(events, void, repo.load_dataset().revision, reason)


def test_roundtrip_restart_and_exact_canonical_values(tmp_path):
    path = tmp_path / "demo.db"
    with LedgerRepository(path) as repo:
        account = repo.create_account(" Demo ")
        buy = event(
            "buy", account=account.id, quantity=".12345678", price="1.23000000", external_id="X"
        )
        assert event_from_json(dumps(buy)) == buy
        apply(repo, buy)
        before = repo.load_dataset()
    with LedgerRepository(path) as repo:
        assert repo.load_dataset() == before
        history = repo.history(buy.id)
        assert history[0]["reason"] == "Synthetic change"
        assert history[0]["version"] == 1 and history[0]["recorded_at"].endswith("+00:00")
        assert "1.23000000" in history[0]["payload"]
    with pytest.raises(ValueError):
        dumps({"number": D("NaN")})
    with pytest.raises(ValueError):
        dumps({"number": float("nan")})


def test_account_casefold_archive_and_stale_revision(tmp_path):
    with LedgerRepository(tmp_path / "demo.db") as repo:
        account = repo.create_account(" Straße ")
        with pytest.raises(ValueError):
            repo.create_account("STRASSE")
        buy = event("buy", account=account.id, quantity="1", price="1")
        revision = repo.load_dataset().revision
        repo.archive_account(account.id)
        assert repo.load_dataset().economic_revision == 0
        with pytest.raises(StaleRevision):
            repo.apply_operation((buy,), (), revision, "Add")
        with pytest.raises(ValueError):
            apply(repo, buy)


def test_identity_void_revival_and_required_reason(tmp_path):
    with LedgerRepository(tmp_path / "demo.db") as repo:
        a, b = repo.create_account("A"), repo.create_account("B")
        buy = event("buy", account=a.id, quantity="1", price="1", external_id="id")
        apply(repo, buy)
        for bad in (
            replace(buy, account_id=b.id),
            replace(buy, external_id="other"),
            replace(buy, id=event("different").id),
        ):
            with pytest.raises(IdentityConflict):
                apply(repo, bad)
        with pytest.raises(ValueError):
            apply(repo, replace(buy, price=D(2)), reason=" ")
        apply(repo, void=(buy.id,))
        assert repo.load_dataset().events == ()
        apply(repo, buy)
        assert [h["status"] for h in repo.history(buy.id)] == ["active", "void", "active"]


def test_sql_trigger_failure_rolls_back_every_write(tmp_path):
    with LedgerRepository(tmp_path / "demo.db") as repo:
        a, b = repo.create_account("A"), repo.create_account("B")
        before = repo.load_dataset()
        audits = repo.connection.execute("SELECT count(*) FROM audit_operations").fetchone()[0]
        repo.connection.execute(
            "CREATE TRIGGER injected BEFORE INSERT ON ledger_event_revisions WHEN NEW.effective_date='2025-01-02' BEGIN SELECT RAISE(ABORT,'injected'); END"
        )
        with pytest.raises(sqlite3.IntegrityError):
            apply(
                repo,
                event("one", account=a.id, quantity="1", price="1"),
                event("two", day=2, account=b.id, quantity="1", price="1"),
            )
        assert repo.load_dataset() == before
        assert (
            repo.connection.execute("SELECT count(*) FROM audit_operations").fetchone()[0] == audits
        )
        assert (
            repo.connection.execute("SELECT count(*) FROM ledger_event_identities").fetchone()[0]
            == 0
        )


def test_snapshot_mutations_invalidate_conversion_preview(tmp_path):
    from datetime import date
    from decimal import Decimal as D

    from stock_portfolio.ledger.repository import StaleRevision
    from stock_portfolio.models import Holding
    from stock_portfolio.storage import Repository

    for mutation in ("replace", "delete_snapshot", "delete_portfolio"):
        path = tmp_path / (mutation + ".db")
        with Repository(path) as snapshots, LedgerRepository(path) as repo:
            pid = snapshots.create_portfolio("Synthetic")
            original = snapshots.save_snapshot(
                pid, date(2025, 1, 1), (Holding("ABC", D(10), D(1000), D(120)),)
            )
            revision = repo.load_dataset().revision
            economic = repo.load_dataset().economic_revision
            if mutation == "replace":
                snapshots.save_snapshot(
                    pid, date(2025, 1, 1), (Holding("ABC", D(20), D(2000), D(120)),), replace=True
                )
            elif mutation == "delete_snapshot":
                snapshots.delete_snapshot(original.id)
            else:
                snapshots.delete_portfolio(pid)
            with pytest.raises(StaleRevision):
                repo.start_from_snapshot(original, "Stale conversion", revision)
            assert repo.load_dataset().accounts == ()
            assert repo.load_dataset().economic_revision == economic


def test_snapshot_conversion_revalidates_source_contents_with_current_revision(tmp_path):
    from dataclasses import replace
    from datetime import date
    from decimal import Decimal as D

    from stock_portfolio.ledger.repository import StaleRevision
    from stock_portfolio.models import Holding
    from stock_portfolio.storage import Repository

    path = tmp_path / "source.db"
    with Repository(path) as snapshots, LedgerRepository(path) as repo:
        pid = snapshots.create_portfolio("Synthetic")
        saved = snapshots.save_snapshot(
            pid, date(2025, 1, 1), (Holding("ABC", D(10), D(1000), D(120)),)
        )
        changed = replace(saved, holdings=(Holding("ABC", D(20), D(2000), D(120)),))
        with pytest.raises(StaleRevision):
            repo.start_from_snapshot(changed, "Mismatch", repo.load_dataset().revision)
        assert repo.load_dataset().accounts == ()
