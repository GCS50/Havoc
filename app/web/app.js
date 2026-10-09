// Havoc web UI - a small single-page app on top of the /v1 REST API.
//
// It talks to the API exactly like any other client (JWT bearer token), so
// every permission rule is still enforced by the server; the UI only decides
// what to show. Routing uses the URL hash (#/, #/certificates/<id>, ...), so
// the server only has to serve index.html once.
//
// AI-assisted: written with the help of Claude (Anthropic).

"use strict";

const API = "/v1";
const TOKEN_KEY = "havoc.token";

const CERTIFICATE_TYPES = {
  certificate: "Certificate",
  course_certificate: "Course certificate",
  award: "Award",
  reference: "Reference",
  general_training: "General training",
};

const state = { token: null, me: null };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

// Build a DOM element. Text is always inserted as text nodes (never as HTML),
// so user-provided data cannot inject markup.
function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value == null || value === false) continue;
    if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else if (key === "class") el.className = value;
    else el.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat(Infinity)) {
    if (child == null || child === false) continue;
    el.append(child instanceof Node ? child : String(child));
  }
  return el;
}

function loadToken() {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}

function saveToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch { /* storage unavailable: the session just won't survive a reload */ }
}

function formatDate(value) {
  if (!value) return "—";
  // Plain dates ("2026-09-01") are parsed as local dates, not UTC midnight.
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  const date = m ? new Date(+m[1], +m[2] - 1, +m[3]) : new Date(value);
  if (isNaN(date)) return value;
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function formatDateTime(value) {
  const date = new Date(value);
  return isNaN(date) ? value : date.toLocaleString();
}

function today() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function typeLabel(type) {
  return CERTIFICATE_TYPES[type] || type || "Certificate";
}

function statusBadge(status) {
  return h("span", { class: `badge badge-${status}` }, status);
}

function metaRow(label, value) {
  return [h("dt", {}, label), h("dd", {}, value)];
}

// Only http(s) URLs become links; anything else is shown as plain text.
function safeLink(url) {
  if (!/^https?:\/\//i.test(url)) return url;
  return h("a", { href: url, target: "_blank", rel: "noopener noreferrer" }, url);
}

function isAdmin() {
  return state.me && state.me.role === "admin";
}

// Map user id -> display name, from an (optional) admin user list.
function userNames(users) {
  const names = new Map();
  if (state.me) names.set(state.me.id, state.me.name);
  for (const u of users || []) names.set(u.id, u.name);
  return names;
}

let toastTimer;
function toast(message, isError = false) {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.className = isError ? "toast error" : "toast";
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 3500);
}

// ---------------------------------------------------------------------------
// API client
// ---------------------------------------------------------------------------

class ApiError extends Error {
  constructor(status, message, errors) {
    super(message);
    this.status = status;
    this.errors = errors || [];
  }
}

function errorMessage(payload, status) {
  const detail = payload && payload.detail;
  if (typeof detail === "string") return detail;
  // FastAPI request validation: a list of {loc, msg}.
  if (Array.isArray(detail)) {
    return detail.map((e) => `${(e.loc || []).slice(1).join(".")}: ${e.msg}`).join("; ");
  }
  return `Request failed (${status})`;
}

async function api(path, { method = "GET", body, auth = true } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth && state.token) headers["Authorization"] = `Bearer ${state.token}`;

  const resp = await fetch(API + path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let payload = null;
  try { payload = await resp.json(); } catch { /* empty or non-JSON body */ }

  if (!resp.ok) {
    // Expired/invalid token: drop the session and go back to the login page.
    if (auth && resp.status === 401) logout();
    throw new ApiError(resp.status, errorMessage(payload, resp.status), payload && payload.errors);
  }
  return payload;
}

// ---------------------------------------------------------------------------
// Session & routing
// ---------------------------------------------------------------------------

function logout(navigate = true) {
  state.token = null;
  state.me = null;
  saveToken(null);
  if (navigate) go("/login");
}

function go(path) {
  if (location.hash === "#" + path) route();
  else location.hash = "#" + path;
}

const routes = [
  { pattern: /^\/login$/, view: loginView, public: true },
  { pattern: /^\/register$/, view: registerView, public: true },
  { pattern: /^\/$/, view: certificatesView },
  { pattern: /^\/certificates\/([0-9a-f-]{36})$/, view: certificateView },
  { pattern: /^\/admin\/users$/, view: usersView, admin: true },
  { pattern: /^\/admin\/issue$/, view: issueView, admin: true },
];

let routeSeq = 0;

async function route() {
  const path = location.hash.replace(/^#/, "") || "/";
  const match = routes.find((r) => r.pattern.test(path));

  if (!match) return go("/");
  if (!match.public && !state.me) return go("/login");
  if (match.public && state.me) return go("/");
  if (match.admin && !isAdmin()) return go("/");

  const seq = ++routeSeq;
  renderChrome(path);
  const view = document.getElementById("view");
  view.replaceChildren(h("p", { class: "muted" }, "Loading…"));

  let node;
  try {
    node = await match.view(...path.match(match.pattern).slice(1));
  } catch (err) {
    node = errorView(err);
  }
  // Ignore results of a view the user already navigated away from.
  if (seq === routeSeq) view.replaceChildren(node);
}

function renderChrome(path) {
  const bar = document.getElementById("topbar");
  bar.hidden = !state.me;
  if (!state.me) return;

  const links = [["/", isAdmin() ? "Certificates" : "My certificates"]];
  if (isAdmin()) links.push(["/admin/users", "Users"], ["/admin/issue", "Issue certificate"]);

  const isActive = (p) => (p === "/" ? path === "/" || path.startsWith("/certificates/") : path === p);
  document.getElementById("nav").replaceChildren(
    ...links.map(([p, label]) => h("a", { href: "#" + p, class: isActive(p) ? "active" : null }, label)),
  );
  document.getElementById("user-name").textContent = `${state.me.name} · ${state.me.role}`;
}

function errorView(err) {
  const title = err.status === 403 ? "Access denied" : err.status === 404 ? "Not found" : "Something went wrong";
  return h("div", { class: "card empty" },
    h("h2", {}, title),
    h("p", {}, err.message),
    h("a", { href: "#/" }, "← Back to certificates"),
  );
}

// Run a form submission: disable the button, show server errors inline.
async function submitting(form, fn) {
  const button = form.querySelector("button[type=submit]");
  const errorBox = form.querySelector(".form-error");
  button.disabled = true;
  errorBox.hidden = true;
  try {
    await fn();
  } catch (err) {
    errorBox.replaceChildren(...[err.message, ...(err.errors || [])].map((line) => h("div", {}, line)));
    errorBox.hidden = false;
  } finally {
    button.disabled = false;
  }
}

// Run a one-click action (approve, revoke, ...) and refresh the current view.
async function act(button, fn, successMessage) {
  button.disabled = true;
  try {
    await fn();
    toast(successMessage);
    await route();
  } catch (err) {
    toast(err.message, true);
    button.disabled = false;
  }
}

function field(label, input, hint) {
  return h("label", { class: "field" },
    h("span", { class: "label" }, label),
    input,
    hint && h("span", { class: "hint" }, hint),
  );
}

// ---------------------------------------------------------------------------
// Views
// ---------------------------------------------------------------------------

function loginView() {
  const form = h("form", {
    class: "card auth",
    onsubmit: (event) => {
      event.preventDefault();
      const data = new FormData(form);
      submitting(form, async () => {
        const token = await api("/auth/login", {
          method: "POST",
          auth: false,
          body: { email: data.get("email"), password: data.get("password") },
        });
        state.token = token.access_token;
        saveToken(state.token);
        state.me = await api("/auth/me");
        go("/");
      });
    },
  },
    h("p", { class: "brand-big" }, "Havoc"),
    h("p", { class: "muted" }, "Sign in to see your certificates."),
    field("Email", h("input", { name: "email", type: "email", required: true, autocomplete: "username" })),
    field("Password", h("input", { name: "password", type: "password", required: true, autocomplete: "current-password" })),
    h("div", { class: "form-error", role: "alert", hidden: true }),
    h("button", { type: "submit", class: "primary" }, "Sign in"),
    h("p", { class: "muted" }, "No account yet? ", h("a", { href: "#/register" }, "Register")),
  );
  return form;
}

function registerView() {
  const form = h("form", {
    class: "card auth",
    onsubmit: (event) => {
      event.preventDefault();
      const data = new FormData(form);
      submitting(form, async () => {
        const user = await api("/auth/register", {
          method: "POST",
          auth: false,
          body: { name: data.get("name"), email: data.get("email"), password: data.get("password") },
        });
        form.replaceWith(h("div", { class: "card auth" },
          h("p", { class: "brand-big" }, "Almost there"),
          h("p", {}, `Thanks, ${user.name}! Your account has been created and is waiting for approval by an administrator.`),
          h("p", { class: "muted" }, "You can sign in as soon as it has been approved."),
          h("a", { class: "button primary", href: "#/login" }, "Back to sign in"),
        ));
      });
    },
  },
    h("p", { class: "brand-big" }, "Create an account"),
    h("p", { class: "muted" }, "An administrator has to approve new accounts before you can sign in."),
    field("Name", h("input", { name: "name", required: true, maxlength: 255, autocomplete: "name" })),
    field("Email", h("input", { name: "email", type: "email", required: true, autocomplete: "email" })),
    field("Password", h("input", { name: "password", type: "password", required: true, minlength: 8, maxlength: 128, autocomplete: "new-password" }), "At least 8 characters."),
    h("div", { class: "form-error", role: "alert", hidden: true }),
    h("button", { type: "submit", class: "primary" }, "Register"),
    h("p", { class: "muted" }, "Already registered? ", h("a", { href: "#/login" }, "Sign in")),
  );
  return form;
}

async function certificatesView() {
  const admin = isAdmin();
  const [certs, users] = await Promise.all([
    api("/content?entity_type=certificate"),
    admin ? api("/admin/users") : null,
  ]);
  const names = userNames(users);

  const head = h("div", { class: "page-head" },
    h("h1", {}, admin ? "All certificates" : "My certificates"),
    admin && h("a", { class: "button primary", href: "#/admin/issue" }, "Issue certificate"),
  );
  if (!certs.length) {
    return h("section", {}, head, h("div", { class: "card empty" },
      admin ? "No certificates have been issued yet." : "You don't have any certificates yet."));
  }
  return h("section", {}, head, h("div", { class: "cert-grid" }, certs.map((c) => certificateCard(c, names))));
}

function certificateCard(cert, names) {
  const d = cert.data || {};
  return h("a", { class: `card cert ${cert.status}`, href: `#/certificates/${cert.id}` },
    h("div", { class: "cert-top" }, h("span", { class: "tag" }, typeLabel(d.type)), statusBadge(cert.status)),
    h("h2", {}, d.title || cert.slug),
    h("dl", { class: "meta" },
      isAdmin() && metaRow("Issued to", names.get(d.issued_to) || d.issued_to),
      metaRow("Issued", formatDate(d.issue_date)),
      d.valid_until && metaRow("Valid until", formatDate(d.valid_until)),
    ),
  );
}

async function certificateView(id) {
  const admin = isAdmin();
  const [cert, versions, users] = await Promise.all([
    api(`/content/${id}`),
    api(`/content/${id}/versions`),
    admin ? api("/admin/users") : null,
  ]);
  const names = userNames(users);
  const d = cert.data || {};

  const revokeButton = admin && cert.status !== "revoked" && h("button", {
    class: "danger",
    onclick: (event) => {
      if (!confirm(`Revoke "${d.title}"? The certificate stays on record but is marked as revoked.`)) return;
      act(event.currentTarget, () => api(`/content/${id}/revoke`, { method: "POST" }), "Certificate revoked");
    },
  }, "Revoke");

  return h("section", {},
    h("a", { class: "back", href: "#/" }, "← All certificates"),
    h("article", { class: "card detail" },
      h("div", { class: "cert-top" }, h("span", { class: "tag" }, typeLabel(d.type)), statusBadge(cert.status)),
      h("div", { class: "page-head", style: "margin: 0" }, h("h1", {}, d.title || cert.slug), revokeButton),
      cert.status === "revoked" && h("div", { class: "form-error" }, "This certificate has been revoked and is no longer valid."),
      h("dl", { class: "meta" },
        metaRow("Issued to", names.get(d.issued_to) || d.issued_to),
        names.has(d.issued_by) && metaRow("Issued by", names.get(d.issued_by)),
        metaRow("Issue date", formatDate(d.issue_date)),
        d.valid_from && metaRow("Valid from", formatDate(d.valid_from)),
        d.valid_until && metaRow("Valid until", formatDate(d.valid_until)),
        d.course_link && metaRow("Course", safeLink(d.course_link)),
        d.pdf_url && metaRow("PDF", safeLink(d.pdf_url)),
        metaRow("Verification token", h("code", {}, d.verification_token)),
      ),
    ),
    h("h2", { class: "section-title" }, `Version history (${versions.length})`),
    h("div", { class: "card table-wrap" }, h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, "#"), h("th", {}, "Created"), h("th", {}, "Author"), h("th", {}, "Data"))),
      h("tbody", {}, versions.map((v, i) => h("tr", {},
        h("td", {}, i + 1, v.id === cert.current_version_id && h("span", { class: "badge badge-active", style: "margin-left: 8px" }, "current")),
        h("td", {}, formatDateTime(v.created_at)),
        h("td", {}, names.get(v.author_id) || "—"),
        h("td", {}, h("details", {}, h("summary", {}, "Show"), h("pre", {}, JSON.stringify(v.data, null, 2)))),
      ))),
    )),
  );
}

