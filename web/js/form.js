(function () {
  "use strict";

  const form = document.getElementById("submissionForm");
  const nameInput = document.getElementById("name");
  const messageInput = document.getElementById("message");
  const charCount = document.getElementById("charCount");
  const photoPreview = document.getElementById("photoPreview");
  const cameraButton = document.getElementById("cameraButton");
  const galleryButton = document.getElementById("galleryButton");
  const cameraInput = document.getElementById("cameraInput");
  const galleryInput = document.getElementById("galleryInput");
  const submitButton = document.getElementById("submitButton");
  const alertBox = document.getElementById("alert");
  const loading = document.getElementById("loading");
  const counter = document.getElementById("counter");

  let selectedPhoto = null;

  function showError(message) {
    alertBox.textContent = message;
    alertBox.classList.add("visible");
  }

  function clearError() {
    alertBox.textContent = "";
    alertBox.classList.remove("visible");
  }

  async function refreshStats() {
    try {
      const res = await fetch("/api/stats");
      const data = await res.json();
      if (data.ok) counter.textContent = data.count;
    } catch (_) {
      counter.textContent = "-";
    }
  }

  function previewPhoto(file) {
    if (!file || !file.type.startsWith("image/")) return;
    selectedPhoto = file;

    const reader = new FileReader();
    reader.onload = function (event) {
      photoPreview.innerHTML = '<img alt="Preview foto" src="' + event.target.result + '">';
      photoPreview.classList.add("has-photo");
    };
    reader.readAsDataURL(file);
  }

  function bindInput(input) {
    input.addEventListener("change", function () {
      if (input.files && input.files[0]) previewPhoto(input.files[0]);
    });
  }

  bindInput(cameraInput);
  bindInput(galleryInput);

  photoPreview.addEventListener("click", function () {
    cameraInput.click();
  });

  cameraButton.addEventListener("click", function () {
    cameraInput.click();
  });

  galleryButton.addEventListener("click", function () {
    galleryInput.click();
  });

  messageInput.addEventListener("input", function () {
    charCount.textContent = messageInput.value.length;
  });

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    clearError();

    const name = nameInput.value.trim();
    const message = messageInput.value.trim();

    if (!name) {
      showError("Nama pengirim wajib diisi.");
      nameInput.focus();
      return;
    }

    if (!message) {
      showError("Pesan ucapan wajib diisi.");
      messageInput.focus();
      return;
    }

    if (!selectedPhoto) {
      showError("Foto wajib diunggah atau diambil dari kamera.");
      return;
    }

    const payload = new FormData();
    payload.append("name", name);
    payload.append("message", message);
    payload.append("photo", selectedPhoto, selectedPhoto.name || "photo.jpg");
    payload.append("device_info", navigator.userAgent.slice(0, 200));

    loading.classList.add("visible");
    submitButton.disabled = true;

    try {
      const res = await fetch("/api/submit", { method: "POST", body: payload });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        showError(data.error || "Gagal mengirim ucapan. Coba lagi.");
        return;
      }
      window.location.href = "/thank-you";
    } catch (_) {
      showError("Koneksi gagal. Pastikan ponsel terhubung ke jaringan venue.");
    } finally {
      loading.classList.remove("visible");
      submitButton.disabled = false;
    }
  });

  refreshStats();
  setInterval(refreshStats, 15000);
})();
