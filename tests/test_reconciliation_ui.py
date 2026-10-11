from dataclasses import replace
from datetime import date
from decimal import Decimal as D
from uuid import uuid4

from test_app import button
from test_ledger_ui import ledger_app

from stock_portfolio.ledger.models import EventKind as K
from stock_portfolio.ledger.models import LedgerEvent
from stock_portfolio.ledger.repository import LedgerRepository


def seeded(tmp_path, monkeypatch):
    with LedgerRepository(tmp_path / "portfolio.sqlite3") as repo:
        a = repo.create_account("Synthetic A")
        buy = LedgerEvent(
            str(uuid4()), a.id, date(2025, 1, 1), 1, K.BUY, "ABC", quantity=D(10), price=D(100)
        )
        repo.apply_operation((buy,), (), repo.load_dataset().revision, "Synthetic buy")
    return ledger_app(tmp_path, monkeypatch), a, buy


def test_statement_confirmation_comparison_stale_recalculate_and_drillthrough(
    tmp_path, monkeypatch
):
    at, a, buy = seeded(tmp_path, monkeypatch)
    at.radio(key="nav_page").set_value("Reconcile").run()
    at.file_uploader[0].upload(
        "statement.csv", b"ticker,quantity,cost_basis\nABC,10,1000\n", "text/csv"
    ).run()
    button(at, "Preview CSV import").click().run()
    assert button(at, "Confirm import").disabled
    at.checkbox(key="complete_statement").check().run()
    button(at, "Confirm import").click().run()
    button(at, "Compare and save evidence").click().run()
    assert not at.exception
    assert any("matched" in str(d.value) for d in at.dataframe)
    with LedgerRepository(tmp_path / "portfolio.sqlite3") as repo:
        repo.apply_operation(
            (replace(buy, price=D(110)),),
            (),
            repo.load_dataset().revision,
            "Synthetic corrected basis",
        )
    at.run()
    assert any("Stale" in w.value for w in at.warning)
    button(at, "Recalculate and save new evidence").click().run()
    assert not at.exception
    with LedgerRepository(tmp_path / "portfolio.sqlite3") as repo:
        assert len(repo.load_reconciliations(a.id)) == 2
    assert any("mismatch" in str(d.value) for d in at.dataframe)


def test_audit_backup_and_offline_recovery_commands(tmp_path, monkeypatch):
    at, _a, _buy = seeded(tmp_path, monkeypatch)
    at.radio(key="nav_page").set_value("Data & recovery").run()
    assert any(
        "Reason" in d.value.columns and "Synthetic buy" in d.value["Reason"].tolist()
        for d in at.dataframe
    )
    button(at, "Prepare consistent database backup").click().run()
    assert not at.exception
    download = next(d for d in at.get("download_button") if d.label == "Download database backup")
    assert not download.disabled
    assert any("--confirm-stopped" in c.value and str(tmp_path) in c.value for c in at.code)
    import sqlite3

    backup = tmp_path / "downloaded.db"
    backup.write_bytes(at.session_state["backup_bytes"])
    with sqlite3.connect(backup) as c:
        assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert c.execute("SELECT count(*) FROM ledger_event_identities").fetchone()[0] == 1
