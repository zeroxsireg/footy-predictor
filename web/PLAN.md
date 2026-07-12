# 🖥️ Webapp — Piano & Sezioni

Frontend del prodotto pronostici. Legge il JSON generato dal motore Python
(`predictions/`) e lo presenta in stile **Industrial Brutalist — Tactical
Telemetry**.

---

## Stack
- **Next.js 16** (App Router) · **TypeScript** · **Tailwind CSS**
- **Static export** (`output: 'export'`) → hosting statico (Netlify/Vercel/GitHub Pages), zero backend
- Cartella: `web/`
- Skill di stile: `industrial-brutalist-ui`

## Architettura dati (disaccoppiata)
```
Python (motore)  →  predictions/*.json  →  web/public/data/  →  Next.js (build)  →  sito statico
```
Il JSON è il **contratto** (`schema_version: 1`). Il frontend non conosce i
modelli, solo il JSON. Un piccolo script copia i JSON in `web/public/data/`.

---

## Design system (archetipo: TACTICAL TELEMETRY — dark)
> Impegno unico: modalità scura, niente gradienti/ombre morbide.

- **Substrato:** `#0A0A0A` / `#121212` (CRT spento). No nero puro.
- **Testo:** off-white / grigio telemetria.
- **Accento unico:** rosso hazard `#E61919` (allarmi, dati vitali, divisori).
- **(opz.) fosforo:** verde terminale per valori "attivi".
- **Macro-tipografia** (header): heavy sans (Archivo Black / Inter Black),
  MAIUSCOLO, scale enormi `clamp(...)`, tracking negativo, leading compresso.
- **Micro-tipografia** (dati): monospace (JetBrains Mono / IBM Plex Mono),
  MAIUSCOLO, piccola, tracking generoso — tutte le metriche, ID, percentuali.
- **Struttura:** griglie rigide, divisori a linea visibile, cornici ASCII
  (`[ ]`, crosshair), alta densità dati, numeri oversized che "bleedano".
- **(opz.) degrado analogico:** scanline/halftone leggeri come texture.

---

## Mappa del sito (SEZIONI)

### 1. DASHBOARD `/`  — la vista d'insieme
- **Barra telemetria** in alto: stato sistema, timestamp ultimo aggiornamento,
  tab leghe (Serie A / La Liga / Premier).
- **Hero**: titolo brutalista gigante (es. `FOOTY // TACTICAL MATCH TELEMETRY`).
- **PROSSIMA GIORNATA**: griglia di *match card* compatte per la lega selezionata.
- Ogni card: squadre, segno 1X2 favorito, Over/Under 2.5, cartellini attesi,
  giocatore più a rischio.

### 2. GIORNATA `/[league]/round/[n]`  — la "schedina"
- **Selettore giornata** (nav round).
- **Tabella densa** di tutte le partite della giornata con i mercati chiave
  (1X2, O/U, BTTS, MG 1-3, cartellini attesi, top ammonito) — stile telemetria.

### 3. MATCH `/match/[fixtureId]`  — la scheda completa
- Header partita (squadre, data, arbitro) con cornice tecnica.
- **Pannelli mercato** (telemetria):
  - `1X2` barra segmentata
  - `GOL` (Over 1.5/2.5/3.5, BTTS)
  - `MULTIGOL` (totale + casa/trasferta)
  - `CARTELLINI` gauge attesi + linee Over
  - `AMMONITI A RISCHIO` tabella monospace (giocatore, ruolo, prob.)
- Se la partita è già giocata: blocco **RISULTATO REALE** + "hit" (🟨/segno).

### 4. METODOLOGIA `/methodology`  — trasparenza (il nostro vantaggio onesto)
- Come funzionano i pronostici, in breve.
- **Calibrazione**: possiamo *dimostrare* che i numeri sono affidabili
  (RPS, "quando diciamo 70% succede ~70%"). Editoriale brutalista.

### 5. (FUTURO) RISULTATI/ARCHIVIO `/results`
- Tracciamento accuratezza: pronostici passati vs esiti reali.

---

## Componenti
- `TelemetryHeader` — barra superiore (stato, timestamp, cornice ASCII)
- `LeagueTabs` — switch lega
- `MatchdaySelector` — nav giornata
- `MatchCard` — card compatta (dashboard/griglia)
- `MatchTable` — tabella densa giornata (schedina)
- `MarketPanel` — blocco mercato (telemetria)
- `ProbBar` — barra/segmenti probabilità (brutalista)
- `CardsGauge` — indicatore cartellini attesi
- `PlayerRiskTable` — tabella ammoniti a rischio
- `ResultBlock` — risultato reale + hit (partite passate)

## Modello dati (TypeScript — dal `schema_version: 1`)
```ts
type Prob = number; // 0..1
interface Markets {
  "1x2": { home: Prob; draw: Prob; away: Prob };
  goals: { over_1_5: Prob; over_2_5: Prob; over_3_5: Prob; btts: Prob };
  multigol: { "1-2": Prob; "2-3": Prob; "1-3": Prob; "2-4": Prob; "home_1-3": Prob; "away_1-3": Prob };
  cards: { expected: number; over_3_5: Prob; over_4_5: Prob; over_5_5: Prob } | null;
  players_at_risk: { name: string; position: string; prob: Prob }[] | null;
}
interface Match {
  fixture_id: number; home: string; away: string; date: string; referee: string | null;
  markets: Markets;
  result: { home_goals: number; away_goals: number } | null;
}
interface RoundDoc {
  schema_version: number;
  league: { id: number; name: string };
  season: number; matchday: number; generated_at: string;
  matches: Match[];
}
```

---

## Ordine di costruzione
1. **Scaffold** `web/` (Next.js 16 + TS + Tailwind) + config static export + font.
2. **Design tokens** (colori/tipografia brutalist) + layout base + `TelemetryHeader`.
3. **Sezione 3 (MATCH)** — la scheda completa (il cuore, riusa tutti i mercati).
4. **Sezione 2 (GIORNATA)** — tabella schedina.
5. **Sezione 1 (DASHBOARD)** — griglia + hero.
6. **Sezione 4 (METODOLOGIA)**.
7. Script copia JSON `predictions/` → `web/public/data/`.
8. Deploy statico.
