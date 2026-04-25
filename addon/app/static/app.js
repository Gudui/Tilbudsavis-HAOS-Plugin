const state = {
  provider: document.body.dataset.provider,
  activeView: "dashboard",
  health: null,
  dashboard: null,
  providerHealth: [],
  watches: [],
  stores: [],
  storeGroups: [],
  productGroups: [],
  bestDeals: [],
  expiring: [],
  upcoming: [],
};

const elements = {
  healthSummary: document.getElementById("health-summary"),
  watchList: document.getElementById("watch-list"),
  watchForm: document.getElementById("watch-form"),
  syncButton: document.getElementById("sync-button"),
  refreshButton: document.getElementById("refresh-button"),
  dashboardSummary: document.getElementById("dashboard-summary"),
  providerHealth: document.getElementById("provider-health"),
  dashboardBest: document.getElementById("dashboard-best"),
  dashboardExpiring: document.getElementById("dashboard-expiring"),
  dashboardUpcoming: document.getElementById("dashboard-upcoming"),
  storeSelect: document.getElementById("store-select"),
  storeGroups: document.getElementById("store-groups"),
  storeDetail: document.getElementById("store-detail"),
  productSelect: document.getElementById("product-select"),
  productGroups: document.getElementById("product-groups"),
  productDetail: document.getElementById("product-detail"),
  bestDeals: document.getElementById("best-deals"),
  expiringList: document.getElementById("expiring-list"),
  upcomingList: document.getElementById("upcoming-list"),
};

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderEmpty(message) {
  return `<div class="empty-state">${escapeHtml(message)}</div>`;
}

function formatPrice(price, currency = "DKK") {
  return price == null ? "Price pending" : `${price.toFixed(2)} ${currency || "DKK"}`;
}

