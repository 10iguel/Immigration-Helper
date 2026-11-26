"""Fills the official fillable Form I-765 with FAKE data, so form review is tested on real PDFs without real people."""
from pathlib import Path

import pymupdf

from immigration_helper.review import i765_rules as fields

I765_PDF = Path("data/forms/i-765.pdf")
_FIELD_PREFIX = "form1[0]."

# A correctly filled form. Every value is made up.
CORRECT_TEXT = {
    fields.FAMILY_NAME: "Testperson",
    fields.GIVEN_NAME: "Alex",
    fields.MAILING_ADDRESS["street number and name (5.b)"]: "100 Example St",
    fields.MAILING_ADDRESS["city or town (5.d)"]: "Provo",
    fields.MAILING_ADDRESS["state (5.e)"]: "UT",
    fields.MAILING_ADDRESS["ZIP code (5.f)"]: "84601",
    fields.A_NUMBER: "N/A",
    fields.DATE_OF_BIRTH: "05/14/1990",
    fields.CATEGORY[0]: "c",
    fields.CATEGORY[1]: "9",
    fields.DAYTIME_PHONE: "8015550100",
    fields.SIGNATURE_DATE: "11/01/2026",
}
CORRECT_CHECKED = {fields.REASON[0], fields.SEX[0], fields.MARITAL_STATUS[2]}


def fill_i765(text: dict[str, str] | None = None, checked: set[str] | None = None) -> bytes:
    """The I-765 PDF with these text values and checked boxes (defaults: the correct form)."""
    text = CORRECT_TEXT if text is None else text
    checked = CORRECT_CHECKED if checked is None else checked
    with pymupdf.open(I765_PDF) as document:
        for page in document:
            for widget in page.widgets():
                name = widget.field_name.removeprefix(_FIELD_PREFIX)
                if name in text:
                    widget.field_value = text[name]
                    widget.update()
                elif name in checked:
                    widget.field_value = widget.on_state()
                    widget.update()
        return document.tobytes()
