# 验收标准与验收记录：平台登录态管理（spec-014）

## 验收标准

- AC-1（对应 FR-1）：设置页展示两平台登录状态。
- AC-2（对应 FR-2）：点击登录启动 Playwright 真实浏览器打开平台。
- AC-3（对应 FR-3）：自动检测登录成功并保存 storage_state。
- AC-4（对应 FR-4）：有登录态时搜索知网/百度能复用 Cookie 抓结果。
- AC-5（对应 FR-5）：无登录态搜索返回「需登录」提示 + 外链。
- AC-6（对应 FR-6）：登录态过期时标记并提示 + 外链。
- AC-7（对应 FR-7）：退出登录清除登录态。
- AC-8（对应 NFR-2）：登录态文件不入库不入 git。
- AC-9（对应 NFR-3）：登录流程超时自动关闭浏览器。

## 验收步骤

1. 启动后端与前端。
2. 设置页查看两平台登录状态，点登录打开真实浏览器。
3. 手动完成验证，确认系统自动检测并标记已登录。
4. 搜索知网/百度，验证复用 Cookie 拿到结果。
5. 退出登录后搜索，验证「需登录」提示 + 外链。
6. 运行 pytest 通过。

## 验收记录

（由验收 Agent 填写）

| 轮次 | 日期 | 结果（PASS/FAIL/BLOCKED） | 问题说明 | 结论/后续 |
| ---- | ---- | ---- | ---- | ---- |
| 1 | 2026-08-26 | PASS | AC-1~9 全部通过；pytest 219 passed；前端 build 通过；独立 mock Playwright 验证登录成功检测/超时/需登录/过期/退出均符合预期。仅 1 处非阻塞观察：`_html.looks_like_verification` 为死代码（未在 provider/browser 中调用，验证页检测实际走 `browser.is_verification_page` 的 URL/title 判定），不影响功能。 | 通过，可进入收尾 |

## 验收结论

**PASS**。AC-1~AC-9 全部满足，无回归（后端 219 项测试全部通过、前端 `npm run build` 成功）。独立使用 TestClient + mock Playwright 实际验证了登录态存取、状态流转、登录成功自动检测并保存 storage_state、无登录态抛「需登录」、过期抛「过期」、退出删除、以及登录流程超时自动关闭浏览器（NFR-3）。登录态文件路径 `backend/data/platform_sessions/<platform>.json` 已被 `.gitignore` 的 `data/` 规则覆盖（`git check-ignore` 验证通过），满足不入库不入 git（NFR-2）。

### AC 逐条判定

- **AC-1 PASS**：`GET /api/platforms` → `sessions.list_states()`（`backend/app/main.py:226-228`）返回 cnki/baidu_xueshu 两平台状态；前端 `PlatformLogin.tsx` 以表格展示四态（未登录/登录中/已登录/已过期），`App.tsx:241-245` 设置页接入。
- **AC-2 PASS**：点击登录 → `POST /api/platforms/{platform}/login` 在独立线程调用 `browser.run_login`（`main.py:237`）；`browser.py:71` `chromium.launch(headless=False)` 打开真实浏览器并 `goto` 平台搜索页（mock 验证 `launch(headless=False)`）。
- **AC-3 PASS**：`browser.py:76-82` 轮询 `is_verification_page(page.url, page.title())`，验证页消失即 `save_state(context.storage_state())` 并标记 `logged_in`；mock 验证「验证页→结果页」自动保存 storage_state。
- **AC-4 PASS**：`cnki.py:27`/`baidu_xueshu.py:27` 有登录态时 `asyncio.to_thread(browser.fetch_search_html)`，`browser.py:114` `new_context(storage_state=state)` 复用 Cookie；mock 验证有态时返回渲染 HTML。
- **AC-5 PASS**：无登录态 `cnki.py:26`/`baidu_xueshu.py:26` 抛 `LoginRequiredError`，`aggregator.py:72` fallback 记 `need_login=True`；前端 `App.tsx:190-194` 显示「需要登录」提示 + 外链。
- **AC-6 PASS**：搜索遇验证页 `browser.py:118-120` 标记 `expired` 并抛 `LoginExpiredError`，`aggregator.py:73` fallback 记 `expired=True`；前端 `App.tsx:192-194` 显示「登录态已过期」提示 + 外链。
- **AC-7 PASS**：`POST /api/platforms/{platform}/logout` → `delete_state` + 置 `not_logged_in`（`main.py:247-252`）；测试 `test_logout_deletes_state` 通过。
- **AC-8 PASS**：登录态存 `data/platform_sessions/<platform>.json`；`git check-ignore` 验证 `backend/data/platform_sessions/cnki.json` 命中 `.gitignore:16` 的 `data/` 规则。
- **AC-9 PASS**：`browser.py:23` `LOGIN_TIMEOUT_SECONDS=300`，`browser.py:76-84` deadline 轮询 + `finally` 关闭浏览器，超时置 `not_logged_in`；mock 验证超时自动关闭浏览器。

### 测试运行情况

- 后端：`python -m pytest -q` → `219 passed in 7.10s`。
- 前端：`npm run build` → `tsc && vite build` 成功（存在 chunk >500kB 体积告警，非错误）。
- 独立验证脚本（TestClient + mock Playwright）全部通过：登录成功检测/超时关闭/无态抛需登录/过期抛过期/有态返回 HTML/退出删除文件。
