// Small helpers shared by the seller page and the shop page. Plain JS, no build step.
// All dynamic text goes through textContent / append(), never innerHTML,
// so model output can't inject markup into the page.

const $ = (selector, root = document) => root.querySelector(selector);

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value);
  }
  node.append(...children.flat().filter((c) => c !== null && c !== undefined));
  return node;
}

// fetch + JSON + readable errors. FastAPI sends {detail: "text"} for our errors
// and {detail: [ ... ]} for schema validation errors.
async function api(path, options = {}) {
  const init = { ...options };
  if (init.json !== undefined) {
    init.method = init.method || "POST";
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(init.json);
    delete init.json;
  }
  const res = await fetch(path, init);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data.detail === "string" ? data.detail : null;
    throw new Error(detail || `Something went wrong (${res.status}).`);
  }
  return data;
}
