import {
  MS_PER_MINUTE,
  MS_PER_HOUR,
  MS_PER_DAY,
  MS_PER_WEEK,
} from "@/constants/time";

const MS_PER_MONTH = 30 * MS_PER_DAY;

/**
 * Returns a human-readable relative time string like "5m ago", "2h ago", "3d ago".
 */
export function timeAgo(isoOrDate: string | Date): string {
  const date = typeof isoOrDate === "string" ? new Date(isoOrDate) : isoOrDate;
  const diff = Date.now() - date.getTime();

  if (diff < MS_PER_MINUTE) return "Just now";
  if (diff < MS_PER_HOUR) return `${Math.floor(diff / MS_PER_MINUTE)}m ago`;
  if (diff < MS_PER_DAY) return `${Math.floor(diff / MS_PER_HOUR)}h ago`;
  if (diff < MS_PER_WEEK) return `${Math.floor(diff / MS_PER_DAY)}d ago`;
  if (diff < MS_PER_MONTH) return `${Math.floor(diff / MS_PER_WEEK)}w ago`;
  return `${Math.floor(diff / MS_PER_MONTH)}mo ago`;
}

/**
 * Compact variant without "ago" suffix, for tight UI contexts like inbox/notifications.
 */
export function timeAgoShort(isoOrDate: string | Date): string {
  const date = typeof isoOrDate === "string" ? new Date(isoOrDate) : isoOrDate;
  const diff = Date.now() - date.getTime();

  if (diff < MS_PER_MINUTE) return "now";
  if (diff < MS_PER_HOUR) return `${Math.floor(diff / MS_PER_MINUTE)}m`;
  if (diff < MS_PER_DAY) return `${Math.floor(diff / MS_PER_HOUR)}h`;
  if (diff < MS_PER_WEEK) return `${Math.floor(diff / MS_PER_DAY)}d`;
  if (diff < MS_PER_MONTH) return `${Math.floor(diff / MS_PER_WEEK)}w`;
  return `${Math.floor(diff / MS_PER_MONTH)}mo`;
}
