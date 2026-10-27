# Data sources
**openFDA Drug Shortages** - https://open.fda.gov/apis/drug/drugshortages/ ; endpoint `https://api.fda.gov/drug/shortages.json`.
Scope: **United States (FDA)** only. It is NOT a feed of shortages in India. Update frequency per openFDA: daily.
Terms: openFDA says not to rely on it for medical-care decisions.

Field confidence:
- Confirmed in the official field reference: `status`, `update_date`, `change_date`, `discontinued_date`, `initial_posting_date`, `openfda.*` (brand_name, dosage_form, ...). Dates arrive as MM/DD/YYYY.
- Taken from secondary descriptions, **must be verified on a live response**: `generic_name`, `company_name`, `availability`, `shortage_reason`, `presentation`, `dosage_form`, `strength`, `therapeutic_category`, `related_info`, `update_type`, `package_ndc`.
- Not verified at all: whether a stable record id exists. We derive `source_key` = SHA-256 of identity fields; `content_hash` detects any change.
- This build had no internet access, so the live API was never called. The client is tested only against a fake transport.

Simulated data (future seed script) will be tagged `is_demo = true` and never mixed with FDA records.
