"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { DocumentUpload } from "@/components/DocumentUpload";
import {
  checkBackendHealth,
  extractStructuredFields,
  generateDraft,
  getLearningRules,
  indexDocument,
  processDocument,
  queryRetrieval,
  saveOperatorEdit,
  updateLearningRule,
  type DraftEditResult,
  type EvidenceChunk,
  type GeneratedDraft,
  type HealthStatus,
  type IndexedDocument,
  type LearnedRule,
  type ProcessedDocument,
  type RetrievalQueryResult,
  type StructuredExtraction,
  type UploadedDocument,
} from "@/lib/api";

type MessageTone = "info" | "success" | "error" | "warning";

type AppMessage = {
  tone: MessageTone;
  title: string;
  body: string;
};

type WorkflowStep = {
  number: number;
  label: string;
  complete: boolean;
  active: boolean;
};

export default function DashboardPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [appMessage, setAppMessage] = useState<AppMessage>({
    tone: "info",
    title: "Ready",
    body: "Start by uploading a PDF, image, or TXT document.",
  });
  const [uploadedDocument, setUploadedDocument] = useState<UploadedDocument | null>(null);
  const [processedDocument, setProcessedDocument] = useState<ProcessedDocument | null>(null);
  const [structuredExtraction, setStructuredExtraction] = useState<StructuredExtraction | null>(null);
  const [indexedDocument, setIndexedDocument] = useState<IndexedDocument | null>(null);
  const [retrievalQuery, setRetrievalQuery] = useState(
    "Generate a case fact summary from this document.",
  );
  const [retrievalResult, setRetrievalResult] = useState<RetrievalQueryResult | null>(null);
  const [generatedDraft, setGeneratedDraft] = useState<GeneratedDraft | null>(null);
  const [previousDraft, setPreviousDraft] = useState<GeneratedDraft | null>(null);
  const [draftText, setDraftText] = useState("");
  const [editResult, setEditResult] = useState<DraftEditResult | null>(null);
  const [learningRules, setLearningRules] = useState<LearnedRule[]>([]);
  const [loadingAction, setLoadingAction] = useState<string | null>(null);
  const [updatingRuleId, setUpdatingRuleId] = useState<string | null>(null);

  const draftEdited = Boolean(generatedDraft && draftText !== generatedDraft.draft);
  const hasActiveRules = learningRules.some((rule) => rule.is_active);
  const improvedDraftGenerated = Boolean(
    previousDraft && generatedDraft && (generatedDraft.applied_learning_rules ?? []).length > 0,
  );

  const workflowSteps = useMemo<WorkflowStep[]>(
    () => [
      { number: 1, label: "Upload Document", complete: Boolean(uploadedDocument), active: !uploadedDocument },
      {
        number: 2,
        label: "Process Document",
        complete: Boolean(processedDocument),
        active: Boolean(uploadedDocument && !processedDocument),
      },
      {
        number: 3,
        label: "Extract Structured Fields",
        complete: Boolean(structuredExtraction),
        active: Boolean(processedDocument && !structuredExtraction),
      },
      {
        number: 4,
        label: "Index for Retrieval",
        complete: Boolean(indexedDocument),
        active: Boolean(processedDocument && !indexedDocument),
      },
      {
        number: 5,
        label: "Retrieve Evidence",
        complete: Boolean(retrievalResult),
        active: Boolean(indexedDocument && !retrievalResult),
      },
      {
        number: 6,
        label: "Generate Grounded Draft",
        complete: Boolean(generatedDraft),
        active: Boolean(indexedDocument && !generatedDraft),
      },
      {
        number: 7,
        label: "Edit Draft",
        complete: draftEdited,
        active: Boolean(generatedDraft && !draftEdited),
      },
      {
        number: 8,
        label: "Save Operator Edit",
        complete: Boolean(editResult),
        active: Boolean(draftEdited && !editResult),
      },
      {
        number: 9,
        label: "View Learned Rules",
        complete: learningRules.length > 0,
        active: Boolean(editResult && learningRules.length === 0),
      },
      {
        number: 10,
        label: "Generate Improved Draft",
        complete: improvedDraftGenerated,
        active: Boolean(hasActiveRules && generatedDraft && !improvedDraftGenerated),
      },
    ],
    [
      draftEdited,
      editResult,
      generatedDraft,
      hasActiveRules,
      improvedDraftGenerated,
      indexedDocument,
      learningRules.length,
      processedDocument,
      retrievalResult,
      structuredExtraction,
      uploadedDocument,
    ],
  );

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

  useEffect(() => {
    void refreshLearningRules();
  }, []);

  async function refreshLearningRules() {
    try {
      const rules = await getLearningRules();
      setLearningRules(rules);
    } catch (error) {
      setAppMessage({
        tone: "warning",
        title: "Learned rules unavailable",
        body: getErrorMessage(error, "Unable to load learned rules."),
      });
    }
  }

  function resetAfterUpload(document: UploadedDocument) {
    setUploadedDocument(document);
    setProcessedDocument(null);
    setStructuredExtraction(null);
    setIndexedDocument(null);
    setRetrievalResult(null);
    setGeneratedDraft(null);
    setPreviousDraft(null);
    setDraftText("");
    setEditResult(null);
    setAppMessage({
      tone: "success",
      title: "Document uploaded",
      body: `${document.original_filename} is ready for processing.`,
    });
  }

  async function runAction(action: string, work: () => Promise<void>) {
    setLoadingAction(action);
    try {
      await work();
    } catch (error) {
      setAppMessage({
        tone: "error",
        title: "Action failed",
        body: getErrorMessage(error, "The request could not be completed."),
      });
    } finally {
      setLoadingAction(null);
    }
  }

  const handleProcess = () =>
    runAction("process", async () => {
      if (!uploadedDocument) {
        return;
      }
      const result = await processDocument(uploadedDocument.document_id);
      setProcessedDocument(result);
      setStructuredExtraction(null);
      setIndexedDocument(null);
      setRetrievalResult(null);
      setGeneratedDraft(null);
      setPreviousDraft(null);
      setDraftText("");
      setEditResult(null);
      setAppMessage({
        tone: "success",
        title: "Document processed",
        body: `${result.page_count} page${result.page_count === 1 ? "" : "s"} extracted.`,
      });
    });

  const handleExtract = () =>
    runAction("extract", async () => {
      if (!processedDocument) {
        return;
      }
      const result = await extractStructuredFields(processedDocument.document_id);
      setStructuredExtraction(result);
      setAppMessage({
        tone: "success",
        title: "Structured fields extracted",
        body: `Extraction method: ${result.method}.`,
      });
    });

  const handleIndex = () =>
    runAction("index", async () => {
      if (!processedDocument) {
        return;
      }
      const result = await indexDocument(processedDocument.document_id);
      setIndexedDocument(result);
      setRetrievalResult(null);
      setGeneratedDraft(null);
      setPreviousDraft(null);
      setDraftText("");
      setEditResult(null);
      setAppMessage({
        tone: "success",
        title: "Document indexed",
        body: `${result.chunk_count} chunks are ready in ${result.vector_db}.`,
      });
    });

  const handleRetrieve = () =>
    runAction("retrieve", async () => {
      if (!indexedDocument) {
        return;
      }
      const result = await queryRetrieval(indexedDocument.document_id, retrievalQuery, 6);
      setRetrievalResult(result);
      setAppMessage({
        tone: result.evidence.length ? "success" : "warning",
        title: result.evidence.length ? "Evidence retrieved" : "No evidence found",
        body: result.evidence.length
          ? `${result.evidence.length} evidence chunk${result.evidence.length === 1 ? "" : "s"} returned.`
          : result.message ?? "Try a more specific retrieval query.",
      });
    });

  const handleGenerate = () =>
    runAction("generate", async () => {
      if (!indexedDocument) {
        return;
      }
      const previous = generatedDraft;
      const result = await generateDraft(indexedDocument.document_id);
      const changedFromPrevious = previous
        ? normalizeDraftText(previous.draft) !== normalizeDraftText(result.draft)
        : null;
      setPreviousDraft(previous);
      setGeneratedDraft(result);
      setDraftText(result.draft);
      setEditResult(null);
      setAppMessage({
        tone: changedFromPrevious === false ? "warning" : "success",
        title:
          changedFromPrevious === false
            ? "Rules were sent, but draft text did not change"
            : (result.applied_learning_rules ?? []).length
              ? "Improved draft generated"
              : "Draft generated",
        body:
          changedFromPrevious === false
            ? "The active learned rules were included in the model request, but the returned draft matched the previous draft."
            : (result.applied_learning_rules ?? []).length
              ? "This draft request included active operator-learned rules."
              : "Grounded draft generated from retrieved evidence.",
      });
    });

  const handleSaveEdit = () =>
    runAction("save-edit", async () => {
      if (!generatedDraft) {
        return;
      }
      const result = await saveOperatorEdit(generatedDraft.draft_id, draftText);
      setEditResult(result);
      await refreshLearningRules();
      setAppMessage({
        tone: result.warning ? "warning" : "success",
        title: "Operator edit saved",
        body: result.warning ?? result.message,
      });
    });

  const handleToggleRule = async (rule: LearnedRule) => {
    setUpdatingRuleId(rule.rule_id);
    try {
      const updated = await updateLearningRule(rule.rule_id, !rule.is_active);
      setLearningRules((current) =>
        current.map((item) => (item.rule_id === updated.rule_id ? updated : item)),
      );
      setAppMessage({
        tone: "success",
        title: updated.is_active ? "Rule enabled" : "Rule disabled",
        body: "Future draft generation will respect the updated active rule set.",
      });
    } catch (error) {
      setAppMessage({
        tone: "error",
        title: "Rule update failed",
        body: getErrorMessage(error, "Unable to update learned rule."),
      });
    } finally {
      setUpdatingRuleId(null);
    }
  };

  return (
    <main className="min-h-screen bg-slate-100">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-6 py-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-medium text-slate-500">AI Engineer Assessment</p>
            <h1 className="text-2xl font-semibold text-slate-950">Legal Document AI Assistant</h1>
          </div>
          <BackendStatus health={health} error={healthError} />
        </div>
      </header>

      <section className="mx-auto grid max-w-7xl gap-5 px-6 py-6 xl:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="space-y-4">
          <WorkflowTracker steps={workflowSteps} />
          <MessageArea message={appMessage} />
          <SystemSnapshot
            uploadedDocument={uploadedDocument}
            processedDocument={processedDocument}
            indexedDocument={indexedDocument}
            generatedDraft={generatedDraft}
            learningRules={learningRules}
          />
        </aside>

        <div className="grid gap-5">
          <section className="grid gap-5 lg:grid-cols-2">
            <DashboardPanel step="1" title="Upload Document" subtitle="PDF, image, or TXT source">
              <DocumentUpload onUploaded={resetAfterUpload} />
            </DashboardPanel>

            <DashboardPanel step="2" title="Process Document" subtitle="Extract page text and OCR signals">
              <ActionPanel
                ready={Boolean(uploadedDocument)}
                complete={Boolean(processedDocument)}
                emptyText="Upload a document to enable processing."
                buttonText="Process Document"
                loadingText="Processing..."
                isLoading={loadingAction === "process"}
                onClick={handleProcess}
              >
                {processedDocument ? <ProcessedSummary processedDocument={processedDocument} /> : null}
              </ActionPanel>
            </DashboardPanel>
          </section>

          <section className="grid gap-5 lg:grid-cols-2">
            <DashboardPanel step="3" title="Extract Structured Fields" subtitle="Parties, dates, money, and key events">
              <StructuredFieldsPanel
                processedDocument={processedDocument}
                structuredExtraction={structuredExtraction}
                isLoading={loadingAction === "extract"}
                onExtract={handleExtract}
              />
            </DashboardPanel>

            <DashboardPanel step="4" title="Index for Retrieval" subtitle="Create chunks and vectors">
              <IndexPanel
                processedDocument={processedDocument}
                indexedDocument={indexedDocument}
                isLoading={loadingAction === "index"}
                onIndex={handleIndex}
              />
            </DashboardPanel>
          </section>

          <section className="grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
            <DashboardPanel step="5" title="Retrieve Evidence" subtitle="Inspect source chunks before drafting">
              <RetrievalPanel
                indexedDocument={indexedDocument}
                query={retrievalQuery}
                result={retrievalResult}
                isLoading={loadingAction === "retrieve"}
                onQueryChange={setRetrievalQuery}
                onRetrieve={handleRetrieve}
              />
            </DashboardPanel>

            <DashboardPanel title="Evidence Panel" subtitle="Filename, page, score, and preview">
              <EvidencePanel
                evidence={generatedDraft?.evidence ?? retrievalResult?.evidence ?? null}
                message={retrievalResult?.message ?? null}
              />
            </DashboardPanel>
          </section>

          <DashboardPanel step="6" title="Generate Grounded Draft" subtitle="Draft from retrieved document evidence">
            <DraftEditorPanel
              indexedDocument={indexedDocument}
              generatedDraft={generatedDraft}
              previousDraft={previousDraft}
              draftText={draftText}
              isGenerating={loadingAction === "generate"}
              isSavingEdit={loadingAction === "save-edit"}
              hasActiveRules={hasActiveRules}
              onGenerate={handleGenerate}
              onDraftChange={setDraftText}
              onSaveEdit={handleSaveEdit}
              editResult={editResult}
            />
          </DashboardPanel>

          <DashboardPanel step="9" title="Learned Rules" subtitle="Operator preferences used for improved drafts">
            <LearnedRulesPanel
              rules={learningRules}
              updatingRuleId={updatingRuleId}
              onToggleRule={handleToggleRule}
            />
          </DashboardPanel>
        </div>
      </section>
    </main>
  );
}

