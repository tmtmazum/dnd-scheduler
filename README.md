# Quest Weekend

A small Flask app for finding a Dungeons & Dragons session time that works for the party. Adventurers can choose any Saturday or Sunday date in the next two calendar months and mark morning (10:30 AM–2:30 PM), afternoon (1:30–5:00 PM), and/or evening (5:00–9:00 PM) as available. Choices are saved to AWS DynamoDB and shown on a shared availability board.

## Run locally

1. Use Python 3.9 or newer and configure AWS credentials with permission to scan, read, write, and delete items in the DynamoDB table.
2. Install dependencies: `python -m pip install -r requirements.txt`
3. Start the app: `python app.py`
4. Open `http://127.0.0.1:5000` in your browser.

## Set the party password

Before the first login, configure AWS credentials and the table/region environment variables in the same terminal session, then run `flask --app app set-party-password`. Enter a passphrase of at least 12 characters when prompted. The app writes a salted PBKDF2 hash to a reserved item in DynamoDB; it never stores or logs the plain password. Run the same command again to change it.

Create a DynamoDB table (in the configured AWS region) with partition key `name_key` of type String. The app stores one item per adventurer, including their saved name in `display_name`, plus `updated_at` and a `slots` list of date/period maps. It stores the party password hash and confirmed-session metadata as reserved records in the same table. Previously saved names appear as suggestions in the name combobox; users can also type a new name. The table must exist before starting the app.

Configuration uses the standard AWS credential chain (for example, an IAM role or locally configured AWS profile). Set `DYNAMODB_TABLE` to choose a table (default: `quest-weekend-availability`) and `AWS_REGION` (or `AWS_DEFAULT_REGION`) to select a region (default: `us-east-1`). For local DynamoDB testing, optionally set `DYNAMODB_ENDPOINT_URL`. Set `SECRET_KEY` to a long, random value and `SESSION_COOKIE_SECURE=true` when deploying behind HTTPS. Existing data from the previous SQLite version is not migrated automatically; export and import it into the DynamoDB item shape if it needs to be retained.

On Windows, use the AWS CLI to save credentials in your local AWS profile. Boto3 reads that profile automatically; the app does not need credentials in its code.

In PowerShell, run:
```
aws configure --profile dnd-sched
$env:AWS_PROFILE = "dnd-sched"
$env:AWS_REGION = "us-east-2"
$env:DYNAMODB_TABLE = "Trainwreck-Schedule"
python app.py
```

aws configure will prompt for your access key, secret key, and default region. Get credentials from an IAM identity that has `dynamodb:Scan`, `dynamodb:GetItem`, `dynamodb:PutItem`, and `dynamodb:DeleteItem` permissions on your table. The profile is saved locally under `%USERPROFILE%\.aws`; don’t put credentials in the project or commit them. These PowerShell environment variables apply to the current terminal session.

To check which AWS identity the profile uses, run aws sts get-caller-identity --profile dnd-sched.


## How it works

- Enter a name, select at least one dated weekend time, and choose **Mark me ready**.
- The page redirects back to the refreshed board after saving.
- The board polls for new submissions every 15 seconds, so open pages stay current.
- Submitting again with the same name (case-insensitive) updates that adventurer’s availability.
- Click a Roll Call card to load that adventurer's current selections, then update and save them; an existing adventurer can clear their personal selections by saving an empty set.
- Roll Call also provides a **Delete Party Member** action that permanently removes that member and their availability from DynamoDB.
- DM controls can confirm one board slot as the planned session, clear the planned session, or reset all availability while keeping saved names.
- On phone-sized and compact layouts, **Your Turn** and **Party Board** start collapsed; tap either heading to expand it.
- Grant the app identity `dynamodb:Scan`, `dynamodb:PutItem`, and `dynamodb:DeleteItem` on the configured table. The app does not currently authenticate DM actions, so anyone with access to the board can use those controls.
- The party password gates the page and board APIs. Authenticated sessions last 12 hours; configure `SECRET_KEY` securely so session cookies cannot be forged. `SESSION_COOKIE_SECURE=true` should be enabled in HTTPS deployments.
