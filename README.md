# Scott Ma’s academic website

The website builds to ordinary HTML, CSS, and JavaScript. The source has no package dependencies and the live site requires no database or application server.

## Edit the site

| To change | Edit |
| --- | --- |
| Name, affiliation, contact, or dissertation heading | `src/site.json` |
| About page | `src/home.md` |
| Research page | `src/research.md` |
| Curriculum vitae | `src/cv.md` |
| Articles, summaries, or external links | `src/publications.json` |
| Profile illustration | `src/assets/scott-ma.webp` |
| Layout and typography | `src/templates/base.html` and `src/assets/site.css` |

The text files support paragraphs, second-level headings, bullets, and italic emphasis. Preserve existing publication slugs to keep their URLs working. Add an HTTPS publisher or DOI URL and any available public PDF link for new entries. The build sorts publications by year and generates the index, detail pages, filters, sitemap, and BibTeX exports.

## Preview

Run `python3 preview.py` and open `Scott-Ma-Website-Preview.html` in a browser. The preview is one file. The navigation, filters, and citation downloads work locally. Publisher and full-text links open their external sites.

For an HTTP preview of the deployable files, run `python3 build.py` and then `python3 -m http.server 8000 --directory dist`. Open `http://localhost:8000`.

## Publish on GitHub Pages

1. Put the source under your GitHub account in a public repository and keep the default branch named `main`.
2. In the repository’s **Settings → Pages**, set the source to **GitHub Actions**. Run **Deploy academic site** manually the first time if needed. Subsequent changes to `main` trigger a rebuild.
3. Open the GitHub Pages address and check the main navigation and a few article links.
4. Set `www.scott-ma.com` as the custom domain in the repository’s Pages settings. Follow [GitHub’s custom domain instructions](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site). Update the applicable website records at Squarespace Domains so the bare domain also redirects to `www`. Keep the existing DNS records for email and other services where applicable.
5. Enable and verify HTTPS on both addresses. Check old Research and CV links and one or more individual publication links before canceling Owlstown.

The old Research, CV, and privacy page paths forward to their new addresses. The eight current publication page paths are retained. Full-text buttons point to public copies on publisher or existing repository/CDN links.
