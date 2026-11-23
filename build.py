"""Build the portable static website from the text and bibliography in src/."""

import argparse
from html import escape
import json
from pathlib import Path
import re
import shutil
from string import Template
from urllib.parse import urlsplit


PROJECT = Path(__file__).resolve().parent
SOURCE = PROJECT / "src"
OUTPUT = PROJECT / "dist"
SITE = json.loads((SOURCE / "site.json").read_text(encoding="utf-8"))
LAYOUT = Template((SOURCE / "templates/base.html").read_text(encoding="utf-8"))
PUBLICATIONS = json.loads((SOURCE / "publications.json").read_text(encoding="utf-8"))
NAVIGATION = {"": "Home", "research": "Research", "publications": "Publications", "cv": "CV"}


def inline(text):
    """Render the emphasis used in the site's Markdown files."""
    return re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", escape(text))


def markdown(name):
    """Render headings, lists, and paragraphs in the site's content files."""
    content = (SOURCE / f"{name}.md").read_text(encoding="utf-8")
    parts = []
    for block in re.split(r"\n\s*\n", content.strip()):
        lines = block.splitlines()
        if block.startswith("## "):
            parts.append(f"<h2>{inline(block[3:])}</h2>")
        elif all(line.startswith("- ") for line in lines):
            items = "".join(f"<li>{inline(line[2:])}</li>" for line in lines)
            parts.append(f"<ul>{items}</ul>")
        else:
            parts.append(f"<p>{inline(' '.join(lines))}</p>")
    return "\n".join(parts)


def local_url(current, target=""):
    prefix = "../" * len(current.split("/")) if current else "./"
    return f"{prefix}{target + '/' if target else ''}"


def origin_url(route):
    return f"{SITE['url']}/{route + '/' if route else ''}"


def write_page(route, title, description, content, active=None, extra_head="", article=False):
    path = OUTPUT / route / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    active = route if active is None else active
    navigation = []
    for key, label in NAVIGATION.items():
        current = ' aria-current="page"' if key == active else ""
        navigation.append(f'<a href="{local_url(route, key)}"{current}>{label}</a>')

    path.write_text(
        LAYOUT.substitute(
            name=escape(SITE["name"]),
            title=escape(title),
            description=escape(description),
            canonical=escape(origin_url(route)),
            site_url=escape(SITE["url"]),
            email=escape(SITE["email"]),
            affiliation=escape(SITE["affiliation"]),
            root="/".join([".."] * len(route.split("/"))) if route else ".",
            navigation="\n".join(navigation),
            content=content,
            extra_head=extra_head,
            og_type="article" if article else "website",
        ),
        encoding="utf-8",
    )


def write_alias(route, target):
    path = OUTPUT / route / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    relative = local_url(route, target)
    path.write_text(
        f'''<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="0;url={relative}">
<link rel="canonical" href="{origin_url(target)}">
<title>Page moved | {escape(SITE["name"])}</title>
<p>This page has moved. <a href="{relative}">Continue to the new address</a>.</p>
</html>
''',
        encoding="utf-8",
    )


def page_header(heading, subtitle="", label="", back=False):
    back_link = '<a class="back-link" href="../">All publications</a>' if back else ""
    context = f'<p class="label">{escape(label)}</p>' if label else ""
    deck = f'<p class="subtitle">{escape(subtitle)}</p>' if subtitle else ""
    style = "page-head article-head" if back else "page-head"
    return f'''<div class="{style}"><div class="frame">
  {back_link}{context}<h1>{escape(heading)}</h1>{deck}
</div></div>'''


def prose_page(heading, body, *, subtitle="", label=""):
    return f'''<main id="main">
  {page_header(heading, subtitle, label)}
  <div class="frame page-body"><div class="prose">{body}</div></div>
</main>'''


