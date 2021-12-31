from __future__ import annotations

import os
from typing import Any, Optional, Union

from pygdrive.exceptions import (
    MoreThanOneFileMatch,
    NotADriveFolderError,
    MethodNotAvailable,
)
from pygdrive.typed import ContentTypes, MimeType
from pygdrive.file import DriveFile
from pygdrive.files import DriveFiles


class DriveFolder(DriveFiles, DriveFile):
    def __init__(self, **kwargs):
        # kwargs to be passed are same as for DriveFile init
        query = f"'{kwargs['id']}' in parents and trashed = false"
        DriveFiles.__init__(self, client=kwargs["client"], query=query)
        DriveFile.__init__(self, **kwargs)

    def refresh(self):
        """
        Update folder attributes and its contents with up-to-date values from Google Drive.
        Attributes of content files are not updated, unless a refresh() is called on them explicitly.
        """
        self._sync_file()
        self._reset_drive_files()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} '{self.title}'>"

    @property
    def trashed_content(self) -> DriveFiles:
        return self._client.search(f"'{self.id}' in parents and trashed = true")

    def create_subfolder(self, title: str) -> DriveFolder:
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
        Returns an existing subfolder with the specified title or creates a new one.

        Args:
            strict: if True (default), raises MoreThanOneFileMatch if more than subfolder with such title exist
                    if False, always returns the first match
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
