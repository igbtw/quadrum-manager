name: CantinaOS

description: Precision-first B2B operations UI for school canteen sales, stock, people, and receivables.

colors:
graphite-950: "#0D100F"
graphite-925: "#111513"
graphite-900: "#151A18"
graphite-850: "#1A201D"
graphite-800: "#202723"
graphite-700: "#2A322E"
graphite-600: "#38413D"
light-050: "#F4F7F5"
light-000: "#FFFFFF"
light-100: "#EDF1EE"
light-200: "#E1E7E3"
light-300: "#D4DCD7"
ink-950: "#151A18"
ink-800: "#2E3733"
ink-600: "#5B6661"
ink-400: "#85908A"
text-dark: "#F1F5F2"
text-dark-muted: "#A8B2AC"
text-dark-faint: "#707A75"
text-light: "#18201C"
text-light-muted: "#5D6862"
text-light-faint: "#7C8781"
mint-500: "#79DDBD"
mint-400: "#93E8CA"
mint-300: "#B1F0DA"
mint-700: "#4AAE90"
mint-800: "#2E8068"
success: "#67D79F"
warning: "#E7B568"
danger: "#E27D7D"
info: "#82B6E3"
white-overlay: "rgba(255,255,255,0.06)"
black-overlay: "rgba(0,0,0,0.08)"

typography:
display:
fontFamily: "IBM Plex Sans, Segoe UI, system-ui, sans-serif"
fontSize: "clamp(2rem, 3vw, 3rem)"
fontWeight: 600
lineHeight: 1.05
letterSpacing: "-0.025em"
headline:
fontFamily: "IBM Plex Sans, Segoe UI, system-ui, sans-serif"
fontSize: "clamp(1.5rem, 2vw, 2rem)"
fontWeight: 600
lineHeight: 1.15
letterSpacing: "-0.015em"
title:
fontFamily: "IBM Plex Sans, Segoe UI, system-ui, sans-serif"
fontSize: "1.125rem"
fontWeight: 600
lineHeight: 1.3
letterSpacing: "-0.005em"
body:
fontFamily: "IBM Plex Sans, Segoe UI, system-ui, sans-serif"
fontSize: "0.9375rem"
fontWeight: 400
lineHeight: 1.5
letterSpacing: "normal"
label:
fontFamily: "IBM Plex Mono, SFMono-Regular, Consolas, monospace"
fontSize: "0.6875rem"
fontWeight: 500
lineHeight: 1.2
letterSpacing: "0.08em"

rounded:
none: "0px"
xs: "2px"
sm: "4px"
md: "6px"
lg: "8px"
xl: "12px"
pill: "999px"

spacing:
1: "4px"
2: "8px"
3: "12px"
4: "16px"
5: "20px"
6: "24px"
8: "32px"
10: "40px"
12: "48px"
16: "64px"

components:
button-primary:
backgroundColor: "{colors.mint-500}"
textColor: "{colors.graphite-950}"
typography: "{typography.body}"
rounded: "{rounded.sm}"
padding: "9px 14px"
height: "38px"
button-secondary:
backgroundColor: "transparent"
textColor: "{colors.text-dark}"
typography: "{typography.body}"
rounded: "{rounded.sm}"
padding: "8px 13px"
height: "38px"
button-ghost:
backgroundColor: "transparent"
textColor: "{colors.text-dark-muted}"
typography: "{typography.body}"
rounded: "{rounded.sm}"
padding: "8px 10px"
height: "36px"
input:
backgroundColor: "{colors.graphite-900}"
textColor: "{colors.text-dark}"
typography: "{typography.body}"
rounded: "{rounded.sm}"
padding: "9px 12px"
height: "40px"
card:
backgroundColor: "{colors.graphite-900}"
textColor: "{colors.text-dark}"
rounded: "{rounded.md}"
padding: "20px"
nav-link:
backgroundColor: "transparent"
textColor: "{colors.text-dark-muted}"
typography: "{typography.body}"
rounded: "{rounded.sm}"
padding: "9px 10px"

Design System: CantinaOS

Overview

Creative North Star: "The Quiet Operations Console"

