from datetime import date
from urllib.parse import urlencode

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import EMPLOYMENT_TYPES
from ..database import get_db
from ..models import Company, OfferLetter
from ..schemas import LetterOut
from ..services.letter_service import build_context
from ..services.pdf_service import PDFUnavailable, render_pdf
from ..services.email_service import EmailSendError, send_offer_email
from ..templating import templates

router = APIRouter()


def _get_letter(db: Session, letter_id: int) -> OfferLetter:
    letter = db.get(OfferLetter, letter_id)
    if not letter:
        raise HTTPException(status_code=404, detail="Offer letter not found")
    return letter


def _form_context(db: Session, errors=None, values=None):
    companies = db.scalars(select(Company).order_by(Company.name)).all()
    return {
        "companies": companies,
        "employment_types": EMPLOYMENT_TYPES,
        "errors": errors or [],
        "values": values or {"letter_date": date.today().isoformat()},
    }


def _validate_letter_values(db: Session, values: dict):
    errors = []
    if not db.get(Company, values["company_id"]):
        errors.append("Choose a company.")
    for key, label in [
        ("candidate_name", "Candidate name"),
        ("position", "Position"),
        ("work_location", "Work location"),
    ]:
        if not values[key]:
            errors.append(f"{label} is required.")
    if values["employment_type"] not in EMPLOYMENT_TYPES:
        errors.append("Choose an employment type.")
    candidate_email = values["candidate_email"]
    if not candidate_email:
        errors.append("Candidate email is required.")
    elif "\r" in candidate_email or "\n" in candidate_email:
        errors.append("Candidate email must not contain newline characters.")
    else:
        try:
            values["candidate_email"] = validate_email(
                candidate_email, check_deliverability=False
            ).normalized
        except EmailNotValidError:
            errors.append("Enter a valid candidate email address.")

    parsed = {}
    for key, label in [("start_date", "Start date"), ("letter_date", "Letter date")]:
        try:
            parsed[key] = date.fromisoformat(values[key])
        except ValueError:
            errors.append(f"{label} must be a valid date.")
    return errors, parsed


def _render_letter_pdf(letter: OfferLetter, request: Request) -> bytes:
    context = build_context(letter, letter.company, for_pdf=True)
    html = templates.get_template("offer_letter.html").render(
        request=request, **context
    )
    return render_pdf(html)


def _send_letter_email(letter: OfferLetter, request: Request) -> None:
    pdf_bytes = _render_letter_pdf(letter, request)
    safe_name = "".join(
        character if character.isalnum() else "_"
        for character in letter.candidate_name
    ).strip("_") or "candidate"
    send_offer_email(
        letter,
        letter.company,
        pdf_bytes,
        f"offer_letter_{safe_name}.pdf",
    )


def _email_result_redirect(
    letter_id: int, status: str, error: str | None = None
) -> RedirectResponse:
    query = {"email_status": status}
    if error:
        query["email_error"] = error
    return RedirectResponse(
        f"/letters/{letter_id}/preview?{urlencode(query)}",
        status_code=303,
    )


@router.get("/")
def home():
    return RedirectResponse("/letters")


@router.get("/letters")
def list_letters(request: Request, db: Session = Depends(get_db)):
    letters = db.scalars(
        select(OfferLetter).order_by(OfferLetter.created_at.desc())
    ).all()
    return templates.TemplateResponse(request, "dashboard.html", {"letters": letters})


@router.get("/letters/new")
def new_letter_form(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "letter_form.html", _form_context(db))


@router.post("/letters")
def create_letter(
    request: Request,
    company_id: int = Form(0),
    candidate_name: str = Form(""),
    candidate_address: str = Form(""),
    position: str = Form(""),
    start_date: str = Form(""),
    employment_type: str = Form(""),
    work_location: str = Form(""),
    body_text: str = Form(""),
    letter_date: str = Form(""),
    candidate_email: str = Form(""),
    send_email: bool = Form(False),
    db: Session = Depends(get_db),
):
    values = {
        "company_id": company_id,
        "candidate_name": candidate_name.strip(),
        "candidate_email": candidate_email.strip(),
        "candidate_address": candidate_address.strip(),
        "position": position.strip(),
        "start_date": start_date,
        "employment_type": employment_type,
        "work_location": work_location.strip(),
        "body_text": body_text.strip(),
        "letter_date": letter_date or date.today().isoformat(),
        "send_email": send_email,
    }
    errors, parsed = _validate_letter_values(db, values)

    if errors:
        return templates.TemplateResponse(
            request,
            "letter_form.html",
            _form_context(db, errors, values),
            status_code=400,
        )

    letter = OfferLetter(
        company_id=company_id,
        candidate_name=values["candidate_name"],
        candidate_email=values["candidate_email"],
        candidate_address=values["candidate_address"],
        position=values["position"],
        start_date=parsed["start_date"],
        employment_type=employment_type,
        work_location=values["work_location"],
        body_text=values["body_text"],
        letter_date=parsed["letter_date"],
    )
    db.add(letter)
    db.commit()
    db.refresh(letter)
    if send_email:
        try:
            _send_letter_email(letter, request)
        except (EmailSendError, PDFUnavailable) as exc:
            return _email_result_redirect(letter.id, "failed", str(exc))
        return _email_result_redirect(letter.id, "sent")
    return RedirectResponse(f"/letters/{letter.id}/preview", status_code=303)


