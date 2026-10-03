# Search and agent discovery

The static site builder publishes these entry points from the same source as the
visible guides:

- `/robots.txt` allows crawling and advertises `/sitemap.xml`.
- `/sitemap.xml` lists shipped HTML pages at their canonical production URLs.
  It excludes the 404 page and avoids invented modification dates.
- Every page has a description, canonical URL and social preview. JSON-LD
  describes the website, Python source project and current page. The 404 page
  uses `noindex`.
- `/llms.txt` provides a short installation and capability index with absolute
  links. `/llms-full.txt` combines it with the published Markdown guides for
  agents that prefer a single request. These files supplement ordinary web
  pages; they do not guarantee recognition by any search or AI provider.
- The portable skill, versioned score schema, instrument catalog and listening
  manifest remain directly downloadable. Installed CLI discovery is authoritative
  when a project's version differs from the website.

Run `uv run python examples/build_site.py --strict` after preparing the listening
assets. Generated discovery files live in `output/site/`; edit their source in
`docs/site/`, `web/site/`, or `examples/_site_discovery.py`. Page URLs follow
Cloudflare's extensionless HTML redirects, while local HTML links retain their
filenames so the downloaded site works offline. The social preview is
`web/site/assets/social.png`, rendered from the adjacent SVG at 1200 × 630.

Check the deployed response as well as local files. A permissive robots file
cannot override a CDN challenge or access rule. In particular, test the Markdown,
skill and schema URLs with the actual client used by an agent. Review the
hosting guide if that request gets Cloudflare error 1010. Do not disguise a
client as a verified search crawler; a named user agent must identify it honestly.

After verifying site ownership, submit `https://audioascode.com/sitemap.xml` in
Google Search Console and Bing Webmaster Tools. Search engines decide whether
and when to index pages. See Google's [sitemap guidance](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap)
and OpenAI's [crawler documentation](https://developers.openai.com/api/docs/bots)
for crawling controls. The [llms.txt proposal](https://llmstxt.org/) is separate
from robots.txt access rules.
