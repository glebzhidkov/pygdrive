
FOLDER_TYPE = 'application/vnd.google-apps.folder'
FILE_ATTRS = 'id, name, mimeType, parents, trashed, starred'

_types_to_mimes = {
    'folder': 'application/vnd.google-apps.folder',
    'shortcut': 'application/vnd.google-apps.shortcut',
    'google sheet': 'application/vnd.google-apps.spreadsheet',
    'google document': 'application/vnd.google-apps.document'
}

_mimes_to_types = {
    'application/vnd.google-apps.folder': 'folder',
    'application/vnd.google-apps.shortcut': 'shortcut',
    'application/vnd.google-apps.spreadsheet': 'google_sheet',
    'application/vnd.google-apps.document': 'google_document'
}

def types_to_mimes(file_type: str) -> str:
    if file_type.lower() in _types_to_mimes:
        return _types_to_mimes[file_type.lower()]
    else:
        return file_type

def mimes_to_types(mime: str) -> str:
    if mime in _mimes_to_types:
        return _mimes_to_types[mime]
    else:
        return mime


"""
https://developers.google.com/drive/api/v3/mime-types
application/vnd.google-apps.drive-sdk	3rd party shortcut
application/vnd.google-apps.drawing	Google Drawing
application/vnd.google-apps.file	Google Drive file
application/vnd.google-apps.form	Google Forms
application/vnd.google-apps.fusiontable	Google Fusion Tables
application/vnd.google-apps.map	Google My Maps
application/vnd.google-apps.photo	
application/vnd.google-apps.presentation	Google Slides
application/vnd.google-apps.script	Google Apps Scripts
application/vnd.google-apps.site	Google Sites
application/vnd.google-apps.unknown	
application/vnd.google-apps.video
"""