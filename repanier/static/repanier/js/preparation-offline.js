(function () {
  "use strict";

  const DB_NAME = "repanier-preparation";
  const DB_VERSION = 1;

  function openDatabase() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains("snapshots")) {
          db.createObjectStore("snapshots", { keyPath: "permanence_id" });
        }
        if (!db.objectStoreNames.contains("sync_queue")) {
          const queue = db.createObjectStore("sync_queue", { keyPath: "uuid" });
          queue.createIndex("client_timestamp", "client_timestamp");
          queue.createIndex("status", "status");
        }
        if (!db.objectStoreNames.contains("device_state")) {
          db.createObjectStore("device_state", { keyPath: "key" });
        }
        if (!db.objectStoreNames.contains("conflicts")) {
          db.createObjectStore("conflicts", { keyPath: "uuid" });
        }
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  function transaction(db, storeName, mode, operation) {
    return new Promise((resolve, reject) => {
      const tx = db.transaction(storeName, mode);
      const store = tx.objectStore(storeName);
      const request = operation(store);
      tx.oncomplete = () => resolve(request && request.result);
      tx.onerror = () => reject(tx.error);
    });
  }

  async function saveSnapshot(snapshot) {
    const db = await openDatabase();
    await transaction(db, "snapshots", "readwrite", (store) =>
      store.put({
        permanence_id: snapshot.permanence_id,
        data: snapshot,
        server_timestamp: snapshot.server_timestamp,
        saved_at: new Date().toISOString(),
      })
    );
  }

  function newUuid() {
    return crypto.randomUUID
        ? crypto.randomUUID()
        : "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
            const r = Math.random() * 16 | 0;
            const v = c === "x" ? r : (r & 0x3 | 0x8);
            return v.toString(16);
          });
  }

  async function enqueueEvent(syncUrl, event) {
    if (!event.uuid) event.uuid = newUuid();
    event.status = "pending";
    event.sync_url = syncUrl;

    const db = await openDatabase();
    await new Promise((resolve, reject) => {
      const tx = db.transaction("sync_queue", "readwrite");
      const store = tx.objectStore("sync_queue");
      const request = store.index("client_timestamp").openCursor(null, "prev");
      request.onsuccess = () => {
        const latest = request.result ? Date.parse(request.result.value.client_timestamp) + 1 : 0;
        event.client_timestamp = new Date(Math.max(Date.now(), latest)).toISOString();
        store.put(event);
      };
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error || new Error("Queue transaction aborted"));
    });
  }

  async function readQueueOrdered() {
    const db = await openDatabase();
    const page = document.querySelector("[data-preparation-sync]");
    return new Promise((resolve, reject) => {
      const tx = db.transaction("sync_queue", "readonly");
      const store = tx.objectStore("sync_queue");
      const index = store.index("client_timestamp");
      const events = [];
      const request = index.openCursor();
      request.onsuccess = () => {
        const cursor = request.result;
        if (cursor) {
          if (page && cursor.value.sync_url === page.dataset.preparationSync &&
              cursor.value.status === "pending") {
            events.push(cursor.value);
          }
          cursor.continue();
        } else {
          resolve(events);
        }
      };
      request.onerror = () => reject(request.error);
    });
  }

  async function updateQueueEvent(event) {
    const db = await openDatabase();
    await transaction(db, "sync_queue", "readwrite", (store) => store.put(event));
  }

  async function queueEventById(uuid) {
    const db = await openDatabase();
    return transaction(db, "sync_queue", "readonly", (store) => store.get(uuid));
  }

  async function updateLocalLineStatus(snapshot, purchaseId, status, quantity) {
    if (!snapshot || !snapshot.purchases) return snapshot;
    snapshot.purchases.forEach((purchase) => {
      if (String(purchase.purchase_id) === String(purchaseId)) {
        purchase.preparation_status = status;
        purchase.local_status = status;
        if (quantity !== undefined) purchase.quantity_received = quantity;
      }
    });
    await saveSnapshot(snapshot);
    return snapshot;
  }

  async function saveConflict(event, result) {
    const db = await openDatabase();
    await transaction(db, "conflicts", "readwrite", (store) =>
      store.put({
        uuid: event.uuid,
        event: event,
        result: result,
        saved_at: new Date().toISOString(),
      })
    );
  }

  async function readSnapshot(permanenceId) {
    const db = await openDatabase();
    return new Promise((resolve, reject) => {
      const tx = db.transaction("snapshots", "readonly");
      const request = tx.objectStore("snapshots").get(permanenceId);
      request.onsuccess = () => resolve(request.result ? request.result.data : null);
      request.onerror = () => reject(request.error);
    });
  }

  async function readLatestSnapshot() {
    const page = document.querySelector("[data-permanence-id]");
    return page ? readSnapshot(Number(page.dataset.permanenceId)) : null;
  }

  async function readConflicts() {
    const db = await openDatabase();
    const page = document.querySelector("[data-preparation-sync]");
    return new Promise((resolve, reject) => {
      const tx = db.transaction("conflicts", "readonly");
      const store = tx.objectStore("conflicts");
      const result = [];
      const request = store.openCursor();
      request.onsuccess = () => {
        const cursor = request.result;
        if (cursor) {
          if (page && cursor.value.event.sync_url === page.dataset.preparationSync) {
            result.push(cursor.value);
          }
          cursor.continue();
        } else {
          resolve(result);
        }
      };
      request.onerror = () => reject(request.error);
    });
  }

  async function deleteConflict(uuid) {
    const db = await openDatabase();
    await transaction(db, "conflicts", "readwrite", (store) => store.delete(uuid));
  }

  function buildSyncPayload(event) {
    const payload = {
      uuid: event.uuid,
      client_timestamp: event.client_timestamp,
      operation: event.operation,
      purchase_id: event.purchase_id,
      quantity: event.quantity,
    };
    const optionalFields = [
      "target_offer_item_id",
      "offer_item_id",
      "customer_id",
      "container_type_id",
      "returned_count",
      "missing_count",
      "disposition",
    ];
    optionalFields.forEach((field) => {
      if (event[field] !== undefined && event[field] !== null) {
        payload[field] = event[field];
      }
    });
    return payload;
  }

  let activeSynchronization = null;
  function synchronizeQueue() {
    if (!activeSynchronization) {
      activeSynchronization = synchronizeQueueOnce().finally(() => {
        activeSynchronization = null;
      });
    }
    return activeSynchronization;
  }

  async function synchronizeQueueOnce() {
    const state = document.querySelector("[data-preparation-network-state]");
    if (!navigator.onLine) {
      updateState(state, "offline", "Hors ligne");
      return;
    }
    const events = await readQueueOrdered();
    if (!events.length) {
      const conflicts = await readConflicts();
      updateState(state, conflicts.length ? "error" : "ready",
        conflicts.length ? "Conflits à traiter" : "À jour");
      updatePendingCount(0);
      return;
    }
    updatePendingCount(events.length);
    updateState(state, "syncing", "Synchronisation");
    let failed = false;

    for (const event of events) {
      try {
        if (event.depends_on) {
          const dependency = await queueEventById(event.depends_on);
          if (!dependency || dependency.status !== "applied") continue;
        }
        const response = await fetch(event.sync_url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(buildSyncPayload(event)),
        });
        if (!response.ok) {
          if (response.status >= 400 && response.status < 500) {
            let result;
            try {
              result = JSON.parse(await response.text());
            } catch (error) {
              failed = true;
              continue;
            }
            const eventResult = result.result || result;
            if (eventResult.status === "conflict" || eventResult.status === "rejected") {
              event.status = eventResult.status;
              await updateQueueEvent(event);
              await saveConflict(event, eventResult);
              await updateGroupEventStatus(event, "conflict");
              await renderConflicts();
            } else {
              failed = true;
            }
          } else {
            failed = true;
          }
          continue;
        }
        let result;
        try {
          const text = await response.text();
          if (!text) {
            throw new Error("Empty response");
          }
          result = JSON.parse(text);
        } catch (error) {
          failed = true;
          continue;
        }
        const eventResult = result.result || result;
        if (eventResult.status === "applied") {
          event.status = "applied";
          await updateQueueEvent(event);
          await updateGroupEventStatus(event, "applied");
        } else if (eventResult.status === "conflict" || eventResult.status === "rejected") {
          event.status = eventResult.status;
          await updateQueueEvent(event);
          await saveConflict(event, eventResult);
          await updateGroupEventStatus(event, "conflict");
        } else {
          failed = true;
        }
      } catch (error) {
        updateState(state, "offline", "Hors ligne");
        return;
      }
    }

    const remaining = await readQueueOrdered();
    updatePendingCount(remaining.length);
    await renderConflicts();
    const conflicts = await readConflicts();
    if (failed || conflicts.length) {
      updateState(state, "error", "Événements en attente ou en conflit");
    } else {
      updateState(state, remaining.length ? "syncing" : "ready", remaining.length ? "En attente" : "À jour");
    }
  }

  function updateState(element, mode, label) {
    if (!element) return;
    element.className = "preparation-network-state " + mode;
    element.dataset.state = mode;
    element.textContent = label;
  }

  function updatePendingCount(count) {
    document.querySelectorAll("[data-preparation-pending-count]").forEach((element) => {
      element.textContent = String(count);
    });
  }

  function populateReferenceSelect(selector, items, nameKey) {
    const select = document.querySelector(selector);
    if (!select) return;
    select.innerHTML = (items || []).map((item) =>
      '<option value="' + escapeHtml(item.id) + '">' +
      escapeHtml(item[nameKey || "name"]) +
      '</option>'
    ).join("");
  }

  function populateSnapshotReferences(snapshot) {
    populateReferenceSelect("[data-express-customer]", snapshot.customers, "name");
    populateReferenceSelect("[data-express-offer]", snapshot.offers, "name");
    populateReferenceSelect("[data-deposit-customer]", snapshot.customers, "name");
    populateReferenceSelect("[data-deposit-type]", snapshot.deposit_types, "name");
    populateReferenceSelect("[data-substitution-target]", snapshot.offers, "name");
    const lines = (snapshot.purchases || []).filter((purchase) => purchase.purchase_id)
      .map((purchase) => ({ id: purchase.purchase_id, product: purchase.product }));
    populateReferenceSelect("[data-substitution-source]", lines, "product");
    populateReferenceSelect("[data-parcel-purchase]", lines, "product");
    const warning = document.querySelector("[data-uncertain-arrival]");
    if (warning) warning.hidden = !snapshot.uncertain_arrival;
  }

  async function renderConflicts() {
    const container = document.querySelector("[data-preparation-conflicts]");
    if (!container) return;
    let conflicts;
    try {
      conflicts = await readConflicts();
    } catch (error) {
      return;
    }
    if (!conflicts.length) {
      container.innerHTML = "";
      return;
    }
    container.innerHTML =
      '<div class="alert alert-warning"><strong>Conflits ou rejets</strong><ul class="mb-0">' +
      conflicts.map((conflict) =>
        '<li data-conflict-uuid="' + escapeHtml(conflict.uuid) + '">' +
        escapeHtml(conflict.result.reason || conflict.result.status || "Événement non synchronisé") +
        (conflict.event.group_handover
          ? ' — Remise en attente : contacter le responsable pour résoudre le conflit.'
          : '<button type="button" class="btn btn-sm btn-outline-secondary ms-2" ' +
            'data-retry-conflict="' + escapeHtml(conflict.uuid) + '">Réessayer</button>' +
            '<button type="button" class="btn btn-sm btn-outline-danger ms-1" ' +
            'data-dismiss-conflict="' + escapeHtml(conflict.uuid) + '">Ignorer</button>') +
        '</li>'
      ).join("") +
      '</ul></div>';

    container.querySelectorAll("[data-retry-conflict]").forEach((button) => {
      button.addEventListener("click", async () => {
        const conflict = conflicts.find((item) => item.uuid === button.dataset.retryConflict);
        if (!conflict) return;
        conflict.event.status = "pending";
        await updateQueueEvent(conflict.event);
        await deleteConflict(conflict.uuid);
        await renderConflicts();
        await synchronizeQueue();
      });
    });
    container.querySelectorAll("[data-dismiss-conflict]").forEach((button) => {
      button.addEventListener("click", async () => {
        await deleteConflict(button.dataset.dismissConflict);
        await renderConflicts();
      });
    });
  }

  async function clearOfflineDemoState() {
    const db = await openDatabase();
    const page = document.querySelector("[data-preparation-sync]");
    if (!page) throw new Error("Missing preparation page");
    const removeMatching = (storeName, matches) => new Promise((resolve, reject) => {
      const tx = db.transaction(storeName, "readwrite");
      const request = tx.objectStore(storeName).openCursor();
      request.onsuccess = () => {
        const cursor = request.result;
        if (cursor) {
          if (matches(cursor.value)) cursor.delete();
          cursor.continue();
        }
      };
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
    });
    await Promise.all([
      removeMatching("sync_queue", (event) => event.sync_url === page.dataset.preparationSync),
      removeMatching("conflicts", (conflict) => conflict.event.sync_url === page.dataset.preparationSync),
      transaction(db, "snapshots", "readwrite", (store) => store.delete(Number(page.dataset.permanenceId))),
    ]);
  }

  function preparationSort(a, b) {
    const producer = String(a.producer || "").localeCompare(String(b.producer || ""));
    if (producer !== 0) return producer;
    const department = String(a.department || "").localeCompare(String(b.department || ""));
    if (department !== 0) return department;
    const weight = Number(b.order_average_weight || 0) - Number(a.order_average_weight || 0);
    if (weight !== 0) return weight;
    return String(a.product || "").localeCompare(String(b.product || ""));
  }

  function lineQuantity(purchase) {
    if (purchase.preparation_status === "ordered") return purchase.quantity_ordered;
    if (purchase.preparation_status === "validated" || purchase.preparation_status === "pending") return purchase.quantity_received;
    return purchase.quantity_prepared;
  }

  function aggregateGroupLines(purchases) {
    const groups = new Map();
    purchases.forEach((purchase) => {
      if (purchase.regime !== "standard" || !purchase.in_group) return;
      const key = purchase.group_id + ":" + purchase.offer_item_id;
      if (!groups.has(key)) {
        groups.set(key, {
          ...purchase,
          purchase_id: null,
          aggregate: true,
          quantity_ordered: "0",
          quantity_prepared: "0",
          quantity_received: "0",
          purchase_ids: [],
          purchase_quantities: {},
          purchase_statuses: {},
        });
      }
      const aggregate = groups.get(key);
      if (purchase.purchase_id != null) {
        aggregate.purchase_ids.push(purchase.purchase_id);
        aggregate.purchase_quantities[purchase.purchase_id] =
          lineQuantity(purchase);
        aggregate.purchase_statuses[purchase.purchase_id] = purchase.preparation_status;
      }
      aggregate.quantity_ordered = String(
        Number(aggregate.quantity_ordered) + Number(purchase.quantity_ordered)
      );
      aggregate.quantity_prepared = String(
        Number(aggregate.quantity_prepared) + Number(purchase.quantity_prepared)
      );
      aggregate.quantity_received = String(
        Number(aggregate.quantity_received) + Number(purchase.quantity_received)
      );
      if (purchase.preparation_status === "conflict") aggregate.preparation_status = "conflict";
      else if (purchase.preparation_status === "pending" && aggregate.preparation_status !== "conflict") aggregate.preparation_status = "pending";
    });
    for (const aggregate of groups.values()) {
      const statuses = Object.values(aggregate.purchase_statuses);
      if (statuses.includes("conflict")) aggregate.preparation_status = "conflict";
      else if (statuses.includes("pending")) aggregate.preparation_status = "pending";
      else if (statuses.every((status) => status === "validated")) aggregate.preparation_status = "validated";
      else if (statuses.every((status) => ["validated", "handed_to_group"].includes(status))) aggregate.preparation_status = "handed_to_group";
      else aggregate.preparation_status = "ordered";
    }
    return Array.from(groups.values());
  }

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value == null ? "" : String(value);
    return div.innerHTML;
  }

  function renderPreparationLines(snapshot) {
    const container = document.querySelector("[data-preparation-lines]");
    const producerFilter = document.querySelector("[data-preparation-producer-filter]");
    if (!container) return;

    let purchases = (snapshot.purchases || []).slice().sort(preparationSort);
    if (producerFilter && producerFilter.value) {
      purchases = purchases.filter((item) => item.producer === producerFilter.value);
    }

    const standardGrouped = aggregateGroupLines(purchases);
    const individual = purchases.filter(
      (item) => item.regime !== "standard" || !item.in_group
    );
    const lines = individual.concat(standardGrouped).sort(preparationSort);

    container.innerHTML = lines.map((item) => {
      const exception = item.aggregate ? "false" : "false";
      const quantity = lineQuantity(item);
      const basketDisposition =
        '<div class="d-grid gap-2 mt-2">' +
          '<button type="button" class="btn btn-success preparation-basket conform" data-basket-status="conform" style="min-height:44px">Colis conforme</button>' +
          '<button type="button" class="btn btn-outline-danger preparation-basket not-in-bl" data-basket-status="not_in_bl" style="min-height:44px">Non livré / absent du BL</button>' +
          '<button type="button" class="btn btn-outline-warning preparation-basket lost" data-basket-status="lost_in_transit" style="min-height:44px">Perdu en chemin</button>' +
        '</div>';
      const wrappedInput =
        '<input class="form-control preparation-quantity wrapped-quantity" type="number" step="0.0001" min="0" ' +
        'value="' + escapeHtml(quantity) + '" data-preparation-quantity="' + escapeHtml(item.purchase_id || "") + '" style="min-height:44px" />';
      const standardInput =
        '<input class="form-control preparation-quantity" type="number" step="0.0001" min="0" ' +
        'value="' + escapeHtml(quantity) + '" data-preparation-quantity="' + escapeHtml(item.purchase_id || "") + '" style="min-height:44px;display:none" />';
      return (
        '<article class="preparation-line" data-status="' + escapeHtml(item.preparation_status) +
        '" data-exception="' + exception + '" data-purchase-id="' + escapeHtml(item.purchase_id || "") +
        '" data-aggregate="' + (item.aggregate ? "true" : "false") +
        '" data-purchase-ids="' + escapeHtml(item.aggregate ? item.purchase_ids.join(",") : "") + '">' +
          '<div>' +
            '<strong>' + escapeHtml(item.product) + '</strong>' +
            '<div class="small text-muted">' + escapeHtml(item.producer) +
            (item.customer ? " — " + escapeHtml(item.customer) : "") + '</div>' +
            '<div class="small">Qté : ' + escapeHtml(quantity) + '</div>' +
          '</div>' +
          ((item.purchase_id || item.aggregate)
            ? '<div>' +
                '<button type="button" class="btn btn-success preparation-conform" data-preparation-conform="' +
                escapeHtml(item.purchase_id || "aggregate") + '"' +
                (item.aggregate && ["pending", "conflict", "validated", "handed_to_group"].includes(item.preparation_status) ? " disabled" : "") +
                ' style="min-height:44px">OK</button>' +
                '<button type="button" class="btn btn-outline-secondary mt-2 w-100" ' +
                'data-preparation-exception="' + escapeHtml(item.purchase_id) + '" style="min-height:44px;display:none">Exception</button>' +
                (item.aggregate
                  ? ''
                  : item.regime === "wrapped"
                    ? wrappedInput
                    : item.regime === "basket"
                      ? basketDisposition
                      : standardInput) +
              '</div>'
            : '<button type="button" class="btn btn-success preparation-conform" style="min-height:44px">OK</button>'
          ) +
        '</article>'
      );
    }).join("");

    bindPreparationActions(lines);
  }

  function bindPreparationActions(lines) {
    document.querySelectorAll("[data-preparation-conform]").forEach((button) => {
      button.addEventListener("click", async () => {
        const purchaseId = Number(button.dataset.preparationConform);
        const line = button.closest(".preparation-line");
        let item = lines.find((entry) => Number(entry.purchase_id) === purchaseId);
        if (!item && line.dataset.aggregate === "true") {
          item = lines.find((entry) =>
            entry.aggregate &&
            line.dataset.purchaseIds
              .split(",")
              .every((id) => entry.purchase_ids.includes(Number(id)))
          );
        }
        if (item && item.aggregate && Array.isArray(item.purchase_ids)) {
          line.dataset.status = "pending";
          button.disabled = true;
          try {
            await queueGroupHandover(item);
          } catch (error) {
            console.error("Group handover failed", error);
            updateState(document.querySelector("[data-preparation-network-state]"), "error", "Remise non confirmée : rechargez et vérifiez la file");
          }
          return;
        }
        const quantityInput = line.querySelector("[data-preparation-quantity]");
        const quantity = quantityInput && quantityInput.style.display !== "none"
          ? quantityInput.value : lineQuantity(item);
        line.dataset.status = "pending";
        button.disabled = true;
        try {
          await queuePreparationOperation("validate", purchaseId, quantity);
          line.querySelector("[data-preparation-exception]").style.display = "block";
        } catch (error) {
          updateState(document.querySelector("[data-preparation-network-state]"), "error", "Erreur de stockage local");
        } finally {
          button.disabled = false;
        }
      });
    });
    document.querySelectorAll("[data-preparation-exception]").forEach((button) => {
      button.addEventListener("click", () => {
        const line = button.closest(".preparation-line");
        const quantityInput = line.querySelector("[data-preparation-quantity]");
        if (quantityInput) {
          quantityInput.style.display =
            quantityInput.style.display === "none" ? "block" : "none";
        }
        line.dataset.exception =
          line.dataset.exception === "true" ? "false" : "true";
      });
    });

    document.querySelectorAll("[data-basket-status]").forEach((button) => {
      button.addEventListener("click", () => {
        const line = button.closest(".preparation-line");
        const purchaseId = Number(line.dataset.purchaseId);
        if (!purchaseId) return;
        if (button.dataset.basketStatus === "conform") {
          const item = lines.find((entry) => entry.purchase_id === purchaseId);
          queuePreparationOperation("validate", purchaseId, lineQuantity(item));
        } else {
          queueParcelDisposition(
            purchaseId,
            button.dataset.basketStatus,
          );
        }
        line.dataset.status = "pending";
      });
    });
  }

  async function queueGroupHandover(item) {
    const page = document.querySelector("[data-preparation-sync]");
    if (!page) throw new Error("Missing preparation page");
    const db = await openDatabase();
    const events = [];
    for (const id of item.purchase_ids) {
      if (["validated", "handed_to_group"].includes(item.purchase_statuses[id])) continue;
      if (!["ordered", "prepared"].includes(item.purchase_statuses[id])) {
        throw new Error("Group line has an unresolved state");
      }
      let dependency = null;
      const operations = item.purchase_statuses[id] === "ordered"
        ? ["prepare", "receive", "hand_to_group"]
        : ["receive", "hand_to_group"];
      for (const operation of operations) {
        const event = {
          uuid: newUuid(), operation, purchase_id: id,
          quantity: item.purchase_quantities[id], status: "pending",
          sync_url: page.dataset.preparationSync, group_handover: true,
          depends_on: dependency,
        };
        dependency = event.uuid;
        events.push(event);
      }
    }
    await new Promise((resolve, reject) => {
      const tx = db.transaction(["sync_queue", "snapshots"], "readwrite");
      const store = tx.objectStore("sync_queue");
      const snapshots = tx.objectStore("snapshots");
      let failure;
      const snapshotRequest = snapshots.get(Number(page.dataset.permanenceId));
      snapshotRequest.onsuccess = () => {
        const record = snapshotRequest.result;
        if (!record || events.some((event) => {
          const purchase = record.data.purchases.find((line) => line.purchase_id === event.purchase_id);
          return !purchase || purchase.preparation_status !== item.purchase_statuses[event.purchase_id];
        })) {
          failure = new Error("Group line changed; refresh before retrying");
          tx.abort();
          return;
        }
        const request = store.index("client_timestamp").openCursor(null, "prev");
        request.onsuccess = () => {
          let timestamp = Math.max(Date.now(), request.result ? Date.parse(request.result.value.client_timestamp) + 1 : 0);
          events.forEach((event) => {
            event.client_timestamp = new Date(timestamp++).toISOString();
            store.add(event);
          });
          record.data.purchases.forEach((purchase) => {
            if (events.some((event) => event.purchase_id === purchase.purchase_id)) {
              purchase.preparation_status = "pending";
              purchase.local_status = "pending";
              purchase.quantity_received = item.purchase_quantities[purchase.purchase_id];
            }
          });
          snapshots.put(record);
        };
      };
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(failure || tx.error || new Error("Queue transaction aborted"));
    });
    const snapshot = await readLatestSnapshot();
    if (snapshot) renderPreparationLines(snapshot);
    if (activeSynchronization) await activeSynchronization;
    await synchronizeQueue();
  }

  async function updateGroupEventStatus(event, status) {
    if (!event.group_handover || (status === "applied" && event.operation !== "hand_to_group")) return;
    const snapshot = await readLatestSnapshot();
    if (snapshot && status === "applied") {
      const purchase = snapshot.purchases.find((line) => line.purchase_id === event.purchase_id);
      if (purchase) purchase.quantity_prepared = event.quantity;
    }
    await updateLocalLineStatus(
      snapshot, event.purchase_id,
      status === "conflict" ? "conflict" : "handed_to_group",
    );
    if (snapshot) renderPreparationLines(snapshot);
  }

  async function queuePreparationOperation(operation, purchaseId, quantity) {
    const page = document.querySelector("[data-preparation-sync]");
    if (!page) return;
    const event = {
      operation: operation,
      purchase_id: purchaseId,
      quantity: quantity,
    };
    await enqueueEvent(page.dataset.preparationSync, event);
    const snapshot = await readLatestSnapshot();
    await updateLocalLineStatus(
      snapshot,
      purchaseId,
      operation === "validate" ? "pending" : "prepared",
      operation === "validate" ? quantity : undefined,
    );
    await synchronizeQueue();
  }

  async function queueSubstitution(sourcePurchaseId, targetOfferItemId, quantity) {
    const page = document.querySelector("[data-preparation-sync]");
    if (!page) return;
    const snapshot = await readLatestSnapshot();
    await updateLocalLineStatus(snapshot, sourcePurchaseId, "pending");
    await enqueueEvent(page.dataset.preparationSync, {
      operation: "substitute",
      purchase_id: sourcePurchaseId,
      target_offer_item_id: targetOfferItemId,
      quantity: quantity,
    });
    await synchronizeQueue();
  }

  async function queueExpressRequest(offerItemId, customerId, quantity) {
    const page = document.querySelector("[data-preparation-sync]");
    if (!page) return;
    const snapshot = await readLatestSnapshot();
    await updateLocalLineStatus(snapshot, null, "pending");
    await enqueueEvent(page.dataset.preparationSync, {
      operation: "express_request",
      offer_item_id: offerItemId,
      customer_id: customerId,
      quantity: quantity,
    });
    await synchronizeQueue();
  }

  async function queueDepositReceipt(containerTypeId, customerId, returnedCount, missingCount) {
    const page = document.querySelector("[data-preparation-sync]");
    if (!page) return;
    await enqueueEvent(page.dataset.preparationSync, {
      operation: "deposit_receipt",
      container_type_id: containerTypeId,
      customer_id: customerId,
      returned_count: returnedCount,
      missing_count: missingCount,
    });
    await synchronizeQueue();
  }

  async function queueParcelDisposition(purchaseId, disposition) {
    const page = document.querySelector("[data-preparation-sync]");
    if (!page) return;
    const snapshot = await readLatestSnapshot();
    await updateLocalLineStatus(snapshot, purchaseId, "pending");
    await enqueueEvent(page.dataset.preparationSync, {
      operation: "parcel_disposition",
      purchase_id: purchaseId,
      disposition: disposition,
    });
    await synchronizeQueue();
  }

  window.repanierPreparationOffline = {
    openDatabase,
    saveSnapshot,
    buildSyncPayload,
    enqueueEvent,
    synchronizeQueue,
    renderPreparationLines,
    aggregateGroupLines,
    readSnapshot,
    readLatestSnapshot,
    readConflicts,
    renderConflicts,
    queueSubstitution,
    queueExpressRequest,
    queueDepositReceipt,
    queueParcelDisposition,
    queueGroupHandover,
  };

  function getCsrfToken() {
    const match = document.cookie.match(/(?:^|; )csrftoken=([^;]*)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-open-preparation-modal]").forEach((button) => {
      button.addEventListener("click", () => {
        const modalIds = {
          substitution: "substitutionModal",
          express: "expressModal",
          deposit: "depositModal",
          parcel: "parcelModal",
        };
        const modalElement = document.getElementById(modalIds[button.dataset.openPreparationModal]);
        if (modalElement && window.bootstrap) {
          window.bootstrap.Modal.getOrCreateInstance(modalElement).show();
        }
      });
    });

    const closeModal = (elementId) => {
        const element = document.getElementById(elementId);
        if (element && window.bootstrap) {
          window.bootstrap.Modal.getOrCreateInstance(element).hide();
        }
    };

    function bindModalSubmit(selector, modalId, action) {
      const button = document.querySelector(selector);
      if (!button) return;
      button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          await action();
          closeModal(modalId);
        } catch (error) {
          updateState(document.querySelector("[data-preparation-network-state]"), "error", "Erreur de stockage local");
        } finally {
          button.disabled = false;
        }
      });
    }

    bindModalSubmit("[data-submit-substitution]", "substitutionModal", () =>
          queueSubstitution(
            Number(document.querySelector("[data-substitution-source]").value),
            Number(document.querySelector("[data-substitution-target]").value),
            document.querySelector("[data-substitution-quantity]").value,
          ));
    bindModalSubmit("[data-submit-express]", "expressModal", () =>
          queueExpressRequest(
            Number(document.querySelector("[data-express-offer]").value),
            Number(document.querySelector("[data-express-customer]").value),
            document.querySelector("[data-express-quantity]").value,
          ));
    bindModalSubmit("[data-submit-deposit]", "depositModal", () =>
          queueDepositReceipt(
            Number(document.querySelector("[data-deposit-type]").value),
            Number(document.querySelector("[data-deposit-customer]").value),
            Number(document.querySelector("[data-deposit-returned]").value),
            Number(document.querySelector("[data-deposit-missing]").value),
          ));
    bindModalSubmit("[data-submit-parcel]", "parcelModal", () =>
          queueParcelDisposition(
            Number(document.querySelector("[data-parcel-purchase]").value),
            document.querySelector("[data-parcel-disposition]").value,
          ));

    const demoReset = document.querySelector("[data-demo-reset]");
    if (demoReset) {
      demoReset.addEventListener("click", async () => {
        const page = document.querySelector("[data-preparation-sync]");
        const main = document.querySelector("[data-demo-reset-url]");
        if (!page || !main) return;
        const response = await fetch(main.dataset.demoResetUrl, {
          method: "POST",
          headers: { "X-CSRFToken": getCsrfToken() },
        });
        if (response.ok) {
          await clearOfflineDemoState();
          window.location.reload();
        }
      });
    }

    const demoReplay = document.querySelector("[data-demo-network-simulate]");
    if (demoReplay) {
      demoReplay.addEventListener("click", async () => {
        const main = document.querySelector("[data-demo-replay-url]");
        if (main) {
          await fetch(main.dataset.demoReplayUrl, {
            method: "POST",
            headers: { "X-CSRFToken": getCsrfToken() },
          });
        }
        await clearOfflineDemoState();
        window.dispatchEvent(new Event("offline"));
        updateState(document.querySelector("[data-preparation-network-state]"), "offline", "Hors ligne");
        await new Promise((resolve) => window.setTimeout(resolve, 800));
        window.dispatchEvent(new Event("online"));
        await synchronizeQueue();
      });
    }

    const state = document.querySelector("[data-preparation-network-state]");
    const page = document.querySelector("[data-preparation-snapshot]");
    let snapshotReady = !page;
    if (page) {
      fetch(page.dataset.preparationSnapshot, { cache: "no-store" })
        .then((response) => {
          if (!response.ok) throw new Error("Snapshot HTTP " + response.status);
          return response.json();
        })
        .then(async (snapshot) => {
          const pending = await readQueueOrdered();
          const conflicts = await readConflicts();
          for (const event of pending.filter((entry) => entry.group_handover)) {
            const purchase = snapshot.purchases.find((line) => line.purchase_id === event.purchase_id);
            if (purchase) {
              purchase.preparation_status = "pending";
              purchase.quantity_received = event.quantity;
            }
          }
          for (const conflict of conflicts.filter((entry) => entry.event.group_handover)) {
            const purchase = snapshot.purchases.find((line) => line.purchase_id === conflict.event.purchase_id);
            if (purchase) purchase.preparation_status = "conflict";
          }
          await saveSnapshot(snapshot);
          populateSnapshotReferences(snapshot);
          const producerFilter = document.querySelector("[data-preparation-producer-filter]");
          if (producerFilter) {
            const producers = Array.from(
              new Set((snapshot.purchases || []).map((item) => item.producer).filter(Boolean))
            ).sort();
            producers.forEach((producer) => {
              const option = document.createElement("option");
              option.value = producer;
              option.textContent = producer;
              producerFilter.appendChild(option);
            });
            producerFilter.addEventListener("change", async () => {
              const latest = await readLatestSnapshot();
              if (latest) renderPreparationLines(latest);
            });
          }
          renderPreparationLines(snapshot);
          snapshotReady = true;
          await synchronizeQueue();
        })
        .catch(async () => {
          const cachedSnapshot = await readLatestSnapshot();
          if (cachedSnapshot) {
            populateSnapshotReferences(cachedSnapshot);
            const producerFilter = document.querySelector("[data-preparation-producer-filter]");
            if (producerFilter) {
              const producers = Array.from(
                new Set((cachedSnapshot.purchases || []).map((item) => item.producer).filter(Boolean))
              ).sort();
              producerFilter.querySelectorAll("option:not([value=''])").forEach((option) => option.remove());
              producers.forEach((producer) => {
                const option = document.createElement("option");
                option.value = producer;
                option.textContent = producer;
                producerFilter.appendChild(option);
              });
              producerFilter.addEventListener("change", async () => {
                const latest = await readLatestSnapshot();
                if (latest) renderPreparationLines(latest);
              });
            }
            renderPreparationLines(cachedSnapshot);
          }
          updateState(document.querySelector("[data-preparation-network-state]"), "offline", "Hors ligne");
          await renderConflicts();
          snapshotReady = true;
          await synchronizeQueue();
        });
    }
    if (!state) return;
    window.addEventListener("online", () => {
      if (snapshotReady) synchronizeQueue();
    });
    window.addEventListener("offline", () => updateState(state, "offline", "Hors ligne"));
    renderConflicts();
    if (!page) synchronizeQueue();
  });
})();
