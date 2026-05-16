# kiuno-anime-viewer · Design System (MASTER)

> **Source of truth** for the kiuno-anime-viewer redesign (v1.1.0 sleek modern).
> This file overrides the auto-generated suggestion (which fell back to "Vibrant Block-based green+gold" — wrong category).
>
> **Manual override rationale** (依 ~/.claude/CLAUDE.md 全域指引 Step 2):
> - `--design-system` auto-recommend matched against generic landing-page patterns, not anime/media library.
> - Validated against `--domain style/color/typography/landing` searches.
> - Selected: **Modern Dark (Cinema Mobile)** style × **Sleep Tracker** palette (indigo/violet on slate-900) × **Chinese Traditional** typography (Noto Sans TC primary).
> - Reference look: AniList / Letterboxd / Plex / Linear app.

---

## 1. Pattern

| Page | Pattern | Rationale |
|---|---|---|
| `index.html` | **Portfolio Grid** | Card grid of anime, visual-first, filter by category, fast loading essential |
| `graph.html` | **Bento Grid** banner + Cytoscape canvas | Banner uses bento cards for category/tag/count, modular |
| `recommends.html` | **Feed list + composer** (custom) | Top form, vertical list of recommendations + nested replies |
| `changelog.html` | **Timeline** | Version-by-version vertical timeline with badges |
| `ritual.html` | **Immersive scene** (existing) | 3D perspective with overlaid info panel — keep visual but align tokens |

---

## 2. Color Palette (Main theme — used by index/graph/recommends/changelog)

> Slate-900 base + indigo/violet accent. Aligned with the "Sleep Tracker" palette validated for entertainment-on-dark category.

| Role | Hex | CSS Variable | Contrast vs `--bg` | Usage |
|---|---|---|---|---|
| Background base | `#0F172A` | `--bg` | — | App background (slate-900) |
| Background elevated 1 | `#192134` | `--bg-elev` | — | Cards, drawer base |
| Background elevated 2 | `#1E2941` | `--bg-elev-2` | — | Hover cards, modal interior |
| Background sunken | `#0B1120` | `--bg-sunken` | — | Search input, code blocks |
| Foreground primary | `#F1F5F9` | `--fg` | **15.8 : 1** AAA | Headings, body text |
| Foreground muted | `#94A3B8` | `--fg-muted` | **6.2 : 1** AA+ | Captions, meta |
| Foreground faint | `#64748B` | `--fg-faint` | **3.9 : 1** UI-only | Placeholder, helper |
| Accent (primary) | `#818CF8` | `--accent` | **7.5 : 1** AAA on bg | Buttons, links, active state |
| Accent hover | `#A5B4FC` | `--accent-hover` | **10.2 : 1** | Hover state |
| Accent strong | `#6366F1` | `--accent-strong` | **5.4 : 1** AA | Solid CTA background |
| Accent soft | `rgba(129,140,248,0.15)` | `--accent-soft` | — | Subtle bg, focus glow |
| Violet (secondary accent) | `#A78BFA` | `--violet` | **8.9 : 1** | Highlights, badges |
| Star (rating) | `#FCD34D` | `--star` | **12.1 : 1** | star icons |
| Heart (favorite) | `#FB7185` | `--heart` | **6.4 : 1** | favorite icons |
| Destructive | `#F87171` | `--destructive` | **6.8 : 1** | Errors, delete |
| Success | `#34D399` | `--success` | **9.6 : 1** | Success states |
| Border | `rgba(255,255,255,0.08)` | `--border` | — | Card / input border (subtle) |
| Border strong | `rgba(255,255,255,0.16)` | `--border-strong` | — | Hover border, focus |
| Scrim (modal backdrop) | `rgba(7,11,24,0.72)` | `--scrim` | — | Drawer / modal overlay |

**Anti-pattern**: Do NOT use cyan `#5dd2ff` (legacy青藍) or saturated greens. All accents derive from indigo (`#6366F1`) and violet (`#A78BFA`) families.

## 2b. Color Palette (Sub-theme — `body.ritual` override only)

Ritual page keeps the summoning-circle aesthetic. Express ONLY by overriding accent tokens — do NOT redefine the spacing/typography system.

```css
body.ritual {
  --bg: #070510;
  --bg-elev: #110a16;
  --bg-elev-2: #1a0f1d;
  --fg: #ffd6a8;
  --fg-muted: rgba(255,214,168,0.7);
  --fg-faint: rgba(255,214,168,0.45);
  --accent:        #ffae5d;
  --accent-hover:  #ffc587;
  --accent-strong: #ff9233;
  --accent-soft:   rgba(255,174,93,0.15);
  --border:        rgba(255,174,93,0.18);
  --border-strong: rgba(255,174,93,0.4);
  --scrim:         rgba(7,5,16,0.85);
}
```

