import io
import os
import sys

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive.appdata",
        "https://www.googleapis.com/auth/drive.scripts",
        "https://www.googleapis.com/auth/drive.metadata"]

TYPE_FOLDER = "application/vnd.google-apps.folder"
target_folder_id = '1-MK-qjhs7De0In2IE1lDNYMrSz4Isa93'

def auth():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            print("Your credentials is expired! re-auth please.")
            flow = InstalledAppFlow.from_client_secrets_file(
                'auth.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return creds

def partial(total_byte_len, part_size_limit):
    s = []
    for p in range(0, total_byte_len, part_size_limit):
        last = min(total_byte_len - 1, p + part_size_limit - 1)
        s.append([p, last])
    return s

def download_file(real_file_id, creds):
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            print("Your credentials is expired! re-auth please.")
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    try:
        # create drive api client
        service = build('drive', 'v3', credentials=creds)

        file_id = real_file_id
        
        # pylint: disable=maybe-no-member
        target = service.files().get(fileId=file_id, fields="mimeType, webContentLink, size, name").execute()
        print(target)
        if target != None and target != {} and target.get('mimeType') == TYPE_FOLDER:
            print("Bamm! pass the folder!")
            return
        total_size = int(target.get('size'))
        print("total_size:", total_size)
        s = partial(total_size, 100*1000*1000)
        with open("/backup/"+target.get("name"), "wb") as f:
            for i, part in enumerate(s):
                headers = {"Range" : 'bytes=%s-%s' % (part[0], part[1])}
                request = service.files().get_media(fileId=file_id)
                request.headers["Range"] = 'bytes=%s-%s' % (part[0], part[1])
                res = request.execute()
                file = io.BytesIO(res)
                print(F'Download part{i+1}/{len(s)}.')
                try:
                    f.write(file.getvalue())
                    f.flush()
                except:
                    print("Error occurs when writing data in file.", file=sys.stderr)


    except HttpError as error:
        print(F'An error occurred: {error}')
        file = None
        return None

def list_files(creds, containsTrashed = False):
    files = []
    try:
        service = build('drive', 'v3', credentials=creds)

        # Call the Drive v3 API

        page_token = None
        while True:
            # pylint: disable=maybe-no-member
            response = service.files().list(q=f"'{target_folder_id}' in parents",
                                            fields='nextPageToken, files(id, name, trashed, mimeType)',
                                            pageToken=page_token).execute()
            for file in response.get('files', []):
                if file.get('trashed') and not containsTrashed:
                    continue
                # Process change
                print(F'Found file: {file.get("name")}, {file.get("id")}')
                files.append(file)
            page_token = response.get('nextPageToken', None)
            if page_token is None:
                break
    except HttpError as error:
        # TODO(developer) - Handle errors from drive API.
        print(f'An error occurred: {error}')

    if len(files)>0:
        print(f"files length : {len(files)}")
    return files

def delete_file(real_file_id, creds):
    try:
        service = build('drive', 'v3', credentials=creds)
        # Call the Drive v3 API
        # pylint: disable=maybe-no-member
        file_metadata = {'trashed': True}
        response = service.files().update(fileId=real_file_id,body=file_metadata).execute()
        print(response)
        if response.get("id") == real_file_id:
            print(f"delete status: success")
        else:
            print(response, file=sys.stderr)
    except HttpError as error:
        # TODO(developer) - Handle errors from drive API.
        print(f'An error occurred: {error}', file=sys.stderr)


def check_disk():
    diskinfo = os.statvfs('/backup')
    total = diskinfo.f_bsize * diskinfo.f_blocks / 1024 / 1024
    free = diskinfo.f_bsize * diskinfo.f_bavail * 100 / 1024 / 1024
    per = round(free/total,2)
    print(f"Disk free space: {per}%({round(free/100/1024,2)}GB)")
    return per > 5

if __name__ == '__main__':
    creds = auth()
    file_list = list_files(creds)
    down_list = []
    for f in file_list:
        if not check_disk():
            exit()
        print(f"start download {f.get('name')}")
        print(f)
        download_file(f.get('id'), creds)
        if f != None and f != {} and f.get('mimeType') == "application/vnd.google-apps.folder":
            print("Bamm! don't delete a folder!")
        else:
            print(f"delete file {f.get('name')}")
            delete_file(f.get('id'), creds)
    

