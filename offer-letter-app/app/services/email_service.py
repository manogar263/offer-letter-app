import smtplib
import socket
import ssl
from email.message import EmailMessage
from email_validator import EmailNotValidError, validate_email

from ..config import (
    SMTP_FROM_EMAIL,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USER,
)
from ..models import Company, OfferLetter


class EmailSendError(RuntimeError):
    pass


def _smtp_port() -> int:
    try:
        port = int(SMTP_PORT)
    except ValueError as exc:
        raise EmailSendError("SMTP_PORT must be a valid port number.") from exc
    if not 1 <= port <= 65535:
        raise EmailSendError("SMTP_PORT must be between 1 and 65535.")
    return port


def _resolve_smtp_host(port: int) -> None:
    host = SMTP_HOST.strip()
    if (
        not host
        or "://" in host
        or "/" in host
        or host.casefold() == "smtp.example.com"
        or host.casefold().endswith(".example")
    ):
        raise EmailSendError(
            "SMTP_HOST is still a placeholder or is not a hostname. "
            "Set it to your email provider's SMTP server in .env "
            "(for example, smtp.gmail.com), then restart the app."
        )
    try:
        socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise EmailSendError(
            f"Cannot resolve SMTP_HOST '{host}'. Check the SMTP_HOST value in .env "
            "and restart the app."
        ) from exc


def _validated_address(address: str, label: str) -> str:
    if "\r" in address or "\n" in address:
        raise EmailSendError(f"{label} must not contain newline characters.")
    try:
        return validate_email(address.strip(), check_deliverability=False).normalized
    except EmailNotValidError as exc:
        raise EmailSendError(f"{label} is not a valid email address: {exc}") from exc


def _header_text(value: str) -> str:
    sanitized = "".join(
        " " if ord(character) < 32 or ord(character) == 127 else character
        for character in value
    )
    return " ".join(sanitized.split()).strip()


def send_offer_email(
    letter: OfferLetter,
    company: Company,
    pdf_bytes: bytes,
    attachment_filename: str,
) -> None:
    required_settings = {
        "SMTP_HOST": SMTP_HOST,
        "SMTP_PORT": SMTP_PORT,
        "SMTP_USER": SMTP_USER,
        "SMTP_PASSWORD": SMTP_PASSWORD,
        "SMTP_FROM_EMAIL": SMTP_FROM_EMAIL,
    }
    missing = [name for name, value in required_settings.items() if not value]
    if missing:
        raise EmailSendError(
            "SMTP is not configured. Set " + ", ".join(missing) + " in .env."
        )

    port = _smtp_port()
    _resolve_smtp_host(port)

    candidate_email = _validated_address(letter.candidate_email, "Candidate email")
    from_email = _validated_address(SMTP_FROM_EMAIL, "SMTP_FROM_EMAIL")
    reply_to = _validated_address(company.email, "Company email for Reply-To")

    message = EmailMessage()
    message["Subject"] = (
        f"Offer Letter - {_header_text(letter.position)} "
        f"at {_header_text(company.name)}"
    )
    message["From"] = from_email
    message["To"] = candidate_email
    message["Reply-To"] = reply_to
    message.set_content(
        f"Dear {letter.candidate_name},\n\n"
        f"We are pleased to offer you the position of {letter.position}. "
        f"Your start date is {letter.start_date.strftime('%B %d, %Y')}.\n\n"
        "Please find your offer letter attached. We look forward to welcoming you.\n\n"
        f"Regards,\n{company.name}"
    )
    message.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=attachment_filename,
    )

    try:
        if port == 465:
            smtp_connection = smtplib.SMTP_SSL(
                SMTP_HOST,
                port,
                timeout=30,
                context=ssl.create_default_context(),
            )
        else:
            smtp_connection = smtplib.SMTP(SMTP_HOST, port, timeout=30)
        with smtp_connection as smtp:
            if port != 465:
                smtp.starttls(context=ssl.create_default_context())
            smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException, ValueError, OverflowError) as exc:
        raise EmailSendError(f"SMTP delivery failed: {exc}") from exc
