from __future__ import annotations

import io
import os
from typing import TYPE_CHECKING, List, Optional, Union

from pygdrive.exceptions import MoreThanOneFileMatch
from pygdrive.typed import ExportType
from pygdrive.file import DriveFile

if TYPE_CHECKING:
    from pygdrive.client import DriveClient
    from pygdrive.folder import DriveFolder


class DriveFiles:
    """
    A lazy implementation of a list of files in a Google Drive folder / search results.
    ```
    client = DriveClient()
    files = client.search(".pdf")
    ```
    """

    _content: List[Union[DriveFile, DriveFolder]]

    def __init__(
        self,
        client: DriveClient,
        query: str,
        title: Optional[str] = None,
        **_search_parms,
    ) -> None:
        self._client = client
        self._title = title #or "Search results"
        self._search_parms = _search_parms
        self._search_parms["query"] = query
        self._reset_drive_files()

    def _reset_drive_files(self):
        self._search_parms["next_page_token"] = None
        self._loaded_first_page = False
        self.__last_returned_idx = -1
        self._content = []

    def refresh(self) -> None:
        self._reset_drive_files()

    def __load_next_page(self) -> None:
        response = self._client._api.list_files(**self._search_parms)
        self._search_parms["next_page_token"] = response.get("nextPageToken")
        self._loaded_first_page = True

        for file in response.get("files", []):
            self._content.append(self._client._build_file_from_api_response(file))

    def __load_all(self) -> None:
        while not self.fully_loaded:
            self.__load_next_page()

    @property
    def fully_loaded(self) -> bool:
        if not self._loaded_first_page:
            return False
        else:
            return self._search_parms["next_page_token"] is None

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
                return self._client._build_file_from_api_response(response[0])

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

    def __repr__(self) -> str:
        if self._title:
            return f"<DriveFiles for {self._title}>"
        else:
            return f"<DriveFiles for query='{self._search_parms['query']}'>"

    def exists(self, title: str) -> bool:
        try:
            self[title]
            return True
        except KeyError:
            return False

    @property
    def content(self) -> List[Union[DriveFile, DriveFolder]]:
        self.__load_all()
        return self._content

    @property
    def files(self) -> List[DriveFile]:
        return list(f for f in self.content if not f.is_folder)

    @property
    def subfolders(self) -> List[DriveFolder]:
        return list(f for f in self.content if f.is_folder)  # type: ignore

    def download(
        self,
        path: Optional[str] = ".",
        export_format: Optional[ExportType] = None,
        include_subfolders: bool = True,
    ) -> io.FileIO:
        """
        Download contents of this folder or search results to path.
        """
        # TODO add progress bar

        if export_format:
            raise ValueError(
                "export_format parameter not supported for folders / search results"
            )
        if not path:
            raise ValueError(
                "path parameter needs to be provided for folders / search results"
            )
        if len(self) == 0:
            raise ValueError("cannot download empty folder")

        path = os.path.join(path, self._title or "Search results")
        if os.path.exists(path):
            raise Exception(f"Folder already exists at {path}")
        os.mkdir(path)

        for obj in self.files:
            io_obj = obj.download(path=path)

        if include_subfolders:
            for obj in self.subfolders:
                io_obj = obj.download(path, include_subfolders=True)

        return io_obj  # type: ignore # not elegant though
