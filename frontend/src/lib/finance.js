// Shared financial interpretation, mirrored by scripts/build_person_index.py.
// MONEY_SERIES order must match the index m-array. Missing values are never zero.
// Income uses the declared total, or the explicitly marked employment-only fallback.
import { resolvePath } from "./records.js";
// Money series for the assets & income chart. The first three are the keys
// every election from 2007 on declares under. The fourth exists because the
// 1996-1997 form does not split turtas from piniginės lėšos -- it publishes
// one summed figure -- so those elections leave the first two null and would
// otherwise chart no turtas at all, despite the page stating it. It is a
// different measure, not a fallback, so it gets its own series rather than
// being folded into the first.
// ORDER MATTERS: it is the order of MONEY_FIELDS in
// scripts/build_person_index.py, which people.json's "m" array follows and
// the Biggest movers picker indexes into.
const MONEY_SERIES = [
  ["Privalomas registruoti turtas", "turto-ir-pajamu-deklaracijos.privalomas-registruoti-turtas", "#2456a4"],
  ["Piniginės lėšos", "turto-ir-pajamu-deklaracijos.pinigines-lesos", "#7fa8d9"],
  ["Gautos pajamos", "turto-ir-pajamu-deklaracijos.gautos-pajamos", "#2c8a4b"],
  ["Turtas ir piniginės lėšos (metų pabaigoje)", "turto-ir-pajamu-deklaracijos.turtas-ir-pinigines-lesos-metu-pabaigoje", "#b5761f"],
];

// The one shared money-string rule, mirrored by parse_money_text in
// scripts/build_person_index.py and held together by the fixture list in
// tests/test_dashboard_money_rendering.py: strip the euro sign and
// whitespace, allow one decimal separator (comma or dot), refuse anything
// else. It used to hand multi-separator strings to parseFloat, whose prefix
// parse silently read "1.234.567,89" as 1.234 while the builder stored None.
function parseMoney(v) {
  if (v == null) return null;
  if (typeof v === "number") return Number.isFinite(v) ? v : null;
  if (typeof v !== "string") return null;
  const cleaned = v.replace(/[€\s]/g, "");
  if (!/^-?\d+(?:[.,]\d+)?$/.test(cleaned)) return null;
  return parseFloat(cleaned.replace(",", "."));
}

// The 2012-2015 pages declare in litas (`valiuta: "Lt"`); converted at the
// irrevocable 2015 changeover rate so a person's series stays comparable.
// Mirrors scripts/build_person_index.py, which does the same for people.json.
const LITAS_PER_EURO = 3.4528;

function declaredInLitas(record) {
  const d = (record.normalized || {})["turto-ir-pajamu-deklaracijos"];
  return !!d && d.valiuta === "Lt";
}

// The `deklaruotos-pajamos` concept, mirrored from
// scraper/shared/deklaracijos.py. The 1990s form prints rows 1 and 20 of its
// income section and row 20 is not always trustworthy -- it fails by rendering
// 0 against a non-zero row 1 -- so the parser refuses it and `gautos-pajamos`
// is null on 4,463 of the 1997 municipal election's 6,276 records. Row 1 is
// printed on every one of them and is the only income figure those records
// have; charting nothing there said "declared no income", which is not what
// the page says. It is employment income, not a total, and the cell says so.
const INCOME_PATH = "turto-ir-pajamu-deklaracijos.gautos-pajamos";

const EMPLOYMENT_INCOME_PATH = "turto-ir-pajamu-deklaracijos.gautos-pajamos-darbo-santykiu";

function declaredIncome(normalized) {
  const total = parseMoney(resolvePath(normalized, INCOME_PATH));
  if (total != null) return { value: total, employmentOnly: false };
  const row1 = parseMoney(resolvePath(normalized, EMPLOYMENT_INCOME_PATH));
  if (row1 != null) return { value: row1, employmentOnly: true };
  return { value: null, employmentOnly: false };
}

function incomeIsEmploymentOnly(record) {
  return declaredIncome(record.normalized || {}).employmentOnly;
}

function moneyEUR(record, path) {
  const v = path === INCOME_PATH
    ? declaredIncome(record.normalized || {}).value
    : parseMoney(resolvePath(record.normalized || {}, path));
  if (v == null) return null;
  return declaredInLitas(record) ? v / LITAS_PER_EURO : v;
}

export { MONEY_SERIES, parseMoney, LITAS_PER_EURO, declaredInLitas, INCOME_PATH, EMPLOYMENT_INCOME_PATH, declaredIncome, incomeIsEmploymentOnly, moneyEUR };
