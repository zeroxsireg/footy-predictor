# Tactical Match Telemetry — UI & Design System

This documentation describes the **Tactical Match Telemetry** design system, CSS variables, utility tokens, layout structures, and reusable components of the Footy Predictor web client. Use this document as a reference when building or extending components.

---

## 1. Design Philosophy & Substrate

The user interface is built on a **mechanical-brutalist / CRT terminal aesthetic**. It represents a high-density, analytical instrument panel.

### Rigid Core Guidelines
- **Zero Border Radius**: Absolutely no rounded corners anywhere in the app. This is globally enforced in CSS: `border-radius: 0 !important;`.
- **CRT Scanlines**: A fixed overlay creates a simulated scanline texture across the substrate:
  ```css
  body::after {
    content: "";
    position: fixed;
    inset: 0;
    z-index: 9999;
    pointer-events: none;
    background: repeating-linear-gradient(
      0deg, transparent, transparent 2px, rgba(0,0,0,0.3) 2px, rgba(0,0,0,0.3) 3px
    );
  }
  ```
- **Rigid Case**: Text is fully uppercase (`text-transform: uppercase`) and mono-spaced by default to evoke retro command-line layouts.

---

## 2. Color System & CSS Variables

We use Tailwind CSS v4 variables mapped inside `@theme`. All colors represent low-glow phosphor lights on dark substrates.

| Variable Name | Utility Class | Value | Usage |
| :--- | :--- | :--- | :--- |
| `--color-bg` | `bg-bg` | `#0a0a0a` | Deactivated CRT screen substrate |
| `--color-panel` | `bg-panel` | `#101010` | Elevated telemetry modules background |
| `--color-line` | `border-line` | `#262626` | Hairline dividers and inactive fill bars |
| `--color-fg` | `text-fg` | `#eaeaea` | Primary telemetry readout (white phosphor) |
| `--color-dim` | `text-dim` | `#6b6b6b` | Secondary telemetry, labels, unit descriptors |
| `--color-red` | `text-red` | `#e61919` | Accent/Hazard red (high warning, alerts, primary accent) |
| `--color-green` | `bg-green` | `#4af626` | Status online led indicator (used sparingly) |

---

## 3. Typography & Micro-Typography Classes

Our system utilizes two primary font faces imported from Google Fonts:
1. **Archivo Black** (`var(--font-archivo)` / `font-display`): Used for bold, high-impact numbers and headings.
2. **JetBrains Mono** (`var(--font-jetbrains)` / `font-mono`): Used for secondary readouts, tables, labels, and standard body text.

### Typography Utility Classes
- **`.hd` (Display Headings)**:
  - Font: Archivo Black
  - Tracking: `-0.04em` (compressed spacing)
  - Line-height: `0.9` (extremely close stack)
  - Text-transform: `uppercase`
- **`.lbl` (Telemetry Labels)**:
  - Font: JetBrains Mono
  - Tracking: `0.12em` (widely spaced terminal readouts)
  - Size: `0.68rem`
  - Text-transform: `uppercase`

---

## 4. Layout & Divider Primitives

To construct mechanical grids and modules:

### A. Razor-Thin Grid (`.hairgrid`)
A custom display utility that uses a contrasting border color as the background and places a `1px` gap between grid elements, yielding a thin divider line between columns.
```tsx
<div className="hairgrid grid-cols-1 sm:grid-cols-3">
  <div>Column 1</div>
  <div>Column 2</div>
  <div>Column 3</div>
</div>
```
- **Underlying CSS**:
  ```css
  .hairgrid {
    display: grid;
    gap: 1px;
    background: var(--color-line);
  }
  .hairgrid > * {
    background: var(--color-bg);
  }
  ```

### B. Module Panel (`.panel` / `bg-panel`)
Provides a simple container structure with a border and background matching the panel layer.
```css
.panel {
  border: 1px solid var(--color-line);
  background: var(--color-panel);
}
```

---

## 5. Reusable UI Atoms & Molecules

These components are located in `web/app/components/ui/`. Always use them to compose panels.

### `Container`
A centralizing layout wrapper with responsive horizontal padding.
- **Path**: `web/app/components/ui/Container.tsx`
- **Props**:
  ```typescript
  {
    children: React.ReactNode;
    className?: string;
  }
  ```
- **Example Usage**:
  ```tsx
  import { Container } from "@/app/components/ui/Container";
  
  <Container className="py-8">
    {/* Page content */}
  </Container>
  ```

### `Label`
Enforces standard micro-typography telemetry tags, with an optional bracket wrapping.
- **Path**: `web/app/components/ui/Label.tsx`
- **Props**:
  ```typescript
  {
    children: React.ReactNode;
    bracket?: boolean; // wraps text in [ ... ]
    tone?: "dim" | "fg" | "red"; // defaults to "dim"
    className?: string;
  }
  ```
