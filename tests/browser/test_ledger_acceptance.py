"""Explicit real-browser acceptance; ephemeral server, data directory and browser profile."""

import csv
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

pytestmark = pytest.mark.browser
ROOT = Path(__file__).resolve().parents[2]


class Server:
    def __init__(self, directory):
        self.directory = directory
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        self.url = f"http://127.0.0.1:{self.port}"
        self.process = None

    def start(self):
        self.log = open(self.directory / "server.log", "a")  # noqa: SIM115 — closed by stop, across restart
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(ROOT / "app.py"),
                "--server.port",
                str(self.port),
                "--server.address",
                "127.0.0.1",
                "--server.headless",
                "true",
                "--browser.gatherUsageStats",
                "false",
            ],
            cwd=ROOT,
            env={**os.environ, "PORTFOLIO_DATA_DIR": str(self.directory / "synthetic-data")},
            stdout=self.log,
            stderr=subprocess.STDOUT,
        )
        for _ in range(200):
            if self.process.poll() is not None:
                raise RuntimeError("Synthetic server exited; inspect server.log")
            try:
                with urllib.request.urlopen(self.url + "/_stcore/health", timeout=1) as response:
                    if response.status == 200:
                        return
            except OSError:
                time.sleep(0.1)
        raise RuntimeError("Synthetic server did not become healthy.")

    def stop(self):
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=15)
            self.log.close()
            self.process = None


def settle(page):
    page.wait_for_timeout(700)  # Allow the input's WebSocket rerun request to reach the server.
    expect(page.get_by_test_id("stApp")).to_have_attribute(
        "data-test-script-state", "notRunning", timeout=30000
    )
    expect(page.get_by_test_id("stException")).to_have_count(0)


def choose(page, label, value):
    group = page.get_by_test_id("stSelectbox").filter(has=page.get_by_text(label, exact=True))
    combo = group.get_by_role("combobox")
    if combo.input_value() == value:
        return
    group.scroll_into_view_if_needed()
    page.wait_for_timeout(500)  # Finish scroll before opening; scrolling dismisses the menu.
    group.get_by_role("button").click()
    expect(combo).to_have_attribute("aria-expanded", "true")
    # Event lists are virtualized; search exposes targets outside the rendered window.
    combo.fill(value)
    page.get_by_role("option", name=value, exact=True).click()
    settle(page)
    expect(combo).to_have_value(value)


def fill(page, label, value):
    page.get_by_role("textbox", name=label, exact=True).fill(value)
    page.get_by_role("textbox", name=label, exact=True).press("Tab")
    settle(page)


def click(page, label):
    page.get_by_role("button", name=label, exact=True).click()
    settle(page)


def navigate(page, label):
    page.get_by_test_id("stSidebar").get_by_text(label, exact=True).click()
    settle(page)


def expand(page, label):
    summary = page.locator("summary").filter(has_text=label)
    if (
        summary.get_attribute("aria-expanded") != "true"
        and summary.locator("..").get_attribute("open") is None
    ):
        summary.click()
    settle(page)


def set_checkbox(page, label, checked):
    if page.get_by_role("checkbox", name=label, exact=True).is_checked() != checked:
        page.get_by_text(label, exact=True).click()
        settle(page)


def upload(page, file):
    page.locator("input[type=file]").set_input_files(file)
    settle(page)


def download(page, label, path):
    with page.expect_download() as pending:
        page.get_by_role("button", name=label, exact=True).click()
    pending.value.save_as(path)


def create_account(page, name, opening=False):
    expand(page, "Create transaction account")
    fill(page, "New account name", name)
    if os.environ.get("PORTFOLIO_BROWSER_EVIDENCE"):
        page.screenshot(
            path=str(Path(os.environ["PORTFOLIO_BROWSER_EVIDENCE"]) / "account-debug.png")
        )
    if opening:
        choose(page, "Starting records", "Opening balance / lots")
        fill(page, "Opening cutoff (end of day)", "2025-01-01")
    else:
        choose(page, "Starting records", "Full history")
    click(page, "Create account")


