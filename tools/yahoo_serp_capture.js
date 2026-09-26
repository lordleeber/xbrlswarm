#!/usr/bin/env node
// Capture a live Yahoo SERP as a Step-44-style fixture (.html.gz, .headers.json, .meta.json).
//
// Yahoo search sends plain HTTP clients through a /_bv/ bot-validation redirect that curl
// cannot complete, so this drives a headed Chromium via Playwright and saves the final
// HTTP 200 document response. See tests/fixtures/yahoo/README.md.
//
// Usage:
//   node tools/yahoo_serp_capture.js <scenario> <query> [--out DIR]
//
// Playwright is resolved from PLAYWRIGHT_MODULE (a path to the playwright package) or the
// normal Node module path. The manifest entry is printed, not written.

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

const SEARCH_URL = 'https://tw.search.yahoo.com/search?p=';
const KEPT_RESPONSE_HEADERS = ['cache-control', 'content-type', 'date', 'server', 'vary'];

function usage(message) {
  if (message) console.error(`error: ${message}`);
  console.error('usage: node tools/yahoo_serp_capture.js <scenario> <query> [--out DIR]');
  process.exit(2);
}

function parseArgs(argv) {
  const positional = [];
  let out = path.join(__dirname, '..', 'tests', 'fixtures', 'yahoo');
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === '--out') {
      out = argv[i + 1];
      i += 1;
    } else {
      positional.push(argv[i]);
    }
  }
  if (positional.length !== 2 || !out) usage();
  const [scenario, query] = positional;
  if (!/^[a-z][a-z0-9_]*$/.test(scenario)) usage('scenario must be snake_case');
  return { scenario, query, out };
}

// Match Python's json.dumps(sort_keys=True, ensure_ascii=False, indent=2) used by the fixtures.
function sortKeys(value) {
  if (Array.isArray(value)) return value.map(sortKeys);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, sortKeys(value[key])]));
  }
  return value;
}

function writeJson(file, value) {
  fs.writeFileSync(file, `${JSON.stringify(sortKeys(value), null, 2)}\n`);
}

async function capture(page, url) {
  const chain = [];
  let final = null;
  const onResponse = (response) => {
    if (response.request().resourceType() !== 'document' || response.frame() !== page.mainFrame()) {
      return;
    }
    chain.push({
      location: response.headers().location || null,
      status: response.status(),
      url: response.url(),
    });
    if (response.status() === 200) final = response;
  };
  page.on('response', onResponse);
  const retrievedAt = new Date().toISOString();
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
  } catch (error) {
    // /_bv/ intermittently answers HTTP 500; Chromium then raises a navigation error.
    console.error(`navigation failed: ${error.message.split('\n')[0]}`);
  }
  await page.waitForTimeout(2000);
  page.off('response', onResponse);
  return { chain, final, retrievedAt };
}

async function main() {
  const { scenario, query, out } = parseArgs(process.argv.slice(2));
  const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
  const url = SEARCH_URL + encodeURIComponent(query);

  const browser = await chromium.launch({ headless: false });
  try {
    const context = await browser.newContext({
      locale: 'zh-TW',
      viewport: { width: 1280, height: 900 },
    });
    const page = await context.newPage();
    const { chain, final, retrievedAt } = await capture(page, url);
    const hops = chain.map((hop) => hop.status).join(' > ') || '(none)';
    if (!final) {
      console.error(`no HTTP 200 document; redirect chain: ${hops}`);
      console.error('treat as a retryable fetch failure and retry later; nothing was written');
      process.exitCode = 1;
      return;
    }

    const body = await final.body();
    const requestHeaders = await final.request().allHeaders();
    const responseHeaders = await final.allHeaders();
    const keptRequestHeaders = Object.fromEntries(
      Object.entries(requestHeaders).filter(([key]) => !key.startsWith(':') && key !== 'cookie'),
    );
    const keptResponseHeaders = Object.fromEntries(
      KEPT_RESPONSE_HEADERS.filter((key) => key in responseHeaders)
        .map((key) => [key, responseHeaders[key]]),
    );
    const gzipped = zlib.gzipSync(body, { level: 9 });
    const sha256 = crypto.createHash('sha256').update(body).digest('hex');

    fs.mkdirSync(out, { recursive: true });
    fs.writeFileSync(path.join(out, `${scenario}.html.gz`), gzipped);
    writeJson(path.join(out, `${scenario}.headers.json`), keptResponseHeaders);
    writeJson(path.join(out, `${scenario}.meta.json`), {
      client: `chromium ${browser.version()} (Playwright, headed)`,
      origin: 'live',
      redirect_chain: chain,
      request: { headers: keptRequestHeaders, method: 'GET', url },
      response: {
        body_file: `${scenario}.html.gz`,
        content_encoding: 'gzip',
        final_url: final.url(),
        headers_file: `${scenario}.headers.json`,
        sha256,
        size_bytes: body.length,
        status: final.status(),
        stored_size_bytes: gzipped.length,
      },
      retrieved_at: retrievedAt,
    });

    console.log(`captured ${scenario}: ${hops}, ${body.length} bytes, title=${await page.title()}`);
    console.log('manifest entry (add page_kind and review before committing):');
    console.log(JSON.stringify({
      scenario,
      origin: 'live',
      page_kind: 'search_results',
      body: `${scenario}.html.gz`,
      headers: `${scenario}.headers.json`,
      metadata: `${scenario}.meta.json`,
      sha256,
    }, null, 2));
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
