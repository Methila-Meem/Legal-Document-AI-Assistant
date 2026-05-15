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
- Placeholders for processing, evidence, drafts, and learned rules
