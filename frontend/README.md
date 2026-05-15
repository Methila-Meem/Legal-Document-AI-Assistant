# Frontend

Next.js, TypeScript, and Tailwind CSS dashboard for the Legal Document AI Assistant.

## Setup

```powershell
cd frontend
npm install
npm run dev
```

The frontend expects the backend at `http://localhost:8000` by default. Set `NEXT_PUBLIC_API_BASE_URL` if the backend runs elsewhere.

## Current UI

- Backend health indicator
- Drag-and-drop document upload using `react-dropzone`
- Selected file name, size, upload status, and returned document ID
- Process Document button after upload
- Processing loading state, extracted page previews, OCR confidence, and warnings
- Extract Fields button after processing
- Structured fields panel with method and fallback warnings
- Index for Retrieval button after processing
- Retrieval index panel with chunk count, embedding model, vector DB, and errors
- Retrieval test panel with default query
- Evidence panel with page number, filename, relevance score, source type, OCR confidence, and text preview
- Generate Draft button after indexing
- Editable grounded draft textarea with model and grounding note
- Evidence panel shows the evidence used for the generated draft
- Placeholder for learned rules
