function initializeArticleReader(root = document) {
  const article = root.querySelector(".article-page");
  if (!article) return () => {};

  const controller = new AbortController();
  initializeArticleNotes(article, controller.signal);
  initializeArticleEdges(article, controller.signal);
  return () => controller.abort();
}

function initializeArticleNotes(article, signal) {
  const selector = ".note-ref a, a[data-reader-note]";
  const notes = article.querySelectorAll(selector);
  if (!notes.length) return;

  const text = article.querySelector(".reader-body");
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
    const sideMargin = 68;
    const readingColumn = text.getBoundingClientRect();
    const rightRoom = viewportWidth - readingColumn.right - margin - sideMargin;
    const leftRoom = readingColumn.left - margin - sideMargin;
    const sidebar = window.matchMedia("(min-width: 801px)").matches;
    const rightSide = rightRoom >= 250;
    const room = rightSide ? rightRoom : leftRoom;
    if (sidebar && room >= 250) {
      const width = Math.min(room, 350);
      const left = rightSide ? readingColumn.right + margin : readingColumn.left - margin - width;
      popover.style.width = `${width}px`;
      popover.style.left = `${left}px`;
      popover.style.top = `${Math.max(margin, Math.min(anchor.top, viewportHeight - popover.offsetHeight - margin))}px`;
      return;
    }

    popover.style.width = "";
    const top = anchor.bottom + margin + popover.offsetHeight > viewportHeight - margin
      ? anchor.top - popover.offsetHeight - margin
      : anchor.bottom + margin;
    const left = Math.min(anchor.left, viewportWidth - popover.offsetWidth - margin);
    popover.style.top = `${Math.max(margin, top)}px`;
    popover.style.left = `${Math.max(margin, left)}px`;
  }

  article.addEventListener("click", (event) => {
    const note = event.target.closest(selector);
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
    label.textContent = trigger.dataset.readerNote || trigger.getAttribute("aria-label") || "Note";
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
  let frame = 0;

  function updateEdges() {
    frame = 0;
    const bounds = layout.getBoundingClientRect();
    const center = window.innerHeight / 2;
    const visible = desktop.matches && bounds.top <= center && bounds.bottom >= center;
    nav.toggleAttribute("data-visible", visible);
    if (!visible || !pointer) {
      delete nav.dataset.gutter;
      return;
    }
    const {x, y} = pointer;
    const hovered = document.elementFromPoint(x, y);
    const shortcut = hovered?.closest(".article-edge");
    if (!shortcut && (y < bounds.top || y >= bounds.bottom || hovered?.closest(
      "a, button, input, select, textarea, .note-popover",
    ))) {
      delete nav.dataset.gutter;
      return;
    }

    const articleBounds = text.getBoundingClientRect();
    const width = document.documentElement.clientWidth;
    if (previous && (shortcut?.rel === "prev" || x < articleBounds.left)) {
      nav.style.setProperty("--gutter-width", `${articleBounds.left}px`);
      nav.dataset.gutter = "prev";
    } else if (next && (shortcut?.rel === "next" || x >= articleBounds.right)) {
      nav.style.setProperty("--gutter-width", `${width - articleBounds.right}px`);
      nav.dataset.gutter = "next";
    } else {
      delete nav.dataset.gutter;
    }
  }

  function scheduleUpdate() {
    if (!frame) frame = window.requestAnimationFrame(updateEdges);
  }

  function resetEdges() {
    pointer = undefined;
    delete nav.dataset.gutter;
  }

  document.addEventListener("pointermove", (event) => {
    if (event.pointerType !== "mouse") return;
    pointer = {x: event.clientX, y: event.clientY};
    scheduleUpdate();
  }, {passive: true, signal});
  document.addEventListener("pointerout", (event) => {
    if (!event.relatedTarget) resetEdges();
  }, {passive: true, signal});
  window.addEventListener("blur", resetEdges, {signal});
  window.addEventListener("resize", scheduleUpdate, {signal});
  window.addEventListener("scroll", scheduleUpdate, {passive: true, signal});
  signal.addEventListener("abort", () => window.cancelAnimationFrame(frame), {once: true});
  updateEdges();
}

initializeArticleReader();
