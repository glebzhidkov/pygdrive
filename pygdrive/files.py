from __future__ import annotations

import io
import os
from typing import TYPE_CHECKING, List, Optional, Union

from pygdrive.enums import ExportType
from pygdrive.exceptions import FileNotFound, MoreThanOneFileMatch
from pygdrive.file import DriveFile
from pygdrive.typed import Corpora, Space, SortKey

if TYPE_CHECKING:
    from pygdrive.client import DriveClient
    from pygdrive.folder import DriveFolder


class DriveFiles:
    """
    A lazy implementation of a list of files in a Google Drive folder / search results.

    ### Lazy methods (load elements only once needed):
    ```
    root_folder = client.root
    root_folder["elephant.png"]  # accessing file by name
    root_folder.exists("elephant.png")

    # iterating over all contents is lazy -- elements are loaded only once reached
    for file in root_folder:
        file.delete()
    ```

    ### Eager methods (load all contents):
    ```
    root_folder.content()  # access list of all contents
    root_folder.subfolders()
    root_folder.files()
    len(root_folder)  # get number of contained files and subfolders
    ```
    """

    _content: List[Union[DriveFile, DriveFolder]]

    def __init__(
        self,
        client: DriveClient,
        query: str,
        corpora: Corpora,
        space: Space,
        drive_id: Optional[str] = None,
        order_by: Optional[str] = None,
        title: Optional[str] = None,
    ) -> None:
        self._client = client
        self._parameters = {
            "query": query,
            "corpora": corpora,
            "space": space,
            "drive_id": drive_id,
            "order_by": order_by,
            "next_page_token": None,
        }
        self._title = title  # or "Search results"
        self._reset_drive_files()

    def _reset_drive_files(self):
        self._parameters["next_page_token"] = None
        self._loaded_first_page = False
        self.__last_returned_idx = -1
        self._content = []

    def refresh(self) -> None:
        """
        Update the list of files with up-to-date values from Google Drive.
        """
        self._reset_drive_files()

    def sort_by(self, key: SortKey, desc: bool = False):
        """
        Chainable. add doc
        """
        sort_statement = self._parameters.get("order_by")
        sort_append = f"{key} desc" if desc else key

        if sort_statement is None:
            self._parameters["order_by"] = sort_append
        else:
            self._parameters["order_by"] = f"{sort_statement}, {sort_append}"

        self._reset_drive_files()
        return self

    def __load_next_page(self) -> None:
        response = self._client._api.list_files(**self._parameters)
        self._parameters["next_page_token"] = response.get("nextPageToken")
        self._loaded_first_page = True

        for file in response.get("files", []):
            self._content.append(self._client._build_file_from_api_response(file))

    def __load_all(self) -> None:
        while not self.is_fully_loaded:
            self.__load_next_page()

    @property
    def is_fully_loaded(self) -> bool:
        """
        Whether all elements have been loaded into the current session.
        """
        if not self._loaded_first_page:
            return False
        else:
            return self._parameters["next_page_token"] is None

    def __getitem__(self, title: str) -> Union[DriveFile, DriveFolder]:
        # scan already loaded content for matches
        matching_items = [file for file in self._content if file.title == title]
        if len(matching_items) > 1:
            raise MoreThanOneFileMatch(files=matching_items, title=title)
        if len(matching_items) == 1:
            return matching_items[0]

        # if content is not fully loaded yet, request file directly
        if not self.is_fully_loaded:
            query = f"{self._parameters['query']} and name = '{title}'"
            response = self._client._api.list_files(query=query).get("files", [])

            if len(response) > 1:
                raise MoreThanOneFileMatch(files=response, title=title)
            elif len(response) == 1:
                return self._client._build_file_from_api_response(response[0])

        raise FileNotFound(f"{title=} does not exist in {self}")

    def __len__(self) -> int:
        return len(self.content)

    def __next__(self) -> Union[DriveFile, DriveFolder]:
        idx = self.__last_returned_idx + 1
        if len(self._content) <= idx and not self.is_fully_loaded:
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
            return f"<DriveFiles for query='{self._parameters['query']}'>"

    def exists(self, title: str) -> bool:
        """
        Whether a file or a folder with the specified title exists in
        this folder or search results (exact match).
        """
        try:
            self[title]
            return True
        except FileNotFound:
            return False

    @property
    def content(self) -> List[Union[DriveFile, DriveFolder]]:
        """
        Returns a list containing all files and subfolders contained in
        this folder or search results. All elements are eagerly loaded.
        """
        self.__load_all()
        return self._content.copy()

    @property
    def files(self) -> List[DriveFile]:
        """
        Returns a list containing all files contained in
        this folder or search results. All elements are eagerly loaded.
        """
        return list(f for f in self.content if not f.is_folder)

    @property
    def subfolders(self) -> List[DriveFolder]:
        """
        Returns a list containing all subfolders contained in
        this folder or search results. All elements are eagerly loaded.
        """
        return list(f for f in self.content if f.is_folder)  # type: ignore

    def download(
        self,
        path: Optional[str] = ".",
        export_format: Optional[ExportType] = None,
        include_subfolders: bool = True,
    ) -> io.FileIO:
        """
        Download all contents of this folder or search results to path.

        Args:
            :path: Local path where a new folder with all contents will be created.
            :export_format: Export format for Google Doc files (if not specified, PDF).
            :include_subfolders: Whether to download all subfolders and their contents.
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
