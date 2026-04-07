import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge Tailwind classes safely. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format a phone number for display: +15551234567 → (555) 123-4567 */
export function formatPhone(phone: string): string {
  const digits = phone.replace(/\D/g, "");
  if (digits.length === 11 && digits.startsWith("1")) {
    const area = digits.slice(1, 4);
    const mid = digits.slice(4, 7);
    const last = digits.slice(7);
    return `(${area}) ${mid}-${last}`;
  }
  return phone;
}

/** Format seconds into mm:ss */
export function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return "--:--";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

/** Trust score to color class */
export function trustScoreColor(score: number | null): string {
  if (score === null) return "text-gray-400";
  if (score >= 0.7) return "text-green-600";
  if (score >= 0.4) return "text-yellow-600";
  return "text-red-600";
}

/** Trust score to human label */
export function trustScoreLabel(score: number | null): string {
  if (score === null) return "Unknown";
  if (score >= 0.8) return "Trusted";
  if (score >= 0.6) return "Likely Safe";
  if (score >= 0.4) return "Uncertain";
  if (score >= 0.2) return "Suspicious";
  return "High Risk";
}

/** Format ISO date string to readable format */
export function formatDate(iso: string | null): string {
  if (!iso) return "--";
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/** Disposition badge colors */
export function dispositionColor(
  d: string | null,
): { bg: string; text: string } {
  switch (d) {
    case "forwarded":
      return { bg: "bg-green-100", text: "text-green-800" };
    case "messaged":
      return { bg: "bg-blue-100", text: "text-blue-800" };
    case "blocked":
      return { bg: "bg-red-100", text: "text-red-800" };
    case "engaged":
      return { bg: "bg-purple-100", text: "text-purple-800" };
    case "emergency":
      return { bg: "bg-orange-100", text: "text-orange-800" };
    default:
      return { bg: "bg-gray-100", text: "text-gray-600" };
  }
}
