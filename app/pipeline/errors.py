"""Errors of the offline pipeline."""


class RefreshError(RuntimeError):
    """A source or reference file cannot be turned into a valid dataset."""


class DataGap(RefreshError):
    """One gun's or arcane's data is incomplete (missing in a source, a field or a row).
    The message is the reason shown with the exclusion, without the entry's name."""