def write_profile_pages():
    name = escape(SITE["name"])
    tagline = escape(SITE["tagline"])
    affiliation = escape(SITE["affiliation"])
    project = escape(SITE["researchTitle"])
    subtitle = escape(SITE["researchSubtitle"])
    write_page("", f'{SITE["name"]} | {SITE["tagline"]}', SITE["tagline"], f'''<main id="main">
  <div class="hero"><div class="frame hero-inner">
    <div>
      <h1>{name}</h1>
      <p class="tagline">{tagline}</p>
      <p class="affiliation">{affiliation}</p>
    </div>
    <figure class="portrait"><img src="./assets/scott-ma.webp" width="200" height="200" alt="Portrait of {name}"></figure>
  </div></div>
  <div class="frame home-body">
    <section>
      <h2>About</h2>
      <div class="prose">{markdown("home")}</div>
    </section>
    <aside class="research-card" aria-labelledby="project-title">
      <p class="label">Dissertation</p>
      <h3 id="project-title">{project}</h3>
      <p>{subtitle}</p>
      <a href="./research/">Read about the project</a>
    </aside>
  </div>
</main>''')
    write_page(
        "research", f'{SITE["researchTitle"]} | {SITE["name"]}', SITE["researchSubtitle"],
        prose_page(SITE["researchTitle"], markdown("research"), subtitle=SITE["researchSubtitle"], label="Dissertation"),
    )
    cv = markdown("cv") + '\n<p>For my publication record, see <a href="../publications/">Publications</a>.</p>'
    write_page("cv", f'CV | {SITE["name"]}', "Appointments, education, fellowships, and languages.", prose_page("Curriculum Vitae", cv))
    privacy = markdown("privacy") + f'\n<p><a href="mailto:{escape(SITE["email"])}">Contact by email</a></p>'
    write_page("privacy", f'Privacy | {SITE["name"]}', "Privacy practices for this academic website.", prose_page("Privacy Policy", privacy))


def citation(paper, include_year=False):
    year = f' ({paper["year"]})' if include_year else ""
    return f'<cite>{escape(paper["journal"])}</cite> {escape(paper["volume"])}{year}, {escape(paper["pages"])}.'


def validated_publications():
    seen = set()
    for paper in PUBLICATIONS:
        slug = paper["slug"]
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug) or slug in seen:
            raise ValueError(f"Invalid or duplicate publication slug: {slug}")
        seen.add(slug)
        for link in [paper["link"], *(item["url"] for item in paper.get("links", []))]:
            url = urlsplit(link)
            if url.scheme != "https" or not url.netloc:
                raise ValueError(f"Publication links must be absolute HTTPS URLs: {link}")
    return sorted(PUBLICATIONS, key=lambda paper: paper["year"], reverse=True)


def bibtex(paper):
    authors = " and ".join(paper["authors"])
    fields = {
        "author": authors,
        "title": "{" + paper["title"] + "}",
        "journal": paper["journal"],
        "year": paper["year"],
        "volume": paper["volume"],
        "pages": paper["pages"].replace("–", "--"),
        "url": paper["link"],
    }
    if paper["link"].startswith("https://doi.org/"):
        fields["doi"] = paper["link"].removeprefix("https://doi.org/")
    key = re.sub(r"[^a-zA-Z0-9]", "", paper["authors"][0].split()[-1])
    key += str(paper["year"]) + "-" + paper["slug"].split("-")[0]
    entries = ",\n".join(f"  {field} = {{{value}}}" for field, value in fields.items())
    return f"@article{{{key},\n{entries}\n}}\n"


