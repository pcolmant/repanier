const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function fakeIndexedDB() {
  const stores = new Map();
  function txFor() {
    let active = 0;
    let aborted = false;
    const tx = {
      error: null,
      transaction: null,
      objectStore(name) { return storeFor(name); },
      abort() { aborted = true; if (tx.onabort) tx.onabort(); },
    };
    function run(action) {
      const request = {};
      active++;
      setImmediate(() => {
        if (aborted) return;
        try {
          request.result = action();
          if (request.onsuccess) request.onsuccess();
        } catch (error) {
          tx.error = error;
          if (tx.onerror) tx.onerror();
          return;
        }
        active--;
        if (!active) setImmediate(() => { if (!aborted && !active && tx.oncomplete) tx.oncomplete(); });
      });
      return request;
    }
    function storeFor(name) {
      const data = stores.get(name);
      return {
      put(value) { return run(() => { data.set(value.uuid ?? value.permanence_id, structuredClone(value)); }); },
      add(value) { return run(() => {
        if (data.has(value.uuid)) throw new Error("duplicate key");
        data.set(value.uuid, structuredClone(value));
      }); },
      get(key) { return run(() => structuredClone(data.get(key))); },
      index() {
        return {
          openCursor(_range, direction) {
            const values = [...data.values()].sort((a, b) =>
              a.client_timestamp.localeCompare(b.client_timestamp));
            if (direction === "prev") values.reverse();
            let position = 0;
            const request = {};
            function next() {
              active++;
              setImmediate(() => {
                const value = values[position];
                request.result = value ? {
                  value: structuredClone(value),
                  continue() { position++; next(); },
                } : null;
                if (request.onsuccess) request.onsuccess();
                active--;
                if (!active) setImmediate(() => { if (!active && tx.oncomplete) tx.oncomplete(); });
              });
            }
            next();
            return request;
          },
        };
      },
      openCursor() {
        const values = [...data.values()];
        let position = 0;
        const request = {};
        function next() {
          active++;
          setImmediate(() => {
            request.result = values[position] ? {
              value: structuredClone(values[position]),
              continue() { position++; next(); },
            } : null;
            if (request.onsuccess) request.onsuccess();
            active--;
            if (!active) setImmediate(() => { if (!active && tx.oncomplete) tx.oncomplete(); });
          });
        }
        next();
        return request;
      },
      };
    }
    return tx;
  }
  const db = {
    objectStoreNames: { contains(name) { return stores.has(name); } },
    createObjectStore(name) {
      stores.set(name, new Map());
      return { createIndex() {} };
    },
    transaction() { return txFor(); },
  };
  return {
    stores,
    open() {
      const request = {};
      setImmediate(() => {
        request.result = db;
        if (!stores.size && request.onupgradeneeded) request.onupgradeneeded();
        if (request.onsuccess) request.onsuccess();
      });
      return request;
    },
  };
}

function load(options = {}) {
  const container = { innerHTML: "" };
  const page = { dataset: { preparationSync: "/sync", permanenceId: "7" } };
  const indexedDB = fakeIndexedDB();
  const document = {
    addEventListener() {},
    querySelector(selector) {
      if (selector === "[data-preparation-lines]") return container;
      if (selector === "[data-preparation-sync]" || selector === "[data-permanence-id]") return page;
      return null;
    },
    querySelectorAll() { return []; },
    createElement() {
      return {
        set textContent(value) {
          this.innerHTML = String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;").replaceAll('"', "&quot;");
        },
      };
    },
  };
  let uuid = 0;
  const context = {
    window: {}, document, console, indexedDB,
    crypto: { randomUUID: () => `uuid-${++uuid}` },
    navigator: { onLine: options.online ?? false },
    fetch: options.fetch,
  };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(
    __dirname, "..", "..", "static", "repanier", "js", "preparation-offline.js"
  ), "utf8"), context);
  return { api: context.window.repanierPreparationOffline, container, indexedDB, context };
}

function purchase(id, offer, quantity, status = "ordered") {
  return {
    purchase_id: id, offer_item_id: offer, group_id: 1, in_group: true,
    product: "Apples", producer: "Farm", customer: "Member", regime: "standard",
    quantity_ordered: quantity, quantity_prepared: "0.0000",
    quantity_received: "0.0000", preparation_status: status,
  };
}

test("group lines preserve ordered quantities and separate distinct products", () => {
  const { api } = load();
  const groups = api.aggregateGroupLines([
    purchase(1, 10, "2"), purchase(2, 10, "3"), purchase(3, 11, "4"),
  ]);
  assert.equal(groups.length, 2);
  assert.equal(groups[0].purchase_ids.join(","), "1,2");
  assert.equal(groups[0].purchase_quantities[1], "2");
  assert.equal(groups[0].purchase_quantities[2], "3");
  assert.equal(groups[0].quantity_ordered, "5");
});

