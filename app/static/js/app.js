// Warehouse Order Management System - Frontend JS

const API_BASE = "/api/v1";
let productsCache = [];
let warehousesCache = [];

function switchTab(tabId) {
  document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active"));
  document.querySelectorAll(".tab-pane").forEach(pane => pane.classList.remove("active"));

  const targetPane = document.getElementById(`tab-${tabId}`);
  if (targetPane) targetPane.classList.add("active");

  const matchingBtn = Array.from(document.querySelectorAll(".tab-btn")).find(
    btn => btn.getAttribute("onclick") && btn.getAttribute("onclick").includes(tabId)
  );
  if (matchingBtn) matchingBtn.classList.add("active");

  if (tabId === "warehouses") loadWarehouses();
  if (tabId === "inventory") loadInventory();
  if (tabId === "orders") loadOrders();
}

function showAlert(message, type = "success") {
  const alertBox = document.getElementById("global-alert");
  alertBox.className = `alert alert-${type}`;
  alertBox.textContent = message;
  alertBox.style.display = "block";
  setTimeout(() => { alertBox.style.display = "none"; }, 5000);
}

// 1. Health check
async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    const data = await res.json();
    const healthBadge = document.getElementById("system-health");
    const healthText = document.getElementById("health-text");

    if (data.status === "HEALTHY") {
      healthText.textContent = `Online (${data.active_warehouses_count}/${data.total_warehouses_count} Active Nodes)`;
      healthBadge.style.color = "var(--success)";
      healthBadge.style.borderColor = "var(--success)";
    } else {
      healthText.textContent = `Degraded (${data.active_warehouses_count} Active Nodes)`;
      healthBadge.style.color = "var(--danger)";
      healthBadge.style.borderColor = "var(--danger)";
    }
  } catch (err) {
    document.getElementById("health-text").textContent = "API Unreachable";
  }
}

// 2. Load Warehouses
async function loadWarehouses() {
  const tbody = document.getElementById("warehouses-table-body");
  const statsDiv = document.getElementById("wh-stats");
  tbody.innerHTML = '<tr><td colspan="7" class="loading">Loading warehouses...</td></tr>';

  try {
    const res = await fetch(`${API_BASE}/warehouses`);
    warehousesCache = await res.json();

    if (warehousesCache.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align: center;">No warehouses found.</td></tr>';
      return;
    }

    let totalCap = 0;
    let totalLoad = 0;
    tbody.innerHTML = warehousesCache.map(wh => {
      totalCap += wh.capacity_limit;
      totalLoad += wh.current_daily_load;
      const statusClass = wh.status === "ACTIVE" ? "badge-active" : (wh.status === "OFFLINE" ? "badge-offline" : "badge-pending");
      const nextStatus = wh.status === "ACTIVE" ? "OFFLINE" : "ACTIVE";

      return `
        <tr>
          <td><strong>${wh.code}</strong></td>
          <td>${wh.name}</td>
          <td><span class="badge ${statusClass}">${wh.status}</span></td>
          <td>(${wh.latitude.toFixed(2)}, ${wh.longitude.toFixed(2)})</td>
          <td>${wh.current_daily_load} / ${wh.capacity_limit}</td>
          <td>$${wh.shipping_base_cost.toFixed(2)} + $${wh.shipping_cost_per_km}/km</td>
          <td>
            <button class="btn btn-sm ${wh.status === 'ACTIVE' ? 'btn-danger' : 'btn-success'}" 
              onclick="toggleWarehouseStatus('${wh.id}', '${nextStatus}')">
              Set ${nextStatus}
            </button>
          </td>
        </tr>
      `;
    }).join("");

    statsDiv.innerHTML = `
      <div class="card">
        <h3>Total Warehouses</h3>
        <div class="stat-value">${warehousesCache.length}</div>
        <div class="stat-desc">Active Fulfillment Nodes</div>
      </div>
      <div class="card">
        <h3>Daily Throughput Load</h3>
        <div class="stat-value">${totalLoad} / ${totalCap}</div>
        <div class="stat-desc">Allocated Units</div>
      </div>
    `;

    populateWarehouseDropdowns();
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" class="alert-error">Failed to load warehouses: ${err.message}</td></tr>`;
  }
}

