from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Company
from ..schemas import CompanyOut
from ..services.upload_service import UploadError, save_image
from ..templating import templates

router = APIRouter()


@router.get("/companies")
def list_companies(request: Request, db: Session = Depends(get_db)):
    companies = db.scalars(select(Company).order_by(Company.name)).all()
    return templates.TemplateResponse(
        request, "companies.html", {"companies": companies}
    )


@router.get("/companies/new")
def new_company_form(request: Request):
    return templates.TemplateResponse(
        request, "company_form.html", {"errors": [], "values": {}}
    )


@router.post("/companies")
async def create_company(
    request: Request,
    name: str = Form(""),
    tagline: str = Form(""),
    website: str = Form(""),
    email: str = Form(""),
    location: str = Form(""),
    founder_name: str = Form(""),
    founder_title: str = Form("Founder"),
    logo: UploadFile | None = File(None),
    signature: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    values = {
        "name": name.strip(),
        "tagline": tagline.strip(),
        "website": website.strip(),
        "email": email.strip(),
        "location": location.strip(),
        "founder_name": founder_name.strip(),
        "founder_title": founder_title.strip() or "Founder",
    }
    errors = []
    if not values["name"]:
        errors.append("Company name is required.")
    if not values["founder_name"]:
        errors.append("Founder name is required.")
    if values["email"] and "@" not in values["email"]:
        errors.append("Enter a valid company email.")

    logo_name = signature_name = None
    if not errors:
        try:
            logo_name = await save_image(logo, "logo")
            signature_name = await save_image(signature, "signature")
        except UploadError as exc:
            errors.append(str(exc))

    if errors:
        return templates.TemplateResponse(
            request,
            "company_form.html",
            {"errors": errors, "values": values},
            status_code=400,
        )

    company = Company(**values, logo_path=logo_name, signature_path=signature_name)
    db.add(company)
    db.commit()
    return RedirectResponse("/letters/new", status_code=303)


@router.get("/api/companies", response_model=list[CompanyOut])
def api_companies(db: Session = Depends(get_db)):
    return db.scalars(select(Company).order_by(Company.name)).all()
