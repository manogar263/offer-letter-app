# Offer Letter Generator

A FastAPI web app where a company registers once (logo, tagline, contact details,
founder name and signature image) and then issues offer letters by filling a form.
Letters render as an A4 page and download as PDF.

The A4 letter layout follows the supplied PSM reference. For a company named
"Problem Solving Mind" (or "PSM"), the reference logo and tagline are used when no
logo or tagline is supplied. Other company branding comes from its company record
and uploaded files.

## Who fills what

| Field | Filled by |
|---|---|
| Logo, tagline, website, email, location, founder name/title, signature image | Company, one time |
| Candidate name, email, city | Company, per letter |
| Position, start date, employment type, work location | Company, per letter |
| Job description / terms | Company, per letter |
| Letter date | Defaults to today, editable |

## Setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000

### Email delivery

Set the SMTP host, port, username, password, and sender address in `.env`.
For Gmail, use `smtp.gmail.com` with port `587`, set both `SMTP_USER` and
`SMTP_FROM_EMAIL` to the full Gmail address, and set `SMTP_PASSWORD` to a Google
app password (not the normal account password). App passwords require
two-step verification to be enabled on the Google account. Never commit `.env`
or share the app password. Restart the app after changing these settings.

New offer letters include a required candidate email; the checked-by-default
option emails the generated PDF after saving. The preview page also allows
sending or resending the PDF.

### PDF export (WeasyPrint)

WeasyPrint needs Pango. On Windows install the GTK runtime
(https://doc.courtbouillon.org/weasyprint/stable/first_steps.html). On Ubuntu/Debian:

```bash
sudo apt install libpango-1.0-0 libpangoft2-1.0-0
```

If PDF export is unavailable, the preview page still works and its **Print** button
can save the letter as PDF from the browser.

## Usage

1. **Companies > Add company**: enter details, upload logo and signature.
2. **New letter**: pick the company, fill candidate email and job details. Sending the PDF is enabled by default and can be unchecked.
3. Preview, then **Download PDF** or **Print**.
4. **Mark as accepted** when the candidate returns the signed copy.

## Routes

| Method | Path | Purpose |
|---|---|---|
| GET | `/letters` | Dashboard |
| GET/POST | `/letters/new`, `/letters` | Letter form / create |
| GET/POST | `/letters/{id}/edit` | Edit an existing letter |
| GET | `/letters/{id}/preview` | Preview page |
| GET | `/letters/{id}/letter` | Bare letter HTML |
| GET | `/letters/{id}/pdf` | PDF download |
| POST | `/letters/{id}/send` | Email the offer letter PDF to the candidate |
| POST | `/letters/{id}/accept` | Mark accepted |
| GET/POST | `/companies/new`, `/companies` | Company form / create |
| GET | `/api/letters`, `/api/companies` | JSON lists |

## Tests

```bash
pytest
```

## Project structure

```
app/
  main.py  config.py  database.py  models.py  schemas.py  templating.py
  routers/    companies.py  letters.py
  services/   letter_service.py  pdf_service.py  upload_service.py
  templates/  base, dashboard, companies, company_form, letter_form,
              preview, offer_letter
  static/css/ app.css (website)  letter.css (A4 letter)
tests/test_letters.py
```

## Palette

| Token | Hex |
|---|---|
| navy | `#0b2a66` |
| title blue | `#123b7c` |
| bright blue | `#0a5cff` |
| sky blue | `#38b6ff` |
| pale blue | `#dce9fb` |

## Before real use

- Add login so each company only sees its own letters.
- Only upload signatures that the named signatory has authorised.
- Move from SQLite to PostgreSQL and use Alembic for migrations.
