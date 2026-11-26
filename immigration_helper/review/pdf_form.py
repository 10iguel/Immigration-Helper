"""Reads the values someone typed into a fillable USCIS PDF form."""
import re
from datetime import datetime

import pymupdf

from immigration_helper.models import FormId
from immigration_helper.review.filled_form import FilledForm

# The footer of every page, e.g. "Form I-765   Edition   08/21/25".
_FOOTER = re.compile(r"Form\s+(I-\d{3}[A-Z]?)\s+Edition\s+(\d{2}/\d{2}/\d{2})")
_FIELD_PREFIX = "form1[0]."


class UnreadableFormError(ValueError):
    """The upload isn't a fillable USCIS form we can read. The message is safe to show the user."""


def read_filled_form(data: bytes) -> FilledForm:
    if not data.startswith(b"%PDF"):
        raise UnreadableFormError("This file isn't a PDF. Upload the filled-in form as a PDF.")
    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except (RuntimeError, ValueError) as error:  # pymupdf's errors for damaged files
        raise UnreadableFormError("This PDF couldn't be opened. It may be damaged.") from error
    with document:
        footer = _FOOTER.search(document[0].get_text()) if document.page_count else None
        if footer is None:
            raise UnreadableFormError("This doesn't look like a USCIS form: its footer has no form number.")
        values = {
            widget.field_name.removeprefix(_FIELD_PREFIX): str(widget.field_value or "")
            for page in document
            for widget in page.widgets()
        }
    if not values:
        raise UnreadableFormError("This PDF has no fillable fields. Fill in the official form from uscis.gov "
                                  "on a computer, save it, and upload that file.")
    edition = datetime.strptime(footer.group(2), "%m/%d/%y").date()
    return FilledForm(FormId(footer.group(1)), edition, values)
