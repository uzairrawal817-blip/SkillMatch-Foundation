// The server cannot observe Escape without a request, and HTMX cannot synchronously dismiss the local dialog DOM.
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  const modalRoot = document.getElementById("modal-root");
  if (modalRoot?.hasChildNodes()) modalRoot.replaceChildren();
});

// The server cannot distinguish a backdrop or close-button click locally; HTMX would require a round-trip for this DOM-only dismissal.
document.addEventListener("click", (event) => {
  if (!(event.target instanceof Element)) return;
  const clickedBackdrop = event.target.matches("[data-modal-overlay]");
  const clickedCloseButton = event.target.closest("[data-modal-close]");
  if (!clickedBackdrop && !clickedCloseButton) return;
  document.getElementById("modal-root")?.replaceChildren();
});

// Clipboard access has no Python or HTMX equivalent.
async function copyEventLink(event) {
  if (!(event.target instanceof Element)) return;
  const button = event.target.closest("[data-copy-event-link]");
  if (!button) return;

  try {
    await navigator.clipboard.writeText(button.dataset.copyEventLink);
    button.textContent = "Link copied";
  } catch {
    button.textContent = "Copy unavailable";
  }
}

document.addEventListener("click", copyEventLink);
