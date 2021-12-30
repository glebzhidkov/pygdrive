import io
from enum import Enum
from typing import Literal, Union

Corpora = Literal["user", "drive", "domain", "allDrives"]

ContentTypes = Union[str, bytes, io.BytesIO]


class MimeType(Enum):
    FOLDER = "application/vnd.google-apps.folder"
    SHORTCUT = "application/vnd.google-apps.shortcut"
    GOOGLE_SHEET = "application/vnd.google-apps.spreadsheet"
    GOOGLE_DOC = "application/vnd.google-apps.document"
