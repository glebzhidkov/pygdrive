class DriveApiError(Exception)

class FileNotFound(DriveApiError): 
    pass

class NotADriveFolderError(DriveApiError): 
    pass

class MoreThanOneFileMatch(DriveApiError): 
    def __init__(self, files, title):
        self.files = files
        self.title = title

class MethodNotAvailable(DriveApiError):
    pass
