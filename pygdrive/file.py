# TODO split into more files. circular references are difficult though

from __future__ import annotations

import io
import mimetypes
import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union, overload

from pygdrive.exceptions import MoreThanOneFileMatch, NotADriveFolderError
from pygdrive.typed import ContentTypes, MimeType

if TYPE_CHECKING:
    from pygdrive.client import DriveClient


class DriveFiles:
    """
    A lazy implementation of a list of files in a Google Drive folder / search results.
    ```
    client = DriveClient()
    files = client.search(".pdf")
    ```
    """
    _content: List[Union[DriveFile, DriveFolder]]

    def __init__(self, client: DriveClient, query: str, **kwargs) -> None:
        self._client = client
        self._search_parms = kwargs
        self._search_parms["query"] = query
        self.refresh()

    def __load_next_page(self) -> None:
        response = self._client._api.list_files(**self._search_parms)
        self._search_parms["next_page_token"] = response.get("nextPageToken")
        self._loaded_first_page = True

        for file in response.get("files", []):
            self._content.append(DriveFile.from_api_response(client=self._client, response=file))
    
    def __load_all(self) -> None:
        while not self.fully_loaded:
            self.__load_next_page()

    @property
    def fully_loaded(self) -> bool:
        if not self._loaded_first_page:
            return False
        else:
            return self._search_parms["next_page_token"] is None

    def refresh(self) -> None:
        self._search_parms["next_page_token"] = None
        self._loaded_first_page = False
        self.__last_returned_idx = -1
        self._content = []

    def __getitem__(self, title: str) -> Union[DriveFile, DriveFolder]:
        # scan already loaded content for matches
        matching_items = [file for file in self._content if file.title == title]
        if len(matching_items) > 1:
            raise MoreThanOneFileMatch(files=matching_items, title=title)
        if len(matching_items) == 1:
            return matching_items[0]
        
        # if content is not fully loaded yet, request file directly
        if not self.fully_loaded:
            query = f"{self._search_parms['query']} and name = '{title}'"
            response = self._client._api.list_files(query=query).get("files", [])

            if len(response) > 1:
                raise MoreThanOneFileMatch(files=response, title=title)
            elif len(response) == 1:
                return DriveFile.from_api_response(client=self._client, response=response[0])

        raise KeyError

    def __len__(self) -> int:
        return len(self.content)

    def __next__(self) -> Union[DriveFile, DriveFolder]:
        idx = self.__last_returned_idx + 1
        if len(self._content) <= idx and not self.fully_loaded:
            self.__load_next_page()
        if len(self._content) <= idx:
            self.__last_returned_idx = -1  # reset
            raise StopIteration
        self.__last_returned_idx = idx
        return self._content[idx]

    def __iter__(self) -> DriveFiles:
        return self

    @property
    def content(self) -> List[Union[DriveFile, DriveFolder]]:
        self.__load_all()
        return self._content

    @property
    def files(self) -> List[DriveFile]:
        return list(f for f in self.content if isinstance(f, DriveFile))

    @property
    def subfolders(self) -> List[DriveFolder]:
        return list(f for f in self.content if isinstance(f, DriveFolder))