async function toggleWarehouseStatus(warehouseId, nextStatus) {
  try {
    const res = await fetch(`${API_BASE}/warehouses/${warehouseId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: nextStatus })
    });
    if (!res.ok) throw new Error("Failed to update warehouse status");
    showAlert(`Warehouse status updated to ${nextStatus}`, "success");
    loadWarehouses();
    checkHealth();
  } catch (err) {
    showAlert(err.message, "error");
  }
}

// 3. Load Inventory
async function loadInventory() {
  const tbody = document.getElementById("inventory-table-body");
  tbody.innerHTML = '<tr><td colspan="7" class="loading">Loading inventory...</td></tr>';

  try {
    const res = await fetch(`${API_BASE}/inventory`);
    const items = await res.json();

    if (items.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align: center;">No inventory records available.</td></tr>';
      return;
    }

    tbody.innerHTML = items.map(inv => `
      <tr>
        <td><strong>${inv.warehouse_code}</strong></td>
        <td><code>${inv.product_sku}</code></td>
        <td>${inv.product_name}</td>
        <td><strong>${inv.quantity_on_hand}</strong></td>
        <td><span style="color: var(--warning);">${inv.quantity_reserved}</span></td>
        <td><strong style="color: var(--success);">${inv.quantity_available}</strong></td>
        <td>${new Date(inv.updated_at).toLocaleTimeString()}</td>
      </tr>
    `).join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" class="alert-error">Failed to load inventory: ${err.message}</td></tr>`;
  }
}

// 4. Load Orders
async function loadOrders() {
  const tbody = document.getElementById("orders-table-body");
  tbody.innerHTML = '<tr><td colspan="8" class="loading">Loading orders...</td></tr>';

  try {
    const res = await fetch(`${API_BASE}/orders?size=20`);
    const data = await res.json();
    const orders = data.items || [];

    if (orders.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align: center;">No orders placed yet.</td></tr>';
      return;
    }

    tbody.innerHTML = orders.map(ord => {
      const statusClass = `badge-${ord.status.toLowerCase()}`;
      const splits = (ord.allocations || []).map(a => 
        `<div><strong>${a.warehouse_code || 'WH'}</strong>: ${a.allocated_quantity} units ($${(a.estimated_shipping_cost + a.estimated_handling_cost).toFixed(2)})</div>`
      ).join("") || `<span style="color: var(--text-secondary);">${ord.failure_reason || 'None'}</span>`;

      let actionButtons = '';
      if (ord.status === "RESERVED") {
        actionButtons = `
          <button class="btn btn-sm btn-success" onclick="fulfillOrder('${ord.id}')">Ship</button>
          <button class="btn btn-sm btn-danger" onclick="cancelOrder('${ord.id}')">Cancel</button>
        `;
      } else if (ord.status === "PENDING") {
        actionButtons = `<button class="btn btn-sm btn-danger" onclick="cancelOrder('${ord.id}')">Cancel</button>`;
      }

      return `
        <tr>
          <td><small><code>${ord.id.substring(0, 8)}...</code></small></td>
          <td>${ord.customer_id}</td>
          <td><span class="badge ${statusClass}">${ord.status}</span></td>
          <td>$${ord.total_item_price.toFixed(2)}</td>
          <td><strong>$${ord.total_fulfillment_cost.toFixed(2)}</strong></td>
          <td><code>${ord.routing_strategy_used || 'OR_TOOLS_LP'}</code></td>
          <td>${splits}</td>
          <td>${actionButtons}</td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" class="alert-error">Failed to load orders: ${err.message}</td></tr>`;
  }
}

async function fulfillOrder(orderId) {
  try {
    const res = await fetch(`${API_BASE}/orders/${orderId}/fulfill`, { method: "POST" });
    if (!res.ok) throw new Error("Fulfillment failed");
    showAlert("Order fulfilled and inventory deducted!", "success");
    loadOrders();
    loadInventory();
  } catch (err) {
    showAlert(err.message, "error");
  }
}

async function cancelOrder(orderId) {
  try {
    const res = await fetch(`${API_BASE}/orders/${orderId}/cancel`, { method: "POST" });
    if (!res.ok) throw new Error("Cancellation failed");
    showAlert("Order cancelled and reservation safely released!", "success");
    loadOrders();
    loadInventory();
  } catch (err) {
    showAlert(err.message, "error");
  }
}

// 5. Create Order
async function handleCreateOrder(e) {
  e.preventDefault();
  const customerId = document.getElementById("order-customer").value;
  const lat = parseFloat(document.getElementById("order-lat").value);
  const lon = parseFloat(document.getElementById("order-lon").value);
  const strategy = document.getElementById("order-strategy").value;
  const productId = document.getElementById("order-product-select").value;
  const quantity = parseInt(document.getElementById("order-quantity").value);

  const idempotencyKey = "ord_" + Math.random().toString(36).substring(2, 12) + Date.now().toString(36);

  try {
    const res = await fetch(`${API_BASE}/orders`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Idempotency-Key": idempotencyKey
      },
      body: JSON.stringify({
        customer_id: customerId,
        destination_lat: lat,
        destination_lon: lon,
        routing_strategy: strategy,
        items: [{ product_id: productId, requested_quantity: quantity }]
      })
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || "Order creation failed");
    }

    showAlert(`Order ${data.id.substring(0, 8)} created & routed! Cost: $${data.total_fulfillment_cost.toFixed(2)}`, "success");
    switchTab("orders");
  } catch (err) {
    showAlert(err.message, "error");
  }
}

// 6. Adjust Stock
async function handleAdjustStock(e) {
  e.preventDefault();
  const whId = document.getElementById("adjust-warehouse-select").value;
  const prodId = document.getElementById("adjust-product-select").value;
  const delta = parseInt(document.getElementById("adjust-delta").value);
  const reason = document.getElementById("adjust-reason").value;

  try {
    const res = await fetch(`${API_BASE}/inventory/adjustments`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        warehouse_id: whId,
        product_id: prodId,
        quantity_delta: delta,
        reason: reason
      })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Stock adjustment failed");

    showAlert(`Stock updated! New On-Hand: ${data.quantity_on_hand}`, "success");
    switchTab("inventory");
  } catch (err) {
    showAlert(err.message, "error");
  }
}

// Populate Dropdowns
async function loadProducts() {
  try {
    const res = await fetch(`${API_BASE}/products?size=100`);
    const data = await res.json();
    productsCache = data.items || [];

    const orderProdSelect = document.getElementById("order-product-select");
    const adjProdSelect = document.getElementById("adjust-product-select");

    const optionsHtml = productsCache.map(p => 
      `<option value="${p.id}">${p.sku} - ${p.name} ($${p.price.toFixed(2)})</option>`
    ).join("");

    if (orderProdSelect) orderProdSelect.innerHTML = optionsHtml;
    if (adjProdSelect) adjProdSelect.innerHTML = optionsHtml;
  } catch (err) {
    console.error("Failed to load products for dropdowns:", err);
  }
}

function populateWarehouseDropdowns() {
  const adjWhSelect = document.getElementById("adjust-warehouse-select");
  if (!adjWhSelect) return;
  adjWhSelect.innerHTML = warehousesCache.map(w => 
    `<option value="${w.id}">${w.code} - ${w.name}</option>`
  ).join("");
}

// Init
window.addEventListener("DOMContentLoaded", () => {
  checkHealth();
  loadWarehouses();
  loadProducts();
  setInterval(checkHealth, 15000);
});
