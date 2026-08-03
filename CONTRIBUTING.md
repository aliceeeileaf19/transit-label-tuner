# Contributing

Thanks for looking. This is a small, deliberately dependency-free project, so
the setup is short — but a few of its rules are load-bearing and will bite you
if you work around them instead of with them.

繁體中文速查在最下面。

---

## Getting it running

```sh
git clone https://github.com/aliceeeileaf19/transit-label-tuner.git
cd transit-label-tuner
python3 -m http.server 8000
# open http://localhost:8000/
```

There is nothing to install. No build step, no package manager, no bundler.
`index.html` is the whole application; `demo/demo-map.svg` is its sample input.

`file://` will not work — the tool loads its map with `fetch()`, and browsers
block that on the file protocol. Any static server is fine.

## Before you open a pull request

```sh
python3 tools/static_audit.py    # translations, themes, demo contract, screenshots
python3 tools/selftest.py        # 22 headless checks
```

It needs Chrome or Chromium; pass `--chrome /path/to/binary` if it cannot find
one. The same suite runs in CI on every push.

If you changed the demo network, regenerate it rather than editing the SVG:

```sh
python3 tools/make_demo_map.py
```

CI asserts that `demo/demo-map.svg` is byte-identical to what the generator
produces, so a hand-edit will fail the build. That is intentional — see below.

---

## Things that are deliberate, not accidental

Please read this section before "fixing" any of it. Each of these looks like
an oversight and is not.

**The tool never writes SVG.** It exports a move list. If you find yourself
adding a "save SVG" button, you have removed the entire reason the project
exists: a generator regenerates the artwork, and a hand-edited SVG is thrown
away on the next render. Edits have to survive regeneration, so they are
recorded as data, not as pixels.

**The demo map is generated, never hand-edited.** It is the executable version
of the map contract in the README. If it drifts from the generator, the
document and the sample stop agreeing and the contract becomes folklore.

**Snapping refuses values the drawing does not already use.** Codes may only
land on the eight configured quadrants; slanted labels may only sit on the
configured angle ladder; a label with no `rotate()` cannot be given one. These
are not arbitrary limits — they stop a drag from quietly inventing a new
convention that the rest of the diagram does not follow. Widening them should
be a config change, not a code change.

**The exported move list stays in English.** It is consumed by a machine. The
interface is bilingual; the artifact is not. Same for `Error()` messages thrown
by the `window.*` scripting hooks — those are read by developers.

**Every interaction has a scripting hook that runs the same path as the mouse.**
Drag behaviour cannot be verified by a screenshot, so `applyMove`, `dragPx`,
`moveBlock` and the rest exist to make it testable. If you add an interaction,
add its hook and route it through the same snap and guard code — a parallel
path that skips `scheduleCount()` is exactly the bug that motivated the rule.

**Yielding uses `nextFrame()`, not bare `requestAnimationFrame`.** A headless
renderer or a backgrounded tab can throttle rAF to nothing, and anything
awaiting it never resumes. `nextFrame()` races rAF against a timer so progress
is guaranteed. Reintroducing a bare rAF await will make the boot sequence hang
intermittently, which is miserable to diagnose.

**The diagram keeps its light paper in both themes.** It is the document being
edited, not part of the interface. The drag-state colours (`.dt-*`) are drawn
on that paper and are theme-independent for the same reason.

**SVG input is data, never application code.** Keep all map loading through
`parseSafeSvg()`. It removes active elements, event handlers and external
resource URLs before adoption into the page. Do not restore direct
`innerHTML` insertion, and add a regression probe when the boundary changes.

---

## How to make common changes

**Support a different diagram.** Edit the `CONFIG` block at the top of
`index.html` — selectors, quadrant slots, angle ladder, layout blocks,
proposal-box markers, limits. If something diagram-specific is *not* reachable
from `CONFIG`, that is a bug worth reporting; the goal is that nobody needs to
touch the rest of the file.

**Add an interface language.** Copy the `en` block inside `I18N`, translate the
values, and the switch picks it up. Missing keys fall back to English and then
to the key itself, so a partial translation is visibly partial rather than
blank. Keep `data-i18n` on static markup and `t(key, params)` for anything
built at runtime.

**Add a theme.** Add a `:root[data-theme="yours"]` block declaring the same
custom properties, then extend the toggle. The rules below the theme blocks
should not need to change — if you find yourself adding a rule to make a theme
work, the value you need is probably missing from the token set, and adding it
there helps every theme.

**Change the move-list format.** Bump `CONFIG.formatVersion`. Drafts and
session files check it, so an old draft will be refused rather than applied to
a format it does not match.

---

## Reporting a bug

The single most useful thing you can include is whether it reproduces on the
demo map. If it only happens with your own diagram, the map contract in the
README is usually where the mismatch is — the issue form asks for the parts
that matter.

## Style

Match the surrounding code. It is plain ES2017-ish JavaScript with no
transpiler, comments explain *why* rather than *what*, and the CSS names
values through semantic custom properties. There is no linter and no
formatter; there is also not much code.

---

## 繁體中文速查

- **跑起來**：`python3 -m http.server 8000`，然後開 `http://localhost:8000/`。
  沒有任何安裝步驟。`file://` 不能用（`fetch()` 會被瀏覽器擋）。
- **送 PR 前**：先跑 `python3 tools/static_audit.py`，再跑
  `python3 tools/selftest.py`（22 項，需要 Chrome）。
- **動過示範圖**：跑 `python3 tools/make_demo_map.py` 重生，**不要手改 SVG**。
  CI 會比對產生器輸出，手改一定失敗。
- **換自己的地圖**：只改 `index.html` 最上方的 `CONFIG`。如果有跟地圖相關的東西
  沒辦法從 `CONFIG` 改到，那是 bug，請開 issue。
- **加語言**：複製 `I18N` 裡的 `en` 區塊翻譯即可。
- **加主題**：新增一組 `:root[data-theme="…"]` 變數即可，下面的規則不該需要改。
- **幾件刻意的設計，別當成漏洞修掉**：工具不寫 SVG（只出搬動清單）、示範圖必須由
  產生器產生、吸附刻意拒絕圖面上原本不存在的值、匯出的清單固定英文、每個互動都要有
  走同一條路徑的程式化入口、讓出畫格一律用 `nextFrame()` 而不是裸的
  `requestAnimationFrame`、地圖在兩種主題下都維持淺色紙面。
- **SVG 是資料，不是程式**：載入必須通過 `parseSafeSvg()`，不可改回直接塞入
  `innerHTML`。