def test_ledger_acceptance(tmp_path):
    evidence = Path(os.environ.get("PORTFOLIO_BROWSER_EVIDENCE", tmp_path / "evidence"))
    evidence.mkdir(parents=True, exist_ok=True)
    server = Server(tmp_path)
    server.start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                channel=os.environ.get("PORTFOLIO_BROWSER_CHANNEL", "msedge"), headless=True
            )
            context = browser.new_context(
                viewport={"width": 1440, "height": 900}, accept_downloads=True
            )
            page = context.new_page()
            page.goto(server.url)
            settle(page)
            page.screenshot(path=str(evidence / "startup.png"))
            choose(page, "Mode", "Transaction accounts")
            fill(page, "New account name", "Synthetic A")
            click(page, "Create account")
            expect(page.get_by_text("Account overview", exact=True)).to_be_visible()
            create_account(page, "Synthetic B")
            choose(page, "Account", "Synthetic A")
            navigate(page, "Transactions")
            set_checkbox(page, "Multiple accounts (exact account_name on every row)", True)
            upload(page, ROOT / "samples/ledger/linked_accounts.csv")
            click(page, "Preview CSV import")
            click(page, "Confirm import")
            click(page, "Preview CSV import")
            expect(page.get_by_text("Previously imported file.", exact=False)).to_be_visible()
            click(page, "Confirm import")
            # Two legitimate identical trades: explicit occurrence decisions.
            set_checkbox(page, "Multiple accounts (exact account_name on every row)", False)
            upload(
                page,
                {
                    "name": "identical.csv",
                    "mimeType": "text/csv",
                    "buffer": b"ticker,date,transaction_type,quantity,price\nNA,2025-01-01,BUY,1,1\nNA,2025-01-01,BUY,1,1\n",
                },
            )
            click(page, "Preview CSV import")
            expect(page.get_by_role("button", name="Confirm import", exact=True)).to_be_disabled()
            choose(page, "Row 2: 2 matching occurrences", "keep")
            choose(page, "Row 3: 2 matching occurrences", "keep")
            click(page, "Update duplicate decisions")
            choose(page, "Row 3: 2 matching occurrences", "skip")
            expect(page.get_by_role("button", name="Confirm import", exact=True)).to_be_disabled()
            choose(page, "Row 3: 2 matching occurrences", "keep")
            click(page, "Update duplicate decisions")
            click(page, "Confirm import")
            from stock_portfolio.ledger.repository import LedgerRepository

            db = server.directory / "synthetic-data/portfolio.sqlite3"
            with LedgerRepository(db) as repo:
                ds = repo.load_dataset()
                aid = next(a.id for a in ds.accounts if a.name == "Synthetic A")
                b1 = next(e for e in ds.events if e.external_id == "b1")
                b2 = next(e for e in ds.events if e.external_id == "b2")
                s1 = next(e for e in ds.events if e.external_id == "s1")
            choose(page, "Event action", "Revise")
            choose(page, "Event to change", "BUY · " + b1.id)
            fill(page, "Trade price", "101")
            fill(page, "Reason / source", "Synthetic corrected execution")
            create_account(page, "Synthetic guarded creation")
            expect(
                page.get_by_role("button", name="Discard draft and navigate", exact=True)
            ).to_be_visible()
            click(page, "Keep editing")
            expect(page.get_by_role("textbox", name="Trade price", exact=True)).to_have_value("101")
            click(page, "Preview operation")
            click(page, "Cancel operation")
            with LedgerRepository(db) as repo:
                assert next(e for e in repo.load_dataset().events if e.id == b1.id).price == 100
            fill(page, "Trade price", "101")
            fill(page, "Reason / source", "Synthetic corrected execution")
            click(page, "Preview operation")
            click(page, "Confirm operation")
            navigate(page, "Lots & realized gains")
            choose(
                page, "Sale or transfer allocation", f"2025-01-03 · SELL · ABC · 12 · {s1.id[:8]}"
            )
            fill(page, f"Quantity from {b1.id[:8]}", "7")
            fill(page, f"Quantity from {b2.id[:8]}", "5")
            fill(page, "Allocation reason / source", "Synthetic broker allocation")
            click(page, "Preview allocation")
            click(page, "Confirm allocation")
            navigate(page, "Transactions")
            expand(page, "Record dividend and reinvestment together")
            for label, value in [
                ("Reinvestment date", "2025-02-01"),
                ("Reinvestment symbol", "ABC"),
                ("Cash dividend received", "50"),
                ("Reinvested quantity", ".4"),
                ("Reinvestment price", "120"),
                ("Reinvestment fees", "1"),
            ]:
                fill(page, label, value)
            click(page, "Preview reinvestment")
            click(page, "Confirm reinvestment")
            choose(page, "Event action", "Add")
            choose(page, "Event type", "TRANSFER")
            for label, value in [
                ("Effective date", "2025-02-02"),
                ("Symbol", "ABC"),
                ("Quantity", "1"),
                ("Destination account name", "Synthetic B"),
            ]:
                fill(page, label, value)
            click(page, "Preview operation")
            click(page, "Confirm operation")
            choose(page, "Event type", "SPLIT")
            for label, value in [
                ("Effective date", "2025-02-03"),
                ("Symbol", "ABC"),
                ("Split numerator", "2"),
                ("Split denominator", "1"),
            ]:
                fill(page, label, value)
            click(page, "Preview operation")
            click(page, "Confirm operation")
            navigate(page, "Data & recovery")
            choose(page, "CSV type", "prices")
            upload(page, ROOT / "samples/ledger/prices.csv")
            click(page, "Preview CSV import")
            click(page, "Confirm import")
            expand(page, "Add or correct a dated price")
            for label, value in [
                ("Price symbol", "ABC"),
                ("Price observation date", "2025-02-03"),
                ("Observation price", "80"),
                ("Price correction reason", "Synthetic post-split observation"),
            ]:
                fill(page, label, value)
            click(page, "Preview price")
            click(page, "Confirm shared price")
            navigate(page, "Reconcile")
            datebox = (
                page.get_by_test_id("stDateInput")
                .filter(has=page.get_by_text("Broker statement date", exact=True))
                .locator("input")
            )
            datebox.fill("2025-02-03")
            datebox.press("Enter")
            settle(page)
            upload(
                page,
                {
                    "name": "broker.csv",
                    "mimeType": "text/csv",
                    "buffer": b"ticker,quantity,cost_basis\nABC,8.5,253.55\nNA,2,2\n",
                },
            )
            click(page, "Preview CSV import")
            expect(page.get_by_role("button", name="Confirm import", exact=True)).to_be_disabled()
            set_checkbox(
                page, "I confirm this is the complete end-of-day statement for this account", True
            )
            click(page, "Confirm import")
            click(page, "Compare and save evidence")
            expect(page.get_by_text("1 mismatch", exact=False)).to_be_visible()
            with LedgerRepository(db) as repo:
                transfer = next(
                    e
                    for e in repo.load_dataset().events
                    if e.account_id == aid
                    and e.kind.value == "TRANSFER"
                    and e.effective_date == date(2025, 2, 2)
                )
            navigate(page, "Transactions")
            choose(page, "Event action", "Revise")
            choose(page, "Event to change", "TRANSFER · " + transfer.id)
            fill(page, "Quantity", ".95")
            fill(page, "Reason / source", "Synthetic statement quantity correction")
            click(page, "Preview operation")
            click(page, "Confirm operation")
            navigate(page, "Reconcile")
            expect(page.get_by_text("Stale comparison:", exact=False)).to_be_visible()
            click(page, "Recalculate and save new evidence")
            expect(page.get_by_text("2 matched", exact=True)).to_be_visible()
            download(page, "Download reconciliation report", evidence / "reconciliation.csv")
            navigate(page, "Data & recovery")
            download(page, "Download all-account transaction data", evidence / "transactions.csv")
            assert len(list(csv.DictReader((evidence / "transactions.csv").open()))) == 14
            expand(page, "Backup & offline recovery")
            click(page, "Prepare consistent database backup")
            download(page, "Download database backup", tmp_path / "synthetic-backup.sqlite3")
            import sqlite3

            with sqlite3.connect(tmp_path / "synthetic-backup.sqlite3") as connection:
                assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            # Opening uncertainty is resolved through the actual lot editor.
            create_account(page, "Synthetic Opening", opening=True)
            navigate(page, "Data & recovery")
            choose(page, "CSV type", "opening_balances")
            upload(page, ROOT / "samples/ledger/unknown_opening.csv")
            click(page, "Preview CSV import")
            click(page, "Confirm import")
            navigate(page, "Transactions")
            upload(page, ROOT / "samples/ledger/unknown_sale.csv")
            click(page, "Preview CSV import")
            click(page, "Confirm import")
            navigate(page, "Lots & realized gains")
            with LedgerRepository(db) as repo:
                opening_account = next(
                    a.id for a in repo.load_dataset().accounts if a.name == "Synthetic Opening"
                )
                pool = next(
                    e
                    for e in repo.load_dataset().events
                    if e.account_id == opening_account and e.kind.value == "OPENING_BALANCE"
                )
            fill(page, f"Quantity from {pool.id[:8]}", "4")
            fill(page, f"User supplied pool basis for {pool.id[:8]}", "400")
            fill(page, "Allocation reason / source", "Synthetic supplied basis")
            click(page, "Preview allocation")
            click(page, "Confirm allocation")
            with LedgerRepository(db) as repo:
                from stock_portfolio.ledger.engine import replay

                assert (
                    next(
                        d
                        for d in replay(repo.load_dataset(), date.today()).disposals
                        if d.account_id == opening_account
                    ).gain
                    == 200
                )
            # A real 10,000-event upload and a 100-row derived overview.
            create_account(page, "Synthetic Stress")
            navigate(page, "Transactions")
            upload(page, ROOT / "samples/ledger/events_10000.csv")
            start = time.perf_counter()
            click(page, "Preview CSV import")
            preview_seconds = time.perf_counter() - start
            start = time.perf_counter()
            click(page, "Confirm import")
            commit_seconds = time.perf_counter() - start
            navigate(page, "Overview")
            expect(page.get_by_text("100 current holdings", exact=False)).to_be_visible()
            # Resolve missing prices through another real upload before inspecting charts.
            symbols = sorted(
                {
                    row["ticker"]
                    for row in csv.DictReader((ROOT / "samples/ledger/events_10000.csv").open())
                }
            )
            navigate(page, "Data & recovery")
            choose(page, "CSV type", "prices")
            price_bytes = (
                "ticker,price_date,price\n"
                + "".join(f"{symbol},2025-01-01,125\n" for symbol in symbols)
            ).encode()
            upload(
                page, {"name": "stress-prices.csv", "mimeType": "text/csv", "buffer": price_bytes}
            )
            click(page, "Preview CSV import")
            click(page, "Confirm import")
            navigate(page, "Overview")
            fill(page, "Filter holdings by symbol", "AAPL")
            download(page, "Download holdings report", evidence / "filtered-holdings.csv")
            assert [
                r["ticker"] for r in csv.DictReader((evidence / "filtered-holdings.csv").open())
            ] == ["AAPL"]
            fill(page, "Filter holdings by symbol", "")
            measurements = []
            for width, height in [(1440, 900), (1366, 900), (1024, 768), (768, 900)]:
                page.set_viewport_size({"width": width, "height": height})
                page.wait_for_timeout(350)
                page.get_by_text("Account overview", exact=True).scroll_into_view_if_needed()
                page.wait_for_timeout(200)
                page.screenshot(path=str(evidence / f"overview-{width}.png"), full_page=True)
                page.get_by_test_id("stPlotlyChart").first.scroll_into_view_if_needed()
                page.wait_for_timeout(200)
                page.screenshot(path=str(evidence / f"charts-{width}.png"), full_page=True)
                overflow = page.get_by_test_id("stMetricValue").evaluate_all(
                    "(els)=>els.map(e=>({text:e.innerText,overflow:e.scrollWidth>e.clientWidth+1}))"
                )
                assert not any(m["overflow"] for m in overflow)
                measurements.append({"width": width, "height": height, "metrics": overflow})
            (evidence / "measurements.json").write_text(
                json.dumps(
                    {
                        "preview_10000_browser_seconds": preview_seconds,
                        "commit_10000_browser_seconds": commit_seconds,
                        "viewports": measurements,
                    },
                    indent=2,
                )
            )
            print(
                json.dumps(
                    {
                        "browser_preview_10000_seconds": preview_seconds,
                        "browser_commit_10000_seconds": commit_seconds,
                    }
                )
            )
            with LedgerRepository(db) as repo:
                before = repo.load_dataset()
            server.stop()
            server.start()
            page.goto(server.url)
            settle(page)
            with LedgerRepository(db) as repo:
                assert repo.load_dataset() == before
            browser.close()
    finally:
        server.stop()


