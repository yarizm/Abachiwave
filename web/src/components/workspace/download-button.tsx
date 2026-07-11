"use client";

import { Download } from "lucide-react";
import { useState } from "react";

import { ensureOk } from "@/lib/api-client";

type DownloadButtonProps = {
  filename: string;
  url: string;
};

export function DownloadButton({ filename, url }: DownloadButtonProps) {
  const [isDownloading, setIsDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleDownload() {
    setIsDownloading(true);
    setError(null);
    try {
      const response = await fetch(url);
      ensureOk(response, "Download");
      const objectUrl = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = filename;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
    } catch (downloadError) {
      setError(downloadError instanceof Error ? downloadError.message : "Download failed");
    } finally {
      setIsDownloading(false);
    }
  }

  return (
    <div className="download-control">
      <button
        className="button secondary icon-button"
        disabled={isDownloading}
        onClick={handleDownload}
        type="button"
      >
        <Download aria-hidden="true" size={18} />
        {isDownloading ? "Downloading" : "Download"}
      </button>
      {error ? (
        <span className="meta error" role="alert">
          {error}
        </span>
      ) : null}
    </div>
  );
}
