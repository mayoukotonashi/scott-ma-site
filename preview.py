"""Create a standalone, offline preview of the generated website."""

from base64 import b64encode
from html import escape, unescape
import json
import mimetypes
from pathlib import Path
import re
from urllib.parse import urlsplit

from build import OUTPUT, PROJECT, build, site_aliases


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
        fragment = f"#{escape(url.fragment)}" if url.fragment else ""
        if target.name == "index.html":
            target = target.parent
        if target.is_dir():
            route = target.relative_to(OUTPUT).as_posix().strip(".")
            return f'{attribute}="#/{route}{fragment}"'
        href = data_url(target) + fragment
        if attribute == "href" and target.suffix == ".bib":
            return f'href="{href}" data-download-name="{escape(target.name)}"'
        return f'{attribute}="{href}"'

    without_script = re.sub(r"<script\b[^>]*></script>", "", body)
    return re.sub(r'(href|src)="([^"]+)"', rewrite, without_script)


def preview():
    build()
    templates = []
    stylesheets = {}
    for path in sorted(OUTPUT.rglob("index.html")):
        html = path.read_text(encoding="utf-8")
        if "<body>" not in html:
            continue
        route = path.parent.relative_to(OUTPUT).as_posix().strip(".")
        title = unescape(re.search(r"<title>(.*?)</title>", html)[1])
        body = html.split("<body>", 1)[1].split("</body>", 1)[0]
        portable = convert_links(body, path.parent)
        styles = []
        for href in re.findall(r'<link rel="stylesheet" href="([^"]+)"', html):
            css = (path.parent / urlsplit(unescape(href)).path).resolve()
            key = css.relative_to(OUTPUT).as_posix()
            if key not in stylesheets:
                stylesheets[key] = re.sub(
                    r'url\((type/[^)]+)\)',
                    lambda m: f'url("{data_url(css.parent / m[1])}")',
                    css.read_text(encoding="utf-8"),
                )
            styles.append(key)
        templates.append(f'<template data-route="{route}" data-title="{escape(title)}" data-styles="{" ".join(styles)}">{portable}</template>')

    style_tags = "\n".join(f'<style data-sheet="{key}" media="not all">{css}</style>' for key, css in stylesheets.items())
    filters = (OUTPUT / "assets/publications.js").read_text(encoding="utf-8")
    reader = (OUTPUT / "assets/article-reader.js").read_text(encoding="utf-8")
    favicon = data_url(OUTPUT / "assets/favicon.svg")
    script = f"const aliases = new Map(Object.entries({json.dumps(site_aliases())}));\n" + r"""
const app = document.querySelector("#site");
const pages = new Map(
  [...document.querySelectorAll("template[data-route]")].map((page) => [page.dataset.route, page])
);
let activeRoute;
let resetArticleReader;
function render() {
  const [path, anchor] = location.hash.replace(/^#\/?/, "").split("#", 2);
  const route = path.replace(/\/$/, "");
  const page = pages.get(aliases.get(route) || route) || pages.get("");
  if (activeRoute !== page.dataset.route) {
    resetArticleReader?.();
    app.replaceChildren(page.content.cloneNode(true));
    activeRoute = page.dataset.route;
    document.title = page.dataset.title;
    const styles = page.dataset.styles.split(" ");
    document.querySelectorAll("style[data-sheet]").forEach(sheet => {
      sheet.media = styles.includes(sheet.dataset.sheet) ? "all" : "not all";
    });
    initializePublicationFilters(app);
    resetArticleReader = initializeArticleReader(app);
    app.querySelectorAll("[data-download-name]").forEach((link) => {
      link.download = link.dataset.downloadName;
    });
    app.querySelector(".skip, .skip-link").addEventListener("click", (event) => {
      event.preventDefault();
      const main = app.querySelector("main");
      main.tabIndex = -1;
      main.focus();
    });
  }
  const heading = anchor && document.getElementById(decodeURIComponent(anchor));
  if (heading) {
    heading.scrollIntoView();
    if (heading.hasAttribute("tabindex")) heading.focus({preventScroll: true});
    return;
  }
  window.scrollTo(0, 0);
}
app.addEventListener("click", (event) => {
  const link = event.target.closest('a[href^="#"]');
  const href = link?.getAttribute("href");
  if (event.defaultPrevented || !href || href.startsWith("#/")) return;
  const id = decodeURIComponent(href.slice(1));
  if (!document.getElementById(id)) return;
  event.preventDefault();
  const target = "#/" + activeRoute + "#" + encodeURIComponent(id);
  if (location.hash === target) render();
  else location.hash = target;
});
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
  {style_tags}
  <style>
#site {{ min-height: 100vh; display: flex; flex-direction: column; }}
  </style>
</head>
<body>
  <div id="site"></div>
  {"".join(templates)}
  <script>{filters}
{reader}
{script}</script>
</body>
</html>
'''
    destination = PROJECT / "Scott-Ma-Website-Preview.html"
    destination.write_text(html, encoding="utf-8")
    print(f"Wrote {destination}")


if __name__ == "__main__":
    preview()
