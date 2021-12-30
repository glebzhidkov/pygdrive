class FileNotFound(Exception): 
    pass

class NotADriveFolderError(Exception): 
    pass

class MoreThanOneFileMatch(Exception): 
    def __init__(self, files, title):
        self.files = files
        self.title = title
