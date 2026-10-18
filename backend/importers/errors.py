class ImportFailure(Exception):
    """An explicit, reported import failure (spec 3.2). Never silently skipped."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code   # unsupported | corrupt | unsafe_archive | no_records | not_activity
        self.message = message
