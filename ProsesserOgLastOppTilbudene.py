import os
import openai
import logging
from dotenv import load_dotenv
import csv
import json
from pathlib import Path
from datetime import datetime
import urllib.parse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler("pipeline_download.log")]
)

# Get the current date and time
current_datetime = datetime.now()
formatted_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S")

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
OpenAIclient = openai.OpenAI(api_key=openai.api_key)

# Directory containing the files
output_dir = 'downloaded_files'
project_dir = 'concatenated_projects'
summary_dir = 'summarized_projects'
files_found = 0
projects_found = 0

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

""" # Read the CSV file to get filenames and URLs
project_database = 'project_mapping.csv'
project_path_urls = {}
if Path(project_database).exists():
    print("Reading the existing database of concatenated project files:")
    with open(project_database, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            filename, url = row
            project_path_urls[filename] = url
            projects_found += 1
    print(f"Read {len(project_path_urls)} files from database.")
else:
    print(f"Required file {project_database} for concatenated project files does not exist.")
    exit(1) """

# define a retry decorator
def retry_with_exponential_backoff(
    func,
    initial_delay: float = 1,
    exponential_base: float = 2,
    jitter: bool = True,
    max_retries: int = 10,
    errors: tuple = (openai.RateLimitError,),
):
    """Retry a function with exponential backoff."""
 
    def wrapper(*args, **kwargs):
        # Initialize variables
        num_retries = 0
        delay = initial_delay
 
        # Loop until a successful response or max_retries is hit or an exception is raised
        while True:
            try:
                return func(*args, **kwargs)
 
            # Retry on specific errors
            except errors as e:
                # Increment retries
                num_retries += 1
 
                # Check if max retries has been reached
                if num_retries > max_retries:
                    raise Exception(
                        f"Maximum number of retries ({max_retries}) exceeded."
                    )
 
                # Increment the delay
                delay *= exponential_base * (1 + jitter * random.random())
 
                # Sleep for the delay
                time.sleep(delay)
 
            # Raise exceptions for any errors not specified
            except Exception as e:
                raise e
 
    return wrapper
    
@retry_with_exponential_backoff
def Query_OpenAI_Completion(instruction, query_text):
    # Call the OpenAI API for a general ChatGPT chat completion
    try:
        # Call OpenAI's completion API for ChatGPT
        completion = OpenAIclient.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": instruction},
                {
                    "role": "user",
                    "content": query_text
                }
            ]
        )
        # Extract and return the OpenAI ChatgTP response
        #return completion.choices[0].message
        # Extract and return the OpenAI ChatGPT response content only
        response_content = completion.choices[0].message.content
        
        # Check if the response content is in JSON format and strip it if needed
        if response_content.startswith("```json"):
            response_content = response_content.strip("```json\n").strip("```")
        
        return response_content
    
    except Exception as e:
        logging.warning(f"An error occurred: {e}")
        return None

import json

@retry_with_exponential_backoff
def Query_OpenAI_Completion_JSON(instruction, query_text):
    """
    Calls the OpenAI API to analyze CV content and return the result as a JSON object.
    
    Args:
        instruction (str): The system instruction for the assistant.
        query_text (str): The consultant's anonymized CV text.

    Returns:
        dict: Parsed JSON response from OpenAI if successful, or None if there's an error.
    """
    try:
        # Call OpenAI's completion API for ChatGPT
        completion = OpenAIclient.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": query_text}
            ]
        )
        
        # Extract the response content
        response_content = completion.choices[0].message.content

        # Check if the response content is in JSON format and strip if needed
        if response_content.startswith("```json"):
            response_content = response_content.strip("```json\n").strip("```")
        
        # Attempt to parse response content as JSON
        try:
            return json.loads(response_content)
        except json.JSONDecodeError as json_error:
            logging.error(f"Failed to decode JSON response: {json_error}")
            logging.error(f"Response content was: {response_content}")
            return None
    
    except Exception as e:
        logging.warning(f"An error occurred: {e}")
        return None

