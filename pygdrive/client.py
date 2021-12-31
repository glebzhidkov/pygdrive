from __future__ import annotations

from typing import Dict, Optional, Union

from pygdrive.api import DriveApi, ResponseDict
from pygdrive.file import DriveFile, isolate_folder_id
from pygdrive.files import DriveFiles
from pygdrive.folder import DriveFolder, assert_is_folder
from pygdrive.typed import Corpora, MimeType


class DriveClient:
    def __init__(self, creds) -> None:
        self._api = DriveApi(creds)
        self._session: Dict[str, Union[DriveFile, DriveFolder]] = {}
        self._root_folder_id = "root"
        self.update_search_config()

    def update_search_config(
        self,
        corpora: Corpora = "user",
        spaces: str = "drive",
        drive_id: Optional[str] = None,
        order_by: Optional[str] = None,
        limit: int = 100,
    ) -> None:
        self._search_config = {
            "corpora": corpora,
            "spaces": spaces,
            "drive_id": drive_id,
            "order_by": order_by,
            "limit": limit,
        }

    def _build_file_from_api_response(
        self, response: ResponseDict
    ) -> Union[DriveFile, DriveFolder]:
        """
        Construct a DriveFile or a DriveFolder from the Google API response
        and register it in the client's session. If this file is already registered
        in this session (based on its ID), return a reference to it instead.
        """
        file_id = response["id"]
        if file_id in self._session:
            return self._session[file_id]

        parents = response.get("parents", [])
        if len(parents) > 2:
            print("File has more than 1 parent")

        is_folder = response["mimeType"] == MimeType.FOLDER.value
        builder = DriveFolder if is_folder else DriveFile

        _content_restrictions = response.get("contentRestrictions", [{}])
        is_locked = _content_restrictions[0].get("readOnly", False)
        locking_reason = _content_restrictions[0].get("reason", None)

        file = builder(
            client=self,
            id=file_id,
            title=response["name"],
            mime_type=response["mimeType"],
            parent_id="root" if not parents else parents[0],
            is_trashed=response.get("trashed", False),
            is_starred=response.get("starred", False),
            is_locked=is_locked,
            locking_reason=locking_reason,
            url=response["webViewLink"],
        )
        self._register_file(file)
        return file

    def _register_file(self, file: Union[DriveFile, DriveFolder]) -> None:
        if file.id in self._session:
            raise Exception("think of how to best handle this")
        self._session[file.id] = file

    def _reset_contents(self, folder_id: str) -> None:
        if folder_id in self._session and isinstance(
            self._session[folder_id], DriveFolder
        ):
            self._session[folder_id].refresh()

    def __getitem__(self, file_id: str) -> Union[DriveFile, DriveFolder]:
        return self.get_file(file_id)

    def get_file(self, file_id: str) -> Union[DriveFile, DriveFolder]:
        """
        Get a `DriveFile` or `DriveFolder` based on its Google Drive ID.
        """
        if not file_id in self._session:
            response = self._api.get_file(file_id=file_id)
            return self._build_file_from_api_response(response)
        return self._session[file_id]

    def get_folder(self, folder_id: str) -> DriveFolder:
        """
        Same as `get_file` but raises an error if the object is not a `DriveFolder`.
        """
        return assert_is_folder(self.get_file(folder_id))

    def get_shared_drive(self, drive_id: str) -> DriveFolder:
        new_client = DriveClient(self._api.creds)
        new_client.update_search_config(corpora="drive", drive_id=drive_id)
        return new_client.get_folder(drive_id)

    def search(self, query: str, **kwargs) -> DriveFiles:
        if not kwargs:
            # make this more elegant?
            kwargs = self._search_config
        return DriveFiles(client=self, query=query, **kwargs)

    def find_file(
        self, title: str, parent: Union[str, DriveFolder, None] = None, **kwargs
    ) -> DriveFiles:
        # TODO rethink logic of this
        query = [f"mimeType != '{MimeType.FOLDER}'", f"name = '{title}'"]
        if parent:
            query.append(f"'{isolate_folder_id(parent)}' in parents")

        return DriveFiles(client=self, query=",".join(query), **kwargs)

    def find_folder(
        self, title: str, parent: Union[str, DriveFolder, None] = None, **kwargs
    ) -> DriveFiles:
        query = [f"mimeType = '{MimeType.FOLDER}'", f"name = '{title}'"]
        if parent:
            query.append(f"'{isolate_folder_id(parent)}' in parents")

        return DriveFiles(client=self, query=",".join(query), **kwargs)

    @property
    def root(self) -> DriveFolder:
        root_folder = self.get_folder(self._root_folder_id)
        self._session[
            "root"
        ] = root_folder  # add additional reference to session as generic 'root'
        self._root_folder_id = (
            root_folder.id
        )  # update generic 'root' with the actual folder ID
        return root_folder

    @property
    def bin(self) -> DriveFiles:
        return self.search(query="trashed = true")

    @property
    def starred(self) -> DriveFiles:
        return self.search(query="starred = true")

    def empty_bin(self) -> None:
        self._api.empty_trash()
