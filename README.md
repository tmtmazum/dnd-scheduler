# Quest Weekend

A small Flask app for finding a Dungeons & Dragons session time that works for the party. Adventurers can choose any Saturday or Sunday date in the next two calendar months and mark morning (10:30 AM–2:30 PM), afternoon (1:30–5:00 PM), and/or evening (5:00–9:00 PM) as available. Choices are saved to AWS DynamoDB and shown on a shared availability board.

## Run locally

1. Use Python 3.9 or newer and configure AWS credentials with permission to scan, write, and delete items in the DynamoDB table.
2. Install dependencies: `python -m pip install -r requirements.txt`
3. Start the app: `python app.py`
4. Open `http://127.0.0.1:5000` in your browser.

Create a DynamoDB table (in the configured AWS region) with partition key `name_key` of type String. The app stores one item per adventurer, including their saved name in `display_name`, plus `updated_at` and a `slots` list of date/period maps. Previously saved names appear as suggestions in the name combobox; users can also type a new name. The table must exist before starting the app.

Configuration uses the standard AWS credential chain (for example, an IAM role or locally configured AWS profile). Set `DYNAMODB_TABLE` to choose a table (default: `quest-weekend-availability`) and `AWS_REGION` (or `AWS_DEFAULT_REGION`) to select a region (default: `us-east-1`). For local DynamoDB testing, optionally set `DYNAMODB_ENDPOINT_URL`. Set `SECRET_KEY` to a random value before deploying beyond local development. Existing data from the previous SQLite version is not migrated automatically; export and import it into the DynamoDB item shape if it needs to be retained.

On Windows, use the AWS CLI to save credentials in your local AWS profile. Boto3 reads that profile automatically; the app does not need credentials in its code.

In PowerShell, run:
```
aws configure --profile dnd-sched
$env:AWS_PROFILE = "dnd-sched"
$env:AWS_REGION = "us-east-2"
$env:DYNAMODB_TABLE = "Trainwreck-Schedule"
python app.py
```

aws configure will prompt for your access key, secret key, and default region. Get credentials from an IAM identity that has `dynamodb:Scan`, `dynamodb:PutItem`, and `dynamodb:DeleteItem` permissions on your table. The profile is saved locally under `%USERPROFILE%\.aws`; don’t put credentials in the project or commit them. These PowerShell environment variables apply to the current terminal session.

To check which AWS identity the profile uses, run aws sts get-caller-identity --profile dnd-sched.


## How it works

- Enter a name, select at least one dated weekend time, and choose **Mark me ready**.
- The page redirects back to the refreshed board after saving.
- The board polls for new submissions every 15 seconds, so open pages stay current.
- Submitting again with the same name (case-insensitive) updates that adventurer’s availability.
- Click a Roll Call card to load that adventurer's current selections, then update and save them; an existing adventurer can clear their personal selections by saving an empty set.
- DM controls can confirm one board slot as the planned session, clear the planned session, or reset all availability while keeping saved names.
- Grant the app identity `dynamodb:Scan`, `dynamodb:PutItem`, and `dynamodb:DeleteItem` on the configured table. The app does not currently authenticate DM actions, so anyone with access to the board can use those controls.
