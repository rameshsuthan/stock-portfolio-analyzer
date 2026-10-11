from datetime import date

from test_app import app, button

from stock_portfolio.ledger.repository import LedgerRepository


def select(at, label):
    return next(s for s in at.selectbox if s.label == label)


def text(at, label):
    return next(s for s in at.text_input if s.label == label)


def ledger_app(tmp_path, monkeypatch):
    at = app(tmp_path, monkeypatch)
    select(at, "Mode").set_value("Transaction accounts").run()
    return at


def create(at, name="Synthetic A"):
    text(at, "New account name").input(name).run()
    button(at, "Create account").click().run()
    return at


def test_onboarding_trade_preview_confirm_and_dirty_navigation(tmp_path, monkeypatch):
    at = create(ledger_app(tmp_path, monkeypatch))
    assert not at.exception
    at.radio(key="nav_page").set_value("Transactions").run()
    text(at, "Symbol").input("ABC").run()
    text(at, "Quantity").input("10").run()
    text(at, "Trade price").input("100").run()
    at.radio(key="nav_page").set_value("Overview").run()
    assert at.session_state["context"][2] == "Transactions"
    button(at, "Keep editing").click().run()
    assert text(at, "Quantity").value == "10"
    button(at, "Preview operation").click().run()
    with LedgerRepository(tmp_path / "portfolio.sqlite3") as repo:
        assert repo.load_dataset().events == ()
    button(at, "Confirm operation").click().run()
    assert not at.exception
    with LedgerRepository(tmp_path / "portfolio.sqlite3") as repo:
        assert len(repo.load_dataset().events) == 1
    at.radio(key="nav_page").set_value("Overview").run()
    assert any("Known value subtotal" == m.label for m in at.metric)
    assert any("Unknown" == m.value for m in at.metric)


def test_upload_does_not_write_preview_confirm_receipt(tmp_path, monkeypatch):
    at = create(ledger_app(tmp_path, monkeypatch))
    at.radio(key="nav_page").set_value("Transactions").run()
    at.file_uploader[0].upload(
        "synthetic.csv",
        b"ticker,date,transaction_type,quantity,price,transaction_id\nABC,2025-01-01,BUY,10,100,b1\n",
        "text/csv",
    ).run()
    with LedgerRepository(tmp_path / "portfolio.sqlite3") as repo:
        assert repo.load_dataset().events == ()
    button(at, "Preview CSV import").click().run()
    assert not at.exception
    button(at, "Confirm import").click().run()
    assert any("Import committed" in m.value for m in at.success)
    with LedgerRepository(tmp_path / "portfolio.sqlite3") as repo:
        assert len(repo.load_dataset().events) == 1


def test_snapshot_conversion_preview_is_atomic_and_preserves_source(tmp_path):
    from decimal import Decimal as D

    from stock_portfolio.models import Holding
    from stock_portfolio.storage import Repository

    with Repository(tmp_path / "demo.db") as snapshots:
        pid = snapshots.create_portfolio("Synthetic original")
        snapshot = snapshots.save_snapshot(
            pid, date(2025, 1, 1), (Holding("ABC", D(10), D(1000), D(120)),)
        )
        with LedgerRepository(tmp_path / "demo.db") as repo:
            a = repo.start_from_snapshot(
                snapshot, "Opening account", repo.load_dataset().revision, True
            )
            ds = repo.load_dataset()
            assert a.opening_date == snapshot.metadata.snapshot_date
            assert ds.events[0].kind.value == "OPENING_BALANCE"
            assert ds.events[0].acquired_date is None and ds.events[0].basis == 1000
            assert repo.load_prices()[0].price == 120
            assert snapshots.load_snapshot(snapshot.id) == snapshot


def test_pool_basis_resolution_and_cancelled_revision(tmp_path, monkeypatch):
    from decimal import Decimal as D
    from uuid import uuid4

    from stock_portfolio.ledger.models import EventKind as K
    from stock_portfolio.ledger.models import LedgerEvent

    with LedgerRepository(tmp_path / "portfolio.sqlite3") as repo:
        a = repo.create_account("Opening", date(2025, 1, 1))
        pool = LedgerEvent(
            str(uuid4()),
            a.id,
            date(2025, 1, 1),
            1,
            K.OPENING_BALANCE,
            "ABC",
            quantity=D(10),
            basis=D(1000),
        )
        sale = LedgerEvent(
            str(uuid4()), a.id, date(2025, 1, 2), 1, K.SELL, "ABC", quantity=D(4), price=D(150)
        )
        repo.apply_operation((pool, sale), (), repo.load_dataset().revision, "Synthetic")
    at = ledger_app(tmp_path, monkeypatch)
    at.radio(key="nav_page").set_value("Lots & realized gains").run()
    text(at, f"Quantity from {pool.id[:8]}").input("4").run()
    text(at, f"User supplied pool basis for {pool.id[:8]}").input("400").run()
    text(at, "Allocation reason / source").input("Synthetic statement detail").run()
    button(at, "Preview allocation").click().run()
    button(at, "Confirm allocation").click().run()
    assert not at.exception
    with LedgerRepository(tmp_path / "portfolio.sqlite3") as repo:
        from stock_portfolio.ledger.engine import replay

        assert replay(repo.load_dataset(), date.today()).disposals[0].gain == 200
    at.radio(key="nav_page").set_value("Transactions").run()
    select(at, "Event action").set_value("Revise").run()
    select(at, "Event to change").set_value(sale.id).run()
    text(at, "Trade price").input("160").run()
    text(at, "Reason / source").input("Review change").run()
    button(at, "Preview operation").click().run()
    button(at, "Cancel operation").click().run()
    with LedgerRepository(tmp_path / "portfolio.sqlite3") as repo:
        assert next(e for e in repo.load_dataset().events if e.id == sale.id).price == 150


