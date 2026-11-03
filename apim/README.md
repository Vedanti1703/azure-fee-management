# Azure API Management (APIM) Configuration & Policies

This directory contains Azure API Management (APIM) policy XML definitions, OpenAPI templates, and gateway configuration guidelines for the Student Fee Management microservice.

---

## 1. Directory Structure

```
/apim
  |-- README.md                         # Architecture and import guide
  \-- policies/
        |-- global-policy.xml           # Tenant/Global level policy (CORS, Rate Limiting)
        |-- api-policy.xml              # Fee Management API level policy
        \-- jwt-validation-policy.xml   # Entra ID / JWT Bearer token validation fragment
```

---

## 2. Policy Hierarchy in Azure APIM

In Azure API Management, policies run at 4 scopes in order:
1. **Global scope** (All APIs in the APIM service)
2. **Product scope** (APIs bundled under a specific developer product tier)
3. **API scope** (All operations within the Fee Management API)
4. **Operation scope** (Specific endpoint, e.g., `POST /payments`)

---

## 3. Key Policy Capabilities Implemented

- **CORS Handling:** Permits frontend origins while restricting unauthorized cross-origin calls.
- **Rate Limiting:** Protects against denial of service (`rate-limit-by-key` by client IP and subscription).
- **Header Sanitization:** Strips internal backend headers (`X-Powered-By`, `Server`) before sending responses.
- **JWT Validation:** Enforces Microsoft Entra ID / OAuth 2.0 token verification at the gateway level before traffic touches Azure Functions.
- **Backend Routing:** Routes `/fee-management/*` requests to the Azure Function App backend using Managed Identity authentication.

---

## 4. Applying Policies via Azure CLI

To apply the API-level policy to your Azure APIM instance:

```bash
az apim api policy update \
  --resource-group rg-student-fee-management \
  --service-name apim-fee-mgmt \
  --api-id fee-management-api \
  --value-path policies/api-policy.xml
```

