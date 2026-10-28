const input = document.querySelector("#images");
const preview = document.querySelector("#preview");

if (input) input.addEventListener("change", () => {
  preview.innerHTML = "";
  [...input.files].forEach(file => {
    const col = document.createElement("div");
    col.className = "col-6 col-md-3 upload-preview-item";
    const img = document.createElement("img");
    img.className = "img-fluid rounded upload-preview-image";
    img.src = URL.createObjectURL(file);
    img.alt = file.name;
    const name = Object.assign(document.createElement("small"), {textContent: file.name, className: "upload-preview-name"});
    const remove = Object.assign(document.createElement("button"), {
      type: "button",
      className: "upload-remove-button",
      textContent: "Remove image",
      title: `Remove ${file.name}`
    });
    remove.setAttribute("aria-label", `Remove ${file.name}`);
    remove.addEventListener("click", () => {
      const remaining = [...input.files].filter(candidate => candidate !== file);
      const transfer = new DataTransfer();
      remaining.forEach(candidate => transfer.items.add(candidate));
      input.files = transfer.files;
      input.dispatchEvent(new Event("change"));
    });
    col.append(img, name, remove);
    preview.append(col);
  });
});

const form = document.querySelector("#analysis-form");
if (form) form.addEventListener("submit", async event => {
  event.preventDefault();
  const status = document.querySelector("#upload-status");
  const uploadButton = document.querySelector("#upload-button");
  const setStatus = (message, type) => {
    status.textContent = message;
    status.className = `alert alert-${type} mt-3 mb-0`;
  };
  if (!input.files.length) {
    setStatus("Please select at least one crack image before uploading.", "warning");
    return;
  }
  setStatus("Uploading and detecting cracks. Please wait...", "info");
  uploadButton.disabled = true;
  try {
    const response = await fetch("/api/analyze", {method: "POST", body: new FormData(form)});
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || "Image processing failed.");
    window.location = `/analysis/${data.analysis_id}`;
  } catch (error) {
    uploadButton.disabled = false;
    setStatus(error.message, "danger");
  }
});

const lightbox = document.querySelector("#image-lightbox");
const lightboxImage = document.querySelector("#image-lightbox-image");
const lightboxCaption = document.querySelector("#image-lightbox-caption");
const lightboxZoom = document.querySelector("#image-lightbox-zoom");
let imageZoom = 1;
const setImageZoom = value => {
  imageZoom = Math.min(4, Math.max(0.5, value));
  if (lightboxImage) {
    lightboxImage.style.transform = "none";
    lightboxImage.style.maxWidth = imageZoom > 1 ? "none" : "100%";
    lightboxImage.style.maxHeight = imageZoom > 1 ? "none" : "82vh";
    lightboxImage.style.width = imageZoom > 1 ? `${imageZoom * 100}%` : "auto";
  }
  if (lightboxZoom) lightboxZoom.textContent = `${Math.round(imageZoom * 100)}%`;
};
const closeLightbox = () => {
  if (!lightbox) return;
  lightbox.hidden = true;
  lightboxImage.removeAttribute("src");
  setImageZoom(1);
};

document.addEventListener("click", event => {
  const zoomButton = event.target.closest("[data-image-zoom]");
  if (zoomButton && lightbox) {
    const action = zoomButton.dataset.imageZoom;
    setImageZoom(action === "in" ? imageZoom + 0.25 : action === "out" ? imageZoom - 0.25 : 1);
    event.stopPropagation();
    return;
  }
  const trigger = event.target.closest("[data-image-preview]");
  if (trigger && lightbox) {
    lightboxImage.src = trigger.dataset.imagePreview;
    lightboxImage.alt = trigger.dataset.imageAlt || "Crack analysis image";
    lightboxCaption.textContent = trigger.dataset.imageCaption || "";
    setImageZoom(1);
    lightbox.hidden = false;
  } else if (event.target === lightbox || event.target.closest(".image-lightbox-close")) {
    closeLightbox();
  }
});

if (lightbox) lightbox.addEventListener("wheel", event => {
  if (lightbox.hidden) return;
  event.preventDefault();
  setImageZoom(imageZoom + (event.deltaY < 0 ? 0.15 : -0.15));
}, {passive: false});

document.addEventListener("keydown", event => {
  if (event.key === "Escape") closeLightbox();
  if (!lightbox || lightbox.hidden) return;
  if (event.key === "+" || event.key === "=") setImageZoom(imageZoom + 0.25);
  if (event.key === "-" || event.key === "_") setImageZoom(imageZoom - 0.25);
  if (event.key === "0") setImageZoom(1);
});
