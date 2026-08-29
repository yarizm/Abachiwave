import type { NextConfig } from "next";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const apiOrigin = new URL(apiBaseUrl).origin;
const scriptPolicy =
  process.env.NODE_ENV === "development"
    ? "script-src 'self' 'unsafe-inline' 'unsafe-eval'"
    : "script-src 'self' 'unsafe-inline'";
const contentSecurityPolicy = [
  "default-src 'self'",
  scriptPolicy,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  // Tone.js drives its transport clock from a Web Worker it builds out of a
  // blob: URL. Without this, that worker is blocked and every transport-
  // scheduled callback silently never fires: audition plays no audio, no
  // chord highlights, and playback never ends. Transport.seconds keeps
  // advancing off the AudioContext clock, so the playhead still moves and
  // the failure looks like working playback. Scoped to same-origin blobs.
  "worker-src 'self' blob:",
  `connect-src 'self' ${apiOrigin}`,
  `media-src 'self' blob: ${apiOrigin}`,
  "font-src 'self' data:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const nextConfig: NextConfig = {
  devIndicators: false,
  output: "standalone",
  outputFileTracingRoot: process.cwd(),
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "Content-Security-Policy", value: contentSecurityPolicy },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
