import sqlite3
from datetime import date
from pathlib import Path

import pytest

from stock_portfolio.csv_io import parse_csv
from stock_portfolio.models import Metadata, Selection
from stock_portfolio.storage import ReplacementRequired, Repository
from stock_portfolio.workflow import DiscardRequired, Draft

META = Metadata("Demo", date(2026, 10, 10))
ROWS = parse_csv(Path("samples/demo.csv").read_bytes()).rows


def test_load_edit_discard_and_filter_reset():
    d = Draft()
    d.load(ROWS, META)
    assert d.dirty and d.validation.valid
    d.selection = Selection(frozenset({"DEMO_A"}))
    with pytest.raises(DiscardRequired):
        d.load([], META)
    assert len(d.rows) == 2
    d.load([], META, discard=True)
    assert d.selection == Selection() and not d.validation.valid


def test_save_full_draft_replacement_and_clean_state(tmp_path):
    with Repository(tmp_path / "test.db") as repo:
        d = Draft()
        d.load(ROWS, META)
        d.selection = Selection(frozenset({"DEMO_A"}))
        saved = d.save(repo)
        assert len(saved.holdings) == 2 and not d.dirty
        changed = [dict(r) for r in d.rows]
        changed[0]["quantity"] = "11"
        d.update(changed, META)
        assert d.dirty
        with pytest.raises(ReplacementRequired):
            d.save(repo)
        assert d.dirty and repo.load_snapshot(saved.id).holdings[0].quantity == 10
        d.save(repo, replace=True)
        assert not d.dirty and repo.load_snapshot(saved.id).holdings[0].quantity == 11


def test_invalid_draft_and_save_failure_preserve_state(tmp_path):
    with Repository(tmp_path / "test.db") as repo:
        d = Draft()
        d.load(ROWS, META)
        bad = [dict(r) for r in ROWS]
        bad[0]["quantity"] = "bad"
        d.update(bad, META)
        with pytest.raises(ValueError):
            d.save(repo)
        with pytest.raises(ValueError):
            d.snapshot()
        assert d.rows == bad and repo.list_portfolios() == []
        d.update(ROWS, META)
        repo.connection.close()
        with pytest.raises(sqlite3.ProgrammingError):
            d.save(repo)
        assert d.rows == ROWS and d.dirty


def test_saved_load_rerun_and_metadata_changes(tmp_path):
    with Repository(tmp_path / "test.db") as repo:
        d = Draft()
        d.load(ROWS, META)
        saved = d.save(repo)
        other = Draft()
        other.load_saved(saved)
        other.update(other.rows, META)
        assert not other.dirty
        other.update(other.rows, Metadata("Other", META.snapshot_date))
        assert other.dirty


def test_metadata_required():
    d = Draft()
    d.load(ROWS, Metadata(" ", META.snapshot_date))
    with pytest.raises(ValueError):
        d.snapshot()


def test_filtered_analysis_report_and_full_snapshot_agree():
    import csv
    import io

    from stock_portfolio.calculations import analyze
    from stock_portfolio.csv_io import export_analysis, export_snapshot

    d = Draft()
    d.load(ROWS, META)
    d.selection = Selection(frozenset({"DEMO_A"}))
    s = d.snapshot()
    a = analyze(s.holdings, d.selection)
    report = list(csv.DictReader(io.StringIO(export_analysis(a, META).decode())))
    assert len(report) == 1 and report[0]["market_value"] == "1200"
    assert report[0]["allocation_percent"] == "100"
    assert len(parse_csv(export_snapshot(s)).rows) == 2
