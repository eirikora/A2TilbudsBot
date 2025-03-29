import os
import json
import csv
import zipfile
from urllib.parse import quote
from datetime import datetime
from pdfminer.high_level import extract_text
import docx2txt
from sharepoint_fields.requestSharepointFields import requestSharepointFields, make_header

# Initialiseringskoder
file_dates = {}
sequence_number = 0
file_metadata = {}
sharepoint_site = 'a2norge.sharepoint.com'
site_name = 'Intranett'
drive_name = 'Tilbud og avtaler'
encoded_drive_name = quote(drive_name)
#file_relative_path = '2021EKS FKJ - gjennomgang ved etablering av interim selskap .docx'
SHAREPOINT_ROOT = f"https://{sharepoint_site}/{encoded_drive_name}/"
DISKPATH = 'C:\\Users\\eor\\OneDrive - A-2 Norge AS\\Tilbud og avtaler\\'
output_folder = 'downloaded_files'

# Last inn lagrede datoer
if os.path.exists('file_dates.json'):
    with open('file_dates.json', 'r') as f:
        file_dates = json.load(f)

# Last inn lagrede metadata
if os.path.exists('file_metadata.json'):
    with open('file_metadata.json', 'r') as f:
        file_metadata = json.load(f)

# Last inn siste sekvensnummer
if os.path.exists('sequence_number.json'):
    with open('sequence_number.json', 'r') as f:
        sequence_number = json.load(f).get('sequence_number', 0)
else:
    sequence_number = 0

def generate_unique_name(file_path, sequence_number):
    seq_str = f"{sequence_number:04d}"
    original_name = os.path.splitext(os.path.basename(file_path))[0]
    extension = '.txt'  # eller '.html' hvis du velger det
    unique_name = f"{seq_str}_{original_name}{extension}"
    return unique_name

# Åpne mapping-filen i tillegg for lesing for å unngå duplikater
existing_mappings = {}
if os.path.exists('mapping.csv'):
    with open('mapping.csv', 'r', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            existing_mappings[row[1]] = row[0]

try:
    with open('mapping.csv', 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)

        root_folder = os.path.dirname(DISKPATH)
        current_folder = ""
        folder_fields = {}
        for root_dir, dirs, files in os.walk(DISKPATH):
            for file in files:
                file_path = os.path.join(root_dir, file)
                file_folder = os.path.dirname(file_path)
                file_main_folder = os.path.relpath(file_folder, DISKPATH)
                parts = file_main_folder.split(os.sep)
                file_main_folder = parts[0] if parts and parts[0] != '.' else ''
                last_modified = os.path.getmtime(file_path)

                if file_main_folder != current_folder: # Get hold of Sharepoint folder field data (as it also applies to files in that folder)
                    # print(f"Current folder: {file_folder}")
                    current_folder = file_main_folder
                    print(f"\nLASTER NED MAPPE: {file_main_folder}")
                    folder_fields = {}
                    # folder_fields = requestSharepointFields(sharepoint_site=sharepoint_site, site_name=site_name, drive_name=drive_name, file_relative_path=FOLDER_PATH.replace('\\', '/'))
                    # print(f"FOLDER HAR FIELDS: {folder_fields}\n")

                if file_path not in file_dates or file_dates[file_path] < last_modified:
                    # Oppdater filens siste endringsdato
                    file_dates[file_path] = last_modified

                    # Trekke ut tekst basert på filtype
                    extension = os.path.splitext(file)[1].lower()

                    try:
                        if extension == '.docx':
                            # Sjekk om filen er en gyldig zip-fil (docx er zip-format)
                            if zipfile.is_zipfile(file_path):
                                text = docx2txt.process(file_path)
                            else:
                                raise zipfile.BadZipFile("Filen er ikke en gyldig docx (zip-fil).")
                        elif extension == '.pdf':
                            text = extract_text(file_path)
                        else:
                            # Hopp over filtyper som ikke støttes
                            continue

                        # Generer unikt filnavn
                        sequence_number += 1
                        unique_name = generate_unique_name(file_path, sequence_number)

                        print(f"- Laster ned #{sequence_number}: {file_path} som {unique_name}")

                        # Lagre teksten til en fil
                        if not os.path.exists(output_folder):
                            os.makedirs(output_folder)
                        
                        # Generer URL
                        PATH = os.path.relpath(file_path, DISKPATH)
                        url = SHAREPOINT_ROOT + quote(PATH.replace('\\', '/'))

                        # Skriv til mapping-filen
                        writer.writerow([unique_name, url])

                        # Hent Sharepoint metadata for file og lagre
                        if folder_fields == {} and file_main_folder != "": # Hent først folder_fields om ikke root og de ikke har blitt hentet enda
                            # print(f"GETTING FOLDER DATA FOR: {file_main_folder}")
                            folder_fields = requestSharepointFields(sharepoint_site=sharepoint_site, site_name=site_name, drive_name=drive_name, file_relative_path=file_main_folder.replace('\\', '/'))
                        file_fields = requestSharepointFields(sharepoint_site=sharepoint_site, site_name=site_name, drive_name=drive_name, file_relative_path=PATH.replace('\\', '/'))
                        # print(f"File has fields: {file_fields}\n")
                        all_fields = {**folder_fields, **file_fields}
                        # print(f"All fields are then: {all_fields} \n\n")
                        file_metadata[unique_name] = all_fields
                        #print(f"SAVED {unique_name} file_fields!")

                        # Insert header at top and write file
                        text = make_header(file_fields) + "Document body:\n" + text
                        with open(os.path.join(output_folder, unique_name), 'w', encoding='utf-8') as text_file:
                            text_file.write(text)

                    except zipfile.BadZipFile as e:
                        print(f"Ugyldig docx-fil {file_path}: {e}")
                        # Logg feilen og fortsett
                        with open('error_log.txt', 'a', encoding='utf-8') as log_file:
                            log_file.write(f"{datetime.now()}: Ugyldig docx-fil {file_path}: {e}\n")
                        continue
                    except Exception as e:
                        # Generell feilbehandling
                        print(f"Feil under behandling av fil {file_path}: {e}")
                        # Logg feilen og fortsett
                        with open('error_log.txt', 'a', encoding='utf-8') as log_file:
                            log_file.write(f"{datetime.now()}: Feil under behandling av fil {file_path}: {e}\n")
                        continue

finally:
    # Sørg for at data lagres selv om det oppstår en feil
    with open('file_dates.json', 'w') as f:
        json.dump(file_dates, f)

    with open('sequence_number.json', 'w') as f:
        json.dump({'sequence_number': sequence_number}, f)

    with open('file_metadata.json', 'w') as f:
        json.dump(file_metadata, f)
