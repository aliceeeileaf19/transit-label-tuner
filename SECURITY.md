# Security policy

## Supported versions

Security fixes are made on the latest release and on `main`. Older snapshots
are not supported separately.

## Reporting a vulnerability

Please use GitHub's **Security → Report a vulnerability** form so the report,
proof of concept and discussion remain private. Do not put exploit details in
a public issue.

If private vulnerability reporting is not yet available, contact the
maintainer through the GitHub profile and ask for a private reporting channel
without including sensitive details in the first message.

Useful reports include the affected browser, a minimal SVG or session file,
steps to reproduce, impact, and whether the bundled demo is affected.

## SVG trust boundary

Transit Label Tuner parses SVG as data and removes common active content before
adopting it into the page: scripts, embedded HTML, event handlers, animation
elements and non-fragment resource URLs. This is defence in depth, not a claim
that arbitrary hostile SVG is safe. Users should load only diagrams they trust.

The project has no telemetry and sends no diagram data to a third-party
service. The browser fetches the SVG URL selected by the user and stores
preferences and diagram-specific drafts in local storage.

---

# 安全政策

安全修正只提供給最新版本與 `main`。請透過 GitHub 的 **Security → Report a
vulnerability** 私下回報，不要在公開 issue 張貼利用方式。若該功能尚未開啟，請先從
維護者的 GitHub 個人頁面聯絡並索取私人回報管道，第一封訊息不要附上敏感細節。

工具會把 SVG 當成資料解析，並在插入頁面前移除常見的主動內容；這是額外防護，不代表
任意惡意 SVG 都安全。請只載入你信任的圖稿。工具沒有遙測，也不會將圖稿送往第三方服務。
