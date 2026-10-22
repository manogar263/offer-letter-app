import re
from datetime import date

from ..config import BASE_DIR, UPLOAD_DIR
from ..models import Company, OfferLetter

DEFAULT_BODY = (
    "This offer is subject to the terms and conditions of employment, as "
    "discussed and agreed upon between you and the company."
)


def format_date(d: date) -> str:
    return d.strftime("%B %d, %Y")


def split_paragraphs(text: str | None) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]


def _asset_src(filename: str | None, for_pdf: bool) -> str | None:
    if not filename:
        return None
    if for_pdf:
        return (UPLOAD_DIR / filename).resolve().as_uri()
    return f"/uploads/{filename}"


def _is_reference_company(company: Company) -> bool:
    return company.name.strip().casefold() in {
        "psm",
        "problem solving mind",
        "problem solving mind (psm)",
    }


def _default_logo_src(company: Company, for_pdf: bool) -> str | None:
    if not _is_reference_company(company):
        return None
    if for_pdf:
        return (BASE_DIR / "static" / "img" / "psm-logo.png").resolve().as_uri()
    return "/static/img/psm-logo.png"


def build_context(letter: OfferLetter, company: Company, for_pdf: bool = False) -> dict:
    """Everything the offer_letter.html template needs. No branding is hardcoded."""
    inline_css = None
    if for_pdf:
        inline_css = (BASE_DIR / "static" / "css" / "letter.css").read_text()
    tagline = company.tagline
    if not tagline.strip() and _is_reference_company(company):
        tagline = "Building Products\nSolving Problems"

    return {
        "company": company,
        "letter": letter,
        "letter_date": format_date(letter.letter_date),
        "start_date": format_date(letter.start_date),
        "tagline_lines": [l.strip() for l in tagline.splitlines() if l.strip()],
        "body_paragraphs": split_paragraphs(letter.body_text) or [DEFAULT_BODY],
        "logo_src": _asset_src(company.logo_path, for_pdf)
        or _default_logo_src(company, for_pdf),
        "signature_src": _asset_src(company.signature_path, for_pdf),
        "inline_css": inline_css,
        "for_pdf": for_pdf,
    }
