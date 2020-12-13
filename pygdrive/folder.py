from __future__ import annotations

from tqdm import tqdm
import os
import io
import mimetypes
from collections import UserDict
from typing import List, Union, TYPE_CHECKING, Tuple, Optional, Dict

from pygdrive.streamer import streamer_upload_file
from pygdrive.object import DriveObject
from pygdrive.utils import FOLDER_TYPE, FILE_ATTRS
from pygdrive.exceptions import FileNotFound, MoreThanOneFileMatch

if TYPE_CHECKING:
    from pygdrive.file import DriveFile


class DriveFolder(DriveObject):
    """A Google Drive folder"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._files = None

    @property
    def content(self) -> Tuple[Union[DriveFile, DriveFolder]]:
        """Returns a tuple containing all `DriveFile`'s and `DriveFolder`'s stored in this folder"""
        if not self._files or self._needs_sync: self.sync()
        return tuple(self._files)
    
    @property
    def files(self) -> Tuple[DriveFile]:
        """Returns a tuple containing all `DriveFile`'s stored in this folder"""
        return tuple(f for f in self.content if not isinstance(f, DriveFolder))
    
    @property
    def subfolders(self) -> Tuple[DriveFolder]:
        """Returns a tuple containing all `DriveFolder`'s stored in this folder"""
        return tuple(f for f in self.content if isinstance(f, DriveFolder))

    @property
    def trashed_content(self) -> Tuple[Union[DriveFile, DriveFolder]]:
        """ """
        return tuple(self.client.search(query=f"'{self.id}' in parents and trashed = false"))

    def create_subfolder(self, title: str) -> DriveFolder:
        """Creates a new folder with specified `title` inside of this folder and returns it as a `DriveFolder`"""
        file_metadata = {'name': title, 'mimeType': FOLDER_TYPE, 'parents': [self.id]}
        drive_object = self.client.service.files().create(body=file_metadata, fields=FILE_ATTRS).execute()
        drive_folder = self.client._object_maker(drive_object)
        if self._files:
            self._files.append(drive_folder)
        return drive_folder

    def __iter__(self):
        for file in self.content:
            yield(file)

    def __getitem__(self, key) -> Union[DriveFile, DriveFolder]:
        query = [obj for obj in self.content if obj.title == key]

        if not query:
            raise FileNotFound(f"No object with title '{key}' is stored in folder '{self.title}'")
        if len(query) > 1:
            raise MoreThanOneFileMatch(f"More than one object with title '{key}' are stored in folder '{self.title}'")
        else:
            return query[0]

    def upload_file(self, **kwargs) -> DriveFile:
        """Uploads a new file to this folder from `path`, `string`, or `bytes_`

        Args:
            path        file location (name and mime type will be inherited 
                        from the file title, unless title is specified)
            title       title of the file (e.g., 'note.txt' or 'drawing.png'),
                        from which the mime type will be inherited
                        (REQUIRED if uploading file from string or bytes)
            string      file string
            bytes_      file bytes

            resumable   file can be uploaded in chunks? default True
            chunk_size  chunk size (defaults to drive.DEFAULT_CHUNK_SIZE = 10*1024*1024)
                        minimum is 1024*1024
            progress    show progress bar? default True

        Returns: a new instance of `DriveFile`
        """
        response = streamer_upload_file(__client=self.client, __parent_id=self.id, **kwargs)
        drive_file = self.client._object_maker(response)
        if self._files:
            self._files.append(drive_file)
        return drive_file

    def download_directory(
            self, 
            target_path: Optional[str] = '', 
            include_subfolders: Optional[bool] = True,
            **kwargs
            ) -> None:
        """ 
        
        """
        if 'pbar' in kwargs:
            pbar = kwargs['pbar']
        else:
            pbar = tqdm()
            pbar.set_description('Preparing directory for download...')
            if include_subfolders:
                LENGTH = self._count_children_and_grandchildren()
            else:
                LENGTH = len(self.files)
            pbar.total = LENGTH + 1

        target_path = os.path.join(target_path, self.title)
        pbar.update(1)
        if not os.path.exists(target_path):
            os.mkdir(target_path)
            self.client.logger.debug(f"Created new local folder at '{target_path}'")

        for obj in self.files:
            try:
                obj.download(target_path=target_path)
                self.client.logger.debug(f"Downloaded '{obj.title} to '{target_path}")
            except Exception as e:
                self.client.logger.error(f"Failed to download '{obj.title}' due to {e}")
            pbar.update(1)

        if include_subfolders:
            for obj in self.subfolders:
                obj.download_directory(target_path=target_path, include_subfolders=include_subfolders, pbar=pbar)

        if 'pbar' not in kwargs:
            pbar.set_description('Directory downloaded.')
            pbar.close()
    
    def upload_directory(self, path: str, **kwargs) -> None:
        """Uploads a local directory with all files and subfolders to Google Drive
        
        """
        if 'pbar' in kwargs:
            pbar = kwargs['pbar']
        else:
            pbar = tqdm()
            pbar.total = sum([len(x[1]) + len(x[2]) for x in os.walk(path or '.')])

        if not os.path.isdir(path):
            raise ValueError(f"{path} is not a folder")

        new_folder = self.create_subfolder(os.path.basename(path))
        self.client.logger.debug(f"Created new remote folder '{new_folder.title}' at {new_folder.url}")

        for obj in os.listdir(path):
            obj_path = os.path.join(path, obj)
            if os.path.isdir(obj_path):
                sub_output = new_folder.upload_directory(obj_path, pbar=pbar)
            else:
                try:
                    f = new_folder.upload_file(obj_path)
                    self.client.logger.debug(f'Uploaded {obj_path} to {f.url}')
                except:
                    self.client.logger.error(f'Failed to upload {obj_path}')
            pbar.update(1)

        if 'pbar' not in kwargs:
            pbar.close()

    def _count_children_and_grandchildren(self) -> int:
        length = len(self.content)
        for subfolder in self.subfolders:
            length += subfolder._count_children_and_grandchildren()
        return length
