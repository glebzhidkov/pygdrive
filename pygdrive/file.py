from __future__ import annotations

import io
import mimetypes
import os
from datetime import datetime
from typing import TYPE_CHECKING, List, Literal, Optional, TypedDict, Union, overload

from google.api_core.datetime_helpers import from_rfc3339
from uritemplate import api

from pygdrive.exceptions import MethodNotAvailable, NotADriveFolderError
from pygdrive.permission import DrivePermission, _PermissionsApiSignatue
from pygdrive.typed import (
    ContentTypes,
    ExportType,
    MimeType,
    PermissionRole,
    ResponseDict,
)

if TYPE_CHECKING:
    from pygdrive.client import DriveClient
    from pygdrive.files import DriveFiles
    from pygdrive.folder import DriveFolder


class _DriveFileArgs(TypedDict):
    """Arguments required to initiate a DriveFile. Not part of the public API."""

    id: str
    title: str
    description: Optional[str]
    mime_type: str
    parent_id: str
    is_trashed: bool
    is_starred: bool
    is_locked: bool
    locking_reason: Optional[str]
    url: str
    created_time: datetime
    modified_time: datetime
    bytes_used: int


def _parse_api_response(response: ResponseDict) -> _DriveFileArgs:

    parents = response.get("parents", [])
    if len(parents) > 2:
        print("File has more than 1 parent")

    _content_restrictions = response.get("contentRestrictions", [{}])
    is_locked = _content_restrictions[0].get("readOnly", False)
    locking_reason = _content_restrictions[0].get("reason", None)

    return _DriveFileArgs(
        id=response["id"],
        title=response["name"],
        description=response.get("description"),
        mime_type=response["mimeType"],
        parent_id="root" if not parents else parents[0],
        is_trashed=response.get("trashed", False),
        is_starred=response.get("starred", False),
        is_locked=is_locked,
        locking_reason=locking_reason,
        url=response["webViewLink"],
        created_time=from_rfc3339(response["createdTime"]),
        modified_time=from_rfc3339(response["modifiedTime"]),
        bytes_used=response.get("quotaBytesUsed", 0),
    )