def Query_OpenAI_Assistant(assistant_id, query_text):
    # Call the OpenAI API for a chat completion from a predefined assistant
    myassistant = OpenAIclient.beta.assistants.retrieve(assistant_id)
    #print(myassistant.name)

    mythread = OpenAIclient.beta.threads.create()
    #print(empty_thread)

    message = OpenAIclient.beta.threads.messages.create(
        thread_id=mythread.id,
        role="user",
        content=query_text
    )

    run = OpenAIclient.beta.threads.runs.create_and_poll(
        thread_id=mythread.id,
        assistant_id=myassistant.id
    )

    response = ""
    if run.status == 'completed': 
        messages = OpenAIclient.beta.threads.messages.list(
            thread_id=mythread.id
        )
        response = messages.data[0].content[0].text.value
    else:
        print(run.status)

    return response

Kompetansekrav_Instruction = """
Du er en tjeneste som mottar en samling dokumenter om forespørsel (om konsulentbistand eller rammeavtale om konsulentbistand) og tilhørende tilbud fra konsulentselskapet A-2 Norge og deres partnere. 
Du skal som tjeneste returnere informasjon i en presis, flat JSON-struktur.
Du mottar teksten som er i alle dokumentene i tilfeldig rekkefølge, adskilt med en metadata seksjoner, som inkluderer kundens forespørsel om tjenester og A-2 Norges svar på denne forespørselen.
Følg disse trinnene for å ekstrahere riktig informasjon:

Trinn 1: Gjennomgå Dokumentene
Identifiser dokumentene: Finn dokumentene som gjelder kundens forespørsel.

Trinn 2: Trekk ut alle konsulentroller som etterspørres og kravene til konsulentrollen.
Noen forespørsler har ikke beskrevet hvilke konsulentroller som kreves. Da er konsulentrolle "Ingen".

Trinn 3: For hver konsulentrolle som beskrives, trekk ut all informasjon etterspurt i JSON-strukturen nedenfor. En rad per konsulentrolle. 

Trinn 4: Instruksjon for svar:
Du skal kun returnere en flat JSON-struktur uten underliggende objekter eller lister, og som følger disse regler:
1. Bruk eksakt samme nøkkelnavn som angitt i strukturen. Ingen variasjoner i store og små bokstaver, ingen ekstra mellomrom eller spesialtegn.
2. Returner alle felter som type tekststreng. Hvis verdien er ukjent returner en tom streng.
3. For årstall returner enten årstallet (4 tall) eller strengen "ukjent".

Besvar med følgende JSON feltstruktur som er en liste med objekter og her vises en:
[{
    "Konsulentrolle": "Kort navn på rolle, f.eks. 'Prosjektleder for prosjekt x'",
    "Rollekategori": "Kategorisert rollen som f.eks. Prosjektleder, Arkitekt, Endringsleder, Testleder, Kvalitetssikrer.",
    "Kompetansekrav": "Hvilken kompetanse må konsulenten ha?",
    "Erfaringskrav": "Hvilken erfaring må konsulenten ha?",
    "Konsulentegenskaper": "Hvilke egenskaper må konsulenten ha?",
    "Kundenavn": "Hvilken virksomhet har sendt forespørselen?",
    "Bransje": "Hvilken bransje gjelder forespørselen?",
    "Årstall": "Hvilket år ble forespørselen sendt?"
}]
"""

def ekstraher_kompetansekrav(file_path):
    file_body = ""
    competency_info = None
    if os.path.exists(file_path): # Cannot generate summary if file does not exist
        with open(file_path, 'r', encoding='utf-8') as infile:
            maxlines = 6400 # Reading max 7000 lines to avoid too long document for OpenAI assistant to summarize
            for _ in range(maxlines):
                line = infile.readline()
                if not line: # Stop if there are no more lines
                    break
                file_body += line

        print(f"Ekstraherer kompetansekrav fra {file_path}")
        # Analyze all text with OpenAI assistant
        try:
            competency_info = Query_OpenAI_Completion_JSON(Kompetansekrav_Instruction, file_body)
        except Exception as e:
            print(f"Error analyzing folder {file_path}: {e}")
    return competency_info

