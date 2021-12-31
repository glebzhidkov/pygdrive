import io
from typing import Literal, Union, Dict, Any

ResponseDict = Dict[str, Any]

Corpora = Literal["user", "drive", "domain", "allDrives"]

PermissionType = Literal["user", "group", "domain", "anyone"]
PermissionRole = Literal["reader", "commenter", "writer", "fileOrganizer", "organizer", "owner"]

ContentTypes = Union[str, bytes, io.BytesIO]
