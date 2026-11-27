"""Build the portable static website from the text and bibliography in src/."""

import argparse
from html import escape, unescape
import json
import os
from pathlib import Path
import re
import shutil
import sys
from string import Template
from urllib.parse import urlsplit

from profile_pages import PROFILE_PAGES, write_profile_pages


PROJECT = Path(__file__).resolve().parent
SOURCE = PROJECT / "src"
OUTPUT = PROJECT / "dist"
ASSETS = SOURCE / "assets"
SITE = json.loads((SOURCE / "site.json").read_text(encoding="utf-8"))
if deployment_url := os.environ.get("SCOTT_MA_SITE_URL"):
    SITE["url"] = deployment_url.rstrip("/").replace("http://", "https://", 1)
SITE_NAME = f'{SITE["name"]} - {SITE["tagline"]}'
LAYOUT = Template((SOURCE / "templates/base.html").read_text(encoding="utf-8"))
PUBLICATIONS = json.loads((SOURCE / "publications.json").read_text(encoding="utf-8"))
GALLERY_PATH = SOURCE / "gallery.json"
GALLERY = json.loads(GALLERY_PATH.read_text(encoding="utf-8")) if GALLERY_PATH.exists() else []
PAGE_IMAGES = json.loads((SOURCE / "page-images.json").read_text(encoding="utf-8"))
NAVIGATION = {"": "Home", "#research": "Research", "publications": "Publications", "cv": "CV"}


def inline(text):
    """Render the emphasis used in the site's Markdown files."""
    text = escape(text).replace(r"\*", "&#42;")
    text = re.sub(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", r"<strong>\1</strong>", text)
    return re.sub(r"(?<!\*)\*(?=\S)([^*]+?)(?<=\S)\*(?!\*)", r"<em>\1</em>", text)


def plain_inline(text):
    return unescape(re.sub(r"</?(?:em|strong)>", "", inline(text)))


def markdown(name):
    """Render headings, lists, and paragraphs in the site's content files."""
    return markdown_text((SOURCE / f"{name}.md").read_text(encoding="utf-8"))


def markdown_text(content, heading_level=2, render_inline=inline):
    parts = []
    for block in filter(None, re.split(r"\n\s*\n", content.strip())):
        lines = block.splitlines()
        if block.startswith("## "):
            parts.append(f"<h{heading_level}>{render_inline(block[3:])}</h{heading_level}>")
        elif all(line.startswith("- ") for line in lines):
            items = "".join(f"<li>{render_inline(line[2:])}</li>" for line in lines)
            parts.append(f"<ul>{items}</ul>")
        elif all(line == ">" or line.startswith("> ") for line in lines):
            paragraphs = "\n".join(line[2:] for line in lines)
            quotes = []
            for paragraph in filter(None, paragraphs.split("\n\n")):
                verse_lines = re.split(r" {2,}\n", paragraph)
                quote = "<br>\n".join(render_inline(" ".join(line.splitlines())) for line in verse_lines)
                quotes.append(f"<p>{quote}</p>")
            parts.append(f"<blockquote>{''.join(quotes)}</blockquote>")
        else:
            parts.append(f"<p>{render_inline(' '.join(lines))}</p>")
    return "\n".join(parts)


def local_url(current, target=""):
    prefix = "../" * len(current.split("/")) if current else "./"
    return f"{prefix}{target + '/' if target else ''}"


def origin_url(route):
    return f"{SITE['url']}/{route + '/' if route else ''}"


def structured_data(**fields):
    data = {"@context": "https://schema.org", **fields}
    encoded = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    return f'<script type="application/ld+json">{encoded}</script>'


def asset_path(name):
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]*", name):
        raise ValueError(f"Invalid asset filename: {name}")
    path = ASSETS / name
    if not path.is_file():
        raise ValueError(f"Missing asset: {path}")
    return path