test("offline group handover persists ordered dependent operations per purchase", async () => {
  const { api, indexedDB } = load();
  const snapshot = { permanence_id: 7, purchases: [
    purchase(1, 10, "2"), purchase(2, 10, "3", "prepared"),
  ] };
  snapshot.purchases[1].quantity_prepared = "3";
  await api.saveSnapshot(snapshot);
  await api.queueGroupHandover(api.aggregateGroupLines(snapshot.purchases)[0]);
  const events = [...indexedDB.stores.get("sync_queue").values()]
    .sort((a, b) => a.client_timestamp.localeCompare(b.client_timestamp));
  assert.equal(events.map((e) => e.operation).join(","), "prepare,receive,hand_to_group,receive,hand_to_group");
  assert.equal(new Set(events.map((e) => e.uuid)).size, 5);
  assert.ok(events.every((e, i) => !i || e.client_timestamp > events[i - 1].client_timestamp));
  assert.equal(events[1].depends_on, events[0].uuid);
  assert.equal(events[2].depends_on, events[1].uuid);
  assert.equal(events[4].depends_on, events[3].uuid);
  assert.equal((await api.readSnapshot(7)).purchases[0].preparation_status, "pending");
});

test("handover waits for receive and exposes conflict without sending dependent event", async () => {
  const requests = [];
  const { api, indexedDB } = load({
    online: true,
    fetch: async (_url, request) => {
      const event = JSON.parse(request.body);
      requests.push(event.operation);
      const status = event.operation === "receive" ? "conflict" : "applied";
      return { ok: true, text: async () => JSON.stringify({ result: { status, reason: "conflict" } }) };
    },
  });
  const snapshot = { permanence_id: 7, purchases: [purchase(1, 10, "2")] };
  await api.saveSnapshot(snapshot);
  await api.queueGroupHandover(api.aggregateGroupLines(snapshot.purchases)[0]);
  assert.equal(requests.join(","), "prepare,receive");
  const events = [...indexedDB.stores.get("sync_queue").values()];
  assert.equal(events.find((e) => e.operation === "hand_to_group").status, "pending");
  assert.equal((await api.readSnapshot(7)).purchases[0].preparation_status, "conflict");
});

test("successful handover remains handed to group until tacit validation", async () => {
  const requests = [];
  const { api } = load({
    online: true,
    fetch: async (_url, request) => {
      requests.push(JSON.parse(request.body).operation);
      return { ok: true, text: async () => JSON.stringify({ result: { status: "applied" } }) };
    },
  });

  const snapshot = { permanence_id: 7, purchases: [purchase(1, 10, "2")] };
  await api.saveSnapshot(snapshot);
  await api.queueGroupHandover(api.aggregateGroupLines(snapshot.purchases)[0]);
  assert.equal(requests.join(","), "prepare,receive,hand_to_group");
  const line = (await api.readSnapshot(7)).purchases[0];
  assert.equal(line.preparation_status, "handed_to_group");
  assert.equal(line.quantity_prepared, "2");
});

test("duplicate group handover does not enqueue a second sequence", async () => {
  const { api, indexedDB } = load();
  const snapshot = { permanence_id: 7, purchases: [purchase(1, 10, "2")] };
  await api.saveSnapshot(snapshot);
  const group = api.aggregateGroupLines(snapshot.purchases)[0];
  await api.queueGroupHandover(group);
  await assert.rejects(api.queueGroupHandover(group));
  assert.equal(indexedDB.stores.get("sync_queue").size, 3);
});

test("later individual events have timestamps after the group sequence", async () => {
  const { api, indexedDB } = load();
  const snapshot = { permanence_id: 7, purchases: [purchase(1, 10, "2")] };
  await api.saveSnapshot(snapshot);
  await api.queueGroupHandover(api.aggregateGroupLines(snapshot.purchases)[0]);
  await api.enqueueEvent("/sync", { operation: "validate", purchase_id: 2, quantity: "1" });
  const events = [...indexedDB.stores.get("sync_queue").values()];
  assert.ok(events.every((event, i) => !i || event.client_timestamp > events[i - 1].client_timestamp));
});

test("handover resumes in order after an interrupted request", async () => {
  const requests = [];
  let interrupted = true;
  const { api } = load({
    online: true,
    fetch: async (_url, request) => {
      const event = JSON.parse(request.body);
      requests.push(event.operation);
      if (event.operation === "receive" && interrupted) throw new Error("network");
      return { ok: true, text: async () => JSON.stringify({ result: { status: "applied" } }) };
    },
  });
  const snapshot = { permanence_id: 7, purchases: [purchase(1, 10, "2")] };
  await api.saveSnapshot(snapshot);
  await api.queueGroupHandover(api.aggregateGroupLines(snapshot.purchases)[0]);
  assert.equal((await api.readSnapshot(7)).purchases[0].preparation_status, "pending");
  assert.ok(!requests.includes("hand_to_group"));
  interrupted = false;
  await api.synchronizeQueue();
  assert.equal(requests.at(-1), "hand_to_group");
  assert.equal((await api.readSnapshot(7)).purchases[0].preparation_status, "handed_to_group");
});

test("render shows ordered quantity for standard, wrapped and group lines", () => {
  const { api, container } = load();
  api.renderPreparationLines({ purchases: [
    purchase(1, 10, "2"),
    { ...purchase(2, 20, "3"), in_group: false, regime: "wrapped" },
    { ...purchase(3, 30, "1"), in_group: false, regime: "basket" },
  ] });
  assert.match(container.innerHTML, /data-purchase-ids="1"/);
  assert.match(container.innerHTML, /value="3" data-preparation-quantity="2"/);
  assert.match(container.innerHTML, /data-basket-status="lost_in_transit"/);
  assert.doesNotMatch(container.innerHTML, /data-purchase-id="null"/);
});
