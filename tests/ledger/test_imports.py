from datetime import date

import pytest

from stock_portfolio.ledger.csv_io import ImportKind as I
from stock_portfolio.ledger.csv_io import parse_import
from stock_portfolio.ledger.engine import replay
from stock_portfolio.ledger.imports import ImportChoice, commit_import, prepare_import
from stock_portfolio.ledger.models import InvalidLedger
from stock_portfolio.ledger.repository import LedgerRepository, StaleRevision

SIMPLE = b"ticker,date,transaction_type,quantity,price\nNA,2025-01-01,BUY,10,100\n"


def preview(repo, account, content=SIMPLE, choices=()):
    return prepare_import(repo, parse_import(content, I.transactions), account, choices=choices)


def test_public_sample_preview_no_write_confirm_once_and_hash_noop(tmp_path):
    with LedgerRepository(tmp_path / "demo.db") as repo:
        a = repo.create_account("A")
        p = preview(repo, a.id)
        assert not p.issues and repo.load_dataset().events == ()
        assert p.proposed_events[0].fees == 0
        batch = commit_import(repo, p)
        repeated = preview(repo, a.id)
        assert repeated.no_op_batch_id == batch
        assert commit_import(repo, repeated) == batch
        assert len(repo.load_dataset().events) == 1


def test_identical_occurrences_and_overlap_require_decisions(tmp_path):
    with LedgerRepository(tmp_path / "demo.db") as repo:
        a = repo.create_account("A")
        data = SIMPLE + b"NA,2025-01-01,BUY,10,100\n"
        p = preview(repo, a.id, data)
        assert set(p.duplicate_rows) == {2, 3}
        with pytest.raises(InvalidLedger):
            commit_import(repo, p)
        p = preview(repo, a.id, data, (ImportChoice(2, "keep"), ImportChoice(3, "keep")))
        commit_import(repo, p)
        assert replay(repo.load_dataset(), date(2025, 1, 1)).positions[0].quantity == 20
        overlap = preview(repo, a.id, SIMPLE)
        assert 2 in overlap.duplicate_rows
        commit_import(repo, preview(repo, a.id, SIMPLE, (ImportChoice(2, "skip"),)))
        assert len(repo.load_dataset().events) == 2


def test_external_identity_dedup_preserves_sequence_and_conflicts(tmp_path):
    with LedgerRepository(tmp_path / "demo.db") as repo:
        a = repo.create_account("A")
        data = b"ticker,date,transaction_type,quantity,price,transaction_id\nABC,2025-01-01,BUY,1,2,id-1\n"
        commit_import(repo, preview(repo, a.id, data))
        same = preview(repo, a.id, data + b"\n")
        assert not same.issues and same.proposed_events == ()
        changed = preview(repo, a.id, data.replace(b",1,2,id-1", b",1,3,id-1"))
        assert any(i.code == "identity_conflict" for i in changed.issues)
        e = repo.load_dataset().events[0]
        repo.apply_operation((), (e.id,), repo.load_dataset().revision, "Void synthetic")
        assert preview(repo, a.id, data + b"\n").issues


@pytest.mark.parametrize(
    "row",
    [
        "ABC,2025-1-1,BUY,1,2",
        "ABC,2099-01-01,BUY,1,2",
        "ABC,2025-01-01,OPTION,1,2",
        "ABC,2025-01-01,BUY,1e2,2",
        "ABC,2025-01-01,BUY,1.000000001,2",
        "ABC,2025-01-01,DIVIDEND,1,2",
        "ABC,2025-01-01,SELL,1,2",
    ],
)
def test_invalid_batch_never_writes(tmp_path, row):
    with LedgerRepository(tmp_path / "demo.db") as repo:
        a = repo.create_account("A")
        p = preview(
            repo, a.id, ("ticker,date,transaction_type,quantity,price\n" + row + "\n").encode()
        )
        assert p.issues and p.issues[0].row == 2
        with pytest.raises(InvalidLedger):
            commit_import(repo, p)
        assert repo.load_dataset().events == ()


def test_stale_preview_and_explicit_order_collision(tmp_path):
    with LedgerRepository(tmp_path / "demo.db") as repo:
        a = repo.create_account("A")
        p = preview(repo, a.id)
        repo.create_account("metadata changes revision")
        with pytest.raises(StaleRevision):
            commit_import(repo, p)
        assert repo.load_dataset().events == ()
        bad = b"ticker,date,transaction_type,quantity,price,sequence\nA,2025-01-01,BUY,1,2,1\nB,2025-01-01,BUY,1,2,1\n"
        assert preview(repo, a.id, bad).issues


def test_import_record_failure_rolls_back_economics_and_audit(tmp_path):
    import sqlite3

    with LedgerRepository(tmp_path / "demo.db") as repo:
        a = repo.create_account("A")
        p = preview(repo, a.id)
        before = repo.load_dataset()
        audits = repo.connection.execute("SELECT count(*) FROM audit_operations").fetchone()[0]
        repo.connection.execute(
            "CREATE TRIGGER fail_batch BEFORE INSERT ON import_rows BEGIN SELECT RAISE(ABORT,'injected'); END"
        )
        with pytest.raises(sqlite3.IntegrityError):
            commit_import(repo, p)
        assert repo.load_dataset() == before
        assert repo.connection.execute("SELECT count(*) FROM import_batches").fetchone()[0] == 0
        assert (
            repo.connection.execute("SELECT count(*) FROM audit_operations").fetchone()[0] == audits
        )


def test_allocation_csv_replaces_entire_allocation(tmp_path):
    with LedgerRepository(tmp_path / "demo.db") as repo:
        a = repo.create_account("A")
        raw = b"ticker,date,transaction_type,quantity,price,transaction_id\nABC,2025-01-01,BUY,10,100,b\nABC,2025-01-02,SELL,4,150,s\n"
        commit_import(repo, preview(repo, a.id, raw))
        buy = next(e for e in repo.load_dataset().events if e.external_id == "b")
        content = f"transaction_id,lot_id,quantity\ns,{buy.id},4\n".encode()
        p = prepare_import(repo, parse_import(content, I.allocations), a.id)
        assert not p.issues
        commit_import(repo, p)
        assert replay(repo.load_dataset(), date(2025, 1, 2)).disposals[0].method == "Explicit"


def test_future_validation_with_explicit_today():
    from conftest import dataset, event

    from stock_portfolio.ledger.validation import validate_events

    assert validate_events(
        dataset(event("future", day=2, quantity="1", price="2")), today=date(2025, 1, 1)
    )


def test_numeric_scale_does_not_bypass_duplicate_occurrence_review(tmp_path):
    with LedgerRepository(tmp_path / "scale.db") as repo:
        a = repo.create_account("A")
        header = b"ticker,date,transaction_type,quantity,price,fees\n"
        first = b"ABC,2025-01-01,BUY,1,100,0\n"
        same = b"ABC,2025-01-01,BUY,1.0,100.00,0.000\n"
        batch = preview(repo, a.id, header + first + same)
        assert set(batch.duplicate_rows) == {2, 3}
        commit_import(repo, preview(repo, a.id, header + first))
        overlap = preview(repo, a.id, header + same)
        assert set(overlap.duplicate_rows) == {2}
        with pytest.raises(InvalidLedger):
            commit_import(repo, overlap)
        assert replay(repo.load_dataset(), date(2025, 1, 1)).positions[0].quantity == 1