class DriveFile:
    """
    API reference: https://developers.google.com/drive/api/v3/reference/files
    """

    def __init__(self, client: DriveClient, file_args: _DriveFileArgs) -> None:
        self._client = client
        self.__file_args = file_args

    def _reset_drive_files(self):
        pass  # only relevant for DriveFolder

    def refresh(self):
        """
        Update attributes of this file with up-to-date values from cloud.
        """
        self.__file_args = _parse_api_response(self._client._api.get_file(self.id))
        self._reset_drive_files()

    @property
    def id(self) -> str:
        """
        The ID of the file (immutable).
        """
        return self.__file_args["id"]

    @property
    def url(self) -> str:
        """
        A link for opening the file in a relevant Google editor or viewer in a browser (immutable).
        """
        return self.__file_args["url"]

    @property
    def title(self) -> str:
        """
        The name of the file (mutable). This is not necessarily unique within a folder.
        """
        return self.__file_args["title"]

    @title.setter
    def title(self, new_title: str) -> None:
        self._client._api.update_file(file_id=self.id, metadata={"name": new_title})
        self.__file_args["title"] = new_title

    @property
    def description(self) -> Optional[str]:
        return self.__file_args["description"]

    @description.setter
    def description(self, new_description: str) -> None:
        self._client._api.update_file(
            file_id=self.id, metadata={"description": new_description}
        )
        self.__file_args["description"] = new_description

    @property
    def mime_type(self) -> str:
        """
        The mime type of the file (immutable).
        """
        return self.__file_args["mime_type"]

    @property
    def bytes_used(self) -> int:
        return self.__file_args["bytes_used"]

    @property
    def parent(self) -> DriveFolder:
        return self._client.get_folder(self.__file_args["parent_id"])

    @parent.setter
    def parent(self, new_parent: Union[DriveFolder, str]) -> None:
        self.move(new_parent)

    def move(self, new_parent: Union[DriveFolder, str]) -> None:
        new_parent_id = isolate_folder_id(new_parent)
        self._client._api.update_file(file_id=self.id, addParents=new_parent_id)

        # reset children of both old and new parents
        self._client._refresh_folder_contents(self.__file_args["parent_id"])
        self._client._refresh_folder_contents(new_parent_id)
        self.__file_args["parent_id"] = new_parent_id

    @property
    def is_trashed(self) -> bool:
        return self.__file_args["is_trashed"]

    @is_trashed.setter
    def is_trashed(self, new_value: bool) -> None:
        if self.is_trashed != new_value:
            self.set_metadata(trashed=new_value)
        self.__file_args["is_trashed"] = new_value
        # reset the list of parent's children if parent already loaded
        self._client._refresh_folder_contents(self.__file_args["parent_id"])

    def delete(self) -> None:
        # TODO: add skip_bin parameter
        self.is_trashed = True

    @property
    def is_starred(self) -> bool:
        return self.__file_args["is_starred"]

    @is_starred.setter
    def is_starred(self, new_value: bool) -> None:
        if self.is_starred != new_value:
            self.set_metadata(starred=new_value)
        self.__file_args["is_starred"] = new_value

    @property
    def is_locked(self) -> bool:
        return self.__file_args["is_locked"]

    def lock(self, locking_reason: str) -> None:
        restriction = [{"readOnly": True, "reason": locking_reason}]
        self.set_metadata(contentRestrictions=restriction)
        self.__file_args["is_locked"] = True

    def unlock(self) -> None:
        restriction = [{"readOnly": False}]
        self.set_metadata(contentRestrictions=restriction)
        self.__file_args["is_locked"] = False

    @property
    def is_folder(self) -> bool:
        return self.mime_type == MimeType.FOLDER.value

    @property
    def is_google_doc(self) -> bool:
        return self.mime_type.startswith("application/vnd.google-apps.")

    @property
    def created_time(self) -> datetime:
        return self.__file_args["created_time"]

    @property
    def modified_time(self) -> datetime:
        return self.__file_args["modified_time"]

    @property
    def permissions(self) -> List[DrivePermission]:
        fields = self._client._api.PERMISSION_ATTRS
        permissions = self.get_metadata(f"permissions({fields})").get("permissions", [])
        return [DrivePermission(file=self, api_response=p) for p in permissions]

    def get_metadata(self, attrs: str) -> ResponseDict:
        return self._client._api.get_file(file_id=self.id, attrs=attrs)

    def set_metadata(self, **kwargs) -> None:
        self._client._api.update_file(file_id=self.id, metadata=kwargs)

    def __eq__(self, other) -> bool:
        if isinstance(other, DriveFile):
            return self.id == other.id
        return False

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} '{self.title}'>"

    def __len__(self) -> int:
        return 0

    def create_shortcut(
        self, parent: Union[DriveFolder, str], title: Optional[str]
    ) -> DriveFile:

        parent_id = isolate_folder_id(parent)
        title = title or f"Shortcut to {self.title}"

        response = self._client._api.create_shortcut(
            file_id=self.id, title=title, parent_id=parent_id
        )

        return DriveFile.from_api_response(client=self._client, response=response)  # type: ignore

    def update(self, content: ContentTypes) -> None:
        self._client._api.update_file_media(
            content=content, file_id=self.id, mime_type=self.mime_type
        )

    @overload
    def download(
        self, path: None = None, export_type: Optional[ExportType] = None, **kwargs
    ) -> io.BytesIO:
        ...

    @overload
    def download(
        self, path: str, export_type: Optional[ExportType] = None, **kwargs
    ) -> io.FileIO:
        ...

    def download(
        self,
        path: Optional[str] = None,
        export_type: Optional[ExportType] = None,
        **kwargs,
    ):
        """
        Export formats: https://developers.google.com/drive/api/v3/ref-export-formats
        """
        if self.is_google_doc:
            export_type = export_type or ExportType.PDF
            try:
                export_format = export_type.value[self.mime_type]
            except KeyError:
                raise ValueError(f"{export_type=} not supported for {self.mime_type=}")

            if path:
                path = os.path.join(
                    path, f"{self.title}.{mimetypes.guess_extension(export_format)}"
                )

        else:
            export_format = None
            if export_type:
                raise Exception("export only supported for google docs")
            if path:
                path = os.path.join(path, self.title)

        # TODO don't overwrite existing files

        return self._client._api.download_file_media(
            file_id=self.id, path=path, export_format=export_format
        )

    def copy(
        self, title: Optional[str] = None, parent: Union[DriveFolder, str, None] = None
    ) -> DriveFile:

        title = title or f"{self.title} (copy)"
        parent_id = isolate_folder_id(parent or self.parent)
        self._client._refresh_folder_contents(parent_id)

        response = self._client._api.copy_file(
            file_id=self.id, title=title, parent_id=parent_id
        )
        return DriveFile.from_api_response(client=self._client, response=response)  # type: ignore

    def share(
        self,
        with_: Union[str, Literal["anyone"]],
        role: PermissionRole = "reader",
        notification: Union[str, Literal[False], None] = None,
        **kwargs,
    ):
        permission: ResponseDict = {"role": role}

        if with_ == "anyone":
            permission["type"] = "anyone"
        elif "@" in with_:
            permission["type"] = "user"
            permission["emailAddress"] = with_
        else:
            permission["type"] = "domain"
            permission["domain"] = with_

        if role == "owner":
            permission["transerOwnership"] = True

        if notification is False:
            permission["sendNotificationEmail"] = False
        if notification is not None:
            permission["emailMessage"] = notification

        for k, v in kwargs.items():
            permission[k] = v

        response = self._client._api.create_permission(file_id=self.id, body=permission)
        return DrivePermission(file=self, api_response=response)

    # properties that are only available for folders
    # implemented for the sake ozzf static type checkers
    @property
    def content(self) -> List[DriveFolder]:
        raise MethodNotAvailable("content", "DriveFile")

    subfolders = content
    files = content

    @property
    def trashed_content(self) -> DriveFiles:
        raise MethodNotAvailable("trashed_content", "DriveFile")

    @property
    def fully_loaded(self) -> bool:
        raise MethodNotAvailable("fully_loaded", "DriveFile")

    def exists(self, title: str) -> DriveFolder:
        raise MethodNotAvailable("exists", "DriveFile")

    def get_subfolder(self, title: str, strict: bool = True) -> DriveFolder:
        raise MethodNotAvailable("get_subfolder", "DriveFile")

    def upload(
        self, content: ContentTypes, title: Optional[str] = None
    ) -> Union[DriveFile, DriveFolder]:
        raise MethodNotAvailable("upload", "DriveFile")


def isolate_folder_id(folder: Union[DriveFolder, DriveFile, str]) -> str:
    if isinstance(folder, DriveFile):
        # not importing DriveFolder to avoid circular reference
        if folder.is_folder:
            return folder.id
        else:
            raise NotADriveFolderError
    return folder