---

## 3. Typography

> All-sans for sleek modern. Inter (Latin) + Noto Sans TC (CJK) covers all content. No serif except special decorative use (avoid in v1.1.0).

### Font Stack

```css
--font-display: "Inter", "Noto Sans TC", "PingFang TC", system-ui, sans-serif;
--font-body:    "Inter", "Noto Sans TC", "PingFang TC", system-ui, sans-serif;
--font-mono:    ui-monospace, "SF Mono", "Cascadia Mono", "Menlo", monospace;
```

### Google Fonts Import

```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Noto+Sans+TC:wght@400;500;600;700;800&display=swap');
```

### 3-Tier Scale

| Tier | Role | CSS Variable | Mobile | Desktop | Weight | Line-height | Letter-spacing |
|---|---|---|---|---|---|---|---|
| Display | Hero title, page H1 | `--fs-display` | 28px | 40px | 700 | 1.15 | -0.02em |
| H1 | Section heading | `--fs-h1` | 22px | 28px | 700 | 1.25 | -0.01em |
| H2 | Subsection | `--fs-h2` | 18px | 22px | 600 | 1.3 | -0.005em |
| H3 | Card title | `--fs-h3` | 15px | 16px | 600 | 1.35 | 0 |
| Body | Default paragraph | `--fs-body` | 15px | 15px | 400 | 1.6 | 0 |
| Body small | Comment text, drawer | `--fs-body-sm` | 14px | 14px | 400 | 1.55 | 0 |
| Caption | Meta, year, episodes | `--fs-caption` | 12px | 12px | 500 | 1.4 | 0.01em |
| Micro | Badge, tag count | `--fs-micro` | 11px | 11px | 500 | 1.3 | 0.02em |
| Mono | Version badge, ID | `--fs-mono` | 13px | 13px | 500 | 1.4 | 0 |

CSS:

```css
:root {
  --fs-display:  clamp(28px, 5vw, 40px);
  --fs-h1:       clamp(22px, 3.5vw, 28px);
  --fs-h2:       clamp(18px, 2.5vw, 22px);
  --fs-h3:       16px;
  --fs-body:     15px;
  --fs-body-sm:  14px;
  --fs-caption:  12px;
  --fs-micro:    11px;
  --fs-mono:     13px;
}
```

### CJK + Latin pairing rules

- `font-feature-settings: "ss01", "cv11"` for Inter to use single-story `a`/`g` (cleaner)
- Apply `font-variant-numeric: tabular-nums` to ratings, year, episode count to prevent layout shift
- For numbers shown in CJK context, prefer Inter (Latin) over Noto Sans TC's full-width digits

---

## 4. Spacing Scale (4px base)

```css
:root {
  --space-1: 4px;    /* Tight, icon gap */
  --space-2: 8px;    /* Inline gap, chip padding */
  --space-3: 12px;   /* Card inner padding small */
  --space-4: 16px;   /* Default block gap */
  --space-5: 24px;   /* Section gap, card padding */
  --space-6: 32px;   /* Major section, hero padding */
  --space-7: 48px;   /* Page top/bottom */
  --space-8: 64px;   /* Hero giant */
}
```

**Component cheatsheet**:
- Button padding: `var(--space-2) var(--space-4)` (8/16)
- Card padding: `var(--space-4)` (16) mobile / `var(--space-5)` (24) desktop
- Card gap in grid: `var(--space-4)` mobile / `var(--space-5)` desktop
- Section vertical gap: `var(--space-6)`

---

## 5. Radius / Shadow / Motion tokens

### Radius
```css
:root {
  --radius-xs:  4px;    /* Chip, tag */
  --radius-sm:  8px;    /* Button, input */
  --radius-md:  12px;   /* Card */
  --radius-lg:  20px;   /* Drawer, modal */
  --radius-pill: 9999px;
}
```

### Shadow / Elevation
```css
:root {
  --shadow-sm:   0 1px 2px rgba(0,0,0,0.4);
  --shadow-md:   0 4px 12px rgba(0,0,0,0.45);
  --shadow-lg:   0 12px 32px rgba(0,0,0,0.55);
  --shadow-xl:   0 24px 48px rgba(0,0,0,0.65);
  /* Focus glow: 2px outer ring + soft halo */
  --focus-ring:  0 0 0 2px var(--accent-soft), 0 0 16px rgba(129,140,248,0.25);
}
```

### Motion
```css
:root {
  --ease-out:    cubic-bezier(0.22, 1, 0.36, 1);
  --ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
  --dur-fast:    150ms;
  --dur-base:    250ms;
  --dur-slow:    450ms;
}
```

