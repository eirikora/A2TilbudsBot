import os
import openai
from dotenv import load_dotenv
import csv
import json
from pathlib import Path
from datetime import datetime

# Get the current date and time
current_datetime = datetime.now()
formatted_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S")

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Directory containing the files
output_dir = 'downloaded_files'

# Read the CSV file to get filenames and URLs
file_database = 'mapping.csv'
downloaded_file_urls = {}
if Path(file_database).exists():
    print("Reading the existing database of downloaded files:")
    with open(file_database, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            filename, url = row
            downloaded_file_urls[filename] = url
    print(f"Read {len(downloaded_file_urls)} files from database.")
else:
    print(f"Required file {file_database} does not exist.")
    exit(1)

file_metadata = {}
# Read the json file with file metadata
if os.path.exists('file_metadata.json'):
    with open('file_metadata.json', 'r') as f:
        file_metadata = json.load(f)

def qualifies_for_upload_tilbudsbase(filename, file_path):
    include_in_dataset = True
    
    if filename in file_metadata:
        metadata = file_metadata[filename]
    else:
        metadata = {}

    if "CV" in filename:
        include_in_dataset = False

    if "under arbeid" in file_path:
        include_in_dataset = False

    if "Konkurransegrunnlag" in file_path:
        include_in_dataset = False
    
    if "Inspirasjon" in file_path:
        include_in_dataset = False

    if 'Status' not in metadata:
        include_in_dataset = False

    if 'Status' in metadata and metadata['Status'] != 'Vunnet':
        include_in_dataset = False

    return include_in_dataset

# Prepare files for upload
file_paths = []
files_found = 0
for filename in downloaded_file_urls.keys():
    file_path = os.path.join(output_dir, filename)
    if qualifies_for_upload_tilbudsbase(filename, file_path):
        if not os.path.exists(file_path):
            print(f"File {file_path} does not exist, skipping.")
            continue
        file_paths.append(file_path)
        files_found += 1
print(f"Found {files_found} relevant files for upload!")

if files_found > 0:
    # Create Vector Store if not existing
    print(f"Connecting to OpenAI.")
    client = openai.OpenAI(api_key=openai.api_key)

    print("Creating a vector store. Status below:")
    vector_store = client.beta.vector_stores.create(
        name=f"Tilbudsfiler A-2 dato {formatted_datetime}"
    )
    print(vector_store)

    # Define batch size for upload
    batch_size = 50
    total_batches = (len(file_paths) + batch_size - 1) // batch_size
    print(f"Total number of batches: {total_batches}")

    # Upload files in batches
    for batch_num, i in enumerate(range(0, len(file_paths), batch_size), start=1):
        batch_file_paths = file_paths[i:i+batch_size]
        print(f"Processing batch {batch_num}/{total_batches} with {len(batch_file_paths)} files.")

        # Open files in the batch
        print(f"Opening {len(batch_file_paths)} files.")
        try:
            file_streams = [open(path, "rb") for path in batch_file_paths]
        except Exception as e:
            print(f"Error opening the files in batch {batch_num}: {e}")
            exit(1)

        # Upload the batch
        try:
            print(f"Uploading batch {batch_num} of {len(batch_file_paths)} files. This may take some time...")
            file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
                vector_store_id=vector_store.id,
                files=file_streams,
                chunking_strategy={
                    "type": "static",
                    "static": {
                        "chunk_overlap_tokens": 200,
                        "max_chunk_size_tokens": 2000
                    }
                }
            )
        except Exception as e:
            print(f"Error uploading batch {batch_num}: {e}")
            exit(1)
        finally:
            # Close file streams
            for f in file_streams:
                f.close()

        # Check the status of files
        print(f"Batch {batch_num} upload ended with status: {file_batch.status}!\n")
