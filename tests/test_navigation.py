from test_app import app, button

from stock_portfolio.ui_state import PendingDraft, guard_navigation


def test_navigation_guard_and_pending_draft_retains_normalized_state():
    current = ("Transaction accounts", "account", "Transactions")
    draft = PendingDraft(*current, "entry", {"quantity": "1.20"}, True)
    assert not guard_navigation(current, ("Snapshots", None, "Overview"), draft.dirty)
    assert guard_navigation(current, current, True)
    assert draft.inputs["quantity"] == "1.20"


def test_snapshot_default_and_dirty_mode_switch_requires_visible_discard(tmp_path, monkeypatch):
    at = app(tmp_path, monkeypatch)
    assert at.selectbox(key="nav_mode").value == "Snapshots"
    button(at, "Load synthetic sample").click().run()
    at.selectbox(key="nav_mode").set_value("Transaction accounts").run()
    assert at.session_state["context"][0] == "Snapshots"
    assert button(at, "Discard draft and navigate")
    assert not any("navigate" in b.label for tab in at.tabs for b in tab.button)
    button(at, "Keep editing").click().run()
    assert at.selectbox(key="nav_mode").value == "Snapshots"
    assert len(at.session_state["draft"].rows) == 2
    at.selectbox(key="nav_mode").set_value("Transaction accounts").run()
    button(at, "Discard draft and navigate").click().run()
    assert at.session_state["context"][0] == "Transaction accounts"
    assert not at.exception
