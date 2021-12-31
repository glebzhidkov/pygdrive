import io
from typing import Literal, Union, Dict, Any

ResponseDict = Dict[str, Any]

SearchCorpora = Literal["user", "drive", "domain", "allDrives"]
SearchSpace = Literal["drive", "appDataFolder"]

PermissionType = Literal["user", "group", "domain", "anyone"]
PermissionRole = Literal["reader", "commenter", "writer", "fileOrganizer", "organizer", "owner"]

ContentTypes = Union[str, bytes, io.BytesIO]