def test_snapshot_browser(tmp_path):
    evidence = Path(os.environ.get("PORTFOLIO_BROWSER_EVIDENCE", tmp_path / "evidence"))
    evidence.mkdir(parents=True, exist_ok=True)
    server = Server(tmp_path)
    server.start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                channel=os.environ.get("PORTFOLIO_BROWSER_CHANNEL", "msedge"), headless=True
            )
            page = browser.new_page(viewport={"width": 1440, "height": 900}, accept_downloads=True)
            page.goto(server.url)
            settle(page)
            page.get_by_role("tab", name="Edit holdings", exact=True).click()
            upload(page, ROOT / "samples/demo.csv")
            click(page, "Import uploaded CSV")
            fill(page, "Target portfolio name", "Synthetic snapshot")
            click(page, "Save complete snapshot")
            page.screenshot(path=str(evidence / "snapshot-editor.png"), full_page=True)
            canvas = page.get_by_role("tabpanel", name="Edit holdings").locator("canvas").first
            # Synthetic screenshot inspection identifies quantity in the first row.
            canvas.scroll_into_view_if_needed()
            page.wait_for_timeout(700)
            box = canvas.bounding_box()
            page.mouse.move(box["x"] + 400, box["y"] + 55)
            page.wait_for_timeout(250)
            page.mouse.click(box["x"] + 400, box["y"] + 55)
            page.wait_for_timeout(250)
            page.keyboard.press("Enter")
            editor = page.locator("textarea.gdg-input")
            expect(editor).to_be_visible()
            expect(editor).to_have_value("10")
            editor.fill("11")
            editor.press("Enter")
            settle(page)
            page.screenshot(path=str(evidence / "snapshot-edited.png"), full_page=True)
            page.get_by_role("tab", name="Analysis", exact=True).click()
            settle(page)
            expect(
                page.get_by_test_id("stMetricValue").filter(has_text="$2,220.00")
            ).to_be_visible()
            choose(page, "Mode", "Transaction accounts")
            expect(
                page.get_by_role("button", name="Discard draft and navigate", exact=True)
            ).to_be_visible()
            click(page, "Keep editing")
            page.get_by_role("tab", name="Edit holdings", exact=True).click()
            click(page, "Save complete snapshot")
            page.get_by_role("tab", name="Analysis", exact=True).click()
            expect(
                page.get_by_role("button", name="Confirm complete replacement", exact=True)
            ).to_be_visible()
            click(page, "Cancel replacement")
            page.get_by_role("tab", name="Edit holdings", exact=True).click()
            click(page, "Save complete snapshot")
            click(page, "Confirm complete replacement")
            page.get_by_role("tab", name="Analysis", exact=True).click()
            settle(page)
            download(page, "Download complete snapshot CSV", evidence / "snapshot.csv")
            download(page, "Download analysis report CSV", evidence / "snapshot-analysis.csv")
            rows = list(csv.DictReader((evidence / "snapshot.csv").open()))
            assert len(rows) == 2 and rows[0]["quantity"] == "11"
            server.stop()
            server.start()
            page.goto(server.url)
            settle(page)
            expect(
                page.get_by_test_id("stMetricValue").filter(has_text="$2,220.00")
            ).to_be_visible()
            page.screenshot(path=str(evidence / "snapshot-analysis.png"), full_page=True)
            choose(page, "Mode", "Transaction accounts")
            fill(page, "New account name", "Conversion host")
            click(page, "Create account")
            navigate(page, "Data & recovery")
            expand(page, "Start account from snapshot")
            fill(page, "Account name from snapshot", "Synthetic converted")
            set_checkbox(page, "Include snapshot prices as dated observations", True)
            click(page, "Preview opening account")
            set_checkbox(page, "Include snapshot prices as dated observations", False)
            expect(
                page.get_by_role("button", name="Confirm opening account", exact=True)
            ).to_have_count(0)
            click(page, "Preview opening account")
            click(page, "Confirm opening account")
            from stock_portfolio.ledger.repository import LedgerRepository

            with LedgerRepository(server.directory / "synthetic-data/portfolio.sqlite3") as repo:
                assert repo.load_prices() == ()
                assert sorted(e.quantity for e in repo.load_dataset().events) == [5, 11]
            browser.close()
    finally:
        server.stop()
