// Use calendar subtraction: subtracting three elapsed hours fails at fall DST.
export function journalDay(now = new Date()) {
  const day = new Date(now);
  if (day.getHours() < 3) day.setDate(day.getDate() - 1);
  return `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`;
}
