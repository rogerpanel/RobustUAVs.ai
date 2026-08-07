/**
 * Post-export step: give the SPA shell something a crawler can read.
 *
 * Expo emits an index.html with a title and an empty root div. Google will
 * render the JavaScript and eventually index the real content; Yandex, Bing and
 * every social-preview scraper are far less reliable at it, and an empty page
 * is what they cache. So the same markup gains:
 *
 *   - title, description, canonical, and language
 *   - Open Graph and Twitter cards, so a shared link renders as something
 *   - JSON-LD describing the artifact as a ScholarlyArticle plus its Dataset,
 *     which is the vocabulary Google Scholar and Dataset Search actually read
 *   - a <noscript> block carrying the substance in plain HTML
 *
 * The noscript block is not a trick: it is the same claim the page makes, in
 * text, for a client that cannot run the app. Serving different content to
 * crawlers than to people is cloaking and would be worth a manual penalty.
 *
 * Run automatically by deploy.sh after `expo export`.
 */
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';

const dist = process.argv[2] ?? 'dist';
const file = resolve(dist, 'index.html');
if (!existsSync(file)) {
  console.error(`inject-seo: ${file} not found — run expo export first`);
  process.exit(1);
}

const SITE = 'https://robustuavs.ai';
const TITLE = 'RobustUAVs.ai — end-to-end UAV security benchmark and certified navigation guarantee';
const DESC = 'An open cross-layer UAV security benchmark unifying six datasets '
  + 'across the network and autonomy layers, with a composition theorem carrying '
  + 'a detector operating point through to a certified Mission Completion Rate floor.';

const KEYWORDS = [
  'UAV security', 'drone security', 'GNSS spoofing', 'GPS jamming',
  'UAV intrusion detection', 'certified robustness', 'Lipschitz Grönwall',
  'randomized smoothing', 'mission completion rate', 'DO-326A', 'JARUS SORA',
  'UAV benchmark', 'swarm mesh security', 'UAVCAN', 'MAVLink', 'PX4',
  'adversarial machine learning', 'NDSS 2027',
].join(', ');

const jsonld = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'ScholarlyArticle',
      name: 'From Wire to Flight: An End-to-End Framework Composing Network '
          + 'Intrusion Detection with Certified Mission Safety for Autonomous UAVs',
      abstract: DESC,
      url: SITE,
      author: [
        { '@type': 'Person', name: 'Roger Nick Anaedevha',
          affiliation: { '@type': 'Organization',
            name: 'Institute of Cyber Intelligent Systems, National Research Nuclear University MEPhI' } },
        { '@type': 'Person', name: 'Keiwan Soltani',
          affiliation: { '@type': 'Organization', name: 'Missouri University of Science and Technology' } },
        { '@type': 'Person', name: 'Federico Corò',
          affiliation: { '@type': 'Organization', name: 'University of Padova' } },
      ],
      keywords: KEYWORDS,
      inLanguage: 'en',
    },
    {
      '@type': 'Dataset',
      name: 'UAVs network and navigation end-to-end security corpus',
      description: 'Six UAV security datasets unified under one two-layer schema: '
          + 'swarm mesh, C2 link and intra-vehicle bus at the network layer; GNSS, '
          + 'controller and mission at the autonomy layer. 431,773 schema-validated events.',
      url: 'https://www.kaggle.com/datasets/rogernickanaedevha/uavs-network-and-navigation-end-to-end-security-data',
      identifier: 'https://doi.org/10.34740/kaggle/dsv/18346203',
      license: 'https://creativecommons.org/licenses/by/4.0/',
      keywords: KEYWORDS,
      isAccessibleForFree: true,
      creator: { '@type': 'Person', name: 'Roger Nick Anaedevha' },
    },
    {
      '@type': 'SoftwareApplication',
      name: 'RobustUAVs.ai',
      applicationCategory: 'ResearchApplication',
      operatingSystem: 'Web',
      url: SITE,
      description: 'Interactive artifact: certificate engine, detector operating '
          + 'curve, live fleet simulation, and bring-your-own-data analysis.',
      offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
    },
  ],
};

