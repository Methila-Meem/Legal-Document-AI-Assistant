"use client";

import { useEffect, useState } from "react";
import { DocumentUpload } from "@/components/DocumentUpload";
import {
  checkBackendHealth,
  extractStructuredFields,
  generateDraft,
  indexDocument,
  processDocument,
  queryRetrieval,
  type EvidenceChunk,
  type GeneratedDraft,
  type HealthStatus,
  type IndexedDocument,
  type ProcessedDocument,
  type RetrievalQueryResult,
  type StructuredExtraction,
  type UploadedDocument,
} from "@/lib/api";

const secondaryPanels = [
  {
    title: "Rules",
    subtitle: "Learned rules placeholder",
    body: "Reusable operator improvement rules will be managed here.",
  },
];

export default function DashboardPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [uploadedDocument, setUploadedDocument] = useState<UploadedDocument | null>(null);
  const [processedDocument, setProcessedDocument] = useState<ProcessedDocument | null>(null);
  const [processingError, setProcessingError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [structuredExtraction, setStructuredExtraction] = useState<StructuredExtraction | null>(null);
  const [fieldExtractionError, setFieldExtractionError] = useState<string | null>(null);
  const [isExtractingFields, setIsExtractingFields] = useState(false);
  const [indexedDocument, setIndexedDocument] = useState<IndexedDocument | null>(null);
  const [indexingError, setIndexingError] = useState<string | null>(null);
  const [isIndexing, setIsIndexing] = useState(false);
  const [retrievalQuery, setRetrievalQuery] = useState(
    "Generate a case fact summary from this document.",
  );
  const [retrievalResult, setRetrievalResult] = useState<RetrievalQueryResult | null>(null);
  const [retrievalError, setRetrievalError] = useState<string | null>(null);
  const [isRetrieving, setIsRetrieving] = useState(false);
  const [generatedDraft, setGeneratedDraft] = useState<GeneratedDraft | null>(null);
  const [draftText, setDraftText] = useState("");
  const [draftError, setDraftError] = useState<string | null>(null);
  const [isGeneratingDraft, setIsGeneratingDraft] = useState(false);

  useEffect(() => {
    checkBackendHealth()
      .then((result) => {
        setHealth(result);
        setHealthError(null);
      })
      .catch((error: Error) => {
        setHealth(null);
        setHealthError(error.message);
      });
  }, []);

  return (
    <main className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-6 py-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-medium text-slate-500">AI Engineer Assessment</p>
            <h1 className="text-2xl font-semibold text-slate-950">Legal Document AI Assistant</h1>
          </div>
          <div className="flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                health?.status === "ok" ? "bg-emerald-500" : "bg-amber-500"
              }`}
              aria-hidden="true"
            />
            <span className="font-medium text-slate-700">
              {health?.status === "ok" ? "Backend online" : "Backend pending"}
            </span>
          </div>
        </div>
      </header>

      <section className="mx-auto grid max-w-7xl gap-4 px-6 py-6 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="grid gap-4">
          <DashboardPanel title="Upload" subtitle="Upload legal-style source document">
            <DocumentUpload
              onUploaded={(document) => {
                setUploadedDocument(document);
                setProcessedDocument(null);
                setProcessingError(null);
                setStructuredExtraction(null);
                setFieldExtractionError(null);
                setIndexedDocument(null);
                setIndexingError(null);
                setRetrievalResult(null);
                setRetrievalError(null);
                setGeneratedDraft(null);
                setDraftText("");
                setDraftError(null);
              }}
            />
          </DashboardPanel>
          <DashboardPanel title="Processing" subtitle="Document processing status placeholder">
            <ProcessingPanel
              uploadedDocument={uploadedDocument}
              processedDocument={processedDocument}
              processingError={processingError}
              isProcessing={isProcessing}
              onProcess={async () => {
                if (!uploadedDocument) {
                  return;
                }
                setIsProcessing(true);
                setProcessingError(null);
                setProcessedDocument(null);
                try {
                  const result = await processDocument(uploadedDocument.document_id);
                  setProcessedDocument(result);
                  setStructuredExtraction(null);
                  setFieldExtractionError(null);
                  setIndexedDocument(null);
                  setIndexingError(null);
                  setRetrievalResult(null);
                  setRetrievalError(null);
                  setGeneratedDraft(null);
                  setDraftText("");
                  setDraftError(null);
                } catch (error) {
                  setProcessingError(
                    error instanceof Error ? error.message : "Document processing failed.",
                  );
                } finally {
                  setIsProcessing(false);
                }
              }}
            />
          </DashboardPanel>
          <DashboardPanel title="Draft" subtitle="Grounded case fact summary">
            <DraftPanel
              indexedDocument={indexedDocument}
              generatedDraft={generatedDraft}
              draftText={draftText}
              error={draftError}
              isGenerating={isGeneratingDraft}
              onDraftChange={setDraftText}
              onGenerate={async () => {
                if (!indexedDocument) {
                  return;
                }
                setIsGeneratingDraft(true);
                setDraftError(null);
                try {
                  const result = await generateDraft(indexedDocument.document_id);
                  setGeneratedDraft(result);
                  setDraftText(result.draft);
                } catch (error) {
                  setDraftError(
                    error instanceof Error ? error.message : "Draft generation failed.",
                  );
                } finally {
                  setIsGeneratingDraft(false);
                }
              }}
            />
          </DashboardPanel>
        </div>
        <aside className="grid gap-4">
          <DashboardPanel title="Structured Fields" subtitle="Extracted legal metadata">
            <StructuredFieldsPanel
              processedDocument={processedDocument}
              structuredExtraction={structuredExtraction}
              error={fieldExtractionError}
              isExtracting={isExtractingFields}
              onExtract={async () => {
                if (!processedDocument) {
                  return;
                }
                setIsExtractingFields(true);
                setFieldExtractionError(null);
                try {
                  const result = await extractStructuredFields(processedDocument.document_id);
                  setStructuredExtraction(result);
                } catch (error) {
                  setFieldExtractionError(
                    error instanceof Error ? error.message : "Field extraction failed.",
                  );
                } finally {
                  setIsExtractingFields(false);
                }
              }}
            />
          </DashboardPanel>
          <DashboardPanel title="Retrieval Index" subtitle="Chunk and vector status">
            <IndexPanel
              processedDocument={processedDocument}
              indexedDocument={indexedDocument}
              error={indexingError}
              isIndexing={isIndexing}
              onIndex={async () => {
                if (!processedDocument) {
                  return;
                }
                setIsIndexing(true);
                setIndexingError(null);
                try {
                  const result = await indexDocument(processedDocument.document_id);
                  setIndexedDocument(result);
                  setRetrievalResult(null);
                  setRetrievalError(null);
                  setGeneratedDraft(null);
                  setDraftText("");
                  setDraftError(null);
                } catch (error) {
                  setIndexingError(error instanceof Error ? error.message : "Indexing failed.");
                } finally {
                  setIsIndexing(false);
                }
              }}
            />
          </DashboardPanel>
          <DashboardPanel title="Retrieval Test" subtitle="Query indexed evidence">
            <RetrievalQueryPanel
              indexedDocument={indexedDocument}
              query={retrievalQuery}
              error={retrievalError}
              isRetrieving={isRetrieving}
              onQueryChange={setRetrievalQuery}
              onRetrieve={async () => {
                if (!indexedDocument) {
                  return;
                }
                setIsRetrieving(true);
                setRetrievalError(null);
                try {
                  const result = await queryRetrieval(indexedDocument.document_id, retrievalQuery, 6);
                  setRetrievalResult(result);
                } catch (error) {
                  setRetrievalError(error instanceof Error ? error.message : "Retrieval failed.");
                } finally {
                  setIsRetrieving(false);
                }
              }}
            />
          </DashboardPanel>
          <DashboardPanel title="Evidence" subtitle="Retrieved document evidence">
            <EvidencePanel
              evidence={generatedDraft?.evidence ?? retrievalResult?.evidence ?? null}
              message={retrievalResult?.message ?? null}
              heading={generatedDraft ? "Evidence used for draft" : "Retrieved evidence"}
            />
          </DashboardPanel>
          {secondaryPanels.map((panel) => (
            <DashboardPanel key={panel.title} {...panel} />
          ))}
          <section className="rounded-md border border-slate-200 bg-white p-5">
            <h2 className="text-base font-semibold text-slate-950">Backend Health</h2>
            <p className="mt-2 text-sm text-slate-600">
              {health
                ? `${health.service} ${health.version} responded with status ${health.status}.`
                : healthError ?? "Checking backend health..."}
            </p>
          </section>
        </aside>
      </section>
    </main>
  );
}

function StructuredFieldsPanel({
  processedDocument,
  structuredExtraction,
  error,
  isExtracting,
  onExtract,
}: {
  processedDocument: ProcessedDocument | null;
  structuredExtraction: StructuredExtraction | null;
  error: string | null;
  isExtracting: boolean;
  onExtract: () => void;
}) {
  if (!processedDocument) {
    return (
      <div className="min-h-28 rounded-md border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600">
        Process a document to enable field extraction.
      </div>
    );
  }

  const fields = structuredExtraction?.structured_fields;

  return (
    <div className="space-y-4 rounded-md border border-slate-200 bg-slate-50 p-4 text-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-medium text-slate-900">Structured extraction</p>
          <p className="text-slate-600">
            {structuredExtraction ? `Method: ${structuredExtraction.method}` : "Ready after processing."}
          </p>
        </div>
        <button
          type="button"
          onClick={onExtract}
          disabled={isExtracting}
          className="rounded-md bg-slate-950 px-3 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
        >
          {isExtracting ? "Extracting..." : "Extract Fields"}
        </button>
      </div>

      {error ? (
        <p className="rounded-md border border-red-200 bg-red-50 p-3 text-red-700">{error}</p>
      ) : null}

      {structuredExtraction?.warnings.length ? (
        <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-amber-800">
          {structuredExtraction.warnings.join(" ")}
        </div>
      ) : null}

      {fields ? (
        <div className="space-y-3">
          <FieldRow label="Document type" value={fields.document_type ?? "Not detected"} />
          <ListField label="Parties" values={fields.parties} />
          <ListField label="Dates" values={fields.dates} />
          <ListField label="Addresses" values={fields.addresses} />
          <ListField label="Monetary amounts" values={fields.monetary_amounts} />
          <ListField label="Case numbers" values={fields.case_numbers} />
          <div className="rounded-md border border-slate-200 bg-white p-3">
            <p className="font-medium text-slate-900">Key events</p>
            {fields.key_events.length ? (
              <ul className="mt-2 space-y-2 text-slate-600">
                {fields.key_events.map((event, index) => (
                  <li key={`${event.event}-${index}`}>
                    {event.event}
                    {event.date ? ` · ${event.date}` : ""}
                    {event.source_page ? ` · page ${event.source_page}` : ""}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-slate-500">None detected.</p>
            )}
          </div>
          <ListField label="Unclear items" values={fields.unclear_items} />
        </div>
      ) : null}
    </div>
  );
}

function FieldRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-3">
      <p className="font-medium text-slate-900">{label}</p>
      <p className="mt-2 text-slate-600">{value}</p>
    </div>
  );
}

function ListField({ label, values }: { label: string; values: string[] }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-3">
      <p className="font-medium text-slate-900">{label}</p>
      {values.length ? (
        <ul className="mt-2 space-y-1 text-slate-600">
          {values.map((value) => (
            <li key={value}>{value}</li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-slate-500">None detected.</p>
      )}
    </div>
  );
}

function DashboardPanel({
  title,
  subtitle,
  body,
  children,
}: {
  title: string;
  subtitle: string;
  body?: string;
  children?: React.ReactNode;
}) {
  return (
    <section className="rounded-md border border-slate-200 bg-white p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
          <p className="mt-1 text-sm font-medium text-slate-500">{subtitle}</p>
        </div>
        <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">
          Phase 7
        </span>
      </div>
      <div className="mt-4">
        {children ?? (
          <div className="min-h-28 rounded-md border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600">
            {body}
          </div>
        )}
      </div>
    </section>
  );
}

function DraftPanel({
  indexedDocument,
  generatedDraft,
  draftText,
  error,
  isGenerating,
  onDraftChange,
  onGenerate,
}: {
  indexedDocument: IndexedDocument | null;
  generatedDraft: GeneratedDraft | null;
  draftText: string;
  error: string | null;
  isGenerating: boolean;
  onDraftChange: (value: string) => void;
  onGenerate: () => void;
}) {
  if (!indexedDocument) {
    return (
      <div className="min-h-28 rounded-md border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600">
        Index a processed document to enable grounded draft generation.
      </div>
    );
  }

  return (
    <div className="space-y-4 rounded-md border border-slate-200 bg-slate-50 p-4 text-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-medium text-slate-900">Case fact summary</p>
          <p className="text-slate-600">
            {generatedDraft ? `Model: ${generatedDraft.model_used}` : "Ready to generate from evidence."}
          </p>
        </div>
        <button
          type="button"
          onClick={onGenerate}
          disabled={isGenerating}
          className="rounded-md bg-slate-950 px-3 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
        >
          {isGenerating ? "Generating..." : "Generate Draft"}
        </button>
      </div>

      <p className="rounded-md border border-amber-200 bg-amber-50 p-3 text-amber-800">
        This draft is generated only from retrieved evidence and may require human review.
      </p>

      {error ? (
        <p className="rounded-md border border-red-200 bg-red-50 p-3 text-red-700">{error}</p>
      ) : null}

      {generatedDraft ? (
        <div className="space-y-3">
          <p className="text-slate-600">{generatedDraft.grounding_note}</p>
          <textarea
            value={draftText}
            onChange={(event) => onDraftChange(event.target.value)}
            rows={18}
            className="w-full resize-y rounded-md border border-slate-300 bg-white px-3 py-2 font-mono text-sm text-slate-900 outline-none transition focus:border-slate-500"
          />
        </div>
      ) : null}
    </div>
  );
}

function RetrievalQueryPanel({
  indexedDocument,
  query,
  error,
  isRetrieving,
  onQueryChange,
  onRetrieve,
}: {
  indexedDocument: IndexedDocument | null;
  query: string;
  error: string | null;
  isRetrieving: boolean;
  onQueryChange: (value: string) => void;
  onRetrieve: () => void;
}) {
  if (!indexedDocument) {
    return (
      <div className="min-h-28 rounded-md border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600">
        Index a processed document to test evidence retrieval.
      </div>
    );
  }

  return (
    <div className="space-y-4 rounded-md border border-slate-200 bg-slate-50 p-4 text-sm">
      <label className="block">
        <span className="font-medium text-slate-900">Retrieval query</span>
        <textarea
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          rows={3}
          className="mt-2 w-full resize-none rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-900 outline-none transition focus:border-slate-500"
        />
      </label>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-slate-600">Top 6 chunks from document {indexedDocument.document_id}</p>
        <button
          type="button"
          onClick={onRetrieve}
          disabled={isRetrieving || !query.trim()}
          className="rounded-md bg-slate-950 px-3 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
        >
          {isRetrieving ? "Retrieving..." : "Retrieve Evidence"}
        </button>
      </div>
      {error ? (
        <p className="rounded-md border border-red-200 bg-red-50 p-3 text-red-700">{error}</p>
      ) : null}
    </div>
  );
}

function EvidencePanel({
  evidence,
  message,
  heading,
}: {
  evidence: EvidenceChunk[] | null;
  message: string | null;
  heading: string;
}) {
  if (!evidence) {
    return (
      <div className="min-h-28 rounded-md border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600">
        Retrieved chunks and source details will appear here after a retrieval query.
      </div>
    );
  }

  if (!evidence.length) {
    return (
      <div className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
        {message ?? "No evidence found for this query."}
      </div>
    );
  }

  return (
    <div className="space-y-3 text-sm">
      <p className="font-medium text-slate-900">{heading}</p>
      {evidence.map((chunk) => (
        <EvidenceCard key={chunk.chunk_id || `${chunk.page_number}-${chunk.text}`} chunk={chunk} />
      ))}
    </div>
  );
}

function EvidenceCard({ chunk }: { chunk: EvidenceChunk }) {
  return (
    <article className="rounded-md border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="font-medium text-slate-900">Page {chunk.page_number}</p>
          <p className="text-slate-600">{chunk.source.filename || "Unknown file"}</p>
        </div>
        <p className="rounded-md bg-white px-2 py-1 text-xs font-medium text-slate-700">
          Score {chunk.relevance_score.toFixed(2)}
        </p>
      </div>
      <p className="mt-2 text-xs uppercase text-slate-500">
        {chunk.source.source_type || "unknown source"}
        {chunk.source.ocr_confidence === null
          ? ""
          : ` | OCR ${(chunk.source.ocr_confidence * 100).toFixed(0)}%`}
      </p>
      <p className="mt-3 line-clamp-6 whitespace-pre-wrap text-slate-700">
        {chunk.text || "No chunk text returned."}
      </p>
    </article>
  );
}

function IndexPanel({
  processedDocument,
  indexedDocument,
  error,
  isIndexing,
  onIndex,
}: {
  processedDocument: ProcessedDocument | null;
  indexedDocument: IndexedDocument | null;
  error: string | null;
  isIndexing: boolean;
  onIndex: () => void;
}) {
  if (!processedDocument) {
    return (
      <div className="min-h-28 rounded-md border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600">
        Process a document to enable retrieval indexing.
      </div>
    );
  }

  return (
    <div className="space-y-4 rounded-md border border-slate-200 bg-slate-50 p-4 text-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-medium text-slate-900">Retrieval-ready index</p>
          <p className="text-slate-600">
            {indexedDocument
              ? `${indexedDocument.chunk_count} chunks in ${indexedDocument.vector_db}`
              : "Ready to create chunks and embeddings."}
          </p>
        </div>
        <button
          type="button"
          onClick={onIndex}
          disabled={isIndexing}
          className="rounded-md bg-slate-950 px-3 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
        >
          {isIndexing ? "Indexing..." : "Index for Retrieval"}
        </button>
      </div>

      {error ? (
        <p className="rounded-md border border-red-200 bg-red-50 p-3 text-red-700">{error}</p>
      ) : null}

      {indexedDocument ? (
        <div className="rounded-md border border-slate-200 bg-white p-3 text-slate-600">
          <p>Status: {indexedDocument.status}</p>
          <p>Embedding model: {indexedDocument.embedding_model}</p>
          <p>Vector DB: {indexedDocument.vector_db}</p>
        </div>
      ) : null}
    </div>
  );
}

function ProcessingPanel({
  uploadedDocument,
  processedDocument,
  processingError,
  isProcessing,
  onProcess,
}: {
  uploadedDocument: UploadedDocument | null;
  processedDocument: ProcessedDocument | null;
  processingError: string | null;
  isProcessing: boolean;
  onProcess: () => void;
}) {
  if (!uploadedDocument) {
    return (
      <div className="min-h-28 rounded-md border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600">
        Upload a document to enable processing.
      </div>
    );
  }

  return (
    <div className="space-y-4 rounded-md border border-slate-200 bg-slate-50 p-4 text-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-medium text-slate-900">{uploadedDocument.original_filename}</p>
          <p className="text-slate-600">Document ID: {uploadedDocument.document_id}</p>
        </div>
        <button
          type="button"
          onClick={onProcess}
          disabled={isProcessing}
          className="rounded-md bg-slate-950 px-3 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
        >
          {isProcessing ? "Processing..." : "Process Document"}
        </button>
      </div>

      {processingError ? (
        <p className="rounded-md border border-red-200 bg-red-50 p-3 text-red-700">
          {processingError}
        </p>
      ) : null}

      {processedDocument ? (
        <div className="space-y-3">
          <p className="font-medium text-slate-900">
            Processed {processedDocument.page_count} page
            {processedDocument.page_count === 1 ? "" : "s"}.
          </p>
          {processedDocument.warnings.length > 0 ? (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-amber-800">
              {processedDocument.warnings.join(" ")}
            </div>
          ) : null}
          <div className="space-y-3">
            {processedDocument.pages.map((page) => (
              <div key={page.page_number} className="rounded-md border border-slate-200 bg-white p-3">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <p className="font-medium text-slate-900">Page {page.page_number}</p>
                  <p className="text-slate-600">
                    {page.source_type}
                    {page.ocr_confidence === null
                      ? ""
                      : ` · Confidence ${(page.ocr_confidence * 100).toFixed(0)}%`}
                  </p>
                </div>
                <p className="mt-2 text-slate-600">
                  {page.text_preview || "No readable text was extracted."}
                </p>
                {page.is_unclear ? (
                  <p className="mt-2 text-amber-700">This page may need operator review.</p>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
