class Error(Exception):
    def __init__(self, *args):
        if args:
            self.message = f"{args[0]}"


class NoDataProvidedError(Error):
    pass


class InvalidDataError(Error):
    pass
