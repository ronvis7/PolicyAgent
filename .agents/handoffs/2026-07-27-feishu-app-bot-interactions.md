# Feishu app bot interactive contest cards

## Scope

- Branch: `codex/feishu-app-bot-interactions`
- Keep the existing custom group Webhook fully compatible.
- Add an enterprise app bot as the preferred notification channel.
- Handle “不再提醒此赛事” inside Feishu without navigating to PolicyAgent.
- Update the original card after ignoring the contest.

## Implemented

- Extended `tenant_settings.feishu_config` JSONB with app bot credentials, Verification Token, target `chat_id`, and enable state; no migration is required.
- Settings API and UI accept app bot configuration but never return secret plaintext.
- App bot obtains `tenant_access_token`, sends interactive cards to `chat_id`, and converts the legacy signed ignore URL into a native card callback value.
- If app sending fails, the notifier sends once through the existing Webhook. Webhook-only tenants behave as before.
- Added public Feishu callback endpoints:
  - `POST /api/integrations/feishu/card-actions`
  - `POST /api/integrations/feishu/events`
- Callback tenant resolution validates App ID and Verification Token. The same App ID cannot be enabled for two tenants, and card actions are restricted to the configured group.
- Ignore callbacks update the tenant-scoped Feed item to `ignored`, then update the original Feishu message to show an ignored status and disabled button.
- Bot-added/bot-removed events can automatically bind or clear the target `chat_id`.

## Feishu configuration

- Required app permissions:
  - `im:message:send_as_bot`
  - `im:message:update`
- Optional for automatic group binding:
  - `im:chat.members:bot_access`
  - events `im.chat.member.bot.added_v1` and `im.chat.member.bot.deleted_v1`
- Configure card callback to `/api/integrations/feishu/card-actions`.
- Configure event callback to `/api/integrations/feishu/events` only when automatic `chat_id` binding is desired.
- Do not enable Encrypt Key in this version; encrypted callbacks are rejected explicitly.
- The callback URL must be publicly reachable over HTTPS.

## Verification

- `python -m compileall -q api/app api/tests`: passed.
- Targeted backend suite: 56 passed.
- Full backend suite: 412 passed, 7 skipped, 1 setup error because local PostgreSQL on `localhost:5432` was unavailable; the failure is the existing status endpoint startup test, not a changed feature test.
- `npm run lint`: 0 errors, 30 existing warnings.
- `npm run build`: passed.
- `git diff --check`: passed.

## Remaining acceptance

- ~~Deploy to an HTTPS-reachable environment.~~ ✅ Merged to main (`cfc9775`) and deployed to .222 (http://118.196.142.222:8888), api/ui/sandbox healthy.
- Fill the tenant’s real App ID, App Secret, Verification Token, and target `chat_id`.
- Publish the Feishu app version after permissions/callback changes.
- Send a test card, click “不再提醒此赛事”, and visually confirm the in-place ignored card state.
