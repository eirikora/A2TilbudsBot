# A-2 Tilbudsbot
Dette er verktøyet som crawler A-2 Sharepoint mappene for "Tilbud og Avtaler", preparerer og filtrerer innholdet og lastert det opp i en Vektordatabase for en KI assistent.

### Forutsetninger / Fremgangsmåte
1. Det er lagt inn en snarvei til OneDrive fra https://a2norge.sharepoint.com/Tilbud%20og%20avtaler/Forms/AllItems.aspx for den brukeren som kjører dette verktøyet

2. Python v 3.10 eller senere er installert på maskinen

3. Man har kjørt kommandoen for å installere bibliotekene:
```
   pip install docx2txt pycparser msal pdfminer.six python-dotenv requests setuptools urllib3 sharepoint_fields
```
5. For å laste ned alle filer og data til lokal maskin, kjør først nedlastningen med kommandoen (Kan ta 4-8 timer å fullføre første gang da særlig nedlastning via OneDrive tar litt tid):
```
   python LastNedTilbudene.py
```
6. For å skape en Vectorstore for tilbudene med relevante dokumenter kjør kommando
```
   python LastOppTilbudsbase.py
```

Utviklet av Eirik Y. Øra, +47  919 06 353, eirik.ora@gmail.com 
