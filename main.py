from __future__ import print_function
import os.path
import pandas as pd
import json
import csv
import re

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

# The ID and range of a sample spreadsheet.
SAMPLE_SPREADSHEET_ID = '1TD1co-1vf4Z7VDq_uZXjpbJBHX6Mm0GOC5nfg0jQggs'
SAMPLE_RANGE_NAME = 'Notion Export2!A1:N1000'


def main():
    """Pulls token data from Gsheet and inserts into pandas df"""

    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('sheets', 'v4', credentials=creds)

        # Call the Sheets API
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=SAMPLE_SPREADSHEET_ID,
                                    range=SAMPLE_RANGE_NAME).execute()
        values = result.get('values', [])

        if not values:
            print('No data found.')
            return

        # Determine the maximum number of columns in the values
        max_cols = max(len(row) for row in values)

        # Fill empty cells with None to ensure consistent number of columns
        filled_values = [row + [None] * (max_cols - len(row)) for row in values]

        # Create a pandas DataFrame from the filled values
        df = pd.DataFrame(filled_values[1:], columns=filled_values[0])

        # Convert DataFrame to JSON
        json_data = df.to_json(orient='records')
        json_data = json.loads(json_data)

        # Return the JSON data
        return json_data

    except HttpError as err:
        print(err)


def convert_json_to_backend_format_asset(json_data):
    """Turns JSON data into asset definitions"""

    backend_data = []
    for item in json_data:
        var_name = item["Symbol"].replace(" ", "").upper()
        display_name = item["Symbol"].upper()
        description = item["Full Name"].upper()
        icon = f"{item['Full Name'].lower()}.svg"
        asset_type = "CRYPTO"

        backend_item = f"var {var_name} = &Asset{{\n" \
                       f"\tID:          \"{var_name}\",\n" \
                       f"\tDisplayName: \"{display_name}\",\n" \
                       f"\tDescription: \"{description}\",\n" \
                       f"\tIcon:        \"{icon}\",\n" \
                       f"\tType:        {asset_type},\n" \
                       f"\tFromRestriction: &Restriction{{\n" \
                       f"\t\tDisabled:              false,\n" \
                       f"\t\tDisplay:               true,\n" \
                       f"\t\tRestrictNonStablyUser: false,\n" \
                       f"\t}},\n" \
                       f"\tToRestriction: &Restriction{{\n" \
                       f"\t\tDisabled:              false,\n" \
                       f"\t\tDisplay:               true,\n" \
                       f"\t\tRestrictNonStablyUser: false,\n" \
                       f"\t}},\n" \
                       f"}}"

        backend_data.append(backend_item)

    return backend_data


def convert_json_to_backend_format_options(json_data):
    """Turns JSON data into option definitions"""

    backend_data = []
    for item in json_data:
        var_name = item["Network"].upper() + "_" + item["Symbol"].upper()
        token_address = item["Main Token Address URL"].split("/")[-1]
        token_decimals = item["Token Decimals"]

        backend_item = f"var {var_name} = createOptionDefinition(\n" \
                       f"\tassets.{item['Symbol']},\n" \
                       f"\tnetworks.{item['Network'].upper()},\n" \
                       f"\t\"{token_address}\",\n" \
                       f"\t{token_decimals},\n" \
                       f"\t&assets.Restriction{{Disabled: false, Display: true, RestrictNonStablyUser: false}},\n" \
                       f"\t&assets.Restriction{{Disabled: false, Display: true, RestrictNonStablyUser: false}},\n" \
                       f"\t[]*venues.Venue{{venues.{item['Venue']}}},\n" \
                       f"\t[]*venues.Venue{{venues.{item['Venue']}}},\n" \
                       f")"

        backend_data.append(backend_item)

    return backend_data


json_data = main()

option_definitions = convert_json_to_backend_format_asset(json_data)
asset_definitions = convert_json_to_backend_format_options(json_data)


# with open('data.json', 'w') as json_file:
#     json_file.write(data)

if json_data is not None and isinstance(json_data, list) and len(json_data) > 0:
    option_definitions = convert_json_to_backend_format_options(json_data)
    asset_definitions = convert_json_to_backend_format_asset(json_data)

    with open('asset_definitions.go', 'w') as json_file:
        json_file.write('\n'.join(asset_definitions))
        print("Data has been written to asset_definitions")

    with open('option_definitions.go', 'w') as json_file:
        json_file.write('\n'.join(option_definitions))
        print("Data has been written to option_definitions")

else:
    print('Invalid or empty JSON data returned from the main function.')

# Read the contents of the options_definitions.json file
with open('option_definitions.go', 'r') as file:
    data = file.read()

# Extract var names & put into txt file
var_names = []
lines = data.split("\n")
for line in lines:
    if line.startswith("var"):
        var_name = line.split()[1].strip("=")
        var_names.append(var_name)

# Add commas after each var name
var_names_with_commas = [var_name + "," for var_name in var_names]

# Write the var names to a text file
with open('variable_names.txt', 'w') as file:
    file.write('\n'.join(var_names_with_commas))
    print("Data has been written to variables_names.txt")

# Read the content of the JSON file as a string
with open('option_definitions.go') as file:
    json_content = file.read()

# Extract the data using regular expressions
data_list = re.findall(r'var\s+(\w+)\s+=\s+createOptionDefinition\(\n\s*assets\.(\w+),\n\s*networks\.(\w+),\n\s*"(.+?)",\n\s*(\d+)', json_content)

# Open the CSV file in write mode
filename = 'notion_output.csv'
with open(filename, 'w', newline='') as file:
    writer = csv.writer(file)

    # Write the header row to the CSV file
    writer.writerow(['Variable', 'Symbol', 'Network', 'Full Name', 'Token Decimals'])

    # Process each data entry and append rows to the CSV file
    for item in data_list:
        variable, symbol, network, full_name, token_decimals = item

        # Write the extracted information as a row in the CSV file
        writer.writerow([variable, symbol, network, full_name, token_decimals])

print("Data has been written to", filename)