async function usersView() {
  const users = await api("/admin/users");
  const pending = users.filter((u) => u.status === "pending");
  const others = users.filter((u) => u.status !== "pending");

  return h("section", {},
    h("div", { class: "page-head" }, h("h1", {}, "Users")),
    h("h2", { class: "section-title", style: "margin-top: 0" }, `Waiting for approval (${pending.length})`),
    pending.length ? usersTable(pending) : h("div", { class: "card empty" }, "No pending registrations."),
    h("h2", { class: "section-title" }, `Accounts (${others.length})`),
    usersTable(others),
  );
}

function usersTable(users) {
  return h("div", { class: "card table-wrap" }, h("table", {},
    h("thead", {}, h("tr", {},
      h("th", {}, "Name"), h("th", {}, "Email"), h("th", {}, "Role"),
      h("th", {}, "Status"), h("th", {}, "Registered"), h("th", {}, ""),
    )),
    h("tbody", {}, users.map((u) => h("tr", {},
      h("td", {}, u.name),
      h("td", {}, u.email),
      h("td", {}, u.role),
      h("td", {}, statusBadge(u.status)),
      h("td", {}, formatDate(u.created_at)),
      h("td", { class: "actions" }, userActions(u)),
    ))),
  ));
}

function userActions(user) {
  if (user.id === state.me.id) return h("span", { class: "muted" }, "you");

  const button = (label, action, cls, message) => h("button", {
    class: `small ${cls}`,
    onclick: (event) => act(event.currentTarget, () => api(`/admin/users/${user.id}/${action}`, { method: "POST" }), message),
  }, label);

  if (user.status === "pending") return button("Approve", "approve", "primary", `${user.name} approved`);
  if (user.status === "active") return button("Suspend", "suspend", "danger", `${user.name} suspended`);
  return button("Reactivate", "approve", "", `${user.name} reactivated`);
}

