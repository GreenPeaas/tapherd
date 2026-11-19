"""Errors safe to show to the local operator."""


class TapHerdError(Exception):
    """An operation failed and the message tells the operator how to recover."""