- **Example Usage**:
  ```tsx
  import { Label } from "@/app/components/ui/Label";
  
  <Label bracket tone="red">ALLARME CRITICO</Label>
  // Output: [ ALLARME CRITICO ] in aviation red
  ```

### `Panel`
A raw brutalist module container.
- **Path**: `web/app/components/ui/Panel.tsx`
- **Example**:
  ```tsx
  import { Panel } from "@/app/components/ui/Panel";
  
  <Panel className="p-4">
    {/* Telemetry panel */}
  </Panel>
  ```

### `SectionBlock`
A high-use composable card block containing a bracketed header label and a bordered body panel.
- **Path**: `web/app/components/ui/Panel.tsx`
- **Props**:
  ```typescript
  {
    title: string;
    children: React.ReactNode;
    className?: string;
  }
  ```
- **Example Usage**:
  ```tsx
  import { SectionBlock } from "@/app/components/ui/Panel";
  
  <SectionBlock title="CARTELLINI GIOCATORE">
    {/* Inside goes the table or content */}
  </SectionBlock>
  ```

### `ProbBar`
A mechanical telemetry readout with a fill progress bar that highlights in red if the probability exceeds a threshold.
- **Path**: `web/app/components/ui/ProbBar.tsx`
- **Props**:
  ```typescript
  {
    label: string;
    value: number; // 0..1
    hot?: boolean; // Highlights fill/text in aviation red
  }
  ```
- **Example Usage**:
  ```tsx
  import { ProbBar } from "@/app/components/ui/ProbBar";
  
  <ProbBar label="OVER 2.5" value={0.78} hot={0.78 >= 0.6} />
  ```

### `ProbList`
A layout molecule that stacks multiple probability bars, automatically setting the hazard red flag for probabilities above the threshold (`hotAt`, default: `1`).
- **Path**: `web/app/components/ui/ProbBar.tsx`
- **Props**:
  ```typescript
  {
    items: { label: string; value: number }[];
    hotAt?: number; // Threshold above which items light up in red (e.g. 0.6)
  }
  ```
- **Example**:
  ```tsx
  import { ProbList } from "@/app/components/ui/ProbBar";
  import { HOT } from "@/app/lib/markets";
  
  <ProbList items={[{ label: "BTTS", value: 0.65 }]} hotAt={HOT} />
  ```

---

## 6. Telemetry Match Components

Located in `web/app/components/match/`, these are structured organisms displaying aggregated predictive indices.

### `MatchHeader`
Displays the league name, date, matchday, competing clubs, and referee telemetry details.
- **Path**: `web/app/components/match/MatchHeader.tsx`
- **Props**:
  ```typescript
  {
    match: Match;
    leagueName: string;
    matchday: number;
  }
  ```

### `Market1x2`
Displays Home, Draw, Away outcomes in a 3-column split, with the highest probability highlighted in warning red.
- **Path**: `web/app/components/match/Market1x2.tsx`
- **Props**:
  ```typescript
  {
    m: Markets["1x2"];
  }
  ```

### `CardsPanel`
Shows expected team card count in display type next to expected card thresholds.
- **Path**: `web/app/components/match/CardsPanel.tsx`
- **Props**:
  ```typescript
  {
    cards: NonNullable<Markets["cards"]>;
  }
  ```

### `PlayerRiskTable`
A tabular readout of booking probability thresholds for high-risk players.
- **Path**: `web/app/components/match/PlayerRiskTable.tsx`
- **Props**:
  ```typescript
  {
    players: NonNullable<Markets["players_at_risk"]>;
  }
  ```

### `ResultBlock`
Appears when the actual fixture has already concluded (backtests or historical data validation).
- **Path**: `web/app/components/match/ResultBlock.tsx`
- **Props**:
  ```typescript
  {
    result: NonNullable<Match["result"]>;
  }
  ```

---

## 7. Localization & Text Modularization (SSOT)

There must be **no inline/hardcoded strings** in pages or component markups. 

### Locale Extraction
All UI text translations are located in [it.ts](file:///Users/sireg/Documents/Projects/footy-predictor/web/app/lib/locales/it.ts):
```typescript
import { locale } from "@/app/lib/locales/it";

// Usage in layouts/pages
<h1>{locale.hero.titleLine1}</h1>
```
If you add another language file (e.g., `en.ts`), import the `AppLocale` type from `@/app/lib/types` to enforce contract matching.

---

## 8. Type Definition Registry (SSOT)

All TypeScript model structures and contracts are centralized in [types.ts](file:///Users/sireg/Documents/Projects/footy-predictor/web/app/lib/types.ts).

### Crucial Data Structs
- `Prob`: Number format between `0` and `1`.
- `MatchBundle`: Full match wrapper matching the payload contract.
- `MarketEntry<K>`: Mapping config for markets showing `{ key, label }`.
- `League`: Campionato config schema containing `{ id, code, name }`.
- `AppLocale`: Global layout translation schema.