@router.get("/letters/{letter_id}/edit")
def edit_letter_form(letter_id: int, request: Request, db: Session = Depends(get_db)):
    letter = _get_letter(db, letter_id)
    values = {
        "company_id": letter.company_id,
        "candidate_name": letter.candidate_name,
        "candidate_email": letter.candidate_email,
        "candidate_address": letter.candidate_address,
        "position": letter.position,
        "start_date": letter.start_date.isoformat(),
        "employment_type": letter.employment_type,
        "work_location": letter.work_location,
        "body_text": letter.body_text,
        "letter_date": letter.letter_date.isoformat(),
    }
    return templates.TemplateResponse(
        request,
        "letter_form.html",
        {**_form_context(db, values=values), "edit_id": letter.id},
    )


@router.post("/letters/{letter_id}/edit")
def update_letter(
    letter_id: int,
    request: Request,
    company_id: int = Form(0),
    candidate_name: str = Form(""),
    candidate_address: str = Form(""),
    position: str = Form(""),
    start_date: str = Form(""),
    employment_type: str = Form(""),
    work_location: str = Form(""),
    body_text: str = Form(""),
    letter_date: str = Form(""),
    candidate_email: str = Form(""),
    db: Session = Depends(get_db),
):
    letter = _get_letter(db, letter_id)
    values = {
        "company_id": company_id,
        "candidate_name": candidate_name.strip(),
        "candidate_email": candidate_email.strip(),
        "candidate_address": candidate_address.strip(),
        "position": position.strip(),
        "start_date": start_date,
        "employment_type": employment_type,
        "work_location": work_location.strip(),
        "body_text": body_text.strip(),
        "letter_date": letter_date or date.today().isoformat(),
    }
    errors, parsed = _validate_letter_values(db, values)

    if errors:
        return templates.TemplateResponse(
            request,
            "letter_form.html",
            {**_form_context(db, errors, values), "edit_id": letter.id},
            status_code=400,
        )

    letter.company_id = company_id
    letter.candidate_name = values["candidate_name"]
    letter.candidate_email = values["candidate_email"]
    letter.candidate_address = values["candidate_address"]
    letter.position = values["position"]
    letter.start_date = parsed["start_date"]
    letter.employment_type = employment_type
    letter.work_location = values["work_location"]
    letter.body_text = values["body_text"]
    letter.letter_date = parsed["letter_date"]
    db.commit()
    return RedirectResponse(f"/letters/{letter.id}/preview", status_code=303)


@router.get("/letters/{letter_id}/letter", response_class=HTMLResponse)
def letter_only(letter_id: int, request: Request, db: Session = Depends(get_db)):
    """The bare letter page (used inside the preview frame and for printing)."""
    letter = _get_letter(db, letter_id)
    ctx = build_context(letter, letter.company)
    return templates.TemplateResponse(request, "offer_letter.html", ctx)


@router.get("/letters/{letter_id}/preview")
def preview_letter(
    letter_id: int,
    request: Request,
    email_status: str | None = None,
    email_error: str | None = None,
    db: Session = Depends(get_db),
):
    letter = _get_letter(db, letter_id)
    return templates.TemplateResponse(
        request,
        "preview.html",
        {
            "letter": letter,
            "email_status": email_status,
            "email_error": email_error,
        },
    )


@router.get("/letters/{letter_id}/pdf")
def download_pdf(letter_id: int, request: Request, db: Session = Depends(get_db)):
    letter = _get_letter(db, letter_id)
    try:
        pdf = _render_letter_pdf(letter, request)
    except PDFUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    safe = "".join(c if c.isalnum() else "_" for c in letter.candidate_name)
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="offer_letter_{safe}.pdf"'},
    )


@router.post("/letters/{letter_id}/send")
def send_letter_email_route(
    letter_id: int, request: Request, db: Session = Depends(get_db)
):
    letter = _get_letter(db, letter_id)
    try:
        _send_letter_email(letter, request)
    except (EmailSendError, PDFUnavailable) as exc:
        return _email_result_redirect(letter.id, "failed", str(exc))
    return _email_result_redirect(letter.id, "sent")


@router.post("/letters/{letter_id}/accept")
def accept_letter(letter_id: int, db: Session = Depends(get_db)):
    letter = _get_letter(db, letter_id)
    letter.status = "Accepted"
    db.commit()
    return RedirectResponse("/letters", status_code=303)


@router.post("/letters/{letter_id}/delete")
def delete_letter(letter_id: int, db: Session = Depends(get_db)):
    letter = _get_letter(db, letter_id)
    db.delete(letter)
    db.commit()
    return RedirectResponse("/letters", status_code=303)


@router.get("/api/letters", response_model=list[LetterOut])
def api_letters(db: Session = Depends(get_db)):
    return db.scalars(select(OfferLetter).order_by(OfferLetter.created_at.desc())).all()