function BackendStatus({ health, error }: { health: HealthStatus | null; error: string | null }) {
  const isOnline = health?.status === "ok";
  return (
    <div className="flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
      <span
        className={`h-2.5 w-2.5 rounded-full ${isOnline ? "bg-emerald-500" : "bg-amber-500"}`}
        aria-hidden="true"
      />
      <span className="font-medium text-slate-700">
        {isOnline ? "Backend online" : error ?? "Backend pending"}
      </span>
    </div>
  );
}

function WorkflowTracker({ steps }: { steps: WorkflowStep[] }) {
  return (
    <section className="rounded-md border border-slate-200 bg-white p-4">
      <h2 className="text-base font-semibold text-slate-950">Reviewer Workflow</h2>
      <ol className="mt-4 space-y-2">
        {steps.map((step) => (
          <li key={step.number} className="flex items-center gap-3 text-sm">
            <span
              className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-md border text-xs font-semibold ${
                step.complete
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                  : step.active
                    ? "border-blue-200 bg-blue-50 text-blue-700"
                    : "border-slate-200 bg-slate-50 text-slate-500"
              }`}
            >
              {step.complete ? "OK" : step.number}
            </span>
            <span className={step.complete ? "text-slate-900" : "text-slate-600"}>
              {step.label}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}

function MessageArea({ message }: { message: AppMessage }) {
  const tone = {
    info: "border-blue-200 bg-blue-50 text-blue-900",
    success: "border-emerald-200 bg-emerald-50 text-emerald-900",
    error: "border-red-200 bg-red-50 text-red-900",
    warning: "border-amber-200 bg-amber-50 text-amber-900",
  }[message.tone];

  return (
    <section className={`rounded-md border p-4 text-sm ${tone}`}>
      <p className="font-semibold">{message.title}</p>
      <p className="mt-1">{message.body}</p>
    </section>
  );
}

function SystemSnapshot({
  uploadedDocument,
  processedDocument,
  indexedDocument,
  generatedDraft,
  learningRules,
}: {
  uploadedDocument: UploadedDocument | null;
  processedDocument: ProcessedDocument | null;
  indexedDocument: IndexedDocument | null;
  generatedDraft: GeneratedDraft | null;
  learningRules: LearnedRule[];
}) {
  const activeRules = learningRules.filter((rule) => rule.is_active).length;
  return (
    <section className="rounded-md border border-slate-200 bg-white p-4 text-sm">
      <h2 className="text-base font-semibold text-slate-950">Current Status</h2>
      <div className="mt-3 space-y-2 text-slate-600">
        <StatusLine label="Document" value={uploadedDocument?.original_filename ?? "Not uploaded"} />
        <StatusLine label="Pages" value={processedDocument ? String(processedDocument.page_count) : "Pending"} />
        <StatusLine label="Index" value={indexedDocument ? `${indexedDocument.chunk_count} chunks` : "Pending"} />
        <StatusLine label="Draft" value={generatedDraft ? `Draft ${generatedDraft.draft_id}` : "Pending"} />
        <StatusLine label="Active rules" value={String(activeRules)} />
      </div>
    </section>
  );
}

function StatusLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <span className="text-slate-500">{label}</span>
      <span className="text-right font-medium text-slate-800">{value}</span>
    </div>
  );
}

function DashboardPanel({
  step,
  title,
  subtitle,
  children,
}: {
  step?: string;
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-md border border-slate-200 bg-white p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            {step ? (
              <span className="rounded-md bg-slate-950 px-2 py-1 text-xs font-semibold text-white">
                Step {step}
              </span>
            ) : null}
            <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
          </div>
          <p className="mt-1 text-sm font-medium text-slate-500">{subtitle}</p>
        </div>
        <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">
          Phase 10
        </span>
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function ActionPanel({
  ready,
  complete,
  emptyText,
  buttonText,
  loadingText,
  isLoading,
  children,
  onClick,
}: {
  ready: boolean;
  complete: boolean;
  emptyText: string;
  buttonText: string;
  loadingText: string;
  isLoading: boolean;
  children: ReactNode;
  onClick: () => void;
}) {
  return (
    <div className="space-y-4 rounded-md border border-slate-200 bg-slate-50 p-4 text-sm">
      {!ready ? <p className="text-slate-600">{emptyText}</p> : null}
      <button
        type="button"
        onClick={onClick}
        disabled={!ready || isLoading}
        className="rounded-md bg-slate-950 px-3 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
      >
        {isLoading ? loadingText : complete ? `Run Again: ${buttonText}` : buttonText}
      </button>
      {children}
    </div>
  );
}

function ProcessedSummary({ processedDocument }: { processedDocument: ProcessedDocument }) {
  return (
    <div className="space-y-3">
      <p className="font-medium text-slate-900">
        Processed {processedDocument.page_count} page
        {processedDocument.page_count === 1 ? "" : "s"}.
      </p>
      {processedDocument.warnings.length ? (
        <p className="rounded-md border border-amber-200 bg-amber-50 p-3 text-amber-800">
          {processedDocument.warnings.join(" ")}
        </p>
      ) : null}
      <div className="space-y-2">
        {processedDocument.pages.map((page) => (
          <div key={page.page_number} className="rounded-md border border-slate-200 bg-white p-3">
            <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
              <p className="font-medium text-slate-900">Page {page.page_number}</p>
              <p className="text-slate-500">
                {page.source_type}
                {page.ocr_engine ? ` | ${page.ocr_engine}` : ""}
                {page.ocr_confidence === null
                  ? ""
                  : ` | OCR ${(page.ocr_confidence * 100).toFixed(0)}%`}
              </p>
            </div>
            <p className="mt-2 text-slate-600">{page.text_preview || "No readable text was extracted."}</p>
            {page.warnings?.length ? (
              <p className="mt-2 text-amber-700">{page.warnings.join(" ")}</p>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}

function StructuredFieldsPanel({
  processedDocument,
  structuredExtraction,
  isLoading,
  onExtract,
}: {
  processedDocument: ProcessedDocument | null;
  structuredExtraction: StructuredExtraction | null;
  isLoading: boolean;
  onExtract: () => void;
}) {
  const fields = structuredExtraction?.structured_fields;

  return (
    <div className="space-y-4 rounded-md border border-slate-200 bg-slate-50 p-4 text-sm">
      <button
        type="button"
        onClick={onExtract}
        disabled={!processedDocument || isLoading}
        className="rounded-md bg-slate-950 px-3 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
      >
        {isLoading ? "Extracting..." : structuredExtraction ? "Run Again: Extract Fields" : "Extract Fields"}
      </button>
      {!processedDocument ? <p className="text-slate-600">Process a document to enable field extraction.</p> : null}
      {structuredExtraction?.warnings.length ? (
        <p className="rounded-md border border-amber-200 bg-amber-50 p-3 text-amber-800">
          {structuredExtraction.warnings.join(" ")}
        </p>
      ) : null}
      {fields ? (
        <div className="grid gap-3 md:grid-cols-2">
          <FieldBlock label="Document type" value={fields.document_type ?? "Not detected"} />
          <ListBlock label="Parties" values={fields.parties} />
          <ListBlock label="Dates" values={fields.dates} />
          <ListBlock label="Money" values={fields.monetary_amounts} />
          <ListBlock label="Case numbers" values={fields.case_numbers} />
          <ListBlock label="Addresses" values={fields.addresses} />
          <div className="rounded-md border border-slate-200 bg-white p-3 md:col-span-2">
            <p className="font-medium text-slate-900">Key events</p>
            {fields.key_events.length ? (
              <ul className="mt-2 space-y-1 text-slate-600">
                {fields.key_events.map((event, index) => (
                  <li key={`${event.event}-${index}`}>
                    {event.event}
                    {event.date ? ` | ${event.date}` : ""}
                    {event.source_page ? ` | page ${event.source_page}` : ""}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-slate-500">None detected.</p>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function FieldBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-3">
      <p className="font-medium text-slate-900">{label}</p>
      <p className="mt-2 text-slate-600">{value}</p>
    </div>
  );
}

function ListBlock({ label, values }: { label: string; values: string[] }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-3">
      <p className="font-medium text-slate-900">{label}</p>
      {values.length ? (
        <ul className="mt-2 space-y-1 text-slate-600">
          {values.map((value, index) => (
            <li key={`${value}-${index}`}>{value}</li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-slate-500">None detected.</p>
      )}
    </div>
  );
}

function IndexPanel({
  processedDocument,
  indexedDocument,
  isLoading,
  onIndex,
}: {
  processedDocument: ProcessedDocument | null;
  indexedDocument: IndexedDocument | null;
  isLoading: boolean;
  onIndex: () => void;
}) {
  return (
    <ActionPanel
      ready={Boolean(processedDocument)}
      complete={Boolean(indexedDocument)}
      emptyText="Process a document to enable retrieval indexing."
      buttonText="Index for Retrieval"
      loadingText="Indexing..."
      isLoading={isLoading}
      onClick={onIndex}
    >
      {indexedDocument ? (
        <div className="rounded-md border border-slate-200 bg-white p-3 text-slate-600">
          <p>Status: {indexedDocument.status}</p>
          <p>Chunks: {indexedDocument.chunk_count}</p>
          <p>Embedding model: {indexedDocument.embedding_model}</p>
          <p>Vector DB: {indexedDocument.vector_db}</p>
        </div>
      ) : null}
    </ActionPanel>
  );
}

function RetrievalPanel({
  indexedDocument,
  query,
  result,
  isLoading,
  onQueryChange,
  onRetrieve,
}: {
  indexedDocument: IndexedDocument | null;
  query: string;
  result: RetrievalQueryResult | null;
  isLoading: boolean;
  onQueryChange: (value: string) => void;
  onRetrieve: () => void;
}) {
  return (
    <div className="space-y-4 rounded-md border border-slate-200 bg-slate-50 p-4 text-sm">
      <label className="block">
        <span className="font-medium text-slate-900">Retrieval query</span>
        <textarea
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          rows={3}
          disabled={!indexedDocument || isLoading}
          className="mt-2 w-full resize-none rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-900 outline-none transition focus:border-slate-500 disabled:bg-slate-100"
        />
      </label>
      <button
        type="button"
        onClick={onRetrieve}
        disabled={!indexedDocument || !query.trim() || isLoading}
        className="rounded-md bg-slate-950 px-3 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
      >
        {isLoading ? "Retrieving..." : result ? "Run Again: Retrieve Evidence" : "Retrieve Evidence"}
      </button>
      {!indexedDocument ? <p className="text-slate-600">Index a processed document to retrieve evidence.</p> : null}
      {result ? (
        <p className="text-slate-600">
          {result.evidence.length} chunk{result.evidence.length === 1 ? "" : "s"} returned.
        </p>
      ) : null}
    </div>
  );
}

function EvidencePanel({
  evidence,
  message,
}: {
  evidence: EvidenceChunk[] | null;
  message: string | null;
}) {
  if (!evidence) {
    return (
      <div className="min-h-32 rounded-md border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600">
        Evidence will appear after Step 5 or after draft generation.
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
      {evidence.map((chunk) => (
        <article key={chunk.chunk_id || `${chunk.page_number}-${chunk.text}`} className="rounded-md border border-slate-200 bg-slate-50 p-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="font-medium text-slate-900">{chunk.source.filename || "Unknown file"}</p>
              <p className="text-slate-600">Page {chunk.page_number}</p>
            </div>
            <span className="rounded-md bg-white px-2 py-1 text-xs font-medium text-slate-700">
              Relevance {chunk.relevance_score.toFixed(2)}
            </span>
          </div>
          <p className="mt-3 line-clamp-5 whitespace-pre-wrap text-slate-700">
            {chunk.text || "No chunk text returned."}
          </p>
        </article>
      ))}
    </div>
  );
}

function DraftEditorPanel({
  indexedDocument,
  generatedDraft,
  previousDraft,
  draftText,
  isGenerating,
  isSavingEdit,
  hasActiveRules,
  editResult,
  onGenerate,
  onDraftChange,
  onSaveEdit,
}: {
  indexedDocument: IndexedDocument | null;
  generatedDraft: GeneratedDraft | null;
  previousDraft: GeneratedDraft | null;
  draftText: string;
  isGenerating: boolean;
  isSavingEdit: boolean;
  hasActiveRules: boolean;
  editResult: DraftEditResult | null;
  onGenerate: () => void;
  onDraftChange: (value: string) => void;
  onSaveEdit: () => void;
}) {
  const isEdited = Boolean(generatedDraft && draftText !== generatedDraft.draft);

  return (
    <div className="space-y-4 rounded-md border border-slate-200 bg-slate-50 p-4 text-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-medium text-slate-900">Draft editor</p>
          <p className="text-slate-600">
            {generatedDraft ? `Model used: ${generatedDraft.model_used}` : "Generate after indexing."}
          </p>
        </div>
        <button
          type="button"
          onClick={onGenerate}
          disabled={!indexedDocument || isGenerating}
          className="rounded-md bg-slate-950 px-3 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
        >
          {isGenerating
            ? "Generating..."
            : hasActiveRules
              ? "Generate Improved Draft"
              : "Generate Grounded Draft"}
        </button>
      </div>

      {!indexedDocument ? <p className="text-slate-600">Index a processed document to generate a draft.</p> : null}

      {generatedDraft ? (
        <>
          <DraftLearningSummary draft={generatedDraft} />
          {previousDraft ? <DraftComparison previousDraft={previousDraft} currentDraft={generatedDraft} /> : null}
          <label className="block">
            <span className="font-medium text-slate-900">Step 7: Edit Draft</span>
            <textarea
              value={draftText}
              onChange={(event) => onDraftChange(event.target.value)}
              rows={18}
              className="mt-2 w-full resize-y rounded-md border border-slate-300 bg-white px-3 py-2 font-mono text-sm text-slate-900 outline-none transition focus:border-slate-500"
            />
          </label>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-slate-600">
              {isEdited
                ? "Edited wording is ready to save as an operator improvement."
                : "Make an edit before saving operator feedback."}
            </p>
            <button
              type="button"
              onClick={onSaveEdit}
              disabled={!isEdited || isSavingEdit || !draftText.trim()}
              className="rounded-md bg-emerald-700 px-3 py-2 text-sm font-medium text-white transition hover:bg-emerald-600 disabled:cursor-not-allowed disabled:bg-slate-400"
            >
              {isSavingEdit ? "Saving..." : "Save Operator Edit"}
            </button>
          </div>
          {editResult ? <SavedEditSummary editResult={editResult} /> : null}
        </>
      ) : null}
    </div>
  );
}

function DraftLearningSummary({ draft }: { draft: GeneratedDraft }) {
  const appliedRules = draft.applied_learning_rules ?? [];

  return (
    <div className="space-y-3">
      <p className="rounded-md border border-amber-200 bg-amber-50 p-3 text-amber-800">
        {draft.grounding_note}
      </p>
      {draft.learning_rules_warning ? (
        <p className="rounded-md border border-amber-200 bg-amber-50 p-3 text-amber-800">
          {draft.learning_rules_warning}
        </p>
      ) : null}
      {appliedRules.length ? (
        <div className="rounded-md border border-sky-200 bg-sky-50 p-3 text-sky-900">
          <p className="font-medium">This draft request included active operator-learned rules.</p>
          <p className="mt-1 text-sm">
            These are the rules returned by the API as injected into the generation prompt.
          </p>
          <div className="mt-3 grid gap-2 md:grid-cols-2">
            {appliedRules.map((rule) => (
              <RuleCard key={rule.rule_id ?? rule.rule_text} rule={rule} compact />
            ))}
          </div>
        </div>
      ) : (
        <p className="rounded-md border border-slate-200 bg-white p-3 text-slate-600">
          No active operator-learned rules were applied to this draft.
        </p>
      )}
    </div>
  );
}

function DraftComparison({
  previousDraft,
  currentDraft,
}: {
  previousDraft: GeneratedDraft;
  currentDraft: GeneratedDraft;
}) {
  const previousText = normalizeDraftText(previousDraft.draft);
  const currentText = normalizeDraftText(currentDraft.draft);
  const changed = previousText !== currentText;

  return (
    <div className="space-y-3">
      <p
        className={`rounded-md border p-3 text-sm ${
          changed
            ? "border-emerald-200 bg-emerald-50 text-emerald-900"
            : "border-amber-200 bg-amber-50 text-amber-900"
        }`}
      >
        {changed
          ? "The improved draft text differs from the previous draft."
          : "No text-level difference detected between the previous and improved draft."}
      </p>
      <div className="grid gap-3 md:grid-cols-2">
        <label className="block">
          <span className="font-medium text-slate-900">Previous draft</span>
          <textarea
            value={previousDraft.draft}
            readOnly
            rows={8}
            className="mt-2 w-full resize-y rounded-md border border-slate-300 bg-white px-3 py-2 font-mono text-xs text-slate-700 outline-none"
          />
        </label>
        <label className="block">
          <span className="font-medium text-slate-900">Improved draft</span>
          <textarea
            value={currentDraft.draft}
            readOnly
            rows={8}
            className="mt-2 w-full resize-y rounded-md border border-slate-300 bg-white px-3 py-2 font-mono text-xs text-slate-700 outline-none"
          />
        </label>
      </div>
    </div>
  );
}

function SavedEditSummary({ editResult }: { editResult: DraftEditResult }) {
  return (
    <div className="space-y-3 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-emerald-900">
      <p className="font-medium">{editResult.message}</p>
      {editResult.warning ? <p>{editResult.warning}</p> : null}
      {editResult.learned_rules.length ? (
        <div className="grid gap-2 md:grid-cols-2">
          {editResult.learned_rules.map((rule) => (
            <RuleCard key={rule.rule_id ?? rule.rule_text} rule={rule} compact />
          ))}
        </div>
      ) : (
        <p>No reusable rule was extracted from this edit.</p>
      )}
    </div>
  );
}

function LearnedRulesPanel({
  rules,
  updatingRuleId,
  onToggleRule,
}: {
  rules: LearnedRule[];
  updatingRuleId: string | null;
  onToggleRule: (rule: LearnedRule) => void;
}) {
  if (!rules.length) {
    return (
      <div className="min-h-28 rounded-md border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600">
        Step 9 will populate after an operator edit is saved and reusable rules are extracted.
      </div>
    );
  }

  const activeCount = rules.filter((rule) => rule.is_active).length;

  return (
    <div className="space-y-4 text-sm">
      <p className="rounded-md border border-sky-200 bg-sky-50 p-3 text-sky-800">
        {activeCount} active rule{activeCount === 1 ? "" : "s"} will be used when Step 10 generates an improved draft.
      </p>
      <div className="grid gap-3 md:grid-cols-2">
        {rules.map((rule) => (
          <div key={rule.rule_id} className="space-y-2">
            <RuleCard rule={rule} />
            <button
              type="button"
              onClick={() => onToggleRule(rule)}
              disabled={updatingRuleId === rule.rule_id}
              className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
            >
              {updatingRuleId === rule.rule_id
                ? "Updating..."
                : rule.is_active
                  ? "Disable Rule"
                  : "Enable Rule"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

function RuleCard({ rule, compact = false }: { rule: LearnedRule; compact?: boolean }) {
  return (
    <article className="rounded-md border border-slate-200 bg-white p-3 text-sm">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <p className="font-medium capitalize text-slate-900">{rule.rule_type}</p>
        <span
          className={`rounded-md px-2 py-1 text-xs font-medium ${
            rule.is_active ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-600"
          }`}
        >
          {rule.is_active ? "Active" : "Inactive"}
        </span>
      </div>
      <p className="mt-2 text-slate-700">{rule.rule_text}</p>
      {!compact && (rule.example_before || rule.example_after) ? (
        <div className="mt-3 space-y-2 text-xs text-slate-600">
          {rule.example_before ? <p>Before: {rule.example_before}</p> : null}
          {rule.example_after ? <p>After: {rule.example_after}</p> : null}
        </div>
      ) : null}
    </article>
  );
}

function getErrorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

function normalizeDraftText(value: string) {
  return value.replace(/\s+/g, " ").trim();
}
