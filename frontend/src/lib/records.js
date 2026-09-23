// Record paths and concept-value traversal. Zero and false are filled answers.

function recordFile(e) {
  return `data/${e.id}/${e.c}-${e.id}.json`;
}

function resolvePath(obj, path) {
  let cur = obj;
  for (const part of path.split(".")) {
    if (cur == null || typeof cur !== "object") return null;
    cur = cur[part];
  }
  return cur === undefined ? null : cur;
}

const ROOT_SECTIONS = new Set(["kandidatavimas"]);

function isFilledValue(v) {
  if (v == null) return false;
  if (typeof v === "string") return v.trim() !== "";
  if (Array.isArray(v)) return v.length > 0;
  if (typeof v === "object") return Object.keys(v).length > 0;
  return true;
}

function walkValue(root, segments) {
  if (!segments.length) return isFilledValue(root) ? root : null;
  if (Array.isArray(root)) {
    for (const entry of root) {
      const value = walkValue(entry, segments);
      if (value != null) return value;
    }
    return null;
  }
  if (root == null || typeof root !== "object" || !(segments[0] in root)) return null;
  return walkValue(root[segments[0]], segments.slice(1));
}

export { recordFile, resolvePath, ROOT_SECTIONS, isFilledValue, walkValue };
