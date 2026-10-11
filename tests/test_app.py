from pathlib import Path

from streamlit.testing.v1 import AppTest


def app(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTFOLIO_DATA_DIR", str(tmp_path))
    return AppTest.from_file(str(Path("app.py").resolve())).run(timeout=20)


def button(at, label):
    return next(b for b in at.button if b.label == label)


def test_startup_and_sample_is_unsaved(tmp_path, monkeypatch):
    at = app(tmp_path, monkeypatch)
    assert not at.exception
    button(at, "Load synthetic sample").click().run()
    assert not at.exception
    assert at.session_state["draft"].validation.valid
    assert at.session_state["draft"].dirty
    from stock_portfolio.storage import Repository

    with Repository(tmp_path / "portfolio.sqlite3") as repo:
        assert repo.list_portfolios() == []
    at.run()
    assert len(at.session_state["draft"].rows) == 2


def test_editor_delta_survives_rerun_and_invalid_blocks_save(tmp_path, monkeypatch):
    at = app(tmp_path, monkeypatch)
    button(at, "Load synthetic sample").click().run()
    generation = at.session_state["generation"]
    # AppTest does not serialize the canvas editor; provide the browser's delta
    # in WidgetStates on each rerun instead of assigning server session state.
    import json
    from streamlit.proto.WidgetStates_pb2 import WidgetState

    editor = next(e for e in at.dataframe if e.proto.id.endswith(f"editor_{generation}"))
    delta = {"edited_rows": {"0": {"quantity": "oops"}}, "added_rows": [], "deleted_rows": []}
    for _ in range(2):
        states = at._tree.get_widget_states()
        states.widgets.append(WidgetState(id=editor.proto.id, string_value=json.dumps(delta)))
        at._run(states)
        assert not at.exception
        assert not at.session_state["draft"].validation.valid
        assert button(at, "Save complete snapshot").disabled
        assert at.session_state["draft"].rows[0]["quantity"] == "oops"


def test_discard_prompt_and_save(tmp_path, monkeypatch):
    at = app(tmp_path, monkeypatch)
    button(at, "Load synthetic sample").click().run()
    button(at, "New blank draft").click().run()
    assert len(at.session_state["draft"].rows) == 2
    button(at, "Cancel switch").click().run()
    button(at, "Save complete snapshot").click().run()
    assert not at.exception and not at.session_state["draft"].dirty
