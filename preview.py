"""Create a standalone, offline preview of the generated website."""

from base64 import b64encode
from html import escape, unescape
import json
import mimetypes
from pathlib import Path
import re
from urllib.parse import urlsplit

from build import OUTPUT, PROJECT, build


def data_url(path):
    mime = {
        ".bib": "application/x-bibtex",
        ".webp": "image/webp",
    }.get(path.suffix, mimetypes.guess_type(path.name)[0])
    data = b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def convert_links(body, folder):
    def rewrite(match):
        attribute, raw_url = match.groups()
        url = urlsplit(unescape(raw_url))
        if url.scheme or url.netloc or not url.path:
            return match[0]
        target = (folder / url.path).resolve()
        if target.is_dir():
            route = target.relative_to(OUTPUT).as_posix().strip(".")
            return f'{attribute}="#/{route}"'
        href = data_url(target)
        if attribute == "href" and target.suffix == ".bib":
            return f'href="{href}" data-download-name="{escape(target.name)}"'
        return f'{attribute}="{href}"'

    without_script = re.sub(r"<script\b[^>]*></script>", "", body)
    return re.sub(r'(href|src)="([^"]+)"', rewrite, without_script)


def preview():
    build()
    templates = []
    for path in sorted(OUTPUT.rglob("index.html")):
        html = path.read_text(encoding="utf-8")
        if "<body>" not in html:
            continue
        route = path.parent.relative_to(OUTPUT).as_posix().strip(".")
        title = unescape(re.search(r"<title>(.*?)</title>", html)[1])
        body = html.split("<body>", 1)[1].split("</body>", 1)[0]
        portable = convert_links(body, path.parent)
        templates.append(f'<template data-route="{route}" data-title="{escape(title)}">{portable}</template>')

    styles = (OUTPUT / "assets/site.css").read_text(encoding="utf-8")
    filters = (OUTPUT / "assets/publications.js").read_text(encoding="utf-8")
    favicon = data_url(OUTPUT / "assets/favicon.svg")
    script = r"""
const app = document.querySelector("#site");
const pages = new Map(
  [...document.querySelectorAll("template[data-route]")].map((page) => [page.dataset.route, page])
);
function render() {
  const route = location.hash.replace(/^#\/?/, "").replace(/\/$/, "");
  const page = pages.get(route) || pages.get("");
  app.replaceChildren(page.content.cloneNode(true));
  document.title = page.dataset.title;
  initializePublicationFilters(app);
  app.querySelectorAll("[data-download-name]").forEach((link) => {
    link.download = link.dataset.downloadName;
  });
  app.querySelector(".skip-link").addEventListener("click", (event) => {
    event.preventDefault();
    const main = app.querySelector("main");
    main.tabIndex = -1;
    main.focus();
  });
  window.scrollTo(0, 0);
}
window.addEventListener("hashchange", render);
render();
"""
    html = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex">
  <title>Scott Ma | Website preview</title>
  <link rel="icon" href="{favicon}">
  <style>{styles}
#site {{ min-height: 100vh; display: flex; flex-direction: column; }}
  </style>
</head>
<body>
  <div id="site"></div>
  {"".join(templates)}
  <script>{filters}
{script}</script>
</body>
</html>
'''
    destination = PROJECT / "Scott-Ma-Website-Preview.html"
    destination.write_text(html, encoding="utf-8")
    print(f"Wrote {destination}")


if __name__ == "__main__":
    preview()
