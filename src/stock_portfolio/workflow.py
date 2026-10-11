"""Session-only drafts; saving and full exports never consume dashboard filters."""

from copy import deepcopy
from datetime import date

from .models import Metadata, Selection, Snapshot
from .validation import holding_rows, validate_rows


class DiscardRequired(ValueError):
    pass


class Draft:
    def __init__(self):
        self.rows = []
        self.metadata = Metadata("", date.today())
        self.selection = Selection()
        self._saved = None

    @property
    def validation(self):
        return validate_rows(self.rows)

    @property
    def dirty(self):
        if self._saved is None:
            return bool(self.rows or self.metadata.portfolio_name.strip())
        return (self.rows, self.metadata) != self._saved

    def load(self, rows, metadata, discard=False, saved=False):
        if self.dirty and not discard:
            raise DiscardRequired("Discard unsaved changes before switching datasets.")
        self.rows, self.metadata = deepcopy(rows), metadata
        self.selection = Selection()
        self._saved = (deepcopy(self.rows), metadata) if saved else None

    def load_saved(self, snapshot, discard=False):
        self.load(holding_rows(snapshot.holdings), snapshot.metadata, discard, saved=True)

    def update(self, rows, metadata):
        if rows != self.rows:
            self.selection = Selection()
        self.rows, self.metadata = deepcopy(rows), metadata

    def snapshot(self):
        result = self.validation
        if (
            not result.valid
            or not self.metadata.portfolio_name.strip()
            or type(self.metadata.snapshot_date) is not date
        ):
            raise ValueError("Valid holdings, portfolio name, and prices-as-of date are required.")
        return Snapshot(
            Metadata(self.metadata.portfolio_name.strip(), self.metadata.snapshot_date),
            result.holdings,
        )

    def save(self, repository, replace=False):
        snapshot = self.snapshot()
        name = snapshot.metadata.portfolio_name
        existing = next(
            (p for p, n in repository.list_portfolios() if n.casefold() == name.casefold()), None
        )
        created = existing is None
        portfolio_id = repository.create_portfolio(name) if created else existing
        try:
            result = repository.save_snapshot(
                portfolio_id, snapshot.metadata.snapshot_date, snapshot.holdings, replace
            )
        except Exception:
            if created:
                repository.delete_portfolio(portfolio_id)
            raise
        self._saved = (deepcopy(self.rows), self.metadata)
        return result
