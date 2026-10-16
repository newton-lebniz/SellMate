// Buyer-facing shop page. Needs common.js loaded first.

const CHIPS = ["What's the price?", "What is it made of?", "What size is it?", "Do you deliver?"];
const MAX_TURN_CHARS = 1200;

let products = [];
let focusId = null; // the item the buyer is asking about, if any
let turns = []; // [{role: "user" | "assistant", content}]

const log = $("#log");
const focusBox = $("#focus");
const form = $("#chat-form");
const messageInput = $("#message");
const sendBtn = $("#send");

// ---------- items ----------

async function loadItems() {
  const grid = $("#items");
  try {
    products = await api("/api/products");
  } catch {
    grid.replaceChildren(el("p", { class: "empty" }, "Couldn't load the shop."));
    return;
  }
  if (!products.length) {
    grid.replaceChildren(el("p", { class: "empty" }, "No items yet. Add one on the seller desk."));
    return;
  }
  grid.replaceChildren(...products.map(itemCard));
}

function itemCard(product) {
  const ask = el("button", { class: "btn btn-small", type: "button" }, "Ask about this");
  ask.addEventListener("click", () => {
    setFocus(product.id);
    messageInput.focus();
  });
  return el(
    "article",
    { class: "item", "data-id": product.id },
    product.photos[0] ? el("img", { src: product.photos[0], alt: product.listing.title }) : null,
    el(
      "div",
      { class: "body" },
      el("h3", {}, product.listing.title),
      product.price ? el("span", { class: "price" }, product.price) : null,
      el("p", { class: "blurb" }, product.listing.description),
      el("div", { class: "actions" }, ask)
    )
  );
}

function setFocus(id) {
  focusId = id;
  const product = products.find((p) => p.id === id);
  focusBox.replaceChildren();
  focusBox.hidden = !product;
  if (product) {
    const clear = el("button", { class: "btn btn-small", type: "button" }, "Ask about anything");
    clear.addEventListener("click", () => setFocus(null));
    focusBox.append(el("span", {}, `Asking about: ${product.listing.title}`), clear);
  }
  document.querySelectorAll(".item").forEach((card) =>
    card.classList.toggle("selected", card.dataset.id === id)
  );
}

// ---------- chat ----------

function addBubble(role, text, note) {
  const empty = $(".empty", log);
  if (empty) empty.remove();
  const bubble = el("div", { class: `bubble ${role}` }, el("p", {}, text), note ? el("small", {}, note) : null);
  log.append(bubble);
  log.scrollTop = log.scrollHeight;
  return bubble;
}

async function ask(question) {
  const history = turns.slice(-6).map((t) => ({ ...t, content: t.content.slice(0, MAX_TURN_CHARS) }));
  addBubble("user", question);
  turns.push({ role: "user", content: question });
  sendBtn.disabled = true;
  messageInput.disabled = true;

  const thinking = addBubble("assistant thinking", "Thinking… (this runs on the seller's laptop, so it can take a little while)");
  try {
    const data = await api("/api/chat", {
      json: { message: question, history, product_id: focusId },
    });
    thinking.remove();
    addBubble(
      "assistant",
      data.answer,
      data.grounded ? null : "Your question was passed on to the seller."
    );
    turns.push({ role: "assistant", content: data.answer });
  } catch (err) {
    thinking.remove();
    addBubble("assistant error", err.message);
  } finally {
    sendBtn.disabled = false;
    messageInput.disabled = false;
    messageInput.focus();
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const question = messageInput.value.trim();
  if (!question) return;
  messageInput.value = "";
  ask(question);
});

$("#chips").append(
  ...CHIPS.map((text) => {
    const chip = el("button", { class: "chip", type: "button" }, text);
    chip.addEventListener("click", () => {
      if (!sendBtn.disabled) ask(text);
    });
    return chip;
  })
);

loadItems();