def test_opening_replacement_preview_preserves_totals(tmp_path):
    from decimal import Decimal as D
    from uuid import uuid4

    from stock_portfolio.ledger.csv_io import ImportKind as I
    from stock_portfolio.ledger.csv_io import parse_import
    from stock_portfolio.ledger.imports import commit_import, prepare_import
    from stock_portfolio.ledger.models import EventKind as K
    from stock_portfolio.ledger.models import LedgerEvent

    with LedgerRepository(tmp_path / "demo.db") as repo:
        a = repo.create_account("A", date(2025, 1, 1))
        pool = LedgerEvent(
            str(uuid4()),
            a.id,
            date(2025, 1, 1),
            1,
            K.OPENING_BALANCE,
            "ABC",
            quantity=D(10),
            basis=D(1000),
        )
        repo.apply_operation((pool,), (), repo.load_dataset().revision, "Synthetic")
        parsed = parse_import(
            b"lot_id,ticker,acquired_date,quantity,cost_basis\nactual,ABC,2020-01-01,10,1000\n",
            I.opening_lots,
        )
        p = prepare_import(repo, parsed, a.id, a.opening_date, replace_openings=True)
        assert not p.issues and p.void_ids == (pool.id,)
        commit_import(repo, p)
        assert all(e.kind == K.OPENING_LOT for e in repo.load_dataset().events)


def test_duplicate_decisions_survive_reruns(tmp_path, monkeypatch):
    at = create(ledger_app(tmp_path, monkeypatch))
    at.radio(key="nav_page").set_value("Transactions").run()
    at.file_uploader[0].upload(
        "same.csv",
        b"ticker,date,transaction_type,quantity,price\nNA,2025-01-01,BUY,1,1\nNA,2025-01-01,BUY,1,1\n",
        "text/csv",
    ).run()
    button(at, "Preview CSV import").click().run()
    select(at, "Row 2: 2 matching occurrences").set_value("keep").run()
    at.run()
    assert select(at, "Row 2: 2 matching occurrences").value == "keep"
    select(at, "Row 3: 2 matching occurrences").set_value("keep").run()
    button(at, "Update duplicate decisions").click().run()
    assert not button(at, "Confirm import").disabled
    button(at, "Confirm import").click().run()
    with LedgerRepository(tmp_path / "portfolio.sqlite3") as repo:
        assert len(repo.load_dataset().events) == 2


def test_two_pending_operation_previews_have_distinct_controls(tmp_path, monkeypatch):
    from decimal import Decimal as D
    from uuid import uuid4

    from stock_portfolio.ledger.models import EventKind as K
    from stock_portfolio.ledger.models import LedgerEvent

    with LedgerRepository(tmp_path / "portfolio.sqlite3") as repo:
        a = repo.create_account("A")
        buy = LedgerEvent(
            str(uuid4()), a.id, date(2025, 1, 1), 1, K.BUY, "ABC", quantity=D(10), price=D(100)
        )
        sale = LedgerEvent(
            str(uuid4()), a.id, date(2025, 1, 2), 1, K.SELL, "ABC", quantity=D(1), price=D(150)
        )
        repo.apply_operation((buy, sale), (), repo.load_dataset().revision, "Synthetic setup")
    at = ledger_app(tmp_path, monkeypatch)
    at.radio(key="nav_page").set_value("Transactions").run()
    for label, value in [("Symbol", "ABC"), ("Quantity", "1"), ("Trade price", "100")]:
        text(at, label).input(value).run()
    button(at, "Preview operation").click().run()
    for label, value in [
        ("Reinvestment symbol", "ABC"),
        ("Cash dividend received", "50"),
        ("Reinvested quantity", ".4"),
        ("Reinvestment price", "120"),
    ]:
        text(at, label).input(value).run()
    button(at, "Preview reinvestment").click().run()
    assert not at.exception
    assert button(at, "Confirm operation") and button(at, "Confirm reinvestment")
