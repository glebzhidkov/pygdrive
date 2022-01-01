import io
from typing import Literal, Union, Dict, Any

ResponseDict = Dict[str, Any]

Corpora = Literal["user", "drive", "domain", "allDrives"]
Space = Literal["drive", "appDataFolder"]

PermissionType = Literal["user", "group", "domain", "anyone"]
PermissionRole = Literal[
    "reader", "commenter", "writer", "fileOrganizer", "organizer", "owner"
]

ContentTypes = Union[str, bytes, io.BytesIO]

SortKey = Literal[
    "createdTime",
    "folder",
    "modifiedByMeTime",
    "modifiedTime",
    "name",
    "name_natural",
    "quotaBytesUsed",
    "recency",
    "sharedWithMeTime",
    "starred",
    "viewedByMeTime",
]
