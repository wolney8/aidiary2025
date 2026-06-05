const LONG_DATE_FORMATTER = new Intl.DateTimeFormat("en-GB", {
  weekday: "long",
  day: "numeric",
  month: "long",
  year: "numeric",
});

const UK_NUMERIC_DATE_FORMATTER = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

export function parseLocalIsoDate(value: unknown): Date | null {
  if (typeof value !== "string" || !value.trim()) {
    return null;
  }

  const trimmed = value.trim();
  const isoDateOnlyMatch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(trimmed);
  if (isoDateOnlyMatch) {
    const year = Number(isoDateOnlyMatch[1]);
    const monthIndex = Number(isoDateOnlyMatch[2]) - 1;
    const day = Number(isoDateOnlyMatch[3]);
    const localDate = new Date(year, monthIndex, day);

    if (
      localDate.getFullYear() === year &&
      localDate.getMonth() === monthIndex &&
      localDate.getDate() === day
    ) {
      return localDate;
    }

    return null;
  }

  const parsed = new Date(trimmed);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function formatUkNumericDate(value: Date | string | null): string {
  const parsed = coerceDateValue(value);
  return parsed ? UK_NUMERIC_DATE_FORMATTER.format(parsed) : "";
}

export function formatReadableLongDate(value: Date | string | null): string {
  const parsed = coerceDateValue(value);
  if (!parsed) {
    return "";
  }

  const formatted = LONG_DATE_FORMATTER.format(parsed);
  const dayNumber = parsed.getDate();
  return formatted.replace(String(dayNumber), `${dayNumber}${getOrdinalSuffix(dayNumber)}`);
}

function coerceDateValue(value: Date | string | null): Date | null {
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }

  if (typeof value === "string") {
    return parseLocalIsoDate(value);
  }

  return null;
}

function getOrdinalSuffix(day: number): string {
  const remainderHundred = day % 100;
  if (remainderHundred >= 11 && remainderHundred <= 13) {
    return "th";
  }

  switch (day % 10) {
    case 1:
      return "st";
    case 2:
      return "nd";
    case 3:
      return "rd";
    default:
      return "th";
  }
}
