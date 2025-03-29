import openai
import csv
import time
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Filbaner
input_file = "kompetansekrav.csv"
output_file = "korrigerte_kompetansekrav.csv"

# Tillatte rollekategorier
allowed_categories = [
    "Prosjektledelse", "Lede agilt team", "Programledelse", "Endringsledelse",
    "Virksomhetsarkitektur", "Løsningsarkitektur", "Rådgivning forretning", "Rådgivning teknisk",
    "Offentlig kvalitetssikring", "Test og kvalitetsikring", "Økonomi og analyse", "Utviklingsrolle",
    "Produkt- og tjenesteansvar", "Prosessledelse og fasilitering", "Kurs og opplæring", "Midlertidig lederrolle"
]

def classify_role(rollekategori, konsulentrolle, kompetansekrav):
    """Sender en forespørsel til OpenAI's API for å klassifisere rollekategori."""
    prompt = f"""
    Du er en ekspert i klassifisering av roller innen IT- og forretningsrådgivning. 
    Kategoriser følgende rolle i en av de forhåndsdefinerte kategoriene:
    
    - Konsulentrolle: {konsulentrolle}
    - Eksisterende Rollekategori: {rollekategori}
    - Kompetansekrav: {kompetansekrav}
    
    Velg den mest passende kategorien fra denne listen:
    {', '.join(allowed_categories)}
    
    Svar kun med kategorien som best passer.
    """
    
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "system", "content": "Du er en ekspert i rollekategorisering."},
                      {"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Feil ved forespørsel: {e}")
        return "Ukategorisert"

# Leser CSV-fil og klassifiserer rad for rad
with open(input_file, newline='', encoding='utf-8') as csvfile, \
     open(output_file, 'w', newline='', encoding='utf-8') as output_csv:
    
    reader = csv.DictReader(csvfile)
    fieldnames = reader.fieldnames + ["Korrigert Rollekategori"]
    writer = csv.DictWriter(output_csv, fieldnames=fieldnames)
    writer.writeheader()

    i = 0
    for row in reader:
        old_category = row['Rollekategori']
        corrected_role = classify_role(row['Rollekategori'], row['Konsulentrolle'], row.get('Kompetansekrav', ''))
        row["Korrigert Rollekategori"] = corrected_role
        i += 1
        print(f"{i}:{old_category} ==> {corrected_role}")
        writer.writerow(row)
        time.sleep(1)  # For å unngå API-rate limit
        
print("Klassifiseringen er ferdig! Filen er lagret som 'korrigerte_kompetansekrav.csv'")
