from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Optional, Union

from pygdrive.enums import MimeType
from pygdrive.exceptions import (
    MethodNotAvailable,
    MoreThanOneFileMatch,
    NotADriveFolderError,
)
from pygdrive.file import DriveFile, _DriveFileArgs
from pygdrive.files import DriveFiles
from pygdrive.typed import ContentTypes

if TYPE_CHECKING:
    from pygdrive.client import DriveClient


class DriveFolder(DriveFiles, DriveFile):
    def __init__(self, client: DriveClient, file_args: _DriveFileArgs):
        # kwargs to be passed are same as for DriveFile init
        query = f"'{file_args['id']}' in parents and trashed = false"
        DriveFiles.__init__(self, client=client, query=query, corpora=client._corpora, space=client._space)
        DriveFile.__init__(self, client=client, file_args=file_args)

    def __repr__(self) -> str:
        # overwrite repr from DriveFiles
        return f"<{self.__class__.__name__} '{self.title}'>"

    @property
    def trashed_content(self) -> DriveFiles:
        """
        All content that was deleted from this folder and is currently trashed (in bin).
        """
        return self._client.search(
            query=f"'{self.id}' in parents and trashed = true",
            title=f"Trashed content in {self}",
        )

    def create_subfolder(self, title: str) -> DriveFolder:
        """
        Creates a new subfolder with the specified title and returns its instance.
        """
        metadata = {
            "name": title,
            "mimeType": MimeType.FOLDER.value,
            "parents": [self.id],
        }
        response = self._client._api.create_file(metadata=metadata)
        folder = self._client._build_file_from_api_response(response)
        return assert_is_folder(folder)

    def get_subfolder(self, title: str, strict: bool = True) -> DriveFolder:
        """
        Returns an existing or creates a new subfolder with the specified title.

        Args:
            :strict:    Whether to raise an Error (MoreThanOneFileMatch) if there is more than
                        one subfolder with such title. If False, the first match is returned.
        """
        matching_entries = [obj for obj in self.subfolders if obj.title == title]

        if not matching_entries:
            return self.create_subfolder(title)
        elif not strict or len(matching_entries) == 1:
            return matching_entries[0]
        else:
            raise MoreThanOneFileMatch(files=matching_entries, title=title)

    def upload(
        self, content: ContentTypes, title: Optional[str] = None
    ) -> Union[DriveFile, DriveFolder]:
        """
        Upload a file or directory with files from path, string, or bytes.
        """
        if isinstance(content, str) and os.path.isdir(content):
            return self.__upload_directory(path=content, title=title)
        else:
            return self.__upload_file(content=content, title=title or "New file")

    def __upload_file(self, content: ContentTypes, title: str) -> DriveFile:
        response = self._client._api.upload_file_media(
            content=content, title=title, parent_id=self.id
        )
        self._client._refresh_folder_contents(self.id)
        return self._client._build_file_from_api_response(response=response)

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

    def _count_children_and_grandchildren(self) -> int:
        length = len(self.content)
        for subfolder in self.subfolders:
            length += subfolder._count_children_and_grandchildren()
        return length

    # overwrite methods inherited from DriveFile that are not available for folders
    def update(self, content: ContentTypes) -> None:
        """
        A folder cannot be updated directly, calling this method will raise an error.
        """
        raise MethodNotAvailable("update", "DriveFolder")

    def copy(
        self, title: Optional[str] = None, parent: Union[DriveFolder, str, None] = None
    ) -> DriveFile:
        """
        A folder cannot be copied directly, calling this method will raise an error.
        """
        raise MethodNotAvailable("copy", "DriveFolder")


def assert_is_folder(folder: Any) -> DriveFolder:
    """
    Raises `NotADriveFolderError` if the file is not a valid `DriveFolder`.
    """
    if not isinstance(folder, DriveFolder):
        raise NotADriveFolderError
    return folder
