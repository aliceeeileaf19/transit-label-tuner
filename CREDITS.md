# Credits and references · 技術來源與參考

This file lists the **techniques** this tool relies on and where they are
properly documented. It is a reading list, not a claim that any of this code
was copied from these sources — every routine here is an independent
implementation, and where a method has a canonical description, that
description is cited so you can check the implementation against it.

本檔列出本工具用到的**技術方法**以及它們的權威出處。這是閱讀清單，不是說程式碼
抄自這些來源——每個函式都是獨立實作；凡是有公認定義的方法，都附上出處，方便你拿
原始定義去核對實作是否正確。

No third-party code, fonts, icons or images are bundled. The tool has no
dependencies and makes no network requests.

本工具不內含任何第三方程式碼、字型、圖示或圖片，無相依套件，也不發出任何網路請求。

---

## Geometry · 幾何

**Separating Axis Theorem (SAT)** — used to decide whether two rotated text
boxes overlap. Two convex polygons are disjoint if and only if some axis
perpendicular to one of their edges separates their projections.
用於判斷兩個帶旋轉的文字框是否重疊。

- Christer Ericson, *Real-Time Collision Detection*, Morgan Kaufmann, 2004 —
  chapter 5, "Basic Primitive Tests".
- Implemented in `overlap()` / `axes()`.

**Crossing-number point-in-polygon test** — used to decide whether a station
dot's centre falls inside a label box. The odd-even ray-casting formulation.
用於判斷站點圓心是否落在標籤框內（奇偶射線法）。

- W. Randolph Franklin, *PNPOLY — Point Inclusion in Polygon Test*,
  <https://wrfranklin.org/Research/Short_Notes/pnpoly.html>
- Implemented in `circPoly()`, together with a point-to-segment distance test
  so a dot that merely touches an edge still counts as a hit.

**Axis-aligned bounding-box pre-filter** — the cheap rejection pass run before
any SAT test. Standard broad-phase practice; see Ericson above, chapter 6.
在做 SAT 之前先用軸對齊邊界框快速排除，是碰撞偵測的標準前置階段。

- Implemented in `bounds()` / `cheap()`.

**Quadratic Bézier corner rounding with setback** — the line-drawing
convention: stop `setback` units short of a corner, then use the corner
itself as the quadratic control point. This keeps a rounded corner exactly
tangent to both segments.
描線的圓角慣例：在距轉角 setback 處收線，再以轉角本身作為二次貝茲控制點。

- SVG path `Q` command: *Scalable Vector Graphics (SVG) 1.1*, §8.3.6,
  <https://www.w3.org/TR/SVG11/paths.html#PathDataQuadraticBezierCommands>
- Implemented in `ext2PathD()`.

---

## Cartography and map labelling · 製圖與標籤配置

**Eight-position label placement around a point feature.** The idea that a
label attached to a point should occupy one of a small, ranked set of
positions — rather than any arbitrary offset — is the foundation of the
quadrant system in `CONFIG.slots`.
「點狀物件的標籤只能落在少數幾個既定位置」是本工具八象限系統的思想來源。

- Eduard Imhof, "Positioning Names on Maps", *The American Cartographer* 2(2),
  1975, pp. 128–144. The original statement of the preference ordering.
- Jon Christensen, Joe Marks, Stuart Shieber, "An Empirical Study of
  Algorithms for Point-Feature Label Placement", *ACM Transactions on
  Graphics* 14(3), 1995, pp. 203–232.

**Octilinear (eight-direction) schematic layout.** The convention that transit
diagrams use only horizontal, vertical and 45° segments.
路網圖只用水平、垂直與 45° 三種方向的慣例。

- Harry Beck's 1933 London Underground diagram is the origin of the
  convention in practice.
- Martin Nöllenburg and Alexander Wolff, "Drawing and Labeling High-Quality
  Metro Maps by Mixed-Integer Programming", *IEEE Transactions on
  Visualization and Computer Graphics* 17(5), 2011, pp. 626–641.
- Jonathan Stott, Peter Rodgers, Juan Carlos Martínez-Ovando, Stephen Walker,
  "Automatic Metro Map Layout Using Multicriteria Optimization", *IEEE TVCG*
  17(1), 2011, pp. 101–114.

This tool deliberately does **not** solve the layout problem those papers
address. It assumes a human has already made the layout decisions and only
provides a way to nudge the result, check it, and record what was changed.

本工具刻意**不**處理上述論文所解的自動佈局問題。它假設佈局已由人決定，只負責讓人
微調、即時檢查，並把改了什麼記錄下來。

---

## Web platform · 網頁平台

**SVG coordinate transforms.** All geometry is converted into the inner map's
user coordinate system via `getScreenCTM()` and its inverse, so zoom and pan
cannot change any verdict.
所有幾何都透過 `getScreenCTM()` 換算到內層地圖的使用者座標系，因此縮放平移不會改變
任何判定結果。

- MDN, *SVGGraphicsElement.getScreenCTM()*,
  <https://developer.mozilla.org/docs/Web/API/SVGGraphicsElement/getScreenCTM>

**`isPointInStroke()`** — used for the name-versus-route-line test, sampling
nine points per label.
用於「站名是否被路線穿過」的判定，每個標籤取九個取樣點。

- MDN, *SVGGeometryElement.isPointInStroke()*,
  <https://developer.mozilla.org/docs/Web/API/SVGGeometryElement/isPointInStroke>

**Accessibility.** Live regions, dialog semantics, visible focus rings and the
reduced-motion opt-out follow:
無障礙做法（即時區域、對話框語意、可見焦點框、減少動態）依循：

- W3C, *WAI-ARIA Authoring Practices Guide*,
  <https://www.w3.org/WAI/ARIA/apg/>
- W3C, *Web Content Accessibility Guidelines (WCAG) 2.2*,
  <https://www.w3.org/TR/WCAG22/>
- CSS Media Queries Level 5, `prefers-reduced-motion`,
  <https://www.w3.org/TR/mediaqueries-5/#prefers-reduced-motion>

**Typography.** No fonts are bundled. The interface uses the operating
system's own UI font stack.
不內含字型，介面使用作業系統本身的 UI 字型堆疊。

---

## Demo data · 示範資料

`demo/demo-map.svg` is generated by `tools/make_demo_map.py`. The network,
station names, line colours and coordinates are entirely invented for this
repository and do not depict any real transit system.

`demo/demo-map.svg` 由 `tools/make_demo_map.py` 產生。其路網、站名、路線顏色與座標
全為本專案虛構，不對應任何真實運輸系統。
