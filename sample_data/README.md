# Sample Data

These sample inputs are fully synthetic and safe for demo/testing. They use fake names, fake addresses, fake case numbers, fake dates, and fake amounts. They are not copied from real legal templates and do not contain real personal information.

Files:

- `sample_notice.txt` - synthetic notice of default with alleged unpaid rent, missing attachments, and unclear items.
- `sample_case_note.txt` - synthetic internal case note with parties, dates, monetary amount, open questions, and suggested follow-up.
- `sample_notice.pdf` - generated PDF version of the synthetic notice for digital PDF extraction testing.
- `sample_notice_scanned.png` - generated scanned-style image version of the synthetic notice for OCR testing.

Suggested demo path:

1. Upload `sample_notice.txt`, `sample_notice.pdf`, or `sample_notice_scanned.png`.
2. Process the document.
3. Extract structured fields.
4. Index for retrieval.
5. Retrieve evidence using a query such as `unpaid rent cure deadline`.
6. Generate a grounded draft.
7. Edit the draft and save the operator edit.
8. Review learned rules.
9. Generate an improved draft.

OCR note:

Use `sample_notice.txt` or `sample_notice.pdf` for the fastest offline demo. Use `sample_notice_scanned.png` when EasyOCR is installed and initialized. The first EasyOCR run may download model weights. If `OCR_ENGINE=auto` is set, Tesseract can be used as an optional fallback when it is installed on the system.
