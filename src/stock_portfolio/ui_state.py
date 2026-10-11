"""Session drafts live independently of Streamlit's hidden-widget cleanup."""

from dataclasses import dataclass, field

import streamlit as st


@dataclass
class PendingDraft:
    mode: str
    account: str | None
    page: str
    key: str
    inputs: dict = field(default_factory=dict)
    dirty: bool = False
    pending_destination: tuple | None = None


def guard_navigation(current_context, requested_context, dirty):
    return current_context == requested_context or not dirty


def draft_for(key):
    state = st.session_state
    context = state["context"]
    drafts = state.setdefault("ledger_drafts", {})
    return drafts.setdefault((*context, key), PendingDraft(*context, key))


def dirty():
    snapshot = st.session_state.get("draft")
    return bool(snapshot and snapshot.dirty) or any(
        d.dirty for d in st.session_state.get("ledger_drafts", {}).values()
    )


def input_changed(draft, field, widget_key):
    draft.inputs[field] = st.session_state[widget_key]
    draft.dirty = True
    draft.inputs.pop("_preview", None)


def text_input(draft, field, label, value="", **kwargs):
    key = "ledger:" + ":".join(str(v) for v in (draft.account, draft.page, draft.key, field))
    st.session_state.setdefault(key, draft.inputs.get(field, value))
    return st.text_input(
        label, key=key, on_change=input_changed, args=(draft, field, key), **kwargs
    )


def clear_draft(draft):
    draft.inputs.clear()
    draft.dirty = False
    for key in list(st.session_state):
        prefix = "ledger:" + ":".join(str(v) for v in (draft.account, draft.page, draft.key)) + ":"
        if key.startswith(prefix):
            del st.session_state[key]


def resolve_navigation(discard):
    state = st.session_state
    if discard:
        target = state.pop("pending_navigation")
        state["ledger_drafts"] = {}
        for key in list(state):
            if key in {
                "draft",
                "editor_base",
                "generation",
                "load_next",
                "target_name",
                "target_date",
                "pending_replace",
                "pending_switch",
                "pending_delete",
                "symbols",
                "sectors",
            } or key.startswith(("editor_", "ledger:")):
                del state[key]
        state["context"] = target
    else:
        state.pop("pending_navigation", None)
    mode, account, page = state["context"]
    state["nav_mode"], state["nav_account"], state["nav_page"] = mode, account, page