def oppsummer_tilbud(file_path):
    # Construct the full output file path
    filename = os.path.basename(file_path)
    output_file_path = os.path.join(summary_dir, filename)
    file_body = ""
    summarized_body = ""
    summary_assistant_id = "asst_NV2jwGQmu8lg1r9M6LKG1sSr"

    if not os.path.exists(output_file_path): # Skip / Do not regenerate existing summaries
        if os.path.exists(file_path): # Cannot generate summary if file does not exist
            with open(file_path, 'r', encoding='utf-8') as infile:
                maxlines = 6400 # Reading max 7000 lines to avoid too long document for OpenAI assistant to summarize
                for _ in range(maxlines):
                    line = infile.readline()
                    if not line: # Stop if there are no more lines
                        break
                    file_body += line

            print(f"Oppsummering av tilbud {file_path}")

            # Call the OpenAI API for a chat completion
            myassistant = OpenAIclient.beta.assistants.retrieve(summary_assistant_id)
            #print(myassistant.name)

            mythread = OpenAIclient.beta.threads.create()
            #print(empty_thread)

            message = OpenAIclient.beta.threads.messages.create(
                thread_id=mythread.id,
                role="user",
                content=file_body
            )

            run = OpenAIclient.beta.threads.runs.create_and_poll(
                thread_id=mythread.id,
                assistant_id=myassistant.id
            )

            response = ""
            if run.status == 'completed': 
                messages = OpenAIclient.beta.threads.messages.list(
                    thread_id=mythread.id
                )
                response = messages.data[0].content[0].text.value
            else:
                print(run.status)

            # Store the response text in a variable
            if len(response) < 10:
                summarized_body = file_body
            else:
                summarized_body = response
            # print("Anonymized Body:", anonymized_body)

        

        # Write `summarized_body` to the file
        with open(output_file_path, 'w', encoding='utf-8') as file:
            file.write(summarized_body)

        # Print the full file path
        # print("File saved to:", output_file_path)

    return output_file_path

def is_a_CV(filename):
    # Files with the following strings in relativeurl with matching case will be removed
    clear_filename = urllib.parse.unquote(filename, encoding='utf-8')
    strings_in_CV_names = ["CV_", "CV ", "_CV", " CV"]
    looks_like_CV = False
    for cv_string in strings_in_CV_names:
        if cv_string in clear_filename:
            looks_like_CV = True
            #print(f"** CV **: {clear_filename}")
            break
    return looks_like_CV

def qualifies_for_upload_tilbudsbase(filename, relativeurl):
    include_in_dataset = True
    
    if filename in file_metadata:
        metadata = file_metadata[filename]
    else:
        metadata = {}

    # Files with the following strings in relativeurl regardless of case will be removed
    unwanted_expression_in_URL = ["erklæring", "/under arbeid/", "/Inspirasjon/", "code of conduct", "Generelle vilkår for konsulent",
                               "/Gartner", "Tripletex", "tilbudte konsulenter", "Justerte priser", "Kvalifikasjonsgrunnlag",
                               "/Bakgrunnsmateriale/", "non-disclosure", "Kompetansematrise", "Revisors beretning", "godkjenning av bemanningsforetak",
                                "Miljøfyrtårnsertifikat", "/Mal for", "Bekreftelse på forlengelse", "årsberetning", "årsrapport",
                                 "Forsikringsbekreftelse", "årsregnskap", "formelle dokumenter og attester", "Fullmakt",
                                  "Miljøpolicy", "Arsrapport", "ESG spørsmål og svar", "kladd", "uferdig", "Sladdet",
                                   "Svarskjema-erfaring", "Kontraktsvilkar-rammeavtale", "ny pris", " priser ", "varsel om", "rammeavtale priser",
                                    "/Underleverandører/", "generell avtaletekst", "generell_avtaletekst", "Retningslinjer for",
                                     "Vedlegg til kravspesifik", "Prosedyre", "Mal innmelding", "etisk handel", "Endringsprotokoll",
                                      "Miljøledelsesstandard", "Formelle dokumenter", "/Markedsdialog/",
                                      "/Referanser besvarelse/", "/Referanser/", "veiledende kunngjøring",
                                      "Informasjon om resultat av konkurransen", "/diverse/", "/Bakgrunnsinfo/"]
    
    for unwantedstring in unwanted_expression_in_URL:    
        if urllib.parse.quote(unwantedstring).lower() in relativeurl.lower():
            include_in_dataset = False

    # Files with the following strings in relativeurl with matching case will be removed
    unwanted_strings_in_URL = [] #"CV_", "CV ", "_CV", " CV" ]
    
    for unwantedstring in unwanted_strings_in_URL:
        if urllib.parse.quote(unwantedstring) in relativeurl:
            include_in_dataset = False

    # Files with the following strings in filename regardless of case will be removed
    unwanted_expression_in_filename = ["prisvarsel", "prisendring", "Firmaattest", "Kredittvurdering", "attest", "garanti", "sertifisering", 
                                       "kvalitetssystem", "Databehandleravtale", "aarsregnskap", "Besvarelse av generelle krav", "Mal ", "Mal_",
                                        "Referanseoppdrag", "Referanse", "Bruksanvisning", "Retningslinje", "sladding", "sladdet", 
                                        "Samhandlingsavta", "Oppstartsmøte", "Administrative bestemmelser", "Pris og prisbestemmelser",
                                         "Kontraktskrav lønns- og arbeidsvilkår", "Tildelingskriterier" ] 
    
    for unwantedstring in unwanted_expression_in_filename:    
        if urllib.parse.quote(unwantedstring).lower() in filename.lower():
            include_in_dataset = False

    # Files with the following strings in filename with matching case will be removed
    unwanted_strings_in_filename = ["NDA_", "NDA ", "_NDA", " NDA" ]
    
    for unwantedstring in unwanted_strings_in_filename:
        if urllib.parse.quote(unwantedstring) in filename:
            include_in_dataset = False

    return include_in_dataset

