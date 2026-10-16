// SellMate frontend. Plain JS, no build step.
// All dynamic text goes through textContent / append(), never innerHTML,
// so model output can't inject markup into the page.

const $ = (selector) => document.querySelector(selector);

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

// ---------- model health ----------

async function checkHealth() {
  const pill = $("#health");
  try {
    const res = await fetch("/api/health");
    const h = await res.json();
    if (!h.ollama) {
      pill.className = "pill pill-bad";
      pill.textContent = "Ollama not running";
    } else if (!h.model_ready) {
      pill.className = "pill pill-warn";
      pill.textContent = `Run: ollama pull ${h.model}`;
    } else {
      pill.className = "pill pill-ok";
      pill.textContent = `${h.model} ready`;
    }
  } catch {
    pill.className = "pill pill-bad";
    pill.textContent = "Server unreachable";
  }
}

// ---------- photo picking ----------

const input = $("#photos");
const dropzone = $("#dropzone");
const previews = $("#previews");

function showPreviews() {
  previews.replaceChildren();
  const files = [...input.files].slice(0, 3);
  for (const file of files) {
    previews.append(el("img", { src: URL.createObjectURL(file), alt: file.name }));
  }
}

input.addEventListener("change", showPreviews);
dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("over");
});
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("over"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("over");
  input.files = e.dataTransfer.files;
  showPreviews();
});

// ---------- generate ----------

const form = $("#listing-form");
const statusEl = $("#status");
const submitBtn = $("#submit");

function setStatus(text, isError = false) {
  statusEl.textContent = text;
  statusEl.classList.toggle("error", isError);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (input.files.length > 3) {
    setStatus("Please choose at most 3 photos.", true);
    return;
  }

  submitBtn.disabled = true;
  const started = Date.now();
  const timer = setInterval(() => {
    const s = Math.round((Date.now() - started) / 1000);
    setStatus(`Gemma is studying your photos… ${s}s (on a CPU this can take a minute or two)`);
  }, 1000);
  setStatus("Gemma is studying your photos…");

  try {
    const res = await fetch("/api/products", { method: "POST", body: new FormData(form) });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `Something went wrong (${res.status}).`);
    renderListing(data);
    setStatus("Done. Saved to your catalog.");
    form.reset();
    previews.replaceChildren();
    loadCatalog();
  } catch (err) {
    setStatus(err.message, true);
  } finally {
    clearInterval(timer);
    submitBtn.disabled = false;
  }
});

// ---------- rendering ----------

function listingText(product) {
  const { listing, price } = product;
  const parts = [listing.title, "", listing.description];
  if (listing.highlights.length) {
    parts.push("", ...listing.highlights.map((h) => `• ${h}`));
  }
  if (price) parts.push("", `Price: ${price}`);
  return parts.join("\n");
}

async function copyText(text, button) {
  try {
    await navigator.clipboard.writeText(text);
    const old = button.textContent;
    button.textContent = "Copied!";
    setTimeout(() => (button.textContent = old), 1500);
  } catch {
    button.textContent = "Copy failed";
  }
}

function renderListing(product) {
  const { listing } = product;
  const copyBtn = el("button", { class: "btn btn-small", type: "button" }, "Copy listing");
  copyBtn.addEventListener("click", () => copyText(listingText(product), copyBtn));

  $("#result").className = "listing";
  $("#result").replaceChildren(
    el("div", { class: "photos" }, product.photos.map((src) => el("img", { src, alt: "" }))),
    el("h3", {}, listing.title),
    el("p", {}, listing.description),
    listing.highlights.length ? el("ul", {}, listing.highlights.map((h) => el("li", {}, h))) : null,
    listing.tags.length
      ? el("div", { class: "tags" }, listing.tags.map((t) => el("span", { class: "tag" }, `#${t}`)))
      : null,
    listing.missing_info.length
      ? el(
          "div",
          { class: "ask" },
          el("strong", {}, "Buyers will ask. Add these details:"),
          el("ul", {}, listing.missing_info.map((q) => el("li", {}, q)))
        )
      : null,
    copyBtn,
    el("p", { class: "meta" }, `Written by ${product.model} in ${product.generation_seconds}s, locally.`)
  );
}

// ---------- catalog ----------

async function loadCatalog() {
  const grid = $("#catalog");
  try {
    const res = await fetch("/api/products");
    const products = await res.json();
    if (!products.length) {
      grid.replaceChildren(el("p", { class: "empty" }, "Nothing here yet. Create your first listing above."));
      return;
    }
    grid.replaceChildren(...products.map(catalogCard));
  } catch {
    grid.replaceChildren(el("p", { class: "empty" }, "Couldn't load the catalog."));
  }
}

function catalogCard(product) {
  const viewBtn = el("button", { class: "btn btn-small", type: "button" }, "View");
  viewBtn.addEventListener("click", () => {
    renderListing(product);
    $("#result").scrollIntoView({ behavior: "smooth", block: "start" });
  });

  const delBtn = el("button", { class: "btn btn-small", type: "button" }, "Delete");
  delBtn.addEventListener("click", async () => {
    if (!confirm(`Delete "${product.name}"?`)) return;
    await fetch(`/api/products/${product.id}`, { method: "DELETE" });
    loadCatalog();
  });

  return el(
    "article",
    { class: "item" },
    product.photos[0] ? el("img", { src: product.photos[0], alt: "", loading: "lazy" }) : null,
    el(
      "div",
      { class: "body" },
      el("h3", {}, product.name),
      product.price ? el("span", { class: "price" }, product.price) : null,
      el("div", { class: "actions" }, viewBtn, delBtn)
    )
  );
}

checkHealth();
loadCatalog();
