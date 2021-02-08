#!/usr/bin/python
"""download from google drive"""

#----IMPORTS
import os
import sys
import time
import io
from glob import glob
sys.path.insert(0, './DATA/')
import random
import numpy as np
import pandas as pd
import unidecode
import re
import argparse
import httplib2
from apiclient.discovery import build
from apiclient.errors import HttpError
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import argparser, run_flow
from oauth2client import tools
from apiclient.http import MediaFileUpload
from apiclient.http import MediaIoBaseDownload
from tenacity import retry, retry_if_exception_type, wait_exponential, stop_after_attempt
#--------------------------------------
# Explicitly tell the underlying HTTP transport library not to retry, since
# we are handling retry logic ourselves.
httplib2.RETRIES = 1
MAX_RETRIES = 10
# Always retry when these exceptions are raised.
RETRIABLE_EXCEPTIONS = (httplib2.HttpLib2Error, IOError)
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]
#----Google API credentials
def open_credentials(SCOPE, CLIENT_SECRETS_FILE, args):
    """Google API credentials. Needs to specify the scope and the secret files, is applicable for any service.

    Args:
        SCOPE (type): Google API scope `SCOPE`.
        CLIENT_SECRETS_FILE (type): json file with credentials `CLIENT_SECRETS_FILE`.

    Returns:
        type: credential object.

    """
    MISSING_CLIENT_SECRETS_MESSAGE = """
    WARNING: Please configure OAuth 2.0

    To make this sample run you will need to populate the client_secrets.json file
    found at:

       %s

    with information from the API Console
    https://console.developers.google.com/

    For more information about the client_secrets.json file format, please visit:
    https://developers.google.com/api-client-library/python/guide/aaa_client_secrets
    """ % os.path.abspath(os.path.join(os.path.dirname(__file__),
                                       CLIENT_SECRETS_FILE))

    flow = flow_from_clientsecrets(CLIENT_SECRETS_FILE,
      message=MISSING_CLIENT_SECRETS_MESSAGE,
      scope=SCOPE)
    storage = Storage("./secret/%s-oauth2.json" % sys.argv[0])
    credentials = storage.get()
    # You may pick the credentials from the browser
    if credentials is None or credentials.invalid:
        flags = tools.argparser.parse_args(args=[])
        credentials = run_flow(flow, storage, flags)

    return credentials

def gdrive_service(args):
    """Initiate gdrive service.

    Args:
        secret (type): credentials JSON `args`.

    Returns:
        type: service

    """
    # This OAuth 2.0 access scope allows an application to upload files to the
    # authenticated user's YouTube channel, but doesn't allow other types of access.
    SCOPE = ['https://www.googleapis.com/auth/drive',
             'https://www.googleapis.com/auth/drive.file',
             'https://www.googleapis.com/auth/drive.readonly'
             ]
    API_SERVICE_NAME = "drive"
    API_VERSION = "v3"

    try:
        CLIENT_SECRETS_FILE = args.secret
    except KeyError as e:
        CLIENT_SECRETS_FILE = './credentials.json'
        pass
    except NameError as e:
        CLIENT_SECRETS_FILE = './credentials.json'
        pass
    #----------------------------------
    credentials = open_credentials(SCOPE, CLIENT_SECRETS_FILE, args)
    #----------------------------------
    service = build(API_SERVICE_NAME, API_VERSION, http=credentials.authorize(httplib2.Http()))

    return service
#----Google Drive functions
def initialize_download(service, file_name='', file_id=''):
    """Initiate service for download from gdrive

    """
    # Call the API's file.getmedia method to download files
    insert_request = service.files().get_media(fileId = file_id)
    fh = io.FileIO(file_name, 'wb')
    downloader = MediaIoBaseDownload(fh, insert_request, chunksize=10*1024*1024)
    manage_downloads(downloader)
    return None

def manage_downloads(object):
    """Manage exponential backoff for http retries.

    Args:
        insert_request (type): youtube service Media insert `insert_request`.

    Returns:
        type: status, response for the service

    """
    response = False
    error = None
    retry = 0

    while response is False:
        try:
            status, response = object.next_chunk()
            if response is not None:
                if status:
                    print( "{}%...".format(int(status.progress() * 100)))
                else:
                    exit("The failed failed with an unexpected response: %s" % response)
        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                error = "A retriable HTTP error %d occurred:\n%s" % (e.resp.status, e.content)
            else:
                raise
        except RETRIABLE_EXCEPTIONS as e:
            error = "A retriable error occurred: %s" % e

        if error is not None:
            print( error)
            retry += 1
            if retry > MAX_RETRIES:
                exit("No longer attempting to retry.")
            max_sleep = 2 ** retry
            sleep_seconds = random.random() * max_sleep
            print( "Sleeping %f seconds and then retrying..." % sleep_seconds)
            time.sleep(sleep_seconds)

    return status, response

def download(args, file_name = '', file_id=''):
    """Download single file from gdrive.

    Args:
        args (type): Description of parameter `args`.
        file_name (type): Description of parameter `file_name`. Defaults to ''.
        file_id (type): Description of parameter `file_id`. Defaults to ''.

    Returns:
        type: Description of returned object.

    """
    if os.path.exists(file_name):
        print("File already exist --file= parameter. DOING NOTHING")
    else:
        try:
            service = gdrive_service(args)
            initialize_download(service, file_name=file_name, file_id=file_id)
        except HttpError as e:
            print( "An HTTP error %d occurred:\n%s" % (e.resp.status, e.content))
    return None

def download_lista(df, args):
    """Download a bunch of files in dataframe format.

    Args:
        df (type): provides LINK_VIDEO (remote ID) and filename (local file) `df`.
        args (type): Description of parameter `args`.

    Returns:
        type: Description of returned object.

    """
    file_id = df['LINK_VIDEO'].to_list()
    filename = df['ID'].apply(lambda row: './VIDEO/'+ str(row) + '.mp4').to_list()
    num = len(file_id)
    for ii in np.arange(num):
        download(args,file_name=filename[ii], file_id=file_id[ii])
    return None
#--------------------------------------
#----Module as script
def parse_args(args):
    parser = argparse.ArgumentParser(description='Download from google drive')
    #----arguments
    parser.add_argument('--file_name', required=True, help='local filename')
    parser.add_argument('--file_id',  required=True, help='ID of file in google drive')
    parser.add_argument('--secret',  required=True, help='OAUTH2 credentials JSON')
    args = parser.parse_args()
    return args

def main(args):
    args = parse_args(args)
    try:
        download(args,file_name=args.file_name, file_id=args.file_id )
    except Error as e:
        print('Error: {}'.e)
    print('Download finished!')
    return None

if __name__ == '__main__':
    main(sys.argv)
