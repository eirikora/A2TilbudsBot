import msal
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def rename_key(data, old_key, new_key):
    """
    Renames a key in a dictionary.
    
    Parameters:
        data (dict): The dictionary to modify.
        old_key (str): The key to rename.
        new_key (str): The new key name.
    
    Returns:
        dict: The dictionary with the renamed key.
    """
    if old_key in data:
        data[new_key] = data.pop(old_key)
    return data

def make_header(file_fields):
    # List of fields you want to include in the header text
    fields = ['Dokumentnavn', 'Status', 'Kunde', 'Marked', 'Dokumenttype', 'Modified']
    
    # Start with an empty string for the header text
    header_text = "Sharepoint Metadata:\n"
    
    # Iterate over the specified fields and add them to header_text if they exist
    for field in fields:
        if field in file_fields:
            header_text += f"  {field}: {file_fields[field]}\n"
    
    # Include Tjenesteområde (list of strings)
    if 'Tjenesteområde' in file_fields:
        fag_list = ', '.join(file_fields['Tjenesteområde'])
        header_text += f"  Tjenesteområde: {fag_list}\n"
    
    # Include Konsulent (list of dictionaries with names)
    if 'Konsulent' in file_fields:
        konsulent_names = ', '.join([k['LookupValue'] for k in file_fields['Konsulent']])
        header_text += f"  Konsulent: {konsulent_names}\n"

    header_text += "\n"
    return header_text

# Cache dictionaries
site_id_cache = {}
drive_id_cache = {}

def getSiteID(sharepoint_site, site_name, token):
    # Get the ID of the named site we need to access.
    # Check if the site_id is already cached
    if (sharepoint_site, site_name) in site_id_cache:
        return site_id_cache[(sharepoint_site, site_name)]
    
    # Use the token to access Microsoft Graph API for SharePoint
    headers = {
        'Authorization': 'Bearer ' + token['access_token']
    }
    # Step 1: Get the site ID
    site_response = requests.get(
        f"https://graph.microsoft.com/v1.0/sites/{sharepoint_site}:/sites/{site_name}",
        headers=headers
    )

    site_id = None
    if site_response.status_code == 200:
        site_info = site_response.json()
        site_id = site_info['id']
        # print("Site ID:", site_id)
    else:
        print("Failed to retrieve site ID.")
        print("Status code:", site_response.status_code)
        print("Response content:", site_response.text)
        exit(1)
    return site_id

def getDriveID(site_id, drive_name, token):
    # Get the ID of the named drive we need to access.
    # Check if the drive_id is already cached
    if (site_id, drive_name) in drive_id_cache:
        return drive_id_cache[(site_id, drive_name)]
    
    # Use the token to access Microsoft Graph API for SharePoint
    headers = {
        'Authorization': 'Bearer ' + token['access_token']
    }
    # Step 2: Find the drive-id
    drives_response = requests.get(
        f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives",
        headers=headers
    )

    drive_id = None
    if drives_response.status_code == 200:
        drives_info = drives_response.json()
        #print("Drives in the site:")
        # Print all drive names and IDs
        #or drive in drives_info['value']:
        #    print(f"Drive Name: {drive['name']}, Drive ID: {drive['id']}")
        # Now try to find the drive with the correct name
        for drive in drives_info['value']:
            #print(f" - Looking at drive: '{drive['name']}'")
            if drive['name'] == drive_name: 
                drive_id = drive['id']
                drive_name = drive['name']
                # print(f"Drive ID for '{drive_name}': {drive_id}")
                break
        if not drive_id:
            print(f"Error: Drive '{drive_name}' not found.")
            exit(1)
    else:
        print("Failed to retrieve drives.")
        print("Status code:", drives_response.status_code)
        print("Response content:", drives_response.text)
        exit(1)

    return drive_id

# Cache dictionary
file_metadata_cache = {}

def doSharepointRequest(sharepoint_site, site_name, drive_name, file_relative_path):
    # Check if the file metadata is already cached
    cache_key = (sharepoint_site, site_name, drive_name, file_relative_path)
    if cache_key in file_metadata_cache:
        return file_metadata_cache[cache_key]
    
    # Azure AD and SharePoint settings
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    tenant_id = os.getenv("TENANT_ID")
    authority = f'https://login.microsoftonline.com/{tenant_id}'

    # Create an MSAL confidential client instance
    app = msal.ConfidentialClientApplication(
        client_id,
        authority=authority,
        client_credential=client_secret
    )

    # Acquire a token for Microsoft Graph API
    token = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])

    sharepoint_fields = {}
    if 'access_token' in token:
        # Find the drive id
        site_id = getSiteID(sharepoint_site, site_name, token)
        # Find the site id
        drive_id = getDriveID(site_id, drive_name, token)

        # Use the token to access Microsoft Graph API for SharePoint
        headers = {
            'Authorization': 'Bearer ' + token['access_token']
        }
        
        # Access the specific file metadata
        file_response = requests.get(
            f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{file_relative_path}:/listItem",
            headers=headers
        )

        if file_response.status_code == 200:
            file_metadata = file_response.json()
            # print("\n\nFile Metadata:", file_metadata)
            sharepoint_fields = file_metadata['fields']
            # print("\n\nFile Fields:", sharepoint_fields)
            # Rename the keys
            sharepoint_fields['Dokumentnavn'] = drive_name + "/" + file_relative_path
            sharepoint_fields = rename_key(sharepoint_fields, 'Test', 'Status')
            sharepoint_fields = rename_key(sharepoint_fields, 'Kunde_x0020__x002F__x0020_Samarbeidspartner', 'Kunde')
            sharepoint_fields = rename_key(sharepoint_fields, 'Fag', 'Tjenesteområde')

        else:
            print("Failed to retrieve file metadata.")
            print("Status code:", file_response.status_code)
            print("Response content:", file_response.text)
    else:
        print("Error acquiring token:", token.get("error"), token.get("error_description"))
    return sharepoint_fields

def has_topfolder(relative_path):
    # Sjekker om det finnes minst én folder i stien før filnavnet
    return '/' in relative_path

def topfolder_of(relative_path):
    # Returnerer den første mappen i stien
    if has_topfolder(relative_path):
        return relative_path.split('/')[0]
    return None

def requestSharepointFields(sharepoint_site, site_name, drive_name, file_relative_path):
    # Will get metadata from root level folder (if exists) and inherit its Sharepoint fields

    # First get the actual fields
    sharepoint_fields = doSharepointRequest(sharepoint_site, site_name, drive_name, file_relative_path)

    # Then inherit root folder fields if it is there
    topfolder_fields = {}
    if has_topfolder(file_relative_path):
        topfolder_fields = doSharepointRequest(sharepoint_site, site_name, drive_name, topfolder_of(file_relative_path))
        for field in ['Status', 'Kunde', 'Marked', 'Tjenesteområde', 'Konsulent']:
            if field in topfolder_fields:
                sharepoint_fields[field] = topfolder_fields[field] # Inherit top folder field value

    return sharepoint_fields
    

def requestSharepointHeader(sharepoint_site, site_name, drive_name, file_relative_path):
    sharepoint_fields = requestSharepointFields(sharepoint_site, site_name, drive_name, file_relative_path)
    sharepoint_header = make_header(sharepoint_fields)
    return sharepoint_header