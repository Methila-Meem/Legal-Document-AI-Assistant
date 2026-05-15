"use client";

import { useCallback, useEffect, useState } from "react";
import { useDropzone } from "react-dropzone";
import { uploadDocument, type UploadedDocument } from "@/lib/api";

type UploadStatus = "idle" | "selected" | "uploading" | "uploaded" | "error";

export function DocumentUpload({
  onUploaded,
}: {
  onUploaded: (document: UploadedDocument) => void;
}) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [status, setStatus] = useState<UploadStatus>("idle");
  const [message, setMessage] = useState("Drop a PDF, image, or TXT document.");
  const [uploadedDocument, setUploadedDocument] = useState<UploadedDocument | null>(null);
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  const handleUpload = useCallback(async (file: File) => {
    setStatus("uploading");
    setMessage("Uploading document...");
    setUploadedDocument(null);

    try {
      const result = await uploadDocument(file);
      setUploadedDocument(result);
      setStatus("uploaded");
      setMessage("Upload complete.");
      onUploaded(result);
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Upload failed.");
    }
  }, [onUploaded]);

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (!file) {
        return;
      }
      setSelectedFile(file);
      setStatus("selected");
      setMessage("File selected.");
      void handleUpload(file);
    },
    [handleUpload],
  );

  return (
    <div className="space-y-4">
      {isMounted ? (
        <UploadDropzone onDrop={onDrop} />
      ) : (
        <div className="flex min-h-36 flex-col items-center justify-center rounded-md border border-dashed border-slate-300 bg-slate-50 p-5 text-center">
          <p className="text-sm font-medium text-slate-800">Drag and drop a document</p>
          <p className="mt-2 text-sm text-slate-600">PDF, PNG, JPG, JPEG, or TXT up to 25 MB</p>
        </div>
      )}

      {selectedFile ? (
        <div className="rounded-md border border-slate-200 bg-white p-4 text-sm">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-medium text-slate-900">{selectedFile.name}</p>
              <p className="text-slate-500">{formatBytes(selectedFile.size)}</p>
            </div>
            <StatusBadge status={status} />
          </div>
          <p
            className={`mt-3 ${
              status === "error" ? "text-red-700" : "text-slate-600"
            }`}
          >
            {message}
          </p>
          {uploadedDocument ? (
            <p className="mt-2 text-slate-600">Document ID: {uploadedDocument.document_id}</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function UploadDropzone({ onDrop }: { onDrop: (acceptedFiles: File[]) => void }) {
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: false,
    accept: {
      "application/pdf": [".pdf"],
      "image/png": [".png"],
      "image/jpeg": [".jpg", ".jpeg"],
      "text/plain": [".txt"],
    },
  });

  return (
    <div
      {...getRootProps()}
      className={`flex min-h-36 cursor-pointer flex-col items-center justify-center rounded-md border border-dashed p-5 text-center transition ${
        isDragActive
          ? "border-blue-500 bg-blue-50"
          : "border-slate-300 bg-slate-50 hover:border-slate-400"
      }`}
    >
      <input {...getInputProps()} />
      <p className="text-sm font-medium text-slate-800">
        {isDragActive ? "Release to upload" : "Drag and drop a document"}
      </p>
      <p className="mt-2 text-sm text-slate-600">PDF, PNG, JPG, JPEG, or TXT up to 25 MB</p>
    </div>
  );
}

function StatusBadge({ status }: { status: UploadStatus }) {
  const label = {
    idle: "Idle",
    selected: "Selected",
    uploading: "Uploading",
    uploaded: "Uploaded",
    error: "Error",
  }[status];

  const tone = {
    idle: "bg-slate-100 text-slate-600",
    selected: "bg-blue-50 text-blue-700",
    uploading: "bg-amber-50 text-amber-700",
    uploaded: "bg-emerald-50 text-emerald-700",
    error: "bg-red-50 text-red-700",
  }[status];

  return <span className={`rounded-md px-2 py-1 text-xs font-medium ${tone}`}>{label}</span>;
}

function formatBytes(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