function formatDate(value) {
  if (!value) {
    return "Unknown date";
  }
  return new Date(value).toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatValidity(offer) {
  if (!offer.valid_from && !offer.valid_until) {
    return "Validity not supplied";
  }
  return `${formatDate(offer.valid_from)} to ${formatDate(offer.valid_until)}`;
}

function renderMatchCard(match) {
  const offer = match.offer;
  const watch = match.watched_product;
  const reasons = (match.reasons || []).map((reason) => `<span class="tag">${escapeHtml(reason)}</span>`).join("");
  const statusLabel = match.date_state ? match.date_state.replaceAll("_", " ") : match.status;
  return `
    <article class="match-card">
      <header>
        <div>
          <h3>${escapeHtml(offer.title)}</h3>
          <div class="match-meta">${escapeHtml(watch.name)} at ${escapeHtml(offer.store_name)}</div>
        </div>
        <div class="price-badge">${escapeHtml(formatPrice(offer.price, offer.currency))}</div>
      </header>
      <div class="tag-row">
        <span class="status-badge ${escapeHtml(match.date_state || match.status)}">${escapeHtml(statusLabel)}</span>
        <span class="tag">${escapeHtml(offer.provider)}</span>
        <span class="tag">${escapeHtml(offer.store_chain || offer.store_name)}</span>
        <span class="tag">${escapeHtml(formatValidity(offer))}</span>
      </div>
      <div class="tag-row">${reasons}</div>
    </article>
  `;
}

function renderMatchList(matches, emptyMessage) {
  if (!matches || matches.length === 0) {
    return renderEmpty(emptyMessage);
  }
  return `<div class="match-list">${matches.map(renderMatchCard).join("")}</div>`;
}

function renderSummaryCards() {
  const dashboard = state.dashboard;
  if (!dashboard) {
    elements.dashboardSummary.innerHTML = renderEmpty("Loading dashboard...");
    return;
  }
  elements.dashboardSummary.innerHTML = `
    <article class="summary-card">
      <div class="summary-label">Active matches</div>
      <strong>${dashboard.active_count}</strong>
    </article>
    <article class="summary-card">
      <div class="summary-label">Stores with matches</div>
      <strong>${dashboard.stores_with_matches}</strong>
    </article>
    <article class="summary-card">
      <div class="summary-label">Expiring soon</div>
      <strong>${dashboard.expiring_count}</strong>
    </article>
    <article class="summary-card">
      <div class="summary-label">Upcoming</div>
      <strong>${dashboard.upcoming_count}</strong>
    </article>
  `;
  elements.dashboardBest.innerHTML = renderMatchList(dashboard.best_matches, "No active matches yet.");
  elements.dashboardExpiring.innerHTML = renderMatchList(dashboard.expiring_soon, "Nothing is expiring soon.");
  elements.dashboardUpcoming.innerHTML = renderMatchList(dashboard.upcoming, "No upcoming offers right now.");
  elements.providerHealth.innerHTML = renderProviderHealthCards();
}

function renderProviderHealthCards() {
  if (!state.providerHealth.length) {
    return renderEmpty("No provider diagnostics yet.");
  }
  return state.providerHealth
    .map(
      (provider) => `
        <article class="summary-card">
          <div class="summary-label">${escapeHtml(provider.provider)}</div>
          <span class="status-badge ${escapeHtml(provider.status)}">${escapeHtml(provider.status)}</span>
          <div class="watch-meta">Last success: ${escapeHtml(provider.last_successful_sync_at ? formatDate(provider.last_successful_sync_at) : "None")}</div>
          <div class="watch-meta">Raw payloads: ${provider.raw_payload_count}</div>
          ${
            provider.last_error
              ? `<div class="watch-meta">Last error: ${escapeHtml(provider.last_error)}</div>`
              : ""
          }
          ${
            provider.last_schema_drift_warning
              ? `<div class="watch-meta">Schema drift: ${escapeHtml(provider.last_schema_drift_warning)}</div>`
              : ""
          }
        </article>
      `,
    )
    .join("");
}

function renderWatches() {
  if (state.watches.length === 0) {
    elements.watchList.innerHTML = renderEmpty("Add a watched product to begin matching offers.");
    return;
  }
  elements.watchList.innerHTML = state.watches
    .map(
      (watch) => `
        <article class="watch-card">
          <div>
            <strong>${escapeHtml(watch.name)}</strong>
            <div class="watch-meta">
              Keywords: ${escapeHtml((watch.keywords || []).join(", ") || watch.name)}
            </div>
            <div class="watch-meta">
              Excludes: ${escapeHtml((watch.exclude_keywords || []).join(", ") || "None")}
            </div>
            <div class="watch-meta">
              Max price: ${watch.max_price == null ? "No limit" : escapeHtml(formatPrice(watch.max_price))}
            </div>
          </div>
          <div class="watch-actions">
            <span class="tag">${watch.enabled ? "Enabled" : "Disabled"}</span>
            <button class="watch-delete" data-watch-id="${escapeHtml(watch.id)}" type="button">Delete</button>
          </div>
        </article>
      `,
    )
    .join("");

  elements.productSelect.innerHTML =
    `<option value="">Pick a watched product</option>` +
    state.watches
      .map((watch) => `<option value="${escapeHtml(watch.id)}">${escapeHtml(watch.name)}</option>`)
      .join("");
}

function renderHealth() {
  if (!state.health) {
    elements.healthSummary.innerHTML = renderEmpty("Loading health...");
    return;
  }
  const lastSync = state.health.last_sync;
  elements.healthSummary.innerHTML = `
    <div class="watch-meta">Status: ${escapeHtml(state.health.status)}</div>
    <div class="watch-meta">Providers: ${escapeHtml((state.health.providers || []).join(", "))}</div>
    <div class="watch-meta">Database: ${escapeHtml(state.health.database_path)}</div>
    <div class="watch-meta">
      Last sync: ${lastSync ? escapeHtml(`${lastSync.status} at ${formatDate(lastSync.completed_at)}`) : "No sync yet"}
    </div>
    ${lastSync?.error ? `<div class="watch-meta">Last error: ${escapeHtml(lastSync.error)}</div>` : ""}
  `;
}

function renderStoreViews() {
  elements.storeSelect.innerHTML =
    `<option value="">All stores with active matches</option>` +
    state.stores
      .map(
        (store) =>
          `<option value="${escapeHtml(store.slug)}">${escapeHtml(
            `${store.chain} (${store.match_count})`,
          )}</option>`,
      )
      .join("");

  if (state.storeGroups.length === 0) {
    elements.storeGroups.innerHTML = renderEmpty("Sync offers to see store-grouped matches.");
    return;
  }

  elements.storeGroups.innerHTML = state.storeGroups
    .map(
      (group) => `
        <section class="store-card">
          <header>
            <div>
              <h3>${escapeHtml(group.title)}</h3>
              <div class="watch-meta">${escapeHtml(group.subtitle)}</div>
            </div>
            <span class="tag">${group.match_count} matches</span>
          </header>
          ${renderMatchList(group.matches, "No matches in this store.")}
        </section>
      `,
    )
    .join("");
}

function renderProductViews() {
  if (state.productGroups.length === 0) {
    elements.productGroups.innerHTML = renderEmpty("Sync offers to compare watched products across stores.");
    return;
  }
  elements.productGroups.innerHTML = state.productGroups
    .map(
      (group) => `
        <section class="store-card">
          <header>
            <div>
              <h3>${escapeHtml(group.title)}</h3>
              <div class="watch-meta">${escapeHtml(group.subtitle)}</div>
            </div>
            <span class="tag">${group.match_count} offers</span>
          </header>
          ${renderMatchList(group.matches, "No competing offers yet.")}
        </section>
      `,
    )
    .join("");
}

async function renderStoreDetail(storeSlug) {
  if (!storeSlug) {
    elements.storeDetail.classList.add("hidden");
    elements.storeDetail.innerHTML = "";
    return;
  }
  const payload = await fetchJson(`api/stores/${encodeURIComponent(storeSlug)}/matches`);
  elements.storeDetail.classList.remove("hidden");
  elements.storeDetail.innerHTML = `
    <div class="panel-heading">
      <h2>Single-store focus</h2>
      <p>Everything worth buying in this store right now.</p>
    </div>
    ${renderMatchList(payload.matches, "No active matches in this store.")}
  `;
}

async function renderProductDetail(productId) {
  if (!productId) {
    elements.productDetail.classList.add("hidden");
    elements.productDetail.innerHTML = "";
    return;
  }
  const payload = await fetchJson(`api/watched-products/${encodeURIComponent(productId)}/matches?status=all`);
  elements.productDetail.classList.remove("hidden");
  elements.productDetail.innerHTML = `
    <div class="panel-heading">
      <h2>Single-product comparison</h2>
      <p>Compare one watched product across chains and dates.</p>
    </div>
    ${renderMatchList(payload.matches, "No matches for this watched product yet.")}
  `;
}

function renderLists() {
  elements.bestDeals.innerHTML = renderMatchList(state.bestDeals, "No active deals yet.");
  elements.expiringList.innerHTML = renderMatchList(state.expiring, "Nothing is expiring soon.");
  elements.upcomingList.innerHTML = renderMatchList(state.upcoming, "No upcoming offers right now.");
}

function activateView(view) {
  state.activeView = view;
  document.querySelectorAll(".tab-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });
  document.querySelectorAll(".view-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `view-${view}`);
  });
}

async function loadAll() {
  const [health, providers, dashboard, watches, storeGroups, productGroups, bestDeals, expiring, upcoming, stores] =
    await Promise.all([
      fetchJson("health"),
      fetchJson("api/providers"),
      fetchJson("api/dashboard"),
      fetchJson("api/watched-products"),
      fetchJson("api/matches/grouped?by=store&status=active"),
      fetchJson("api/matches/grouped?by=product&status=active"),
      fetchJson("api/matches/sorted?by=price&status=active"),
      fetchJson("api/matches?status=expiring"),
      fetchJson("api/matches?status=upcoming"),
      fetchJson("api/stores"),
    ]);

  state.health = health;
  state.providerHealth = providers.providers;
  state.dashboard = dashboard;
  state.watches = watches;
  state.storeGroups = storeGroups.groups;
  state.productGroups = productGroups.groups;
  state.bestDeals = bestDeals.matches;
  state.expiring = expiring.matches;
  state.upcoming = upcoming.matches;
  state.stores = stores.stores;

  renderHealth();
  renderWatches();
  renderSummaryCards();
  renderStoreViews();
  renderProductViews();
  renderLists();
}

async function syncOffers() {
  elements.syncButton.disabled = true;
  elements.syncButton.textContent = "Syncing...";
  try {
    await fetchJson("api/sync", { method: "POST" });
    await loadAll();
  } finally {
    elements.syncButton.disabled = false;
    elements.syncButton.textContent = "Sync Offers";
  }
}

function bindEvents() {
  document.querySelectorAll(".tab-button").forEach((button) => {
    button.addEventListener("click", () => activateView(button.dataset.view));
  });

  elements.syncButton.addEventListener("click", syncOffers);
  elements.refreshButton.addEventListener("click", loadAll);

  elements.watchForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(elements.watchForm);
    const payload = {
      name: formData.get("name"),
      keywords: splitCsv(formData.get("keywords")),
      exclude_keywords: splitCsv(formData.get("exclude_keywords")),
      store_filters: splitCsv(formData.get("store_filters")),
      max_price: formData.get("max_price") ? Number(formData.get("max_price")) : null,
      enabled: true,
    };
    await fetchJson("api/watched-products", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    elements.watchForm.reset();
    await loadAll();
  });

  elements.watchList.addEventListener("click", async (event) => {
    const target = event.target.closest("[data-watch-id]");
    if (!target) {
      return;
    }
    await fetchJson(`api/watched-products/${encodeURIComponent(target.dataset.watchId)}`, {
      method: "DELETE",
    });
    await loadAll();
  });

  elements.storeSelect.addEventListener("change", async (event) => {
    await renderStoreDetail(event.target.value);
  });

  elements.productSelect.addEventListener("change", async (event) => {
    await renderProductDetail(event.target.value);
  });
}

function splitCsv(value) {
  return String(value || "")
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

async function init() {
  bindEvents();

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("sw.js").catch(() => undefined);
    });
  }

  await loadAll();

  if (state.provider === "mock" && !state.health.last_sync) {
    await syncOffers();
  }
}

init().catch((error) => {
  elements.healthSummary.innerHTML = renderEmpty(`Unable to load Offer Radar: ${error.message}`);
});
