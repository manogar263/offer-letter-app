import os
import tempfile
from datetime import date
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["UPLOAD_DIR"] = f"{_tmp}/uploads"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app.database import migrate_sqlite_schema  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import letters as letters_router  # noqa: E402
from app.services import email_service  # noqa: E402
from app.services.email_service import EmailSendError  # noqa: E402

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05"
    b"\xfe\x02\xfe\xa7V\xbd\xfa\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def company(client):
    r = client.post(
        "/companies",
        data={
            "name": "Acme Labs",
            "tagline": "Building Products\nSolving Problems",
            "website": "www.acme.test",
            "email": "hello@acme.test",
            "location": "Chennai, India",
            "founder_name": "Jane Founder",
            "founder_title": "Founder",
        },
        files={
            "logo": ("logo.png", PNG, "image/png"),
            "signature": ("sig.png", PNG, "image/png"),
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    return client.get("/api/companies").json()[0]


def letter_data(company_id, **over):
    data = {
        "company_id": company_id,
        "candidate_name": "Test Candidate",
        "candidate_email": "candidate@example.com",
        "candidate_address": "Chennai",
        "position": "Research Analyst",
        "start_date": "2026-11-01",
        "employment_type": "Full Time",
        "work_location": "Chennai",
        "body_text": "First paragraph.\n\nSecond paragraph.",
        "letter_date": "2026-10-21",
    }
    data.update(over)
    return data


def test_company_requires_name_and_founder(client):
    r = client.post("/companies", data={"name": "", "founder_name": ""})
    assert r.status_code == 400
    assert "Company name is required" in r.text


def test_rejects_bad_logo_type(client):
    r = client.post(
        "/companies",
        data={"name": "X", "founder_name": "Y"},
        files={"logo": ("logo.exe", b"abc", "application/octet-stream")},
    )
    assert r.status_code == 400
    assert "must be one of" in r.text


def test_create_and_preview_letter(client, company):
    r = client.post("/letters", data=letter_data(company["id"]), follow_redirects=False)
    assert r.status_code == 303
    preview = r.headers["location"]
    assert preview.endswith("/preview")
    assert parse_qs(urlparse(r.headers["location"]).query) == {}

    preview_page = client.get(preview).text
    assert "Download PDF" not in preview_page
    assert f'href="/letters/{int(preview.split("/")[-2])}/edit"' in preview_page
    assert "Print" in preview_page
    assert 'aria-label="Remove this offer letter"' in preview_page
    assert 'class="icon-button danger-icon"' in preview_page
    assert client.get("/api/letters").json()[0]["candidate_email"] == "candidate@example.com"

    page = client.get(preview.replace("/preview", "/letter")).text
    assert "OFFER LETTER" in page
    assert "Test Candidate" in page
    assert "RESEARCH ANALYST" in page
    assert "November 01, 2026" in page
    assert "Jane Founder" in page
    assert "First paragraph." in page and "Second paragraph." in page
    assert "/uploads/logo-" in page and "/uploads/signature-" in page


def test_candidate_email_and_send_checkbox_render(client, company):
    page = client.get("/letters/new").text
    assert 'id="candidate_email" name="candidate_email" type="email"' in page
    checkbox = page.split('id="send_email"', 1)[1].split(">", 1)[0]
    assert 'name="send_email"' in checkbox
    assert 'type="checkbox"' in checkbox
    assert "checked" in checkbox


def test_candidate_email_validation(client, company):
    for invalid_email in ("", "not-an-email", "candidate@example.com\r\nBcc:bad@example.com"):
        response = client.post(
            "/letters",
            data=letter_data(company["id"], candidate_email=invalid_email),
        )
        assert response.status_code == 400
        assert (
            "valid candidate email" in response.text
            or "newline characters" in response.text
            or "Candidate email is required" in response.text
        )


def test_create_sends_when_checkbox_is_checked(client, company, monkeypatch):
    sent = []

    def fake_send(letter, request):
        sent.append((letter.candidate_email, letter.candidate_name))

    monkeypatch.setattr(letters_router, "_send_letter_email", fake_send)
    response = client.post(
        "/letters",
        data=letter_data(company["id"], send_email="true"),
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert sent == [("candidate@example.com", "Test Candidate")]
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query == {"email_status": ["sent"]}


def test_reference_branding_for_problem_solving_mind(client):
    response = client.post(
        "/companies",
        data={
            "name": "Problem Solving Mind",
            "founder_name": "Prasanna Venkatesan",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    company = client.get("/api/companies").json()
    company_id = next(c["id"] for c in company if c["name"] == "Problem Solving Mind")

    response = client.post(
        "/letters",
        data=letter_data(company_id),
        follow_redirects=False,
    )
    page = client.get(response.headers["location"].replace("/preview", "/letter")).text

    assert "/static/img/psm-logo.png" in page
    assert "Building Products<br>Solving Problems" in page


def test_letter_validation(client, company):
    r = client.post("/letters", data=letter_data(company["id"], position="", start_date="bad"))
    assert r.status_code == 400
    assert "Position is required" in r.text
    assert "Start date must be a valid date" in r.text


def test_html_is_escaped(client, company):
    r = client.post(
        "/letters",
        data=letter_data(company["id"], candidate_name="<script>alert(1)</script>"),
        follow_redirects=False,
    )
    page = client.get(r.headers["location"].replace("/preview", "/letter")).text
    assert "<script>alert(1)</script>" not in page


def test_list_and_accept(client, company):
    letters = client.get("/api/letters").json()
    assert letters
    lid = letters[0]["id"]
    assert client.post(f"/letters/{lid}/accept", follow_redirects=False).status_code == 303
    assert client.get("/api/letters").json()[0]["status"] == "Accepted"
    assert client.get("/letters").status_code == 200


def test_remove_letter_from_preview_and_dashboard(client, company):
    response = client.post(
        "/letters",
        data=letter_data(company["id"], candidate_name="Remove Me"),
        follow_redirects=False,
    )
    letter_url = response.headers["location"]
    letter_id = int(letter_url.split("/")[2])

    dashboard = client.get("/letters").text
    assert f"/letters/{letter_id}/delete" in dashboard
    assert f'aria-label="Remove Remove Me offer letter"' in dashboard
    assert 'class="icon-button danger-icon"' in dashboard

    preview = client.get(letter_url).text
    assert f"/letters/{letter_id}/delete" in preview
    assert 'aria-label="Remove this offer letter"' in preview

    removed = client.post(f"/letters/{letter_id}/delete", follow_redirects=False)
    assert removed.status_code == 303
    assert removed.headers["location"] == "/letters"
    assert client.get(f"/letters/{letter_id}/preview").status_code == 404
    assert all(item["id"] != letter_id for item in client.get("/api/letters").json())


def test_edit_letter_prefills_updates_and_validates(client, company):
    response = client.post(
        "/letters",
        data=letter_data(company["id"]),
        follow_redirects=False,
    )
    letter_url = response.headers["location"]
    letter_id = int(letter_url.split("/")[2])

    form = client.get(f"/letters/{letter_id}/edit")
    assert form.status_code == 200
    assert "value=\"Test Candidate\"" in form.text
    assert "Save changes" in form.text
    assert 'value="candidate@example.com"' in form.text
    assert f'href="/letters/{letter_id}/edit"' in client.get("/letters").text

    changed = letter_data(
        company["id"],
        candidate_name="Updated Candidate",
        position="Senior Analyst",
        start_date="2026-12-15",
        letter_date="2026-10-25",
        body_text="Updated terms.",
    )
    saved = client.post(
        f"/letters/{letter_id}/edit",
        data=changed,
        follow_redirects=False,
    )
    assert saved.status_code == 303
    assert saved.headers["location"] == f"/letters/{letter_id}/preview"

    rendered = client.get(f"/letters/{letter_id}/letter").text
    assert "Updated Candidate" in rendered
    assert "SENIOR ANALYST" in rendered
    assert "December 15, 2026" in rendered
    assert "October 25, 2026" in rendered
    assert "Updated terms." in rendered
    assert client.get("/api/letters").json()[0]["candidate_email"] == "candidate@example.com"

    invalid = client.post(
        f"/letters/{letter_id}/edit",
        data=letter_data(company["id"], candidate_name="", start_date="bad"),
    )
    assert invalid.status_code == 400
    assert "Candidate name is required" in invalid.text
    assert "Start date must be a valid date" in invalid.text


def test_missing_letter_404(client):
    assert client.get("/letters/9999/preview").status_code == 404


def test_pdf(client, company):
    lid = client.get("/api/letters").json()[0]["id"]
    r = client.get(f"/letters/{lid}/pdf")
    if r.status_code == 503:
        pytest.skip("WeasyPrint system libraries not installed")
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF")


def test_send_route_reports_success_and_failure(client, company, monkeypatch):
    response = client.post(
        "/letters",
        data=letter_data(company["id"]),
        follow_redirects=False,
    )
    letter_id = int(response.headers["location"].split("/")[2])

    monkeypatch.setattr(letters_router, "_send_letter_email", lambda letter, request: None)
    sent = client.post(f"/letters/{letter_id}/send", follow_redirects=False)
    assert parse_qs(urlparse(sent.headers["location"]).query) == {
        "email_status": ["sent"]
    }
    assert "Email status: Sent" in client.get(sent.headers["location"]).text

    def fail_send(letter, request):
        raise EmailSendError("SMTP server unavailable")

    monkeypatch.setattr(letters_router, "_send_letter_email", fail_send)
    failed = client.post(f"/letters/{letter_id}/send", follow_redirects=False)
    query = parse_qs(urlparse(failed.headers["location"]).query)
    assert query["email_status"] == ["failed"]
    page = client.get(failed.headers["location"]).text
    assert "Email status: Failed" in page
    assert "SMTP server unavailable" in page


def test_email_service_builds_pdf_email_and_rejects_header_injection(monkeypatch):
    sent_messages = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            assert host == "smtp.acme.test"
            assert port == 587
            assert timeout == 30

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def starttls(self, context):
            assert context

        def login(self, username, password):
            assert username == "smtp-user"
            assert password == "secret-password"

        def send_message(self, message):
            sent_messages.append(message)

    monkeypatch.setattr(email_service, "SMTP_HOST", "smtp.acme.test")
    monkeypatch.setattr(email_service, "SMTP_PORT", "587")
    monkeypatch.setattr(email_service, "SMTP_USER", "smtp-user")
    monkeypatch.setattr(email_service, "SMTP_PASSWORD", "secret-password")
    monkeypatch.setattr(email_service, "SMTP_FROM_EMAIL", "offers@example.com")
    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(
        email_service.socket,
        "getaddrinfo",
        lambda host, port, type: [(None, None, None, None, None)],
    )

    letter = SimpleNamespace(
        candidate_email="candidate@example.com",
        candidate_name="Candidate Name",
        position="Research Analyst",
        start_date=date(2026, 11, 1),
    )
    company = SimpleNamespace(name="Acme Labs", email="people@acme.example")
    email_service.send_offer_email(
        letter, company, b"%PDF-test", "offer_letter_Candidate_Name.pdf"
    )

    message = sent_messages[0]
    assert message["Subject"] == "Offer Letter - Research Analyst at Acme Labs"
    assert message["To"] == "candidate@example.com"
    assert message["Reply-To"] == "people@acme.example"
    body = message.get_body(preferencelist=("plain",))
    assert body is not None
    assert "November 01, 2026" in body.get_content()
    attachment = list(message.iter_attachments())[0]
    assert attachment.get_filename() == "offer_letter_Candidate_Name.pdf"
    assert attachment.get_content() == b"%PDF-test"

    letter.candidate_email = "candidate@example.com\r\nBcc:attacker@example.com"
    with pytest.raises(EmailSendError, match="newline"):
        email_service.send_offer_email(
            letter, company, b"%PDF-test", "offer_letter_Candidate_Name.pdf"
        )


def test_email_service_explains_unresolvable_smtp_host(monkeypatch):
    monkeypatch.setattr(email_service, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(email_service, "SMTP_PORT", "587")
    with pytest.raises(EmailSendError, match="placeholder"):
        email_service._resolve_smtp_host(587)

    monkeypatch.setattr(email_service, "SMTP_HOST", "smtp.unresolvable.invalid")

    def fail_resolution(host, port, type):
        raise email_service.socket.gaierror(-2, "Name or service not known")

    monkeypatch.setattr(email_service.socket, "getaddrinfo", fail_resolution)
    with pytest.raises(EmailSendError, match="Cannot resolve SMTP_HOST"):
        email_service._resolve_smtp_host(587)


def test_startup_schema_migration_preserves_existing_rows():
    legacy_engine = create_engine("sqlite://")
    with legacy_engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE offer_letters "
                "(id INTEGER PRIMARY KEY, candidate_name VARCHAR(120) NOT NULL)"
            )
        )
        connection.execute(
            text("INSERT INTO offer_letters (id, candidate_name) VALUES (1, 'Existing')")
        )

    migrate_sqlite_schema(legacy_engine)
    with legacy_engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT candidate_name, candidate_email "
                "FROM offer_letters WHERE id = 1"
            )
        ).one()
    assert row.candidate_name == "Existing"
    assert row.candidate_email == ""
    legacy_engine.dispose()
