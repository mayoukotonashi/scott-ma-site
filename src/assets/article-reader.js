function initializeArticleReader(root = document) {
  const article = root.querySelector(".article-page");
  if (!article) return () => {};

  const controller = new AbortController();
  initializeArticleNotes(article, controller.signal);
  initializeArticleEdges(article, controller.signal);
  return () => controller.abort();
}

function initializeArticleNotes(article, signal) {
  const notes = article.querySelectorAll(".note-ref a");
  if (!notes.length) return;

  const popover = document.createElement("div");
  popover.className = "note-popover";
  popover.id = "article-note-popover";
  popover.hidden = true;
  popover.tabIndex = -1;
  popover.setAttribute("role", "dialog");
  popover.setAttribute("aria-labelledby", "article-note-label");
  popover.setAttribute("aria-describedby", "article-note-content");
  popover.innerHTML = `
    <div class="note-popover-header">
      <strong id="article-note-label"></strong>
      <button type="button" class="note-popover-close" aria-label="Close note">×</button>
    </div>
    <div id="article-note-content"></div>`;
  article.append(popover);

  for (const note of notes) {
    note.setAttribute("aria-haspopup", "dialog");
    note.setAttribute("aria-controls", popover.id);
    note.setAttribute("aria-expanded", "false");
  }

  const label = popover.querySelector("#article-note-label");
  const content = popover.querySelector("#article-note-content");
  let trigger;

  function closeNote(restoreFocus = false) {
    if (!trigger) return;
    trigger.setAttribute("aria-expanded", "false");
    if (restoreFocus) trigger.focus({preventScroll: true});
    trigger = undefined;
    popover.hidden = true;
  }

  function positionNote() {
    if (!trigger) return;
    const anchor = trigger.getBoundingClientRect();
    const viewportWidth = document.documentElement.clientWidth;
    const viewportHeight = window.innerHeight;
    if (anchor.bottom < 0 || anchor.top > viewportHeight) {
      closeNote();
      return;
    }

    const margin = 12;
    const top = anchor.bottom + margin + popover.offsetHeight > viewportHeight - margin
      ? anchor.top - popover.offsetHeight - margin
      : anchor.bottom + margin;
    const left = Math.min(anchor.left, viewportWidth - popover.offsetWidth - margin);
    popover.style.top = `${Math.max(margin, top)}px`;
    popover.style.left = `${Math.max(margin, left)}px`;
  }

  article.addEventListener("click", (event) => {
    const note = event.target.closest(".note-ref a");
    if (!note || event.defaultPrevented || event.button !== 0
        || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    const destination = article.querySelector(note.hash + " .note-text");
    if (!destination) return;
    event.preventDefault();

    if (note === trigger) {
      closeNote(true);
      return;
    }

    closeNote();
    trigger = note;
    trigger.setAttribute("aria-expanded", "true");
    label.textContent = trigger.getAttribute("aria-label");
    content.replaceChildren(destination.cloneNode(true));
    popover.hidden = false;
    positionNote();
    popover.focus({preventScroll: true});
  }, {signal});

  popover.querySelector(".note-popover-close").addEventListener("click", () => closeNote(true), {signal});
  document.addEventListener("pointerdown", (event) => {
    if (!trigger || popover.contains(event.target) || trigger.contains(event.target)) return;
    closeNote();
  }, {signal});
  document.addEventListener("keydown", (event) => {
    if (!trigger || event.key !== "Escape") return;
    event.preventDefault();
    closeNote(true);
  }, {signal});
  window.addEventListener("scroll", positionNote, {passive: true, signal});
  window.addEventListener("resize", positionNote, {signal});
}

function initializeArticleEdges(article, signal) {
  const nav = article.querySelector(".article-edges");
  if (!nav) return;

  const layout = article.querySelector(".reader-layout");
  const text = article.querySelector(".reader-body");
  const previous = nav.querySelector(".article-edge-prev");
  const next = nav.querySelector(".article-edge-next");
  const desktop = window.matchMedia("(min-width: 801px) and (hover: hover) and (pointer: fine)");
  let pointer;
  let pendingEdge;
  let revealTimer;

  function cueEdge(gutter, outerEdge) {
    nav.dataset.gutter = gutter;
    if (outerEdge === pendingEdge) return;
    window.clearTimeout(revealTimer);
    pendingEdge = outerEdge;
    delete nav.dataset.ready;
    if (outerEdge) {
      revealTimer = window.setTimeout(() => {
        nav.dataset.ready = outerEdge;
      }, 170);
    }
  }

  function updateEdges() {
    if (!pointer || !desktop.matches) {
      cueEdge("", "");
      return;
    }
    const {x, y} = pointer;
    const bounds = layout.getBoundingClientRect();
    const hovered = document.elementFromPoint(x, y);
    const shortcut = hovered?.closest(".article-edge");
    if (shortcut && shortcut.rel === nav.dataset.ready) return;
    if (y < bounds.top || y >= bounds.bottom || hovered?.closest(
      "a, button, input, select, textarea, .note-popover",
    )) {
      cueEdge("", "");
      return;
    }

    const articleBounds = text.getBoundingClientRect();
    const width = document.documentElement.clientWidth;
    if (previous && x < articleBounds.left) {
      nav.style.setProperty("--gutter-width", `${articleBounds.left}px`);
      cueEdge("prev", x <= 48 ? "prev" : "");
    } else if (next && x >= articleBounds.right) {
      nav.style.setProperty("--gutter-width", `${width - articleBounds.right}px`);
      cueEdge("next", x >= width - 48 ? "next" : "");
    } else {
      cueEdge("", "");
    }
  }

  function resetEdges() {
    pointer = undefined;
    cueEdge("", "");
  }

  document.addEventListener("pointermove", (event) => {
    if (event.pointerType !== "mouse") return;
    pointer = {x: event.clientX, y: event.clientY};
    updateEdges();
  }, {passive: true, signal});
  document.addEventListener("pointerout", (event) => {
    if (!event.relatedTarget) resetEdges();
  }, {passive: true, signal});
  window.addEventListener("blur", resetEdges, {signal});
  window.addEventListener("resize", updateEdges, {signal});
  window.addEventListener("scroll", updateEdges, {passive: true, signal});
  signal.addEventListener("abort", resetEdges, {once: true});
}

initializeArticleReader();