def https_url(link):
    url = urlsplit(link)
    if url.scheme != "https" or not url.netloc:
        raise ValueError(f"Expected an absolute HTTPS link: {link}")
    return escape(link)


def page_image(route):
    return PAGE_IMAGES.get(route, PAGE_IMAGES[""])


def favicon_links(route):
    icon = local_url(route, "assets") + "favicon.png"
    return (f'<link rel="icon" href="{icon}" type="image/png" sizes="192x192">\n  '
            f'<link rel="apple-touch-icon" href="{icon}">')


def social_metadata(route, title, description, article=False):
    image = page_image(route)
    image_url = origin_url("assets") + image["asset"]
    properties = {
        "og:type": "article" if article else "website",
        "og:site_name": SITE_NAME,
        "og:title": title,
        "og:description": description,
        "og:url": origin_url(route),
        "og:image": image_url,
        "og:image:type": "image/jpeg",
        "og:image:width": "1200",
        "og:image:height": "630",
        "og:image:alt": image["alt"],
    }
    card = {"twitter:card": "summary_large_image", "twitter:title": title,
            "twitter:description": description, "twitter:image": image_url, "twitter:image:alt": image["alt"]}
    return "\n  ".join(
        f'<meta {attribute}="{name}" content="{escape(value)}">'
        for attribute, values in (("property", properties), ("name", card))
        for name, value in values.items()
    )


def write_page(route, title, description, content, active=None, extra_head="", article=False):
    path = OUTPUT / route / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    active = route if active is None else active
    navigation = []
    for key, label in NAVIGATION.items():
        current = ' aria-current="page"' if key == active else ""
        path_part, separator, fragment = key.partition("#")
        href = local_url(route, path_part) + separator + fragment
        navigation.append(f'<a href="{href}"{current}>{label}</a>')

    path.write_text(
        LAYOUT.substitute(
            name=escape(SITE["name"]),
            title=escape(title),
            description=escape(description),
            canonical=escape(origin_url(route)),
            email=escape(SITE["email"]),
            affiliation=escape(SITE["affiliation"]),
            root="/".join([".."] * len(route.split("/"))) if route else ".",
            navigation="\n".join(navigation),
            content=content,
            extra_head=extra_head,
            social_head=social_metadata(route, title, description, article=article),
            favicon_head=favicon_links(route),
        ),
        encoding="utf-8",
    )


