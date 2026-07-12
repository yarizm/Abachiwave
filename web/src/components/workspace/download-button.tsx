"use client";

import { Download } from "lucide-react";
import { useState } from "react";

import { useLocale } from "@/i18n/locale-provider";
import { fetchBlob } from "@/lib/api-client";

type DownloadButtonProps = {
  filename: string;
  url: string;
};

export function DownloadButton({ filename, url }: DownloadButtonProps) {
  const { errorMessage, t } = useLocale();
  const [isDownloading, setIsDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleDownload() {
    setIsDownloading(true);
    setError(null);
    try {
      const objectUrl = URL.createObjectURL(await fetchBlob(url, "Download"));
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = filename;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
    } catch (downloadError) {
      setError(errorMessage(downloadError, "Download failed"));
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
        {isDownloading ? t("Downloading") : t("Download")}
      </button>
      {error ? (
        <span className="meta error" role="alert">
          {error}
        </span>
      ) : null}
    </div>
  );
}
