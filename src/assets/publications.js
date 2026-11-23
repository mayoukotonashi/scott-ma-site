function initializePublicationFilters(container) {
  container.querySelectorAll("[data-publications]").forEach((section) => {
    const form = section.querySelector("form");
    const search = form.querySelector("input");
    const year = form.querySelector("select");
    const status = section.querySelector("[role=status]");
    const items = [...section.querySelectorAll("[data-year]")];

    function filter() {
      const query = search.value.toLocaleLowerCase().trim();
      let visible = 0;
      for (const item of items) {
        const matchesQuery = item.textContent.toLocaleLowerCase().includes(query);
        const matchesYear = !year.value || item.dataset.year === year.value;
        item.hidden = !(matchesQuery && matchesYear);
        visible += Number(!item.hidden);
      }
      const noun = visible === 1 ? "publication" : "publications";
      status.textContent = visible ? `${visible} ${noun}` : "No publications match.";
    }

    form.hidden = false;
    form.addEventListener("input", filter);
    form.addEventListener("submit", (event) => event.preventDefault());
    filter();
  });
}

initializePublicationFilters(document);
