export type HealthStatus = {
  status: string;
  service: string;
  version: string;
};

export type UploadedDocument = {
  document_id: string;
  original_filename: string;
  stored_filename: string;
  file_type: string;
  size_bytes: number;
  status: "uploaded";
};

export type ProcessedPage = {
  page_number: number;
  source_type: "pdf_text" | "ocr" | string;
  text_preview: string;
  ocr_confidence: number | null;
  is_unclear: boolean;
};

export type ProcessedDocument = {
  document_id: string;
  status: "processed";
  page_count: number;
  pages: ProcessedPage[];
  warnings: string[];
};

export type KeyEvent = {
  event: string;
  date: string | null;
  source_page: number | null;
};

export type StructuredFields = {
  document_type: string | null;
  parties: string[];
  dates: string[];
  addresses: string[];
  monetary_amounts: string[];
  case_numbers: string[];
  key_events: KeyEvent[];
  unclear_items: string[];
};

export type StructuredExtraction = {
  document_id: string;
  structured_fields: StructuredFields;
  method: "rules" | "llm" | "hybrid" | string;
  warnings: string[];
};

export type IndexedDocument = {
  document_id: string;
  status: "indexed";
  chunk_count: number;
  embedding_model: string;
  vector_db: string;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function checkBackendHealth(): Promise<HealthStatus> {
  const response = await fetch(`${API_BASE_URL}/api/health`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`);
  }

  return response.json() as Promise<HealthStatus>;
}

export async function uploadDocument(file: File): Promise<UploadedDocument> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/api/documents/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    let message = `Upload failed with status ${response.status}`;
    try {
      const payload = await response.json();
      message = payload?.error?.message ?? payload?.detail ?? message;
    } catch {
      // Keep the generic status message when the response is not JSON.
    }
    throw new Error(message);
  }

  return response.json() as Promise<UploadedDocument>;
}

export async function processDocument(documentId: string): Promise<ProcessedDocument> {
  const response = await fetch(`${API_BASE_URL}/api/documents/${documentId}/process`, {
    method: "POST",
  });

  if (!response.ok) {
    let message = `Processing failed with status ${response.status}`;
    try {
      const payload = await response.json();
      message = payload?.error?.message ?? payload?.detail ?? message;
    } catch {
      // Keep the generic status message when the response is not JSON.
    }
    throw new Error(message);
  }

  return response.json() as Promise<ProcessedDocument>;
}

export async function extractStructuredFields(documentId: string): Promise<StructuredExtraction> {
  const response = await fetch(`${API_BASE_URL}/api/documents/${documentId}/extract-fields`, {
    method: "POST",
  });

  if (!response.ok) {
    let message = `Field extraction failed with status ${response.status}`;
    try {
      const payload = await response.json();
      message = payload?.error?.message ?? payload?.detail ?? message;
    } catch {
      // Keep the generic status message when the response is not JSON.
    }
    throw new Error(message);
  }

  return response.json() as Promise<StructuredExtraction>;
}

export async function indexDocument(documentId: string): Promise<IndexedDocument> {
  const response = await fetch(`${API_BASE_URL}/api/documents/${documentId}/index`, {
    method: "POST",
  });

  if (!response.ok) {
    let message = `Indexing failed with status ${response.status}`;
    try {
      const payload = await response.json();
      message = payload?.error?.message ?? payload?.detail ?? message;
    } catch {
      // Keep the generic status message when the response is not JSON.
    }
    throw new Error(message);
  }

  return response.json() as Promise<IndexedDocument>;
}
