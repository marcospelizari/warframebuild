"""Errors of the offline pipeline."""


class RefreshError(RuntimeError):
    """A source or reference file cannot be turned into a valid dataset."""