async function issueView() {
  const users = await api("/admin/users?status=active");

  const form = h("form", {
    class: "card form-card",
    onsubmit: (event) => {
      event.preventDefault();
      const f = new FormData(form);
      const data = {
        type: f.get("type"),
        title: f.get("title").trim(),
        issued_to: f.get("issued_to"),
        issued_by: state.me.id,
        issue_date: f.get("issue_date"),
      };
      // Optional fields are only sent when filled in.
      for (const key of ["valid_from", "valid_until", "course_link", "pdf_url"]) {
        const value = f.get(key).trim();
        if (value) data[key] = value;
      }
      submitting(form, async () => {
        const cert = await api("/content", { method: "POST", body: { entity_type: "certificate", data } });
        toast("Certificate issued");
        go(`/certificates/${cert.id}`);
      });
    },
  },
    field("Recipient", h("select", { name: "issued_to", required: true },
      h("option", { value: "" }, "Choose a user…"),
      users.map((u) => h("option", { value: u.id }, `${u.name} (${u.email})`)),
    ), "Only active accounts are listed."),
    h("div", { class: "form-row" },
      field("Type", h("select", { name: "type", required: true },
        Object.entries(CERTIFICATE_TYPES).map(([value, label]) =>
          h("option", { value, selected: value === "course_certificate" }, label)),
      )),
      field("Issue date", h("input", { name: "issue_date", type: "date", required: true, value: today() })),
    ),
    field("Title", h("input", { name: "title", required: true, placeholder: "e.g. Async Python for the Moon Backend" })),
    h("div", { class: "form-row" },
      field("Valid from", h("input", { name: "valid_from", type: "date" }), "Optional"),
      field("Valid until", h("input", { name: "valid_until", type: "date" }), "Optional"),
    ),
    field("Course link", h("input", { name: "course_link", type: "url", placeholder: "https://…" }), "Optional"),
    field("PDF URL", h("input", { name: "pdf_url", placeholder: "https://…" }), "Optional"),
    h("div", { class: "form-error", role: "alert", hidden: true }),
    h("div", { class: "form-actions" },
      h("a", { class: "button", href: "#/" }, "Cancel"),
      h("button", { type: "submit", class: "primary" }, "Issue certificate"),
    ),
  );

  return h("section", {}, h("div", { class: "page-head" }, h("h1", {}, "Issue a certificate")), form);
}

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------

async function init() {
  document.getElementById("logout").addEventListener("click", () => logout());
  window.addEventListener("hashchange", route);

  state.token = loadToken();
  if (state.token) {
    try {
      state.me = await api("/auth/me");
    } catch {
      // Expired token or account no longer active.
      logout(false);
    }
  }
  route();
}

init();
