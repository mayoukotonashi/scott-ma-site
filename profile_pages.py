"""Build the profile and research pages from src/pages and the publication records."""

from html import escape
from shutil import copyfile, copytree
from string import Template


PROFILE_PAGES = {
    "": ("Historian of science and political thought",
         "Scott Ma studies the history of science and political thought at the University of Zurich, "
         "with research on Confucian statecraft, agriculture, and the politics of culture in Japan."),
    "research/confucian-science": ("A Confucian Science",
                                  "Agricultural science and imperial statecraft in modern East Asia. Dissertation research by Scott Ma."),
    "research/japan": ("The politics of culture in Japan, 2020–2023",
                      "Research in Japan from 2020 to 2023 on the politics of culture in Japanese cities, museums, housing estates, and popular fiction."),
    "research/new-work": ("Science, Nature, and the Meiji Restoration",
                         "Work in progress on Confucian statecraft and scientific authority in modern Japan."),
    "publications": ("Publications", "Peer-reviewed articles by Scott Ma, with full-text readers and citations."),
    "cv": ("CV", "Scott Ma’s research fields, education, visiting appointments, and publications."),
    "privacy": ("Privacy", "Privacy and external links."),
}


def publication_fields(site):
    """Journal labels for selected articles and full citations for the printable CV."""
    fields = {}
    entries = []
    for paper in site.validated_publications():
        slug = paper["slug"]
        journal = paper.get("shortJournal", paper["journal"])
        fields["journal_" + slug] = f'{escape(journal)} · {paper["year"]}'

        authors = ", ".join(escape(name) for name in paper["authors"])
        title = escape(paper["title"].replace("“", "‘").replace("”", "’"))
        url = escape(site.origin_url("publications/" + slug))
        citation = site.citation({**paper, "journal": journal}, include_year=True)
        entries.append(f'<li>{authors}. “<a href="{url}">{title}</a>.” {citation}</li>')
    fields["print_entries"] = "\n".join(entries)
    return fields


def page_metadata(site, route, title, description):
    if route == "":
        head = site.structured_data(**{"@type": "WebSite", "name": site.SITE_NAME,
                                       "alternateName": site.SITE["name"], "url": site.origin_url("")})
        verification = site.SITE.get("googleSiteVerification")
        if verification:
            head += f'\n  <meta name="google-site-verification" content="{escape(verification)}">'
        return head
    if route == "research/confucian-science":
        return site.structured_data(**{
            "@type": "WebPage", "name": title, "url": site.origin_url(route), "description": description,
            "author": {"@type": "Person", "name": site.SITE["name"]},
            "mainEntity": {"@type": "CreativeWork", "name": site.SITE["dissertationTitle"]},
        })
    if route == "publications":
        return f'<script src="{site.local_url(route)}assets/publications.js" defer></script>'
    return ""


def write_profile_pages(site, publication_listing):
    """Write the site-wide landing pages using the same records as the article readers."""
    layout = Template((site.SOURCE / "templates/profile.html").read_text(encoding="utf-8"))
    dissertation = site.markdown("research").splitlines()
    fields = publication_fields(site)
    fields.update(
        email=escape(site.SITE["email"]),
        dissertation_title=escape(site.SITE["researchTitle"]),
        dissertation_subtitle=escape(site.SITE["researchSubtitle"]),
        dissertation_argument="\n".join(dissertation[:2]),
        dissertation_settings="\n".join(dissertation[2:4]),
        dissertation_sources="\n".join(dissertation[4:]),
        publication_listing=publication_listing,
    )
    for route, (title, description) in PROFILE_PAGES.items():
        root = site.local_url(route)
        slug = route.rsplit("/", 1)[-1] or "home"
        body = Template((site.SOURCE / "pages" / (slug + ".html")).read_text(encoding="utf-8"))
        links = []
        for label, href in (("Research", "#research"), ("Publications", "publications/"), ("CV", "cv/")):
            current = ' aria-current="page"' if href == route + "/" else ""
            links.append(f'<a href="{root}{href}"{current}>{label}</a>')
        page_title = f'{title} | {site.SITE["name"]}'
        document = layout.substitute(
            name=escape(site.SITE["name"]), root=root, navigation="".join(links), email=fields["email"],
            title=escape(page_title), description=escape(description), canonical=escape(site.origin_url(route)),
            favicon_head=site.favicon_links(route), social_head=site.social_metadata(route, page_title, description),
            extra_head=page_metadata(site, route, title, description), content=body.substitute(fields),
        )
        path = site.OUTPUT / route / "index.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(document, encoding="utf-8")

    for asset in ("identity.css", "woman-with-cat.webp", "flora-japonica-hydrangea.webp"):
        copyfile(site.asset_path(asset), site.OUTPUT / "assets" / asset)
    copytree(site.ASSETS / "type", site.OUTPUT / "assets/type", dirs_exist_ok=True)
    copyfile(site.SOURCE / "Scott-Ma-CV.pdf", site.OUTPUT / "cv/Scott-Ma-CV.pdf")
