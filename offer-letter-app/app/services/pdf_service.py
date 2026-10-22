from ..config import BASE_DIR


class PDFUnavailable(RuntimeError):
    """WeasyPrint (or its system libraries) is not installed."""


def render_pdf(html: str) -> bytes:
    try:
        from weasyprint import HTML
    except Exception as exc:  # ImportError or missing pango/cairo libs
        raise PDFUnavailable(
            "PDF export needs WeasyPrint and its system libraries. "
            "See README.md. You can still use the Print button on the preview page."
        ) from exc
    return HTML(string=html, base_url=str(BASE_DIR)).write_pdf()
