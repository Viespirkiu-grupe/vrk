// Lithuanian display, accent-insensitive search, CSV, and aggregate helpers.

const fold = (s) => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase();

// Lithuanian counts three integer forms -- 1 asmuo, 2 asmenys, 11 asmenų --
// on a rule that is not "n === 1", so pick them through Intl rather than by
// hand. ("many" is Lithuanian's fraction form; it falls back to the genitive.)
const PLURAL = new Intl.PluralRules("lt");

const plural = (n, one, few, rest) => ({ one, few, many: rest, other: rest })[PLURAL.select(n)];

const fmtInt = (n) => n.toLocaleString("lt-LT");

const capitalize = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);

function deslug(key) {
  const words = String(key)
    .replace(/([a-ząčęėįšųūž])([A-ZĄČĘĖĮŠŲŪŽ])/g, "$1 $2")
    .replace(/-/g, " ")
    .toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function csvField(value) {
  if (value == null) return "";
  let s = String(value);
  // A cell a spreadsheet would read as a formula gets a leading apostrophe.
  // 90 cells of the full export start with one of these — 88 workplace
  // strings and two negative money figures — and Excel renders them as
  // #NAME? (issue #149).
  if (/^[=+\-@\t\r]/.test(s)) s = "'" + s;
  return /[;"\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

// Money for an lt-LT spreadsheet: a comma decimal, because the locale's
// decimal separator is a comma and `String(number)` writes a dot. 199,626
// of the export's 308,135 money cells carried a dot, which imports as
// left-aligned text — no sum, no sort, no chart (issue #149). The field
// separator is `;`, so a comma inside a cell needs no quoting.
function csvMoney(value) {
  if (value == null) return "";
  return String(value).replace(".", ",");
}

function median(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = sorted.length >> 1;
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

const pct = (part, whole) => whole ? `${(100 * part / whole).toFixed(1).replace(".", ",")} %` : "—";

const fmtEUR = (n) => n.toLocaleString("lt-LT", { maximumFractionDigits: 0 }) + " €";

export { fold, PLURAL, plural, fmtInt, capitalize, deslug, csvField, csvMoney, median, pct, fmtEUR };
