# Making robustuavs.ai discoverable

The hard constraint: the site is a single-page application. A crawler receives
an HTML shell with an empty root div, and the content only exists after
JavaScript runs. Google renders JavaScript but queues it separately and can lag
by days; **Yandex, Bing and every social-preview scraper are far less reliable**,
and an empty page is what they cache.

Everything below exists to work around that without cloaking — the `<noscript>`
block states the same claims the app does, so a crawler and a person are told
the same thing. Serving different content to crawlers is worth a manual penalty.

## What is already in the build

Run automatically by `deploy.sh` after `expo export`:

| Piece | Where | Purpose |
|---|---|---|
| `<title>`, description, canonical, `lang` | `scripts/inject-seo.mjs` | the basics Expo does not emit |
| Open Graph + Twitter card | same | a shared link renders as a card, not a bare URL |
| `citation_*` tags | same | Google Scholar's preferred vocabulary |
| JSON-LD `ScholarlyArticle` + `Dataset` + `SoftwareApplication` | same | what Google Dataset Search actually reads |
| `<noscript>` content block | same | the substance, in plain HTML, for crawlers that do not execute JS |
| `robots.txt` | `public/robots.txt` | allows the app, blocks `/artifact/` and `/api/` |
| `sitemap.xml` | `public/sitemap.xml` | route list plus the sitemap reference |

`/artifact/` is disallowed deliberately: it is a directory listing of thousands
of small research files with no search value, and letting a crawler walk it
wastes crawl budget that should go to the pages.

## What you have to do by hand

These cannot be done from the codebase.

**1. Verify ownership.**
- Google Search Console → add `robustuavs.ai` as a *Domain* property → add the
  TXT record it gives you in Cloudflare DNS. Domain properties cover every
  subdomain and both schemes, which is why they beat URL-prefix properties.
- Yandex Webmaster → same flow. Yandex matters here: it indexes Russian-language
  academic material well, and MEPhI affiliation makes that audience relevant.
- Bing Webmaster Tools → can import directly from Search Console.

**2. Submit the sitemap** in each: `https://robustuavs.ai/sitemap.xml`.

**3. Request indexing** for the root URL in Search Console. Do this once;
repeatedly requesting does not help.

**4. Turn OFF Cloudflare's bot fight mode** for search-engine user agents if it
is on — it can serve challenges to crawlers, which reads as an unreachable site.
Cloudflare → Security → Bots. Verified bots should be allowed.

## Where the real ranking will come from

For an artifact like this, backlinks from authoritative sources outrank
on-page tuning:

- The **Kaggle dataset page** (DOI 10.34740/kaggle/dsv/18346203) — add the site
  URL to its description. Kaggle carries real domain authority.
- The **paper** — put the URL in the abstract and on the first page. NDSS
  proceedings are indexed and heavily cited.
- **ORCID, Google Scholar profile, ResearchGate, arXiv** if you preprint.
- **GitHub repository** description and README.
- University and lab pages at MEPhI, Missouri S&T, Padova.

A single link from an indexed proceedings page will do more than any
meta-tag change.

## Double-blind caution

**Do not do any of the above until the review outcome is known**, or at least
not in a way that ties the artifact to the author list. NDSS is double-blind;
a submission whose artifact is indexed under the authors' names, cross-linked
from personal profiles, is trivially de-anonymisable, and that is a desk-reject
risk rather than a hypothetical.

Safe order:

1. Now — keep the technical SEO in the build. It costs nothing and does not
   name anyone in a way a reviewer would search for.
2. Now — consider adding `<meta name="robots" content="noindex">` until
   submission closes if you want to be strict. One line in
   `scripts/inject-seo.mjs`.
3. After acceptance or rejection — verify ownership, submit sitemaps, and
   build the backlinks.

The author names currently appear in the JSON-LD and the `citation_*` tags. If
you want the artifact reachable but unattributable during review, strip the
`author` arrays from `inject-seo.mjs` and restore them afterwards — the rest of
the metadata is subject-matter only.

## Checking it works

```bash
curl -s https://robustuavs.ai/robots.txt
curl -s https://robustuavs.ai/sitemap.xml | head -5
curl -s https://robustuavs.ai/ | grep -o '<title>[^<]*</title>'
curl -s https://robustuavs.ai/ | python3 -c "import sys,re,json; \
  m=re.search(r'application/ld\+json\">(.*?)</script>', sys.stdin.read(), re.S); \
  print(json.dumps(json.loads(m.group(1)), indent=2)[:400])"
```

Then:
- Rich Results Test — <https://search.google.com/test/rich-results>
- Schema validator — <https://validator.schema.org/>
- Open Graph preview — paste the URL into any Slack or LinkedIn compose box.

## If you later want real per-route indexing

The proper fix is server-side rendering or prerendering, so `/#/Composition`
becomes a distinct crawlable document. Two routes:

- Switch the client to `expo-router` with `web.output: "static"`, which emits
  one HTML file per route. That is a real migration and would have to be
  re-tested against the build fragility this project has already fought.
- Or prerender the handful of pages worth indexing with a headless Chromium at
  deploy time — Chromium is already installed on the build host.

Neither is worth doing before the conference. The single-document artifact with
good metadata is enough to be found by name and by subject.
