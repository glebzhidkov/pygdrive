
# pygdrive - Google Drive Python API v3 (in development)

pygdrive offers a simple python interface to work with Google Drive.

### Main features:
* Upload new files to Drive, update and download existing files
* Upload and download folders with all their content
* Export Google Documents to PDF or other formats
* Search for files and folders
* Extensive file and folder management: changing parents, un/trashing, un/starring, renaming
* _Permission management (in work)_

The library relies on three object types:
* `DriveClient`: the main interface
* `DriveFolder`: a Google Drive folder instance, possibly containing subfolders and files
* `DriveFile`: a Google Drive file

Both `DriveFolder` and `DriveFile` share the metaclass `DriveObject` and share most of their attributes and functions.

## Installation
```
...
```

## Basic usage
### Authentication
```python
from pygdrive import authenticate

drive = authenticate(client_secret='creds.json') # or
drive = authenticate(service_account_secret='service.json')
# Returns: DriveClient
```

### Folder management
```python
root = drive.root # "My Drive" folder

search_results = drive.find_folder('my_fav_folder') 
# Returns: Tuple[DriveFolder]

new_folder = fav_folder.create_folder('new_folder')

assert new_folder in fav_folder.content    # subfolders + files within new_folder
assert new_folder in fav_folder.subfolders # subfolders
assert new_folder not in fav_folder.files  # files
```

### Upload new files
```python
pic = root.upload_file(path='elephant.png')

string = 'Hello world!'
hello = root.upload_file(string=string, title='readme.txt')
```

### Find and manage files
```python
search_results = drive.find_file('elephant.png') 
# Returns: Tuple[DriveFile]

pic = search_results[0]
pic.download(path='elephant_downloaded.png')
pic.update(path='elephant_edit.png') # replace content

pic.title = 'not_an_elephant.png' # rename file
pic.parent = new_folder           # move file
pic.is_starred = True             # star file

pic.delete()                      # delete file
pic.restore()                     # restore file
pic.delete(skip_bin=True)         # delete irreversably
```

### Creating copies and shortcuts
```python
hello_copy = hello.copy(parent=fav_folder)
hello_sc = hello.create_shortcut(parent=fav_folder)
```

### Download and upload whole directories
```python
new_folder.download_directory()
new_folder.upload_directory('upload_this_folder')
```

### Special collections
```python
drive.starred   # starred files and folders
drive.bin       # trashed (deleted after 30 days)

drive.empty_bin()
```