class DriveFileMixin:
    
    def __init__(
        self,
        client: DriveClient,
        id: str,
        title: str, 
        mime_type: str, 
        parent_id: str,
        is_trashed: bool,
        is_starred: bool
    ) -> None:
        self._client = client
        self._id = id
        self._title = title
        self._mime_type = mime_type
        self._parent_id = parent_id
        self._is_trashed = is_trashed
        self._is_starred = is_starred
        self._load_content()
    
    def _load_content(self):
        pass

    def refresh(self):
        response = self._client._api.get_file(self.id)
        self._title = response["name"]
        self._is_starred = response.get("starred", False)
        self._is_trashed = response.get("trashed", False)
        parents = response.get('parents', [])
        if len(parents) > 2:
            print("File has more than 1 parent")
        self._parent_id = "root" if not parents else parents[0]
        self._load_content()

    @classmethod
    def from_api_response(cls, client: DriveClient, response: Dict[str, Any]) -> Union[DriveFile, DriveFolder]:
        """
        Construct a DriveFile or a DriveFolder from the Google API response 
        and register it in the client's session. If this file is already registered
        in this session (based on its ID), return a reference to it instead.
        """
        file_id = response["id"]
        if file_id in client._session:
            return client._session[file_id]

        parents = response.get('parents', [])
        if len(parents) > 2:
            print("File has more than 1 parent")

        is_folder = response["mimeType"] == MimeType.FOLDER.value
        builder = DriveFolder if is_folder else DriveFile

        file = builder(
            client=client,
            id=file_id,
            title=response["name"],
            mime_type=response["mimeType"],
            parent_id="root" if not parents else parents[0],
            is_trashed=response.get("trashed", False),
            is_starred=response.get("starred", False),
        )
        client._add_to_session(file)
        return file

    @property
    def id(self) -> str:
        return self._id

    @property
    def url(self) -> str:
        if self.is_folder:
            return f"https://drive.google.com/drive/u/1/folders/{self.id}"
        else:
            return f"https://drive.google.com/file/d/{self.id}"

    @property
    def title(self) -> str:
        return self._title

    @title.setter
    def title(self, new_title: str) -> None:
        self._client._api.update_file(file_id=self.id, metadata={"name": new_title})

    @property
    def mime_type(self) -> str:
        return self._mime_type

    @property
    def parent(self) -> DriveFolder:
        return self._client.get_folder(self._parent_id)

    @parent.setter
    def parent(self, new_parent: Union[DriveFolder, str]) -> None:
        self.move(new_parent)

    def move(self, new_parent: Union[DriveFolder, str]) -> None:
        new_parent_id = isolate_folder_id(new_parent)
        self._client._api.update_file(file_id=self.id, addParents=new_parent_id)

        # reset children of both old and new parents
        self._client._reset_contents(self._parent_id)
        self._client._reset_contents(new_parent_id)
        self._parent_id = new_parent_id

    @property
    def is_trashed(self) -> bool:
        return self._is_trashed
    
    @is_trashed.setter
    def is_trashed(self, new_value: bool) -> None:
        if self.is_trashed != new_value:
            self.set_metadata(trashed=new_value)
        self._is_trashed = new_value
        self._client._reset_contents(self._parent_id)  # reset the list of parent's children

    def delete(self) -> None:
        self.is_trashed = True

    @property
    def is_starred(self) -> bool:
        return self._is_starred

    @is_starred.setter
    def is_starred(self, new_value: bool) -> None:
        if self.is_starred != new_value:
            self.set_metadata(starred=new_value)
        self._is_starred = new_value

    @property
    def is_folder(self) -> bool:
        return self._mime_type == MimeType.FOLDER

    @property
    def is_google_doc(self) -> bool:
        return self.mime_type.startswith('application/vnd.google-apps.')

    def get_metadata(self, attrs: str) -> dict:
        return self._client._api.get_file(file_id=self.id, attrs=attrs)
    
    def set_metadata(self, **kwargs) -> None:
        self._client._api.update_file(file_id=self.id, metadata=kwargs)

    def __eq__(self, other) -> bool:
        if isinstance(other, DriveFile):
            return self.id == other.id
        return False

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} '{self.title}'>"

    def create_shortcut(self, parent: Union[DriveFolder, str], title: Optional[str]) -> DriveFile:
        
        parent_id = isolate_folder_id(parent)
        title = title or f'Shortcut to {self.title}'

        response = self._client._api.create_shortcut(file_id=self.id, title=title, parent_id=parent_id)

        return DriveFile.from_api_response(client=self._client, response=response)  # type: ignore 


class DriveFile(DriveFileMixin):
    __len__ = 0
    content = files = subfolders = None
    
    def update(self, content: ContentTypes):
        self._client._api.update_file_media(
            content=content, file_id=self.id, mime_type=self.mime_type
        )

    @overload
    def download(self, path: None = None, export_format: Optional[str] = None) -> io.BytesIO: ...

    @overload
    def download(self, path: str, export_format: Optional[str] = None) -> io.FileIO: ...
    
    def download(self, path: Optional[str] = None, export_format: Optional[str] = None):

        if self.is_google_doc and not export_format:
            export_format = self._client._api.EXPORT_DEFAULT
        if not self.is_google_doc and export_format:
            raise Exception("export only supported for google docs")

        if path:
            if export_format:
                path = os.path.join(path, f"{self.title}.{mimetypes.guess_extension(export_format)}")
            else:
                path = os.path.join(path, self.title)

        return self._client._api.download_file_media(file_id=self.id, path=path, export_format=export_format)

    def copy(self, title: Optional[str] = None, parent: Union[DriveFolder, str, None] = None) -> DriveFile:
        
        title = title or f"{self.title} (copy)"
        parent_id = isolate_folder_id(parent or self.parent)
        self._client._reset_contents(parent_id)

        response = self._client._api.copy_file(file_id=self.id, title=title, parent_id=parent_id)
        return DriveFile.from_api_response(client=self._client, response=response)  # type: ignore


