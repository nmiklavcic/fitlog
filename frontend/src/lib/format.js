import { format, formatDistanceToNowStrict, parseISO } from "date-fns";

export function timeAgo(iso) {
  return formatDistanceToNowStrict(parseISO(iso), { addSuffix: true });
}

export function niceDate(isoDate, pattern = "EEE, d MMM yyyy") {
  return format(parseISO(isoDate), pattern);
}

export function todayIso() {
  return format(new Date(), "yyyy-MM-dd");
}

export function muscleLabel(muscle) {
  return muscle ? muscle.charAt(0).toUpperCase() + muscle.slice(1) : "";
}