def write_alias(route, target):
    path = OUTPUT / route / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    relative = local_url(route, target)
    paper = next((item for item in PUBLICATIONS if target == f'publications/{item["slug"]}'), None)
    title = paper["title"] if paper else PROFILE_PAGES[target][0]
    description = plain_inline(paper.get("hook") or paper.get("abstract", "")) if paper else SITE["tagline"]
    path.write_text(
        f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="canonical" href="{escape(origin_url(target))}">
<title>{escape(title if paper else f"{title} | {SITE['name']}")}</title>
{social_metadata(target, title, description, article=paper is not None)}
{favicon_links(route)}
<script>location.replace({json.dumps(relative)} + location.search + location.hash);</script>
<meta http-equiv="refresh" content="0;url={relative}">
</head>
<p>This page has moved to <a href="{relative}">{escape(title)}</a>.</p>
</html>
''',
        encoding="utf-8",
    )


def page_header(heading, subtitle="", label="", back=False, split_title=False, image=None):
    back_link = '<a class="back-link" href="../">All publications</a>' if back else ""
    context = f'<p class="label">{escape(label)}</p>' if label else ""
    deck = f'<p class="subtitle">{escape(subtitle)}</p>' if subtitle else ""
    title = escape(heading)
    if split_title and ": " in heading:
        lead, continuation = heading.split(": ", 1)
        title = f'{escape(lead)}: <span class="title-continuation">{escape(continuation)}</span>'
    style = "page-head article-head" if back else "page-head"
    artwork = ''
    if image:
        filename = escape(image["asset"])
        artwork = f'<img class="article-head-image" src="../../assets/{filename}" width="1200" height="630" alt="" fetchpriority="high">'
    return f'''<div class="{style}">{artwork}<div class="frame">
  {back_link}{context}<h1>{title}</h1>{deck}
</div></div>'''


def image_credit(image):
    if not image.get("credit"):
        return ""
    credit = escape(image["credit"])
    if image.get("source"):
        credit = f'<a href="{https_url(image["source"])}">{credit}</a>'
    license_label = escape(image.get("license", ""))
    if license_label and image.get("licenseUrl"):
        license_label = f'<a href="{https_url(image["licenseUrl"])}">{license_label}</a>'
    if license_label:
        credit += f' · {license_label}'
    return f'<p class="article-image-credit">{credit}</p>'


def citation(paper, include_year=False, *, full=False):
    year = f' ({paper["year"]})' if include_year or full else ""
    volume = "" if paper.get("issueOnly") else f' {escape(str(paper["volume"]))}'
    number = paper_issue(paper)
    issue = f", no. {escape(str(number))}" if number else ""
    journal = f'<cite>{escape(paper["journal"])}</cite>{volume}{issue}{year}'
    pages = escape(paper["pages"])
    if not full:
        return f"{journal}, {pages}."

    authors = paper.get("citationAuthors", paper["authors"])
    byline = f"{authors[0]} et al." if len(authors) > 2 else " and ".join(authors)
    title = escape(paper["title"].replace("“", "‘").replace("”", "’"))
    doi = paper_doi(paper)
    source = f"https://doi.org/{doi}" if doi else paper["link"]
    link = https_url(source)
    return f'{escape(byline)}, “{title},” {journal}: {pages}, <a href="{link}">{link}</a>.'


def paper_issue(paper):
    return paper.get("issue") or (paper["volume"] if paper.get("issueOnly") else "")


def paper_doi(paper):
    doi = paper.get("doi", "")
    if not doi and paper["link"].startswith("https://doi.org/"):
        doi = paper["link"]
    return doi.removeprefix("https://doi.org/")


def validated_publications():
    seen = set()
    legacy_seen = set()
    for paper in PUBLICATIONS:
        slug = paper["slug"]
        if not re.fullmatch(r"[a-z][a-z0-9]*", slug) or slug in seen:
            raise ValueError(f"Invalid or duplicate publication slug: {slug}")
        seen.add(slug)
        if legacy := paper.get("legacySlug"):
            if not re.fullmatch(r"\d+-[a-z0-9]+(?:-[a-z0-9]+)*", legacy) or legacy in legacy_seen:
                raise ValueError(f"Invalid or duplicate legacy publication slug: {legacy}")
            legacy_seen.add(legacy)
        for link in [paper["link"], *(item["url"] for item in paper.get("links", []))]:
            https_url(link)
        if paper.get("publicText") and paper.get("publicTextEdition") != "version-of-record":
            raise ValueError(f"Public full text must use the version of record: {slug}")
        if paper.get("publicPdf") and paper.get("publicPdfLabel") != "Version of record (PDF)":
            raise ValueError(f"Public PDF must use the version of record: {slug}")
        for key in ("publicPdf", "publicText", "readingPdf"):
            if paper.get(key):
                asset_path(paper[key])
        if paper.get("license"):
            https_url(paper["license"]["url"])
    return sorted(PUBLICATIONS, key=lambda paper: paper["year"], reverse=True)


def bibtex(paper):
    authors = " and ".join(paper["authors"])
    fields = {
        "author": authors,
        "title": "{" + paper["title"] + "}",
        "journal": paper["journal"],
        "year": paper["year"],
        "pages": paper["pages"].replace("–", "--"),
        "url": paper["link"],
    }
    if not paper.get("issueOnly"):
        fields["volume"] = paper["volume"]
    if paper_issue(paper):
        fields["number"] = paper_issue(paper)
    if paper_doi(paper):
        fields["doi"] = paper_doi(paper)
    key = re.sub(r"[^a-zA-Z0-9]", "", paper["authors"][0].split()[-1])
    previous_id = paper.get("legacySlug", paper["slug"]).split("-", 1)[0]
    key += str(paper["year"]) + "-" + previous_id
    entries = ",\n".join(f"  {field} = {{{value}}}" for field, value in fields.items())
    return f"@article{{{key},\n{entries}\n}}\n"


def write_publications():
    papers = validated_publications()
    rows = []
    for index, paper in enumerate(papers):
        slug = paper["slug"]
        year = paper["year"]
        title = escape(paper["title"])
        authors = escape(", ".join(paper["authors"]))
        index_citation = citation({**paper, "journal": paper.get("shortJournal", paper["journal"])})
        rows.append(f'''<li class="publication-item" data-year="{year}">
  <span class="publication-year">{year}</span>
  <div><h2><a href="./{slug}/">{title}</a></h2>
    <p class="publication-byline">{authors}</p>
    <p class="publication-journal">{index_citation}</p></div>
</li>''')
        previous = papers[index - 1] if index else None
        following = papers[index + 1] if index + 1 < len(papers) else None
        write_publication(paper, previous, following)

    years = sorted({paper["year"] for paper in papers}, reverse=True)
    options = "".join(f'<option value="{year}">{year}</option>' for year in years)
    listing = f'''<section class="publications" data-publications aria-label="Journal articles">
      <form class="filters" role="search" hidden>
        <label>Search publications<input type="search" name="query" placeholder="Title, author, or journal"></label>
        <label>Year<select name="year"><option value="">All years</option>{options}</select></label>
      </form>
      <p class="filter-status" role="status"></p>
      <ol class="publication-list">{"".join(rows)}</ol>
    </section>'''
    (OUTPUT / "publications").mkdir(exist_ok=True)
    (OUTPUT / "publications/scott-ma.bib").write_text("\n".join(map(bibtex, papers)), encoding="utf-8")
    return listing


def visible_keyword(keyword):
    return re.sub(r"(?<=[A-Za-z\u00c0-\u024f])\s*[（(][\u3005\u3040-\u30ff\u3400-\u9fff]+[）)]$", "", keyword)


def write_publication(paper, previous, following):
    route = f'publications/{paper["slug"]}'
    title = paper["title"]
    authors = ", ".join(paper["authors"])
    summary = paper.get("abstract", "")
    hook = paper.get("hook", "")
    description = plain_inline(hook or summary) or f"{title}, by {authors}."
    pdf_name = publication_pdf_name(paper)
    pdf_url = f"{origin_url(route)}{pdf_name}" if pdf_name else ""
    hook_html = f'<p class="article-hook"><strong>{inline(hook)}</strong></p>' if hook else ""
    abstract_label = paper.get("abstractLabel", "Summary")
    abstract = article_section("article-abstract", abstract_label, markdown_text(summary, heading_level=3))
    keywords = "".join(f"<li>{escape(visible_keyword(keyword))}</li>" for keyword in paper.get("keywords", []))
    keywords_label = paper.get("keywordsLabel", "Keywords")
    keywords = article_section("article-keywords", keywords_label, f'<ul class="keywords">{keywords}</ul>') if keywords else ""
    edition_label = paper.get("publicTextLabel", "Full text")
    edition, headings, figures = publication_text(paper)
    contents = [("article-abstract", abstract_label)] if abstract else []
    if edition:
        contents.append(("article-text", edition_label))
    cover = page_image(route)
    content = f'''<main id="main" class="article-page">
  {page_header(title, authors, back=True, split_title=True, image=cover)}
  <div class="frame article-tools" id="article-resources" tabindex="-1">
    <p class="article-citation">{citation(paper, include_year=True)}</p>
    <div class="resource-links">{publication_links(paper, pdf_name)}</div>
  </div>
  {article_neighbors(previous, following, edge=True)}
  <div class="frame page-body reader-layout">
    {article_contents(contents, headings)}
    <article class="prose reader-body" aria-label="{escape(title)}">
      {hook_html}
      {abstract}
      {keywords}
      {edition}
    </article>
  </div>
  <div class="frame">{image_credit(cover)}{article_neighbors(previous, following)}</div>
</main>
<script src="../../assets/article-reader.js?v=7" defer></script>'''
    metadata = publication_metadata(paper, route, description, pdf_url)
    write_page(route, title, description, content, active="publications", extra_head=metadata, article=True)
    (OUTPUT / route / "citation.bib").write_text(bibtex(paper), encoding="utf-8")
    if pdf_name:
        shutil.copyfile(asset_path(paper.get("publicPdf") or paper["readingPdf"]), OUTPUT / route / pdf_name)
    for figure in figures:
        shutil.copyfile(asset_path(figure), OUTPUT / "assets" / figure)


def article_contents(contents, headings):
    items = []
    for section_id, label in contents:
        children = ""
        if section_id == "article-text" and headings:
            children = "".join(
                f'<li class="contents-level-{level}"><a href="#{escape(anchor)}">{inline(heading)}</a></li>'
                for anchor, heading, level in headings
            )
            children = f'<ul class="reader-sections">{children}</ul>'
        items.append(f'<li><a href="#{section_id}">{escape(label)}</a>{children}</li>')
    return f'''<nav class="reader-contents" aria-labelledby="reader-contents-title">
  <h2 id="reader-contents-title">Contents</h2>
  <ul>{"".join(items)}</ul>
</nav>'''


def article_neighbors(previous, following, edge=False):
    links = []
    for direction, paper in (("prev", previous), ("next", following)):
        if not paper:
            continue
        label, arrow = ("Previous article", "←") if direction == "prev" else ("Next article", "→")
        href = f'../{escape(paper["slug"])}/'
        title = escape(paper["title"])
        if edge:
            links.append(f'''<a class="article-edge article-edge-{direction}" href="{href}" rel="{direction}" aria-label="{label}, {title}">
  <span class="article-edge-arrow" aria-hidden="true">{arrow}</span>
  <span class="neighbor-title" aria-hidden="true">{title}</span>
</a>''')
        else:
            links.append(f'''<a href="{href}" rel="{direction}">
  <span class="label">{label}</span><span class="neighbor-title">{title}</span>
</a>''')
    if not links:
        return ""
    if edge:
        return f'<nav class="article-edges" aria-label="Article shortcuts" inert>{"".join(links)}</nav>'
    return f'<nav class="article-neighbors" id="article-neighbors" tabindex="-1" aria-label="More publications">{"".join(links)}</nav>'


def publication_pdf_name(paper):
    if paper.get("publicPdf"):
        return "version-of-record.pdf"
    return "reading-edition.pdf" if paper.get("readingPdf") else ""


def publication_links(paper, pdf_name):
    publisher_class = "" if pdf_name else ' class="primary"'
    links = [f'<a{publisher_class} href="{https_url(paper["link"])}">Publisher version of record</a>']
    if pdf_name:
        download_name = escape(paper["slug"]) + ".pdf"
        links.insert(0, f'<a class="primary" href="./{pdf_name}" download="{download_name}">Download PDF</a>')
        if paper.get("license") and not paper.get("publicText"):
            license_url = https_url(paper["license"]["url"])
            license_label = escape(paper["license"]["label"])
            links.append(f'<a href="{license_url}">{license_label}</a>')
    download_labels = {"download pdf", "download reading pdf", paper.get("publicPdfLabel", "").casefold()}
    links.extend(f'<a href="{https_url(item["url"])}">{escape(item["label"])}</a>'
                 for item in paper.get("links", [])
                 if not pdf_name or item["label"].casefold() not in download_labels)
    links.append('<a href="./citation.bib" download>BibTeX</a>')
    return "".join(links)


def article_section(section_id, label, body):
    return f'''<section class="article-section" aria-labelledby="{section_id}">
  <h2 id="{section_id}" tabindex="-1">{escape(label)}</h2>{body}
</section>''' if body else ""


def publication_text(paper):
    if not paper.get("publicText"):
        return "", [], set()
    text = asset_path(paper["publicText"]).read_text(encoding="utf-8")
    credit = f'<p class="full-text-credit">{citation(paper, full=True)}'
    if paper.get("license"):
        license_url = https_url(paper["license"]["url"])
        license_label = escape(paper["license"]["label"])
        credit += f' <a href="{license_url}">{license_label}</a>.'
    body, headings, figures = article_markdown(text)
    body = credit + "</p>" + body
    return article_section("article-text", paper.get("publicTextLabel", "Full text"), body), headings, figures


def article_markdown(content):
    parts, headings, figures = [], [], set()
    anchors = set()
    notes, references = [], {}
    notes_position = None
    conclusion_level = None
    in_back_matter = False
    ordered = re.compile(r"(?m)^(\d+)\\?[.)][ \t]+")
    footnote = re.compile(r"(?m)^\[\^(\d+)\]:[ \t]+")
    available_notes = {int(marker[1]) for marker in footnote.finditer(content)}
    reference_entry = re.compile(r"(?m)^\[@([a-z0-9-]+)\]:[ \t]+")
    available_citations = reference_entry.findall(content)
    if len(available_citations) != len(set(available_citations)):
        raise ValueError("Duplicate article bibliography entry")
    available_citations = set(available_citations)
    author_date = re.compile(r"\[@([a-z0-9-]+)\|([^\]\n]+)\]")
    figure_pattern = r"!\[([^\]\n]+)\]\(([a-zA-Z0-9][a-zA-Z0-9._-]*\.(?:webp|jpe?g|png))\)"
    caption_pattern = r"(?:Figure|Fig\.|Table)\s+\d+[.:]"
    content = re.sub(rf"({figure_pattern})\n\s*\n(?={caption_pattern})", r"\1\n", content)

    def render_inline(text):
        def note_reference(match):
            number = int(match[1])
            if number not in available_notes:
                raise ValueError(f"Missing article footnote {number}")
            targets = references.setdefault(number, [])
            anchor = f"note-ref-{number}-{len(targets) + 1}"
            targets.append(anchor)
            return (f'<sup class="note-ref" id="{anchor}" tabindex="-1">'
                    f'<a href="#footnote-{number}" role="doc-noteref" aria-label="Note {number}">{number}</a></sup>')

        def citation_reference(match):
            key, label = match.groups()
            if key not in available_citations:
                raise ValueError(f"Missing article bibliography entry {key}")
            return (f'<a class="author-date-citation" data-reader-note="Citation" '
                    f'href="#reference-{key}">{label}</a>')

        def link_reference(match):
            label, url = match.groups()
            href = https_url(unescape(url)) if url.startswith("https://") else url
            return f'<a href="{href}">{label}</a>'

        text = re.sub(r"\[([^\]\n]+)\]\((https://[^\s<>()]+|\./version-of-record\.pdf#page=\d+)\)",
                      link_reference, inline(text))
        text = author_date.sub(citation_reference, text)
        return re.sub(r"\[\^(\d+)\]", note_reference, text)

    blocks = []
    for block in re.split(r"\n\s*\n", content.strip()):
        if blocks and ordered.match(blocks[-1]) and ordered.match(block):
            blocks[-1] += "\n" + block
        else:
            blocks.append(block)

    for block in blocks:
        if heading := re.fullmatch(r"(#{2,3}) (.+)", block):
            marks, label = heading.groups()
            base = re.sub(r"[^\w]+", "-", label.casefold()).strip("-") or "heading"
            anchor = f"section-{base}"
            count = 1
            while anchor in anchors:
                count += 1
                anchor = f"section-{base}-{count}"
            anchors.add(anchor)
            level = len(marks) + 1
            if conclusion_level is not None and level <= conclusion_level:
                parts.append('<hr class="article-end-rule" aria-label="End of article text">')
                in_back_matter = True
                conclusion_level = None
            heading_text = plain_inline(label).casefold()
            if not in_back_matter or heading_text in {"notes", "references", "works cited", "bibliography"}:
                headings.append((anchor, label, level))
            if not in_back_matter and re.match(r"(?:\d+\.\s+)?conclusion\b", heading_text):
                conclusion_level = level
            parts.append(f'<h{level} id="{escape(anchor)}" tabindex="-1">{render_inline(label)}</h{level}>')
        elif figure := re.fullmatch(rf"{figure_pattern}(?:\n([\s\S]+))?", block):
            alt, filename, caption = figure.groups()
            figures.add(filename)
            caption = f'<figcaption>{render_inline(" ".join(caption.splitlines()))}</figcaption>' if caption else ""
            parts.append(f'''<figure class="article-figure">
  <img src="../../assets/{escape(filename)}" alt="{escape(alt)}" loading="lazy" decoding="async">{caption}
</figure>''')
        elif re.match(caption_pattern, block):
            parts.append(f'<p class="article-caption">{render_inline(" ".join(block.splitlines()))}</p>')
        elif entry := reference_entry.match(block):
            key = entry[1]
            text = render_inline(" ".join(block[entry.end():].splitlines()))
            parts.append(f'<p class="article-reference" id="reference-{key}" tabindex="-1">'
                         f'<span class="note-text">{text}</span></p>')
        elif footnote.match(block):
            if notes_position is None:
                notes_position = len(parts)
            notes.extend(numbered_article_items(block, footnote))
        elif ordered.match(block):
            items = "".join(f'<li value="{number}">{render_inline(item)}</li>'
                            for number, item in numbered_article_items(block, ordered))
            parts.append(f'<ol class="article-list">{items}</ol>')
        else:
            parts.append(markdown_text(block, heading_level=3, render_inline=render_inline))

    if notes:
        notes = [(number, render_inline(text)) for number, text in notes]
        parts.insert(notes_position, article_footnotes(notes, references))
    return "\n".join(parts), headings, figures


def numbered_article_items(block, pattern):
    markers = list(pattern.finditer(block))
    boundaries = [marker.start() for marker in markers[1:]] + [len(block)]
    return [(int(marker[1]), " ".join(block[marker.end():end].strip().splitlines()))
            for marker, end in zip(markers, boundaries)]


def article_footnotes(notes, references):
    items = []
    for number, text in notes:
        targets = references.get(number, [])
        backlinks = "".join(
            f' <a href="#{target}" class="note-backlink" role="doc-backlink" '
            f'aria-label="Back to text at note {number}, reference {index}">'
            f'Back to text{f" {index}" if len(targets) > 1 else ""}</a>'
            for index, target in enumerate(targets, 1)
        )
        items.append(f'<li id="footnote-{number}" value="{number}" tabindex="-1">'
                     f'<span class="note-text">{text}</span>{backlinks}</li>')
    return f'<ol class="article-list article-notes">{"".join(items)}</ol>'


def publication_metadata(paper, route, description, pdf_url):
    published = str(paper.get("publicationDate") or paper["year"])
    doi = paper_doi(paper)
    title = paper["title"]
    number = paper_issue(paper)
    volume = None if paper.get("issueOnly") else paper["volume"]
    meta_fields = [("citation_title", title), ("citation_journal_title", paper["journal"]),
                   ("citation_publication_date", published.replace("-", "/"))]
    meta_fields.extend(("citation_author", author) for author in paper["authors"])
    page_bounds = re.split(r"\s*[–—-]\s*", paper["pages"], maxsplit=1)
    meta_fields.append(("citation_firstpage", page_bounds[0]))
    if len(page_bounds) == 2:
        meta_fields.append(("citation_lastpage", page_bounds[1]))
    optional = [("citation_volume", volume), ("citation_issue", number), ("citation_issn", paper.get("issn")),
                ("citation_doi", doi), ("citation_pdf_url", pdf_url)]
    meta_fields.extend((name, value) for name, value in optional if value)
    meta = "\n  ".join(f'<meta name="{name}" content="{escape(str(value))}">' for name, value in meta_fields)

    journal = {"@type": "Periodical", "name": paper["journal"]}
    if paper.get("issn"):
        journal["issn"] = paper["issn"]
    collection = {"@type": "PublicationVolume", "volumeNumber": volume, "isPartOf": journal} if volume else journal
    if number:
        collection = {"@type": "PublicationIssue", "issueNumber": number, "isPartOf": collection}
    article = {"@type": "ScholarlyArticle", "headline": title, "description": description,
               "url": origin_url(route), "mainEntityOfPage": origin_url(route),
               "sameAs": paper["link"], "author": [{"@type": "Person", "name": name} for name in paper["authors"]],
               "datePublished": published.replace("/", "-"), "isPartOf": collection, "pagination": paper["pages"],
               "image": origin_url("assets") + page_image(route)["asset"]}
    if doi:
        article["identifier"] = {"@type": "PropertyValue", "propertyID": "DOI", "value": doi}
    if paper.get("keywords"):
        article["keywords"] = paper["keywords"]
    if paper.get("abstract") and paper.get("abstractLabel") == "Abstract":
        article["abstract"] = plain_inline(paper["abstract"])
    if pdf_url:
        article["encoding"] = {"@type": "MediaObject", "encodingFormat": "application/pdf", "contentUrl": pdf_url,
                               "name": paper.get("publicPdfLabel", "Reading edition (PDF)")}
    if paper.get("license"):
        article["license"] = paper["license"]["url"]
    return meta + "\n  " + structured_data(**article)


def site_aliases():
    aliases = {
        "research": "research/confucian-science",
        "pages/9881": "research/confucian-science",
        "pages/9882": "cv",
        "privacy_policy": "privacy",
        "confucius": "research/confucian-science",
        "cvit": "cv",
    }
    for paper in PUBLICATIONS:
        slug = paper["slug"]
        target = f"publications/{slug}"
        if legacy := paper.get("legacySlug"):
            aliases[f"publications/{legacy}"] = target
        if slug in {"isekai", "japonisme", "nagasaki", "homi"}:
            aliases[slug] = target
    return aliases


def build():
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    (OUTPUT / "assets").mkdir(parents=True)
    site_assets = {"article-reader.js", "favicon.svg", "favicon.png", "site.css", "reader-chrome.css", "scott-ma.webp", "publications.js"}
    site_assets.update(image["asset"] for image in GALLERY)
    site_assets.update(image["asset"] for image in PAGE_IMAGES.values())
    for name in sorted(site_assets):
        shutil.copyfile(asset_path(name), OUTPUT / "assets" / name)
    shutil.copyfile(asset_path("favicon.ico"), OUTPUT / "favicon.ico")
    publication_listing = write_publications()
    write_profile_pages(sys.modules[__name__], publication_listing)
    for old, new in site_aliases().items():
        write_alias(old, new)
        if old.startswith("publications/"):
            for filename in ("citation.bib", "version-of-record.pdf", "reading-edition.pdf"):
                source = OUTPUT / new / filename
                if source.is_file():
                    shutil.copyfile(source, OUTPUT / old / filename)
    urls = [origin_url(route) for route in [*PROFILE_PAGES, *(f'publications/{paper["slug"]}' for paper in PUBLICATIONS)]]
    urls.extend(f'{origin_url(f"publications/{paper["slug"]}")}{publication_pdf_name(paper)}'
                for paper in PUBLICATIONS if publication_pdf_name(paper))
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
