const PARIS_TIME_ZONE = "Europe/Paris";

export function formatDateInputValue(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function addDaysToDateValue(dateValue, days) {
  const date = new Date(`${dateValue}T12:00:00`);
  date.setDate(date.getDate() + days);
  return formatDateInputValue(date);
}

export function getSelectedDateRange(dateValue) {
  const nextDateValue = addDaysToDateValue(dateValue, 1);

  return {
    startDate: `${dateValue}T00:00:00${getParisOffset(dateValue)}`,
    endDate: `${nextDateValue}T00:00:00${getParisOffset(nextDateValue)}`,
  };
}

export function getParisDayBounds(dateValue) {
  const { startDate, endDate } = getSelectedDateRange(dateValue);

  return {
    min: new Date(startDate).getTime(),
    max: new Date(endDate).getTime(),
  };
}

export function formatParisTime(value) {
  return new Intl.DateTimeFormat("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: PARIS_TIME_ZONE,
  }).format(new Date(value));
}

export function formatParisDateTime(value) {
  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: PARIS_TIME_ZONE,
  }).format(new Date(value));
}

function getParisOffset(dateValue) {
  const date = new Date(`${dateValue}T12:00:00Z`);
  const formatter = new Intl.DateTimeFormat("en-US", {
    timeZone: PARIS_TIME_ZONE,
    timeZoneName: "shortOffset",
  });
  const timeZoneName = formatter
    .formatToParts(date)
    .find((part) => part.type === "timeZoneName")?.value;
  const match = timeZoneName?.match(/GMT([+-])(\d{1,2})(?::(\d{2}))?/);

  if (!match) {
    return "+01:00";
  }

  const [, sign, hours, minutes = "00"] = match;
  return `${sign}${hours.padStart(2, "0")}:${minutes}`;
}
