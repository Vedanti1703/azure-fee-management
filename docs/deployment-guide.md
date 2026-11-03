# Azure Student Fee Management System - Deployment Guide

This guide walks you through setting up the system locally for development and deploying the solution to Microsoft Azure.

---

## 1. Prerequisites

### Local Development Tools
- **Python:** Version 3.10 or 3.11
- **Docker & Docker Compose:** Docker Desktop (Windows/macOS/Linux)
- **Azure Functions Core Tools:** v4 (`npm install -g azure-functions-core-tools@4 --unsafe-perm true`)
- **SQL Server Client:** `sqlcmd` or Azure Data Studio / VS Code MSSQL Extension
- **ODBC Driver:** Microsoft ODBC Driver 18 for SQL Server
- **Azure CLI:** `az` (for cloud deployment)

---

## 2. Local Development Setup (Quickstart)

### Step 2.1: Clone and Configure Environment Files
From the project root:

```bash
# 1. Create root environment file
cp .env.example .env

# 2. Create Azure Functions local configuration
cp functions/local.settings.json.example functions/local.settings.json
```

> [!NOTE]
> Review `.env` and `functions/local.settings.json`. For local development, default values work out of the box with the Docker compose stack.

### Step 2.2: Start Local Containers (SQL Server + Mailpit)
Start the background services:

```bash
docker compose up -d
```

Verify services are running:
- **SQL Server 2022:** `localhost:1433`
- **Mailpit Web UI:** [http://localhost:8025](http://localhost:8025)
- **Mailpit SMTP Server:** `localhost:1025`

### Step 2.3: Initialize the Database
Execute the schema and seed scripts against the local container:

Using `sqlcmd`:
```bash
# Apply schema
sqlcmd -S localhost,1433 -U sa -P "LocalDevSecret123!" -C -i database/schema.sql

# Seed initial baseline data
sqlcmd -S localhost,1433 -U sa -P "LocalDevSecret123!" -C -i database/seed.sql

# Optional: Seed 5,000 synthetic records for load testing
sqlcmd -S localhost,1433 -U sa -P "LocalDevSecret123!" -C -i database/seed_5000.sql
```

*Alternatively, execute the SQL scripts using Azure Data Studio or SQL Server Management Studio (SSMS).*

### Step 2.4: Set Up Python Virtual Environment
```bash
python -m venv .venv

# Activate environment:
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On Linux / macOS:
source .venv/bin/activate

# Install dependencies:
pip install --upgrade pip
pip install -r functions/requirements.txt
```

### Step 2.5: Run Unit Tests
Validate that modules, authentication helpers, and database utilities operate properly:

```bash
cd functions
pytest -v tests/
cd ..
```

### Step 2.6: Start Azure Functions App Locally
```bash
cd functions
func start
```

Your function endpoints will now be accessible at `http://localhost:7071/api/`:
- `GET http://localhost:7071/api/health`
- `GET http://localhost:7071/api/students`
- `GET http://localhost:7071/api/invoices`
- `POST http://localhost:7071/api/payments`
- `POST http://localhost:7071/api/reminders/trigger`

### Step 2.7: Test Local Fee Reminders Dispatch
In another terminal (with `.venv` active):

```bash
python scripts/send_reminders_local.py --days-ahead 7
```

Open [http://localhost:8025](http://localhost:8025) in your web browser. You will see formatted HTML reminder emails captured inside Mailpit!

---

## 3. Azure Cloud Deployment

### Step 3.1: Log in to Azure & Create Resource Group
```bash
az login
az group create --name rg-student-fee-management --location eastus
```

### Step 3.2: Provision Azure SQL Database
```bash
# Provision Azure SQL Logical Server
az sql server create \
  --name sql-fee-mgmt-prod \
  --resource-group rg-student-fee-management \
  --location eastus \
  --admin-user sqladmin \
  --admin-password "<YourComplexAzurePassword>"

# Configure Azure Services Firewall Rule
az sql server firewall-rule create \
  --resource-group rg-student-fee-management \
  --server sql-fee-mgmt-prod \
  --name AllowAzureServices \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0

# Create Database (Standard S0 or General Purpose Serverless)
az sql db create \
  --resource-group rg-student-fee-management \
  --server sql-fee-mgmt-prod \
  --name StudentFeeManagementDB \
  --service-objective S0
```

Apply database schema to Azure SQL:
```bash
sqlcmd -S sql-fee-mgmt-prod.database.windows.net -d StudentFeeManagementDB -U sqladmin -P "<YourComplexAzurePassword>" -i database/schema.sql
sqlcmd -S sql-fee-mgmt-prod.database.windows.net -d StudentFeeManagementDB -U sqladmin -P "<YourComplexAzurePassword>" -i database/seed.sql
```

### Step 3.3: Deploy Storage Account & Azure Function App
```bash
# Create Storage Account
az storage account create \
  --name stfeemgmtprod \
  --resource-group rg-student-fee-management \
  --location eastus \
  --sku Standard_LRS

# Create Linux Function App (Python 3.10 runtime)
az functionapp create \
  --resource-group rg-student-fee-management \
  --consumption-plan-location eastus \
  --runtime python \
  --runtime-version 3.10 \
  --functions-version 4 \
  --name func-fee-mgmt-prod \
  --storage-account stfeemgmtprod \
  --os-type Linux

# Assign System-Assigned Managed Identity
az functionapp identity assign \
  --resource-group rg-student-fee-management \
  --name func-fee-mgmt-prod

# Configure Application Settings (Connection Strings & Secrets)
az functionapp config appsettings set \
  --resource-group rg-student-fee-management \
  --name func-fee-mgmt-prod \
  --settings \
    AZURE_SQL_CONNECTIONSTRING="Driver={ODBC Driver 18 for SQL Server};Server=tcp:sql-fee-mgmt-prod.database.windows.net,1433;Database=StudentFeeManagementDB;Uid=sqladmin;Pwd=<YourComplexAzurePassword>;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;" \
    ENVIRONMENT="production" \
    JWT_SECRET_KEY="<production-random-secret-key-64-bytes>" \
    JWT_ALGORITHM="HS256" \
    JWT_ISSUER="https://login.microsoftonline.com/<your-tenant-id>/v2.0" \
    JWT_AUDIENCE="api://fee-management"
```

### Step 3.4: Publish Azure Function Code
From the `functions/` directory:

```bash
cd functions
func azure functionapp publish func-fee-mgmt-prod
```

### Step 3.5: Configure Azure API Management (APIM)
1. Deploy an APIM instance (Developer or Standard tier).
2. Import the Function App API into APIM using the Azure Portal or Azure CLI.
3. Apply the policy XML files located in `apim/policies/`:
   - `apim/policies/global-policy.xml` at the service level.
   - `apim/policies/api-policy.xml` at the API level.
   - `apim/policies/jwt-validation-policy.xml` on secured operations.

---

## 4. Operational Monitoring & Diagnostics

- **Application Insights:** Inspect real-time telemetry, execution latency, and exceptions.
- **Failures & Alerts:** Set up Azure Monitor alert rules when HTTP 5xx responses exceed 1% or when payment transaction errors occur.
- **Audit Trails:** Query `dbo.AuditLogs` and `dbo.RemindersLog` in Azure SQL for compliance auditing.

