/**
 * The blueprint's page model, out of its HTML and into committed JSON.
 *
 * `docs/product/token-iq-product-blueprint.html` holds the product specification twice over: as a
 * page a person reads, and as four JavaScript globals the page builds itself from. Section 12 of
 * the restructure plan names those globals as "the machine-readable model", and phase 5A's
 * acceptance comes from them rather than from taste, so they have to exist as data a test can read.
 *
 * Evaluated rather than re-parsed. The globals are JavaScript object literals with comments and
 * trailing commas, and a hand-written parser would be a second, worse implementation of a thing
 * Node already does exactly.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { createContext, runInContext } from "node:vm";

const BLUEPRINT = "docs/product/token-iq-product-blueprint.html";
const OUT = "docs/product/page-model.json";

// Only the model script. The file has others that touch the DOM and would need a browser.
const MARKER = "/* Token IQ v7 page model";
const html = readFileSync(BLUEPRINT, "utf8");
const start = html.indexOf(MARKER);
if (start < 0) {
  throw new Error(`${BLUEPRINT} no longer contains ${MARKER}`);
}
const end = html.indexOf("</script>", start);
if (end < 0) {
  throw new Error("the page model script is not closed");
}
const source = html.slice(start, end);

// A bare context: no DOM, no network, nothing the script could reach for. If the model ever starts
// depending on the document, this throws rather than silently extracting half of it.
const sandbox = { window: {} };
runInContext(source, createContext(sandbox));

const model = {
  roles: sandbox.window.TIQ_ROLES,
  matrixRoles: sandbox.window.TIQ_MROLES,
  matrix: sandbox.window.TIQ_MATRIX,
  pages: sandbox.window.TIQ_PAGES,
  modals: sandbox.window.TIQ_MODALS,
};

const missing = Object.entries(model)
  .filter(([, value]) => value === undefined)
  .map(([name]) => name);
if (missing.length > 0) {
  throw new Error(`the blueprint defined none of: ${missing.join(", ")}`);
}

writeFileSync(OUT, `${JSON.stringify(model, null, 1)}\n`, "utf8");
const counts = Object.entries(model)
  .map(([name, value]) => `${name}=${Array.isArray(value) ? value.length : Object.keys(value).length}`)
  .join("  ");
process.stdout.write(`${OUT}\n${counts}\n`);