# Create folder for concatenated project files
if not os.path.exists(project_dir):
    os.makedirs(project_dir)

# Create folder for concatenated project files
if not os.path.exists(summary_dir):
    os.makedirs(summary_dir)

# Prepare files for upload
file_paths = []
found_corefilenames = []
project_path_urls = {}
project_link = "_undefined_"
previous_rootfolder = "_undefined_"
previous_link = "_undefined_"
for filename in downloaded_file_urls.keys():
    file_path = os.path.join(output_dir, filename)
    fileurl = downloaded_file_urls[filename]
    relativeurl = fileurl.split("/Tilbud%20og%20avtaler")[-1]
    rooturl = fileurl.split("/Tilbud%20og%20avtaler")[0] + "/Tilbud%20og%20avtaler/"
    urlfilename = relativeurl.split("/")[-1]
    corefilename, extension = os.path.splitext(urlfilename)
    root_folder = relativeurl.split('/')[1]

    if root_folder != previous_rootfolder and previous_rootfolder != "_undefined_":
        print("ANALYSE AV:" + urllib.parse.unquote(root_folder, encoding='utf-8'))
        found_corefilenames = []
        # Concatenate all files in project into just one file.
        project_out_file = f"{project_dir}\\{projects_found:04d}_{previous_rootfolder}.txt"
        project_link = rooturl + root_folder
        project_path_urls[project_out_file] = previous_link
        with open(project_out_file, 'w', encoding='utf-8') as p_outfile:
            unquoted_previous_rootfolder = urllib.parse.unquote(previous_rootfolder, encoding='utf-8')
            p_outfile.write(f"TILBUD:{unquoted_previous_rootfolder}\n")
            for found_file in file_paths:
                p_outfile.write("\n\n------\n")
                with open(found_file, 'r', encoding='utf-8') as infile:
                    maxlines = 700
                    if is_a_CV(found_file):
                        maxlines = 10 # Only the first lines of the CVs
                    #else:
                    #    print((f"** NOT CV ** {found_file}"))
                    for _ in range(maxlines): 
                        line = infile.readline()
                        if not line: # Stop if there are no more lines
                            break
                        p_outfile.write(line)
        file_paths = []
        projects_found += 1

    if qualifies_for_upload_tilbudsbase(filename, relativeurl):
        if corefilename not in found_corefilenames:
            if not os.path.exists(file_path):
                print(f"File {file_path} does not exist, skipping.")
                continue
            file_paths.append(file_path)
            found_corefilenames.append(corefilename)
            # print("    " + relativeurl)
            files_found += 1
        #else:
        #    print("  REPEATING skipped:" + urlfilename)
    #else:
    #    print(" SKIP:" + relativeurl)
    previous_rootfolder = root_folder
    previous_link = project_link

# Concatenate files in the very last project folder into just one file.
project_out_file = f"{project_dir}\\{projects_found:04d}_{previous_rootfolder}.txt"
project_link = rooturl + root_folder
project_path_urls[project_out_file] = previous_link
with open(project_out_file, 'w', encoding='utf-8') as p_outfile:
    unquoted_previous_rootfolder = urllib.parse.unquote(previous_rootfolder, encoding='utf-8')
    p_outfile.write(f"TILBUD:{unquoted_previous_rootfolder}\n")
    for found_file in file_paths:
        p_outfile.write("\n\n------\n")
        with open(found_file, 'r', encoding='utf-8') as infile:
            maxlines = 700
            if is_a_CV(found_file):
                maxlines = 10 # Only the first lines of the CVs
            #else:
            #    print((f"** NOT CV ** {found_file}"))
            for _ in range(maxlines): 
                line = infile.readline()
                if not line: # Stop if there are no more lines
                    break
                p_outfile.write(line)