def write_publications():
    papers = validated_publications()
    rows = []
    for paper in papers:
        slug = paper["slug"]
        year = paper["year"]
        title = escape(paper["title"])
        authors = escape(", ".join(paper["authors"]))
        rows.append(f'''<li class="publication-item" data-year="{year}">
  <span class="publication-year">{year}</span>
  <div><h2><a href="./{slug}/">{title}</a></h2>
    <p class="publication-byline">{authors}</p>
    <p class="publication-journal">{citation(paper)}</p></div>
</li>''')
        write_publication(paper)

    years = sorted({paper["year"] for paper in papers}, reverse=True)
    options = "".join(f'<option value="{year}">{year}</option>' for year in years)
    listing = f'''<main id="main">
  {page_header("Publications")}
  <div class="frame page-body">
    <section class="publications" data-publications aria-label="Journal articles">
      <form class="filters" role="search" hidden>
        <label>Search publications<input type="search" name="query" placeholder="Title, author, or journal"></label>
        <label>Year<select name="year"><option value="">All years</option>{options}</select></label>
      </form>
      <p class="filter-status" role="status"></p>
      <ol class="publication-list">{"".join(rows)}</ol>
      <p class="bibliography"><a href="./scott-ma.bib" download>Download bibliography (BibTeX)</a></p>
    </section>
  </div>
</main>
<script src="../assets/publications.js" defer></script>'''
    write_page("publications", f'Publications | {SITE["name"]}', f'Journal articles by {SITE["name"]}.', listing)
    (OUTPUT / "publications/scott-ma.bib").write_text("\n".join(map(bibtex, papers)), encoding="utf-8")


def write_publication(paper):
    route = f'publications/{paper["slug"]}'
    title = paper["title"]
    authors = ", ".join(paper["authors"])
    summary = paper.get("abstract", "")
    links = [f'<a class="primary" href="{escape(paper["link"])}">Publisher page</a>']
    links.extend(f'<a href="{escape(item["url"])}">{escape(item["label"])}</a>' for item in paper.get("links", []))
    links.append('<a href="./citation.bib" download>BibTeX</a>')
    meta_fields = [("citation_title", title), ("citation_journal_title", paper["journal"]),
                   ("citation_publication_date", paper["year"]), ("citation_volume", paper["volume"])]
    meta_fields.extend(("citation_author", author) for author in paper["authors"])
    first_page, separator, last_page = paper["pages"].partition("–")
    if separator:
        meta_fields.extend([("citation_firstpage", first_page), ("citation_lastpage", last_page)])
    if paper["link"].startswith("https://doi.org/"):
        meta_fields.append(("citation_doi", paper["link"].removeprefix("https://doi.org/")))
    meta = "\n  ".join(f'<meta name="{name}" content="{escape(str(value))}">' for name, value in meta_fields)
    abstract = f'<div class="prose"><h2>Summary</h2><p>{escape(summary)}</p></div>' if summary else ""
    content = f'''<main id="main">
  {page_header(title, authors, back=True)}
  <div class="frame page-body">
    <p class="article-citation">{citation(paper, include_year=True)}</p>
    <div class="resource-links">{"".join(links)}</div>
    {abstract}
  </div>
</main>'''
    write_page(route, f'{title} | {SITE["name"]}', summary or f"{title}, by {authors}.",
               content, active="publications", extra_head=meta, article=True)
    (OUTPUT / route / "citation.bib").write_text(bibtex(paper), encoding="utf-8")


def build():
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    shutil.copytree(SOURCE / "assets", OUTPUT / "assets")
    write_profile_pages()
    write_publications()
    page_aliases = {
        "pages/9881": "research",
        "pages/9882": "cv",
        "privacy_policy": "privacy",
        "confucius": "research",
        "cvit": "cv",
    }
    for old, new in page_aliases.items():
        write_alias(old, new)
    article_aliases = {"67052": "isekai", "67055": "japonisme", "67054": "nagasaki", "67048": "homi"}
    for paper in PUBLICATIONS:
        alias = article_aliases.get(paper["slug"].split("-")[0])
        if alias:
            write_alias(alias, f'publications/{paper["slug"]}')
    urls = [origin_url(route) for route in [*NAVIGATION, *(f'publications/{paper["slug"]}' for paper in PUBLICATIONS)]]
    entries = "\n".join(f"  <url><loc>{escape(url)}</loc></url>" for url in urls)
    (OUTPUT / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{entries}\n</urlset>\n',
        encoding="utf-8",
    )
    (OUTPUT / "robots.txt").write_text(f'User-agent: *\nAllow: /\nSitemap: {SITE["url"]}/sitemap.xml\n', encoding="utf-8")
    (OUTPUT / ".nojekyll").touch()
    print(f"Built {len(urls)} public content pages in {OUTPUT}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    build()