const head = `
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <link rel="alternate icon" href="/favicon.ico" sizes="32x32">
  <link rel="apple-touch-icon" href="/icon-192.png">
  <meta name="theme-color" content="#0F172A">
  <meta name="description" content="${DESC}">
  <meta name="keywords" content="${KEYWORDS}">
  <meta name="author" content="Roger Nick Anaedevha">
  <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">
  <link rel="canonical" href="${SITE}/">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="RobustUAVs.ai">
  <meta property="og:title" content="${TITLE}">
  <meta property="og:description" content="${DESC}">
  <meta property="og:url" content="${SITE}/">
  <meta property="og:locale" content="en_GB">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="${TITLE}">
  <meta name="twitter:description" content="${DESC}">
  <meta name="citation_title" content="From Wire to Flight: An End-to-End Framework Composing Network Intrusion Detection with Certified Mission Safety for Autonomous UAVs">
  <meta name="citation_author" content="Anaedevha, Roger Nick">
  <meta name="citation_author" content="Soltani, Keiwan">
  <meta name="citation_author" content="Corò, Federico">
  <meta name="citation_public_url" content="${SITE}">
  <script type="application/ld+json">${JSON.stringify(jsonld)}</script>
`;

const noscript = `
<noscript>
  <div style="max-width:44rem;margin:3rem auto;padding:0 1.25rem;font:16px/1.65 system-ui,sans-serif">
    <h1>RobustUAVs.ai</h1>
    <p>An end-to-end UAV security benchmark and a composed network-to-navigation
       certificate. The interactive client needs JavaScript; the substance is below.</p>
    <h2>What this is</h2>
    <p>UAV security research is split in two. Network-layer work studies the swarm
       mesh, the command-and-control link and the intra-vehicle bus. Autonomy-layer
       work studies GNSS spoofing, controller robustness and mission completion.
       Neither half tells you what an attacker who defeats the first can do to the
       second. This project closes that gap with a unified six-source benchmark and
       a composition theorem carrying a detector operating point through to a
       certified Mission-Completion-Rate floor.</p>
    <h2>The six sources</h2>
    <ul>
      <li>UAV-EW-Bench — autonomy, mission and GNSS, 93,600 flights</li>
      <li>UAVIDS-2025 — network, swarm mesh, 122,171 flows</li>
      <li>DATAMUt — network, swarm mesh, per-hop traces</li>
      <li>HCRL UAVCAN — network, intra-vehicle bus, 10 scenarios</li>
      <li>UAV Attack Dataset — autonomy, GNSS, 3 live PX4 flights</li>
      <li>UAV-CAS — network, swarm mesh, flow statistics</li>
    </ul>
    <h2>Artifact</h2>
    <p>The schema, per-dataset adapters, certificate engine, experiment scripts and
       every committed result are browsable at <a href="/artifact/">/artifact/</a>.
       All six datasets are published on Kaggle under
       DOI 10.34740/kaggle/dsv/18346203.</p>
    <p>Roger Nick Anaedevha, Institute of Cyber Intelligent Systems, MEPhI ·
       Keiwan Soltani, Missouri S&amp;T · Federico Corò, University of Padova.</p>
  </div>
</noscript>
`;

let html = readFileSync(file, 'utf8');

if (html.includes('name="description"')) {
  console.log('inject-seo: already injected, skipping');
  process.exit(0);
}

html = html.replace(/<title>.*?<\/title>/i, `<title>${TITLE}</title>`);
if (!/<title>/i.test(html)) html = html.replace('<head>', `<head><title>${TITLE}</title>`);
html = html.replace('</head>', `${head}</head>`);
html = html.replace('</body>', `${noscript}</body>`);
html = html.replace('<html', '<html lang="en"').replace('<html lang="en" lang=', '<html lang=');

writeFileSync(file, html);
console.log(`inject-seo: ${file} — meta, JSON-LD and noscript added`);
