# Billing Web Application

This project implements a minimal Flask application targeting Azure App Service (Linux, Python 3.10). The app provides two pages:

* **UP01** – upload billing CSV files to Azure Blob Storage
* **LS01** – query billing data stored in Azure Database for PostgreSQL

## Requirements

* Python 3.10
* Azure resources:
  * App Service (with Easy Auth enabled)
  * Azure Blob Storage container (`kakinfiles`)
  * Azure Database for PostgreSQL

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set the environment variables in `.env` (or App Service configuration).

## Running locally

```bash
flask --app app run --debug
```

or using gunicorn:

```bash
gunicorn app:app --workers 2 --timeout 120
```

## Tests

```bash
pytest
```

## Deployment

Deploy the contents of this folder to Azure App Service using your preferred method (Zip Deploy, GitHub Actions, etc.). Ensure the App Settings include:

* `AUTH_MODE=easy_auth`
* `AZURE_STORAGE_ACCOUNT_URL`
* `BLOB_CONTAINER`
* `DB_URL`
* `FLASK_SECRET_KEY`
* `TZ=Asia/Tokyo`
