## Summary

This PR covers two interconnected workstreams from the `fix/web-discovery-bing-quality` branch:

### 1. Bing Web Discovery Quality Fixes
- **Market/language**: Switched Bing requests to Chinese market (`mkt=zh-CN`, `setlang=zh-hans`) for better Chinese policy/contest results
- **Double-encoding fix**: Raw filter params now passed directly, letting `httpx` encode exactly once — fixes date filtering that was broken by `%` double-encoding
- **Canonical URL extraction**: Parse Bing `/ck/a` tracking links to extract real target URLs from the `u` parameter, enabling stable `source_url` dedup
- **RSS-first parsing**: Prefer Bing's public RSS feed over HTML parsing since `li.b_algo` DOM is unreliable on current Chinese Bing; HTML parser retained as fallback
- **Query quality**: Added contest/registration intent keywords and exclusion terms; skip low-value domains (Bing, Google, YouTube, app stores)

### 2. Tenant Contest Sources & Observability
- **Enterprise sources CRUD**: `POST/GET/PUT/DELETE /api/tenant/contest-sources` for static HTML sources with preflight validation
- **TenantContestCrawler**: Public static HTML only; rejects credentials, internal IPs, non-HTML, oversized responses
- **contest_runs**: Last 10 run statuses per subscription/source with 5-minute cooldown
- **Tenant isolation**: `origin_type=tenant` with `tenant_contest_source_items` association; filtering/scoping per current tenant
- **Official source presets**: cnmaker/wnd/gxt/cq with region picker; Agent-powered suggestions for unlisted regions
- **Daily pipeline**: Tenant sources run after official, before keyword discovery; manual runs skip notification callbacks
- **Feed fix**: Contest feed push had gone silent since July 9; daily pipeline re-wired to tenant-level status summary
- **Frontend**: Search history panel, "My Contest Sources" CRUD form, independent filter/management data loading

### Migrations
- `b1c2d3e4f5a6`: tenant_contest_sources, contest_runs tables
- `c2d3e4f5a6b7`: preset_source_id on tenant_contest_sources

### Test Plan
- [x] 42 pytest passed (Bing search adapter, contest discovery, policy ingest, feed)
- [x] `python -m compileall api/app` passed
- [x] Real Bing smoke test: 10 Chinese original results
- [x] `npm run build` (UI) passed
- [ ] Deploy to .222 and verify tenant contest sources CRUD
- [ ] Verify contest feed push resumes after deploy
- [ ] Verify second tenant sees reused public contests but isolated feed

🤖 Generated with [Claude Code](https://claude.com/claude-code)
