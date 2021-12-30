
from googleapiclient import errors

class pygdriveException(Exception):
    """ """
    pass

class FileNotFound(pygdriveException):
    """ """
    pass

class MoreThanOneFileMatch(pygdriveException):
    """ """
    pass

class FileNotUploaded(pygdriveException):
    """ """
    pass

class NotAFolder(pygdriveException):
    """ """
    pass

class DriveAPIError(pygdriveException):
    """ """
    pass
