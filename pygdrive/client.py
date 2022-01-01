from __future__ import annotations

from typing import Dict, Optional, Union

from google.auth.credentials import Credentials

from pygdrive.api import DriveApi
from pygdrive.enums import MimeType
from pygdrive.exceptions import FileAlreadyRegisteredInSession, MethodNotAvailable
from pygdrive.file import DriveFile, _parse_api_response, isolate_folder_id
from pygdrive.files import DriveFiles
from pygdrive.folder import DriveFolder, assert_is_folder
from pygdrive.typed import ResponseDict, Space, Corpora


class DriveClient:
    """
    Google Drive API v3 client.

    Basic examples:
    ```
    from pygrdrive import authenticate
    client = authenticate()

    # access file or folder directly by its ID
    file = client[file_id]

    # access file or folder by a sequence of folder names
    file = client.root["documents"]["drafts"]["proposal.pdf"]
    file.download(".")
    file.move(root["documents"]["approved"])

    # upload file or folder to the root folder
    file = client.root.upload("local_folder", title="new_folder")
    file.share("axel@lexa.com", role="editor")
    ```
    """
    _corpora: Corpora
    _space: Space

    def __init__(
        self,
        creds: Credentials,
        drive_id: Optional[str] = None,
        app_data_folder: bool = False,
    ) -> None:
        self._api = DriveApi(creds)
        self._session: Dict[str, Union[DriveFile, DriveFolder]] = {}
        self.__set_parms(drive_id=drive_id, app_data_folder=app_data_folder)

    def __set_parms(self, drive_id: Optional[str], app_data_folder: bool):
        if drive_id:
            self._drive_id = drive_id
            self._root_folder_id = drive_id
            self._space = "drive"
            self._corpora = "drive"
        elif app_data_folder:
            self._drive_id = None
            self._root_folder_id = "appDataFolder"
            self._space = "appDataFolder"
            self._corpora = "user"
        else:
            self._drive_id = None
            self._root_folder_id = "root"
            self._space = "drive"
            self._corpora = "user"
        
        if drive_id and app_data_folder:
            raise ValueError

    @property
    def drive_id(self) -> Optional[str]:
        return self._drive_id

    @drive_id.setter
    def drive_id(self, new_drive_id: Optional[str]) -> None:
        if self._space == "appDataFolder":
            raise Exception
        self.__set_parms(drive_id=new_drive_id, app_data_folder=False)

    def _build_file_from_api_response(
        self, response: ResponseDict
    ) -> Union[DriveFile, DriveFolder]:
        """
        Construct a DriveFile or a DriveFolder from the Google API response
        and register it in the client's session. If this file is already registered
        in this session (based on its ID), return a reference to it instead.
        """
        file_args = _parse_api_response(response)

        if file_args["id"] in self._session:
            return self._session[file_args["id"]]

        is_folder = file_args["mime_type"] == MimeType.FOLDER.value
        builder = DriveFolder if is_folder else DriveFile

        file = builder(client=self, file_args=file_args)
        self._register_file(file)
        return file

    def _register_file(self, file: Union[DriveFile, DriveFolder]) -> None:
        """
        Register a DriveFile in the current session.
        """
        if file.id in self._session:
            # safety check to avoid multiple instances of the same file, already handled in _build_file_from_api_response
            raise FileAlreadyRegisteredInSession(file.id)
        self._session[file.id] = file

    def _refresh_folder_contents(self, folder_id: str) -> None:
        """
        Reset loaded contents of a DriveFolder, if this folder is registered in the current session.
        """
        folder = self._session.get(folder_id)
        if folder and isinstance(folder, DriveFolder):
            folder._reset_drive_files()

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

    def get_shared_drive(self, drive_id: str) -> DriveClient:
        """
        Returns a `DriveFolder` that is the root folder of the drive with the specified ID.
        """
        return DriveClient(self._api.creds, drive_id=drive_id)

    def get_app_data(self) -> DriveClient:
        """
        """
        return DriveClient(self._api.creds, app_data_folder=True)

    def search(self, query: str, **kwargs) -> DriveFiles:
        return DriveFiles(
            client=self,
            query=query,
            corpora=kwargs.get("corpora") or self._corpora,
            space=kwargs.get("space") or self._space,
            drive_id=kwargs.get("drive_id") or self.drive_id,
            title=kwargs.get("title"),
        )

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
        """
        """
        root_folder = self.get_folder(self._root_folder_id)
        # add additional reference to session as generic 'root'
        self._session["root"] = root_folder
        # update generic 'root' with the actual folder ID
        self._root_folder_id = root_folder.id
        return root_folder

    @property
    def bin(self) -> DriveFiles:
        return self.search(query="trashed = true", title="Google Drive - Bin")

    @property
    def starred(self) -> DriveFiles:
        return self.search(query="starred = true", title="Google Drive - Starred")

    def empty_bin(self) -> None:
        self._api.empty_trash()
