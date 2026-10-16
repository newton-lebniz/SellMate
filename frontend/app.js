// Seller desk. Needs common.js loaded first.

// ---------- model health ----------

async function checkHealth() {
  const pill = $("#health");
  const set = (cls, text) => {
    pill.className = `pill ${cls}`;
    pill.textContent = text;
  };
  try {
    const h = await api("/api/health");
    if (!h.ollama) return set("pill-bad", "Ollama not running");

    const todo = [];
    if (!h.text_ready) todo.push(`ollama pull ${h.text_model}`);
    if (h.mode === "two-stage") {
      if (!h.vision_ready) todo.push(`ollama pull ${h.vision_model}`);
    } else if (h.text_ready && !h.vision_ready) {
      return set("pill-warn", `${h.text_model} can't read photos. Set VISION_MODEL`);
    }
    if (todo.length) return set("pill-warn", `Run: ${todo.join(" and ")}`);

    set(
      "pill-ok",
      h.mode === "two-stage"
        ? `${h.vision_model} + ${h.text_model} ready`
        : `${h.text_model} ready`
    );
  } catch {
    set("pill-bad", "Server unreachable");
  }
}

// ---------- photo picking ----------

const input = $("#photos");
const dropzone = $("#dropzone");
const previews = $("#previews");

function showPreviews() {
  previews.replaceChildren();
  for (const file of [...input.files].slice(0, 3)) {
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
  const tick = () => {
    const s = Math.round((Date.now() - started) / 1000);
    setStatus(`Looking at your photos, then writing… ${s}s (on a CPU this can take a minute or two)`);
  };
  tick();
  const timer = setInterval(tick, 1000);

  try {
    const product = await api("/api/products", { method: "POST", body: new FormData(form) });
    renderListing(product);
    setStatus("Done. Saved to your catalog. Add the missing details so buyers get answers.");
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

// ---------- listing view ----------

function listingText(product) {
  const { listing, price } = product;
  const parts = [listing.title, "", listing.description];
  if (listing.highlights.length) {
    parts.push("", ...listing.highlights.map((h) => `• ${h}`));
  }
  if (product.seller_notes) parts.push("", product.seller_notes);
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

// The seller's own facts are what the buyer-facing assistant trusts most.
function detailsBox(product) {
  const notes = el("textarea", {
    rows: "3",
    maxlength: "800",
    placeholder: "e.g. Sterling silver, 6 cm long, nickel free. Ships in 2 days.",
    "aria-label": "Details for buyers",
  });
  notes.value = product.seller_notes || "";
  const saved = el("span", { class: "meta" });
  const saveBtn = el("button", { class: "btn btn-small", type: "button" }, "Save details");
  saveBtn.addEventListener("click", async () => {
    saveBtn.disabled = true;
    try {
      const updated = await api(`/api/products/${product.id}`, {
        method: "PATCH",
        json: { seller_notes: notes.value },
      });
      product.seller_notes = updated.seller_notes;
      saved.textContent = "Saved. The shop assistant will use this.";
      loadCatalog();
    } catch (err) {
      saved.textContent = err.message;
    } finally {
      saveBtn.disabled = false;
    }
  });
  return el(
    "div",
    { class: "details" },
    el("strong", {}, "Your details for buyers"),
    notes,
    el("div", { class: "details-actions" }, saveBtn, saved)
  );
}

function renderListing(product) {
  const { listing } = product;
  const copyBtn = el("button", { class: "btn btn-small", type: "button" }, "Copy listing");
  copyBtn.addEventListener("click", () => copyText(listingText(product), copyBtn));

  const timing = product.vision_model
    ? `${product.vision_model} looked in ${product.vision_seconds}s, ${product.model} wrote in ${product.writing_seconds}s`
    : `${product.model} wrote it in ${product.generation_seconds}s`;

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
          el("strong", {}, "Buyers will ask. Answer these below:"),
          el("ul", {}, listing.missing_info.map((q) => el("li", {}, q)))
        )
      : null,
    detailsBox(product),
    copyBtn,
    el("p", { class: "meta" }, `Done locally: ${timing}.`),
    product.visual_notes
      ? el("details", { class: "meta" }, el("summary", {}, "What the vision model saw"), product.visual_notes)
      : null
  );
}

// ---------- catalog ----------

async function loadCatalog() {
  const grid = $("#catalog");
  try {
    const products = await api("/api/products");
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
    await api(`/api/products/${product.id}`, { method: "DELETE" });
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
      product.seller_notes ? null : el("span", { class: "meta" }, "No details added yet"),
      el("div", { class: "actions" }, viewBtn, delBtn)
    )
  );
}

// ---------- unanswered buyer questions ----------

async function loadQuestions() {
  const box = $("#questions");
  try {
    const items = await api("/api/questions");
    if (!items.length) {
      box.replaceChildren(
        el("p", { class: "empty" }, "None yet. When a buyer asks something your details don't cover, it shows up here.")
      );
      return;
    }
    box.replaceChildren(
      el(
        "ul",
        { class: "qlist" },
        items.map((q) => {
          const done = el("button", { class: "btn btn-small", type: "button" }, "Done");
          done.addEventListener("click", async () => {
            await api(`/api/questions/${q.id}`, { method: "DELETE" });
            loadQuestions();
          });
          return el(
            "li",
            {},
            el(
              "div",
              {},
              el("strong", {}, q.question),
              q.product_name ? el("div", { class: "meta" }, `About: ${q.product_name}`) : null
            ),
            done
          );
        })
      )
    );
  } catch {
    box.replaceChildren(el("p", { class: "empty" }, "Couldn't load questions."));
  }
}

checkHealth();
loadCatalog();
loadQuestions();
