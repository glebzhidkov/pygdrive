from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal, Optional, Union

from google.api_core.datetime_helpers import from_rfc3339, to_rfc3339

from pygdrive.typed import PermissionRole, PermissionType, ResponseDict

if TYPE_CHECKING:
    from pygdrive.file import DriveFile


class DrivePermission:
    def __init__(self, file: DriveFile, api_response: ResponseDict):
        self._file = file
        self._api = file._client._api
        self._id: str = api_response["id"]
        self._type: PermissionType = api_response["type"]
        self._role: PermissionRole = api_response["role"]
        self._email: Optional[str] = api_response.get("emailAddress")
        self._name: Optional[str] = api_response.get("displayName")
        self._expiration_time: Optional[str] = api_response.get("expirationTime")

    @property
    def file(self) -> DriveFile:
        return self._file

    @property
    def type(self) -> PermissionType:
        return self._type

    @property
    def email(self) -> Optional[str]:
        return self._email

    @property
    def role(self) -> PermissionRole:
        return self._role

    @role.setter
    def role(self, new_role: PermissionRole) -> None:
        self._api.update_permission(
            file_id=self.file.id, permission_id=self._id, body={"role": new_role}
        )
        self._role = new_role

    @property
    def name(self) -> Optional[str]:
        return self._name

    @property
    def expiration_time(self) -> Optional[datetime]:
        # TODO only works for google suite ? then distinguish between files
        # TODO can be set when creating a permission ?
        return from_rfc3339(self._expiration_time) if self._expiration_time else None

    @expiration_time.setter
    def expiration_time(self, new_expiration_time: Optional[datetime]) -> None:
        if not new_expiration_time and self.expiration_time:
            self._api.update_permission(
                file_id=self.file.id,
                permission_id=self._id,
                removeExpiration=True,
                body={},
            )
        if new_expiration_time:
            self._api.update_permission(
                file_id=self.file.id,
                permission_id=self._id,
                body={
                    "expirationTime": to_rfc3339(new_expiration_time),
                    "role": self.role,
                },
            )

    def __repr__(self) -> str:
        return (
            f"<DrivePermission for {self.file}: type={self.type} role={self.role} "
            f"email={self.email} name={self.name} expiration_time={self.expiration_time}>"
        )

    def delete(self):
        self._api.delete_permission(file_id=self.file.id, permission_id=self._id)

    def copy_to(
        self,
        email: Optional[str] = None,
        file: Optional[DriveFile] = None,
        notification: Union[str, Literal[False], None] = None,
        **kwargs,
    ) -> DrivePermission:
        # TODO improve support for domains!

        if email is not None and file is None:
            target_file = self.file
            with_ = email

        elif file is not None:
            if isinstance(file, str):  # hidden support for file id instead of DriveFile
                file = self.file._client.get_file(file)
            target_file = file

            with_ = "anyone" if self.type == "anyone" else self.email
            assert with_ is not None

        else:
            raise ValueError("a permission can be copied only to a file OR to a user")

        return target_file.share(
            with_=with_, role=self.role, notification=notification, **kwargs
        )

        # fix
        if self.expiration_time:
            target_file = self.expiration_time
