class DriveApiError(Exception):
    pass


class FileNotFound(DriveApiError):
    pass


class NotADriveFolderError(DriveApiError):
    pass


class MoreThanOneFileMatch(DriveApiError):
    def __init__(self, files, title):
        self.files = files
        self.title = title


class MethodNotAvailable(DriveApiError):
    def __init__(self, method: str, context: str):
        self.method = method
        self.context = context

    def __repr__(self):
        return f"{self.method} is not available for {self.context}"