CantinaOS should feel like a serious piece of operational software: calm, exact, fast to scan, and trustworthy under routine pressure. The visual language combines graphite surfaces, precise hairline rules, restrained mint signals, and strong typographic hierarchy. It should feel closer to a refined B2B operations console than to a school project, generic admin template, or consumer food app.

The interface is intentionally information-dense without becoming cramped. Every element should answer a practical question: What happened? What needs attention? What can I do next? What is the current state? The visual system uses structure rather than decoration to create personality: alignment, rhythm, data hierarchy, compact controls, and carefully controlled contrast do most of the work.

The aesthetic may take inspiration from modern developer infrastructure products such as Neon, Linear, and premium operational dashboards, but it must remain distinctly CantinaOS. Do not copy their layouts, logos, exact visual treatments, or signature components. The target is the same level of restraint, precision, and polish expressed through CantinaOS's own palette, information architecture, and operational vocabulary.

Key Characteristics:

Graphite-first, low-noise visual hierarchy with a restrained mint accent.

Square/compact geometry: small radii, thin borders, minimal shadow, precise alignment.

Data-forward B2B density: tables, metrics, filters, status indicators, and actions are first-class content.

Two equally intentional themes: Graphite Dark and Light, with shared semantic tokens.

Motion is subtle and functional; nothing should bounce, float, or distract from work.

Premium because of consistency and craft, not because of ornament.

Colors

The palette is built around mineral graphite neutrals with one recognizable brand signal: a muted technical mint. Dark mode is the primary visual reference, while Light mode is a complete first-class theme rather than a simple color inversion.

Primary