class DriveFolder(DriveFileMixin):

    def _load_content(self):
        self._content = self._client.search(f"'{self.id}' in parents and trashed = false")

    # references to drivefiles
    @property
    def content(self):
        return self._content.content
    
    @property
    def files(self):
        return self._content.files

    @property
    def subfolders(self):
        return self._content.subfolders 

    def __getitem__(self, title: str):
        return self._content.__getitem__(title=title)

    def __next__(self):
        return next(self._content)

    def __iter__(self):
        return iter(self._content)

    def __len__(self):
        return len(self._content)

    # own methods
    @property
    def trashed_content(self) -> DriveFiles:
        return self._client.search(f"'{self.id}' in parents and trashed = false")

    def create_subfolder(self, title: str) -> DriveFolder:
        metadata = {'name': title, 'mimeType': str(MimeType.FOLDER), 'parents': [self.id]}
        response = self._client._api.create_file(metadata=metadata)
        folder = DriveFolder.from_api_response(client=self._client, response=response)
        return assert_is_folder(folder)

    def go_to_subfolder(self, title: str) -> DriveFolder:
        matching_entries = [obj for obj in self.subfolders if obj.title == title]
        
        if not matching_entries:
            return self.create_subfolder(title)
        elif len(matching_entries) > 1:
            raise MoreThanOneFileMatch(files=matching_entries, title=title)
        else:
            return matching_entries[0]

    def upload(self, content: ContentTypes, title: Optional[str] = None) -> Union[DriveFile, DriveFolder]:
        """
        Upload a file or directory with files from path, string, or bytes.
        """
        if isinstance(content, str) and os.path.isdir(content):
            return self.__upload_directory(path=content, title=title)
        else:
            return self.__upload_file(content=content, title=title or "New file")

    def __upload_file(self, content: ContentTypes, title: str) -> DriveFile:
        response = self._client._api.upload_file_media(content=content, title=title, parent_id=self.id)
        self._client._reset_contents(self.id)
        return DriveFile.from_api_response(client=self._client, response=response)  # type: ignore

    def __upload_directory(self, path: str, title: Optional[str] = None) -> DriveFolder:
        title = title or os.path.basename(path)
        new_folder = self.create_subfolder(title)

        for obj in os.listdir(path):
            obj_path = os.path.join(path, obj)
            if os.path.isdir(obj_path):
                new_folder.__upload_directory(obj_path)
            else:
                try:
                    self.__upload_file(obj_path, title=os.path.basename(obj_path))
                except:
                    pass
        
        return new_folder

    def download(self, path: str, include_subfolders: bool = True, export_format = None):
        # add progress bar

        if export_format:
            raise ValueError("export_format parameter not supported for folders")

        path = os.path.join(path, self.title)
        if os.path.exists(path):
            raise Exception(f"Folder already exists at {path}")
        os.mkdir(path)

        for obj in self.files:
            obj.download(path=path)

        if include_subfolders:
            for obj in self.subfolders:
                obj.download(path, include_subfolders=True)

    def _count_children_and_grandchildren(self) -> int:
        length = len(self.content)
        for subfolder in self.subfolders:
            length += subfolder._count_children_and_grandchildren()
        return length


def isolate_folder_id(folder: Union[DriveFolder, DriveFile, str]) -> str:
    if isinstance(folder, DriveFolder):
        return folder.id
    if isinstance(folder, DriveFile):
        raise NotADriveFolderError
    return folder


def assert_is_folder(folder: Any) -> DriveFolder:
    """
    Raises `NotADriveFolderError` if the file is not a valid `DriveFolder`.
    """
    if not DriveFolder:
        raise NotADriveFolderError
    return folder
