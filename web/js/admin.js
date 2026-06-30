(function () {
  "use strict";

  const tokenInput = document.getElementById("adminToken");
  const totalCount = document.getElementById("totalCount");
  const tableBody = document.getElementById("tableBody");
  const refreshButton = document.getElementById("refreshButton");
  const deleteSelectedButton = document.getElementById("deleteSelectedButton");
  const resetButton = document.getElementById("resetButton");
  const selectAll = document.getElementById("selectAll");

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value || "";
    return div.innerHTML;
  }

  async function loadSubmissions() {
    try {
      const res = await fetch("/api/submissions");
      const data = await res.json();
      if (!data.ok) return;

      totalCount.textContent = data.count;
      tableBody.innerHTML = "";

      data.submissions.slice().reverse().forEach(function (submission) {
        const row = document.createElement("tr");
        row.innerHTML =
          '<td><input class="entry-check" type="checkbox" value="' + escapeHtml(submission.id) + '"></td>' +
          '<td><img src="/images/' + encodeURIComponent(submission.image) + '" alt=""></td>' +
          "<td>" + escapeHtml(submission.name) + "</td>" +
          "<td>" + escapeHtml(submission.message) + "</td>" +
          "<td>" + escapeHtml(submission.timestamp) + "</td>";
        tableBody.appendChild(row);
      });
      selectAll.checked = false;
    } catch (_) {
      totalCount.textContent = "ERR";
    }
  }

  async function resetAll() {
    const token = tokenInput.value.trim();
    if (!token) {
      alert("Masukkan admin token terlebih dahulu.");
      return;
    }

    if (!confirm("Hapus semua submission dan foto?")) return;

    try {
      const res = await fetch("/api/admin/reset", {
        method: "POST",
        headers: { "X-Admin-Token": token },
      });
      const data = await res.json();
      if (!data.ok) {
        alert(data.error || "Reset gagal.");
        return;
      }
      await loadSubmissions();
    } catch (_) {
      alert("Koneksi gagal.");
    }
  }

  function selectedIds() {
    return Array.from(document.querySelectorAll(".entry-check:checked")).map(function (input) {
      return input.value;
    });
  }

  async function deleteSelected() {
    const token = tokenInput.value.trim();
    if (!token) {
      alert("Masukkan admin token terlebih dahulu.");
      return;
    }

    const ids = selectedIds();
    if (!ids.length) {
      alert("Pilih minimal satu entry.");
      return;
    }

    if (!confirm("Hapus " + ids.length + " entry terpilih beserta fotonya?")) return;

    try {
      const res = await fetch("/api/admin/delete", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Admin-Token": token,
        },
        body: JSON.stringify({ ids: ids }),
      });
      const data = await res.json();
      if (!data.ok) {
        alert(data.error || "Delete gagal.");
        return;
      }
      await loadSubmissions();
    } catch (_) {
      alert("Koneksi gagal.");
    }
  }

  refreshButton.addEventListener("click", loadSubmissions);
  deleteSelectedButton.addEventListener("click", deleteSelected);
  resetButton.addEventListener("click", resetAll);
  selectAll.addEventListener("change", function () {
    document.querySelectorAll(".entry-check").forEach(function (input) {
      input.checked = selectAll.checked;
    });
  });

  loadSubmissions();
  setInterval(loadSubmissions, 10000);
})();
