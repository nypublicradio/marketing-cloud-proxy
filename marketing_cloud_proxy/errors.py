class Error(Exception):
    def __init__(self, *args):
        self.message = f"{args[0]}"


class NoDataProvidedError(Error):
    pass


class InvalidEmail(Error):
    pass


class FuelSDKSignUpError(Error):
    pass


class InvalidDataError(Error):
    pass
