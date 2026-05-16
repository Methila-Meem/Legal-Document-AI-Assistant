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
  ocr_engine: string | null;
  is_unclear: boolean;
  warnings: string[];
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

export type EvidenceChunk = {
  chunk_id: string;
  document_id: string;
  page_number: number;
  text: string;
  relevance_score: number;
  source: {
    filename: string;
    source_type: string;
    ocr_confidence: number | null;
  };
};

export type RetrievalQueryResult = {
  query: string;
  document_id: string;
  evidence: EvidenceChunk[];
  message: string | null;
};

export type GeneratedDraft = {
  draft_id: string;
  document_id: string;
  draft_type: "case_fact_summary" | string;
  draft: string;
  evidence: EvidenceChunk[];
  model_used: string;
  grounding_note: string;
  applied_learning_rules: LearnedRule[];
  learning_rules_warning: string | null;
};

export type LearnedRule = {
  rule_id: string;
  rule_type: string;
  rule_text: string;
  example_before: string | null;
  example_after: string | null;
  is_active: boolean;
  source_edit_id?: string | null;
};

export type DraftEditResult = {
  edit_id: string;
  draft_id: string;
  learned_rules: LearnedRule[];
  message: string;
  warning: string | null;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function formatApiError(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== "object") {
    return fallback;
  }
  const candidate = payload as {
    detail?: unknown;
    error?: { message?: unknown; details?: unknown };
  };
  const details = candidate.error?.details;
  if (details && typeof details === "object") {
    const diagnostic = details as {
      message?: unknown;
      error?: unknown;
      hint?: unknown;
    };
    const parts = [
      diagnostic.message,
      summarizeDiagnosticText(diagnostic.error),
      diagnostic.hint,
    ]
      .filter((part): part is string => typeof part === "string" && part.trim().length > 0);
    if (parts.length) {
      return parts.join(" ");
    }
  }
  if (typeof candidate.error?.message === "string") {
    return candidate.error.message;
  }
  if (typeof candidate.detail === "string") {
    return candidate.detail;
  }
  if (candidate.detail && typeof candidate.detail === "object") {
    const diagnostic = candidate.detail as {
      message?: unknown;
      error?: unknown;
      hint?: unknown;
    };
    const parts = [
      diagnostic.message,
      summarizeDiagnosticText(diagnostic.error),
      diagnostic.hint,
    ]
      .filter((part): part is string => typeof part === "string" && part.trim().length > 0);
    if (parts.length) {
      return parts.join(" ");
    }
  }
  return fallback;
}

function summarizeDiagnosticText(value: unknown): string | null {
  if (typeof value !== "string" || !value.trim()) {
    return null;
  }
  const lines = value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const importantLine =
    [...lines].reverse().find((line) => /error|exception|no module|winerror|failed/i.test(line)) ??
    lines[0];
  if (!importantLine) {
    return null;
  }
  return importantLine.length > 400 ? `${importantLine.slice(0, 397)}...` : importantLine;
}

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
      message = formatApiError(payload, message);
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

export async function queryRetrieval(
  documentId: string,
  query: string,
  topK = 6,
): Promise<RetrievalQueryResult> {
  const response = await fetch(`${API_BASE_URL}/api/retrieval/query`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      document_id: documentId,
      query,
      top_k: topK,
    }),
  });

  if (!response.ok) {
    let message = `Retrieval failed with status ${response.status}`;
    try {
      const payload = await response.json();
      message = payload?.error?.message ?? payload?.detail ?? message;
    } catch {
      // Keep the generic status message when the response is not JSON.
    }
    throw new Error(message);
  }

  return response.json() as Promise<RetrievalQueryResult>;
}

export async function generateDraft(
  documentId: string,
  draftType = "case_fact_summary",
  topK = 8,
): Promise<GeneratedDraft> {
  const response = await fetch(`${API_BASE_URL}/api/drafts/generate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      document_id: documentId,
      draft_type: draftType,
      top_k: topK,
    }),
  });

  if (!response.ok) {
    let message = `Draft generation failed with status ${response.status}`;
    try {
      const payload = await response.json();
      message = payload?.error?.message ?? payload?.detail ?? message;
    } catch {
      // Keep the generic status message when the response is not JSON.
    }
    throw new Error(message);
  }

  const payload = (await response.json()) as GeneratedDraft;
  return {
    ...payload,
    evidence: payload.evidence ?? [],
    applied_learning_rules: payload.applied_learning_rules ?? [],
    learning_rules_warning: payload.learning_rules_warning ?? null,
  };
}

export async function saveOperatorEdit(
  draftId: string,
  editedDraft: string,
): Promise<DraftEditResult> {
  const response = await fetch(`${API_BASE_URL}/api/drafts/${draftId}/edits`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      edited_draft: editedDraft,
    }),
  });

  if (!response.ok) {
    let message = `Saving operator edit failed with status ${response.status}`;
    try {
      const payload = await response.json();
      message = payload?.error?.message ?? payload?.detail ?? message;
    } catch {
      // Keep the generic status message when the response is not JSON.
    }
    throw new Error(message);
  }

  return response.json() as Promise<DraftEditResult>;
}

export async function getLearningRules(): Promise<LearnedRule[]> {
  const response = await fetch(`${API_BASE_URL}/api/learning-rules`, {
    cache: "no-store",
  });

  if (!response.ok) {
    let message = `Loading learned rules failed with status ${response.status}`;
    try {
      const payload = await response.json();
      message = payload?.error?.message ?? payload?.detail ?? message;
    } catch {
      // Keep the generic status message when the response is not JSON.
    }
    throw new Error(message);
  }

  return response.json() as Promise<LearnedRule[]>;
}

export async function updateLearningRule(
  ruleId: string,
  isActive: boolean,
): Promise<LearnedRule> {
  const response = await fetch(`${API_BASE_URL}/api/learning-rules/${ruleId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      is_active: isActive,
    }),
  });

  if (!response.ok) {
    let message = `Updating learned rule failed with status ${response.status}`;
    try {
      const payload = await response.json();
      message = payload?.error?.message ?? payload?.detail ?? message;
    } catch {
      // Keep the generic status message when the response is not JSON.
    }
    throw new Error(message);
  }

  return response.json() as Promise<LearnedRule>;
}