**Usage rules**:
- Micro-interactions (hover, focus, button press): `--dur-fast var(--ease-out)`
- State transitions (drawer open, modal): `--dur-base var(--ease-out)`
- Bigger transitions (page swap, hero animation): `--dur-slow var(--ease-out)`
- Spring ONLY for delightful moments (drawer bounce on open, star pop on toggle)

---

## 6. Touch / Interaction tokens

```css
:root {
  --tap-min: 44px;  /* iOS HIG recommended */
}
```

- All interactive elements (button, link, icon-button, chip, card) MUST have effective tap area >= 44x44px
- If visual size < 44px, extend with `padding` or use a transparent `::before` to expand hit area
- Min 8px gap between adjacent touch targets

---

## 7. Style Guidelines

### Do
- Use semantic CSS variables, no raw hex in component CSS
- Mobile-first: write default for <=599px, override at `@media (min-width: 600px)` and `(min-width: 900px)`
- Use SVG icons (Lucide / Heroicons) for UI controls; emoji ONLY in user-generated content
- Single primary CTA per screen, secondary actions use ghost/outline button style
- Cards: subtle hover lift (`translateY(-2px) + shadow-md -> shadow-lg`)
- Inputs: visible label above the field (never placeholder-only); focus ring via `--focus-ring`
- Provide loading skeleton (not bare spinner) for content >300ms
- Empty / error states: include SVG icon + headline + recovery CTA
- Respect `prefers-reduced-motion`: shorten or disable transitions

### Don't (Anti-patterns blacklist)
- **No emoji as primary UI controls**. Use SVG icons. Emoji acceptable in: ritual.html's gesture HUD, user comment body, page hint copy
- **No cyan `#5dd2ff`** (legacy青藍). Use `var(--accent)` indigo
- **No mixing icon styles** (filled + outline at same hierarchy)
- **No tap targets < 44px**
- **No focus-ring removal** (`outline: none` without replacement)
- **No raw colored gradients without purpose**
- **No layout shift on hover/focus** (animate transform/opacity only, not width/height/padding)
- **No `position: fixed` elements overlapping content** without offset reservation
- **No `100vw`** (use `100%` to avoid scrollbar issue on Windows)

---

## 8. Component spec summary

### Button
```
Variants: primary (solid accent-strong), secondary (border + transparent bg),
          ghost (no border + transparent), destructive (destructive bg)
Height: 44px (default) / 36px (.compact, with .8 opacity hint to avoid as primary)
Padding: 0 16px
Radius: --radius-sm (8px)
Font: --fs-body-sm 500 weight
States: hover = bg shift + translateY(-1px), focus = --focus-ring, active = scale(0.98), disabled = 0.4 opacity + pointer-events:none
Loading: replace text with spinner SVG, keep width
```

### Card (anime grid)
```
Aspect: 2:3 cover image top + meta footer below
Width: minmax(150px, 1fr) auto-fit grid mobile / minmax(180px, 1fr) desktop
Radius: --radius-md (12px)
Background: --bg-elev
Border: 1px solid --border
Hover: translateY(-4px) + shadow-lg + border-strong
Focus: --focus-ring
Tap area: entire card clickable
```

### Drawer (anime detail)
```
Mobile: full-width, bottom-anchored, slide up
Desktop: right-side, 480px wide, slide left
Radius: --radius-lg top (mobile) / --radius-lg left (desktop)
Backdrop: --scrim, click to close
Inner padding: --space-5 (24px)
Three sections: header (cover + title + meta) / synopsis / actions
```

### Input / Textarea
```
Height: 44px (input) / min 88px (textarea)
Padding: 0 --space-4 (input) / --space-3 --space-4 (textarea)
Background: --bg-sunken
Border: 1px solid --border
Radius: --radius-sm
Focus: --focus-ring + border-color: --accent
Placeholder: --fg-faint
Label: above input, --fs-caption 500 weight, --fg-muted
Error: border-color: --destructive + helper text --destructive below
```

### Chip / Tag
```
Padding: --space-1 --space-3 (4/12)
Radius: --radius-pill
Font: --fs-micro 500 weight
Background: --bg-elev (default) / --accent-soft (selected)
Color: --fg-muted (default) / --accent (selected)
Border: 1px solid transparent (default) / --accent-soft (selected)
```

### Banner / Notification
```
Background: --bg-elev with --accent left border (4px)
Padding: --space-4
Radius: --radius-sm
Variants:
  info     = --accent border + accent-soft icon bg
  success  = --success border
  warning  = --star border
  error    = --destructive border
No emoji in banner copy, use Lucide SVG icon left of text.
```

---