print(f"Found {files_found} relevant files for upload!")
print(f"Written as {projects_found} concatenated project files.")

# Write raw tilbud/project mapping-file
with open('project_mapping.csv', 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.writer(csvfile)
    # Write the header
    writer.writerow(['Filename', 'URL'])

    for project_file in project_path_urls.keys():
        # Skriv til mapping-filen
        url = project_path_urls[project_file]
        filename = os.path.basename(project_file)
        writer.writerow([filename, url])

#Ekstraher Kompetansekrav fra alle forespørsler
alle_kompetansekrav = []
if projects_found > 0:
    # Hent ut alle kompetansekrav fra alle prosjektene
    for pro_path in list(project_path_urls.keys()): #[:25]:
        kompetanse_krav = ekstraher_kompetansekrav(pro_path)
        print(kompetanse_krav)
        if kompetanse_krav != None:
            for entry in kompetanse_krav:
                alle_kompetansekrav.append(entry)

# Skriv alle kompetansekrav til CSV fil
with open('kompetansekrav.csv', 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.writer(csvfile)
    # Write the header
    writer.writerow(["Konsulentrolle", "Rollekategori", "Kompetansekrav", "Erfaringskrav", "Konsulentegenskaper", "Kundenavn", "Bransje", "Årstall"])
    # Write the content
    for kompetanse_krav in alle_kompetansekrav:
        if kompetanse_krav != None:
            Konsulentrolle = kompetanse_krav["Konsulentrolle"]
            Rollekategori = kompetanse_krav["Rollekategori"]
            Kompetansekrav = kompetanse_krav["Kompetansekrav"]
            Erfaringskrav = kompetanse_krav["Erfaringskrav"]
            Konsulentegenskaper = kompetanse_krav["Konsulentegenskaper"]
            Kundenavn = kompetanse_krav["Kundenavn"]
            Bransje = kompetanse_krav["Bransje"]
            Årstall = kompetanse_krav["Årstall"]
            if Konsulentrolle.lower() != "ingen" and Konsulentrolle != "":
                writer.writerow([Konsulentrolle, Rollekategori, Kompetansekrav, Erfaringskrav, Konsulentegenskaper, Kundenavn, Bransje, Årstall])
#exit(0)
# Oppsummer alle tilbudsdokumenter så de er søkbare
summarized_tilbud_urls = {}
if projects_found > 0:
    # Convert all project files to a summarized file
    for pro_path in project_path_urls.keys():
        summarized_filepath = oppsummer_tilbud(pro_path)
        summarized_tilbud_urls[summarized_filepath] = project_path_urls[pro_path]

# Write summary mapping-file
with open('summary_mapping.csv', 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.writer(csvfile)
    # Write the header
    writer.writerow(['Filename', 'URL'])

    for summary_file in summarized_tilbud_urls.keys():
        # Skriv til mapping-filen
        url = summarized_tilbud_urls[summary_file]
        filename = os.path.basename(summary_file)
        writer.writerow([filename, url])

# Last opp project summaries til Vector store
if projects_found > 0:
    # Create Vector Store if not existing
    print(f"Connecting to OpenAI.")
    OpenAIclient = openai.OpenAI(api_key=openai.api_key)

    print("Creating a vector store. Status below:")
    vector_store = OpenAIclient.beta.vector_stores.create(
        name=f"Summerte tilbudsfiler A-2 dato {formatted_datetime}"
    )
    print(vector_store)

    # Define batch size for upload
    batch_size = 50
    total_batches = (projects_found + batch_size - 1) // batch_size
    print(f"Total number of batches: {total_batches}")

    # Upload files in batches
    project_paths = []
    for summaryfile_path in summarized_tilbud_urls.keys():
        project_paths.append(summaryfile_path)
    for batch_num, i in enumerate(range(0, projects_found, batch_size), start=1):
        batch_file_paths = project_paths[i:i+batch_size]
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
            file_batch = OpenAIclient.beta.vector_stores.file_batches.upload_and_poll(
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