Cantina Mint (#79DDBD): The single brand accent. Use for primary actions, selected states, key interactive focus, chart emphasis, and important positive deltas. Keep it visually scarce; it should identify intent, not decorate every surface.

Cantina Mint Bright (#93E8CA): Hover, active emphasis, or high-contrast text/icon treatment when the base mint is insufficient.

Cantina Mint Deep (#2E8068): Darker accent for subtle tinted surfaces, borders, charts with layered series, and light-theme contrast.

Secondary

Operational Success (#67D79F): Confirmed, healthy, paid, available, or completed states. Do not use the primary mint automatically when a state-specific green is clearer.

Operational Warning (#E7B568): Low stock, overdue risk, pending review, and other caution states.

Operational Danger (#E27D7D): Failed, cancelled, blocked, destructive, or materially incorrect states.

Operational Info (#82B6E3): Neutral informational context where blue improves semantic distinction.

Neutral

Graphite 950 (#0D100F): Dark-mode page canvas. Near-black, but never literal #000000.

Graphite 925 (#111513): Dark-mode shell/sidebar background when an additional tonal layer is useful.

Graphite 900 (#151A18): Primary dark surface for panels, tables, forms, and cards.

Graphite 850 (#1A201D): Raised dark surface and hover state.

Graphite 800 (#202723): Stronger raised surface or grouped region.

Graphite 700 (#2A322E): Standard dark border/divider tone.

Graphite 600 (#38413D): Higher-contrast border and focus-adjacent structure.

Text Dark (#F1F5F2): Primary dark-theme text.

Text Dark Muted (#A8B2AC): Secondary labels, metadata, supporting copy.

Text Dark Faint (#707A75): Tertiary metadata and low-priority chrome; never use for essential text.

Light 050 (#F4F7F5): Light-theme page canvas.

Light 000 (#FFFFFF): Light-theme surface when a true white surface creates clear hierarchy.

Light 100 (#EDF1EE): Light raised surface and subtle grouped regions.

Light 200 (#E1E7E3): Standard light border/divider.

Light 300 (#D4DCD7): Stronger light border and field boundary.

Text Light (#18201C): Primary light-theme text.

Text Light Muted (#5D6862): Secondary light-theme text.

Text Light Faint (#7C8781): Tertiary metadata; never use for essential text.

Named Rules

The One Signal Rule. Mint is an action/state signal, not a background color. A typical screen should have only a small fraction of its visual area using strong mint.

The No Pure Black Rule. Do not use #000 for application backgrounds, large surfaces, or text. Depth comes from layered graphite tones and borders.

The Semantic Color Rule. Status colors communicate state consistently across tables, badges, charts, forms, and notifications. Do not repurpose warning/danger colors as decorative accents.

Typography

Display Font: IBM Plex Sans, with Segoe UI / system-ui fallbacks.

Body Font: IBM Plex Sans, with Segoe UI / system-ui fallbacks.

Label/Mono Font: IBM Plex Mono, with SFMono-Regular / Consolas / monospace fallbacks.

Character: Technical, mature, highly legible, and slightly industrial without becoming sci-fi. The sans family carries the human-facing workflow; the mono face is reserved for compact labels, timestamps, IDs, metrics metadata, and operational notation.

Hierarchy

Display (600, clamp(2rem, 3vw, 3rem), 1.05): Primary page heading on high-level dashboards and major views. Use sparingly; most internal screens should use the smaller headline/title scale.

Headline (600, clamp(1.5rem, 2vw, 2rem), 1.15): Page titles and major section headings. Strong and readable, never oversized for the sake of drama.

Title (600, 1.125rem, 1.3): Card/section titles, dialog titles, table-group headings, and important local hierarchy.

Body (400, 0.9375rem, 1.5): Default interface text. Prefer readable line length and do not compress copy just to make a component denser.

Label (500, 0.6875rem, 1.2, 0.08em tracking, uppercase only when useful): Utility metadata, table headers, KPI eyebrows, status labels, and navigation section markers. Labels are structural, not decorative.

Use larger numerals for key metrics: approximately 1.75rem–2.25rem at desktop sizes, with tabular numerals enabled where the font supports them. Prices, quantities, totals, and percentages should align predictably.

Do not use excessive font-weight variation. Most interfaces should live in 400/500/600; reserve 700 for exceptional emphasis such as critical totals or a destructive warning.

Named Rules

The Scanline Rule. A user should be able to scan any major page top-to-bottom and understand its hierarchy from type size, weight, alignment, and spacing before reading every word.

The Numbers Rule. Numeric data should be easy to compare. Use tabular numerals, consistent decimal formatting, and aligned numeric columns whenever practical.

The No Tiny Body Rule. Never solve density by shrinking ordinary body copy below the 14px equivalent. Dense UI should come from structure, not microscopic text.

Layout

CantinaOS uses a structured application shell rather than a centered marketing page. The experience is a persistent workspace with a stable sidebar, compact top bar, and flexible content canvas.

Spatial model

Desktop shell: persistent left navigation at approximately 248px wide, with a compact mode around 72px when explicitly collapsed. The main content must use the remaining width directly; never double-apply sidebar margins or offsets.

Top bar: approximately 64px tall. It contains contextual search/actions, theme control, notifications, and user/session affordances without competing with the page title.

Content canvas: fluid width with a comfortable maximum around 1480px. Center content inside the available canvas when useful, but never create unnecessary empty margins on smaller screens.

Desktop page padding: 32px horizontal / 28–32px vertical as the baseline. Use 24px at medium widths and 16px on small screens.

Primary grid: 12-column grid on desktop with 16–24px gutters. Use explicit 8/4, 7/5, or 6/6 relationships where content weight differs. Avoid arbitrary masonry.

Section rhythm: major page sections are separated by 24–32px; internal component spacing usually follows 8/12/16/24px increments.

Dashboard composition

The dashboard is a decision surface, not a collection of decorative cards.

Page header: title, concise context, and the most relevant global filter/action.

KPI strip: four compact metrics on desktop, each with one value, one label, and one concise trend/context line.

Primary operational split: sales performance receives the larger region; stock health receives the smaller region when both are present.

Secondary operational split: recent sales and accounts receivable occupy equal or content-driven regions.

Tables should use the full width available inside their region and must never force page-level horizontal scrolling.

Responsive behavior

≥ 1200px: full sidebar, multi-column dashboard, generous but controlled table density.

900–1199px: compact sidebar or full sidebar depending on available content width; reduce grid spans before reducing text size.

< 900px: sidebar becomes a drawer or compact rail; dashboard regions stack logically by priority.

< 640px: single-column content, 16px page padding, full-width controls, horizontally scrollable tables only when unavoidable and only inside their own container.

Preserve touch targets at roughly 40px minimum for controls. Do not rely on hover for essential information.

Density and alignment

Align titles, values, controls, tables, and charts to shared vertical edges.

Prefer fewer, larger regions over many small cards.

Never use nested cards to create visual hierarchy. Use borders, spacing, section headers, and tonal changes first.

Every major row should have an obvious reading order from left to right and top to bottom.

Do not hide content behind accordions or tabs merely to make the initial view look cleaner when the information is operationally important.

Layout rules

The Shared Edge Rule. Important content should align to common left/right edges so the interface feels engineered rather than assembled.

The No Overflow Rule. Page-level horizontal scrolling is a bug. Long text, wide tables, filters, and selects must adapt or contain their overflow locally.

The Priority Before Compression Rule. On narrow screens, reduce columns, hide secondary metadata, and stack regions before shrinking typography to unreadable sizes.

Elevation & Depth

CantinaOS is primarily a flat, layered system. Depth is created by tonal contrast, 1px borders, and controlled surface hierarchy rather than floating cards and large shadows.

Use three main dark tonal levels: page canvas → surface → raised surface. Use the equivalent light levels in Light mode. A panel should look separated because its surface and border are intentional, not because a large shadow was placed underneath it.

Shadows are exceptional rather than default. Use a very soft shadow only for overlays, dropdowns, dialogs, and elements that physically sit above the workspace. Static dashboard panels should normally have no shadow.

Shadow Vocabulary

Overlay: 0 8px 32px rgba(0,0,0,0.28) — menus, popovers, command/search surfaces, and dialogs in dark mode; reduce opacity appropriately in Light mode.

Focus emphasis: no drop shadow. Use a 1–2px visible focus ring or tokenized outline so keyboard focus is clear and crisp.

Named Rules

The Flat-by-Default Rule. If a component can communicate hierarchy through surface tone and border, do not add a shadow.

The One Plane Rule. A dashboard region should read as one coherent plane. Do not place cards inside cards inside cards.

Shapes

Geometry is compact and deliberate. CantinaOS should feel like precision equipment rather than a collection of friendly bubbles.

Default control radius: 4px.

Panel/card radius: 6px.

Modal/drawer radius: 8px.

Icon-only controls: 4px unless the control is explicitly a circular affordance.

Status pills: 999px only for semantic badges/chips where pill geometry adds meaning.

Buttons: square-ish corners, never oversized capsules.

Borders: 1px hairlines by default, using low-contrast neutral tokens. Increase contrast only for active/focused/critical boundaries.

Dividers: prefer 1px rules over empty whitespace when a structural boundary helps scanning.

Clipping: avoid decorative clipping, masks, blobs, and irregular shapes. Geometry should support information hierarchy.

Components

Components should feel related enough that a user can predict how the interface behaves before interacting with it. Reuse the same primitive patterns across Dashboard, PDV, Products, Stock, People, Sales, Finance, Reports, and authentication surfaces.

Buttons

Buttons are compact, tactile, and explicit.

Primary: solid Cantina Mint with dark text. Use for the single highest-value action in a context: Confirm sale, Save, Register payment, etc.

Secondary: transparent or tonal surface with a 1px border. Use for alternative actions.

Ghost: text/icon action for low-emphasis controls. Avoid turning every table action into a filled button.

Danger: use the semantic danger token sparingly and only for destructive actions.

Hover: small tonal shift; no glow flood, no bounce.

Focus: visible :focus-visible ring with sufficient contrast.

Active: tiny 1px/1–2% positional compression is acceptable; never exaggerated scaling.

Loading: preserve button width and label; use a subtle inline indicator rather than replacing the entire control with a spinner-only state.

Chips / Badges / Status

Use compact semantic badges for categorical state such as Active, Paid, Pending, Low stock, Cancelled.

Pills are reserved for status/tags, not general containers.

Prefer tinted neutral or semantic backgrounds with clear text rather than saturated solid blocks.

Status must never rely on color alone; include text or icon context.

Cards / Containers

Cards are structural containers, not the default wrapper for every section.

Corner: 6px.

Background: one tonal step above the parent surface where separation is needed.

Border: 1px neutral border.

Shadow: none by default.

Padding: 20px standard; 16px for dense utility panels; 24px for larger analytical sections.

When several related regions form a single section, prefer one shared container with internal dividers over many sibling cards.

KPI / Metric Blocks

A metric block contains: eyebrow/label → large value → concise context/trend.

No giant decorative icons above the metric.

Prefer the actual number as the visual anchor.

Use delta text sparingly and always explain its period when ambiguous.

Use a small semantic indicator for positive/negative/attention states rather than coloring the entire metric.

Inputs / Fields

Forms should feel reliable and dense without looking cramped.

Style: dark/light tonal surface, 1px border, 4px radius, 40px baseline height.

Placeholder: muted, never used as the only field label.

Focus: crisp accent ring and/or border shift; no oversized glow.

Error: danger border plus concise supporting text directly below the field.

Disabled: reduced contrast and clear non-interactive cursor/state.

Search: may use a leading icon, but avoid ornamental icon tiles.

Labels remain visible above fields for important workflows.

Navigation

Navigation is a persistent workspace index, not a decorative sidebar.

Brand/wordmark at top with restrained scale.

Group related destinations under small mono labels when categories genuinely help.

One clearly active destination at a time.

Active state uses a subtle tonal fill plus mint indicator or text/icon emphasis; do not use a huge filled pill.

Icons are simple 16–18px line icons with consistent stroke weight.

Collapsed state preserves discoverability through tooltips and accessible labels.

Sidebar collapse should feel like the same shell becoming denser, not a floating rail appearing over the application.

Mobile navigation becomes a deliberate drawer or compact top-level control; it must not shrink desktop navigation into unusable text.

Header / Top Bar

The top bar is quiet chrome.

Use one compact search/control region, theme toggle, notifications, and user/session affordance.

Avoid stacking multiple large controls in the header.

The header may be separated from content with a subtle bottom border rather than a heavy shadow.

The theme toggle must visibly communicate the current mode and work without inline JavaScript dependencies.

Tables

Tables are one of the core visual signatures of CantinaOS.

Use clear column alignment: text left, numeric/currency right, status centered or left depending on width.

Header labels use the mono label style or concise 11–12px uppercase text where appropriate.

Row height should feel compact but comfortable, roughly 44–52px depending on density.

Hover highlight is subtle and localized to the row.

Avoid zebra striping unless a specific dense-data context demonstrably benefits from it.

Keep row actions compact; use icon buttons with tooltips for secondary operations and text buttons for consequential actions.

Long tables gain pagination, filtering, and sorting before gaining more decorative UI.

On small screens, contain horizontal overflow inside the table region rather than allowing the entire page to scroll sideways.

Charts

Charts should look like product instrumentation, not dashboard wallpaper.

Use one dominant accent series whenever possible.

Line weight approximately 2px; point markers only when data density is low or points are actionable.

Area fills, if used, must be extremely subtle and never become a gradient spectacle.

Gridlines are sparse, low-contrast, and subordinate to data.

Axis labels and legends use muted typography.

Tooltips should be compact, aligned with the visual system, and show exact values when useful.

Prefer honest scales and clear date/period labels. Never decorate a chart in ways that imply precision the data does not have.

Do not use a chart merely because there is empty space; every visualization needs a decision-making purpose.

Tabs / Filters

Filters are operational controls.

Use compact segmented/tabs only when switching between mutually related views.

Use select/date-range controls for query parameters.

Active filter states must be clearly visible without relying solely on color.

Filter bars should align with the table/chart they control.

Modals / Drawers

Use overlays only when the current task truly benefits from temporary focus.

Keep widths restrained and predictable.

Prioritize title → explanation → fields/content → actions.

Destructive confirmation dialogs should state the consequence plainly and name the affected object when possible.

Never stack modals.

Toasts / Feedback

Feedback should confirm what changed and what the user can do next.

Success: brief and calm.

Warning: specific and actionable.

Error: explain the failed action and how to recover.

Auto-dismiss only non-critical feedback; critical errors remain visible.

Avoid notification spam for routine operations.

Empty / Loading / Error States

These states are part of the design, not afterthoughts.

Empty: explain what the user can do next; one clear action.

Loading: use skeletons that preserve final layout geometry to prevent layout shift.

Error: keep the affected region's context visible, explain the failure plainly, and provide a recovery action when possible.

Never replace a useful page with a generic "Something went wrong" screen when a localized recovery state is possible.

Do's and Don'ts

Do:

Do make the application feel like a commercial operational product, not a student CRUD template.

Do keep the visual language graphite, precise, restrained, and information-first.

Do use mint as a recognizable but scarce brand signal.

Do use 4–8px radii for most interface geometry and reserve pills for semantic chips/badges.

Do use 1px borders, tonal layering, and alignment to create hierarchy before reaching for shadows.

Do make Light and Graphite Dark equally intentional and semantically consistent.

Do reuse primitives across every screen so the product develops a coherent visual grammar.

Do make tables, filters, metrics, and actions easy to scan in under a few seconds.

Do use concise Brazilian Portuguese interface copy, consistent currency/date formatting, and operational terminology.

Do support keyboard navigation, visible focus, reduced motion, readable contrast, and touch-friendly controls.

Do preserve content hierarchy when responsive behavior changes; stack and simplify before shrinking type.

Do test the real interaction path and rendered result rather than trusting static markup alone.

Do keep motion around 120–180ms for routine transitions, using a calm ease-out/standard easing curve.

Do maintain a single coherent token system so theme changes affect semantic variables rather than isolated component hardcodes.

Don't:

Don't use Inter as the default font merely because it is familiar; use the documented type system.

Don't use pure black backgrounds or pure white/black extremes as the entire visual system.

Don't use purple/blue SaaS gradients, mesh gradients, glowing borders, or neon-futuristic decoration.

Don't turn every section into a rounded floating card.

Don't nest cards inside cards to manufacture hierarchy.

Don't use oversized rounded rectangles, pill buttons, or capsule navigation for ordinary controls.

Don't add decorative illustrations, blobs, giant hero graphics, or icon tiles to an operations dashboard unless they solve a real usability problem.

Don't use excessive shadows, glassmorphism, blur, backdrop filters, or floating panels as the default surface language.

Don't rely on hover for essential information or actions.

Don't use color alone to communicate state.

Don't hide important operational information merely to make the screen look minimal.

Don't solve density problems by making body text tiny.

Don't let page-level horizontal overflow appear on desktop or mobile.

Don't introduce page-specific button/card/input variants when an existing primitive can express the need.

Don't create animations that bounce, wobble, overshoot, or compete with data entry and scanning.

Don't redesign working information architecture merely to imitate another product's screenshot.

Don't copy Neon, Linear, Stripe, or any other reference product's exact layout, branding, iconography, or signature patterns.

## Motion & Interaction

Motion is functional, restrained, and nearly invisible.

CantinaOS is an operational application, not a marketing site. Animation must communicate state, hierarchy, continuity, or feedback.

### Principles

- Prefer CSS transitions for simple hover/focus/color changes.
- Use Motion only when CSS cannot express the interaction cleanly.
- Never animate for decoration alone.
- Never delay a user's interaction with unnecessary animation.
- Never use exaggerated spring/bounce behavior.
- Never use parallax or scroll-driven spectacle.
- Respect `prefers-reduced-motion`.

### Timing

Micro interactions:
- 100–160ms

Controls and state changes:
- 140–220ms

Panels, dialogs, drawers:
- 180–280ms

Complex layout transitions:
- 220–350ms

Avoid animations longer than 400ms unless the duration represents a meaningful process.

### Preferred Properties

Prefer:
- opacity
- transform
- scale
- translate
- clip-path where appropriate

Avoid animating expensive layout properties unnecessarily:
- width
- height
- top
- left
- margin
- padding

### Appropriate Uses

Use animation for:

- sidebar collapse/expansion
- dialogs and drawers
- dropdown menus
- toast notifications
- table row insertion/removal
- filtering transitions
- navigation state changes
- KPI value changes
- loading state transitions
- button press feedback
- expanding/collapsing panels
- chart state changes

### Inappropriate Uses

Do not use:

- bouncing cards
- animated gradients
- floating decorative elements
- continuous background animation
- excessive staggered entrance animations
- flashy page transitions
- parallax
- spinning UI elements unless representing loading
- animations that resemble a marketing landing page

### Reduced Motion

All non-essential animation must respect:

`prefers-reduced-motion: reduce`

When reduced motion is enabled:
- remove transforms
- remove decorative transitions
- minimize opacity transitions
- preserve functional state changes
- never hide important information behind animation