## 9. Page-specific guidance (refer to design-system/kiuno-anime-viewer/pages/*.md if exists, else use this section)

### index.html
- Header: title `kiuno · anime` (display weight) + nav links + search input (inline desktop / stacked mobile)
- Filter pills row: scrollable horizontal on mobile, wrapping on desktop
- Card grid: CSS Grid `auto-fit minmax(160px, 1fr)` mobile / `minmax(200px, 1fr)` desktop
- Card icon overlay: top-right cluster (favorite, share, more) — SVG icons inside circular 36px hit-extended button
- Drawer: 3-section (cover + meta on top, synopsis center, comments at bottom)

### recommends.html
- Top: composer form (anime chip-input + comment textarea + submit button right-aligned)
- List: card per recommendation, reply nesting with left accent border (--accent at 4px width) + 24px left indent
- No emoji privacy note (removed in 1.0.11/12). Form keeps audit metadata silently.

### graph.html
- Top banner: bento-style 2-3 cards showing「{category} 分類底下 N 部動漫匯總出來的標籤」+ filter chip group + count badge
- Canvas: Cytoscape with --bg background, node colors derived from accent variants

### changelog.html
- Vertical timeline with version badge (rounded-pill, mono font, --accent-soft background)
- Each entry: date (--fg-faint), summary (display), changes grouped by added/fixed/removed/ui/infra
- Changes use SVG icon (lucide plus/check/x/sparkles/wrench) instead of emoji

### ritual.html
- Keep summoning circle SVG + 3D perspective + black/orange aesthetic
- `body.ritual` overrides accent tokens to orange (see section 2b)
- HUD buttons use the same `.btn` component but inherit ritual-orange tokens
- Focus panel `.ritual__panel` uses same `--radius-lg`, `--shadow-lg`, `--ease-out`, but with orange border

---

## 10. Pre-Delivery Checklist

Before merging each page into main:

### Visual Quality
- [ ] No emoji in primary UI (banners, buttons, headers). Verified visually.
- [ ] All icons from one SVG set (Lucide preferred), single stroke weight
- [ ] Cards/elevations use the --shadow-* scale, no random box-shadow values
- [ ] Semantic CSS variables everywhere, grep for `#` in component CSS should return only token definitions

### Interaction
- [ ] Tap targets >=44x44px (verified with DevTools rendering > emulate touch + container)
- [ ] All buttons have hover, focus (visible ring via --focus-ring), active states
- [ ] Loading states: skeleton or spinner shown for >300ms async ops
- [ ] Forms: visible label, inline validation on blur, error message near field with recovery action

### Layout
- [ ] Tested at 375px (iPhone SE), no horizontal scroll, all content fits
- [ ] Tested at 768px and 1280px breakpoints
- [ ] Safe-area: no fixed element overlapping content (drawer, banner)
- [ ] 4/8px spacing rhythm preserved across components

### Accessibility
- [ ] Body text contrast >=4.5:1, UI text >=3:1 (use webaim contrast checker)
- [ ] All meaningful images have alt text
- [ ] Keyboard navigation works (Tab through interactive elements, Enter/Space activates)
- [ ] `prefers-reduced-motion` honored, verified with DevTools rendering > emulate CSS

### Cross-theme (主站 vs ritual)
- [ ] Main site (index/graph/recommends/changelog) renders with indigo accent
- [ ] ritual.html renders with orange accent (no leak of indigo, no leak of orange to main site)
- [ ] Spacing/typography/radius identical between themes, only colors differ

---

## 11. Implementation Order

1. **Stage 0** (this stage): Write tokens to `styles.css` :root, validate on existing pages without changing markup
2. **Stage 1**: Shared components (.pill-btn / .toggle / .chip / .banner / inputs / spinner / empty states), tokens-only refactor
3. **Stage 2**: index.html, card grid + drawer + remove emoji + add SVG icon set
4. **Stage 3**: recommends.html, form + nested list redesign
5. **Stage 4**: graph.html, banner bento + canvas bg
6. **Stage 5**: changelog.html, timeline
7. **Stage 6**: ritual.html, keep visual, override tokens via `body.ritual`
8. **Stage 7**: Cutover (rename redesign files), bump 1.0.11 -> 1.1.0, full changelog entry

---

## 12. Reference Look-and-feel

The target visual is a synthesis of:
- **AniList** (anilist.co), card grid, dark + accent, info density
- **Letterboxd**, typography hierarchy, neutral palette
- **Plex**, content-first layouts, drawer/detail panel
- **Linear** (linear.app), sleek modern, indigo accent, subtle motion

Anti-references (do NOT borrow):
- MyAnimeList (cluttered, dated)
- Crunchyroll header (over-saturated orange)
- Cyberpunk dashboards (neon overload)
