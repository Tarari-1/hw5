# The Back Desk: dashboard design

The dashboard (`frontend/`, React + Vite + TypeScript) is where a person watches the
five-agent team work a ticket, signs for the money, and sees the cash move.
Screenshots referenced below are in `output/dashboard_screenshots/` (in the published repo: compressed JPEGs, all desktop states plus two phone shots). They were
taken with headless Chrome against a scratch backend playing a scripted demo, so
the agent words in them start with "[demo]" and are not real agent output.

## The concept: a print shop's back desk

One idea carried all the way through: **a navy desk mat with cream paper on it.**
Everything a person reads is a piece of paper on the desk, and each piece behaves
like the real thing:

| Real object | On the dashboard |
|---|---|
| Ticket spike | Tickets as paper slips with a perforated edge, a brass clip, threaded on a gold rail (left column). |
| Rubber stamp | A red-ink **RESOLVED** stamp (grey **DECLINED**) that thumps onto the ticket, and the subject gets struck through. |
| Paper clip / flag | A gold "Needs a signature" flag on open tickets with pending approvals. |
| Name plates | Five colleagues on "the floor", each with its own plate shape and mark. |
| Routing slip | A numbered list of who asked whom, beside a map of the team. |
| Memo | The Boss's final decision as an interoffice memo. |
| Time cards | One card per colleague: tools used, counts, their final words. |
| Carbon copies | The full event log, in carbon-blue monospace. |
| Till / receipt | The checking balance on receipt paper under a brass header. A change prints a torn tape slip (−$840.00). |
| Slips that need a signature | Approvals as slips with a signature line; signing opens a confirmation dialog. |
| Drafts tray | Customer drafts with a faint "DRAFT · NOT SENT" watermark. |
| End of day | Reset is "Clear the desk…", in a dashed red danger outline. |

**Type.** Zilla Slab, a slab serif with a letterpress feel, for headings, stamps
and the memo. IBM Plex Sans for reading text. IBM Plex Mono for anything that is a
record: ledger figures, tool names, carbon copies, ticket numbers. All three are
self-hosted through `@fontsource`; the build bundles them, so no font CDN is
contacted.

**Palette.** Campus navy (`#16223f` ink, `#1a2747` mat), cream paper (`#fbf6ea`),
brass gold (`#c99a33`) for the till header and the primary "hand it to the team"
button, and one stamp red (`#a3262a`) kept for stamps, money going out, refusals
and danger. There are no gradients beyond the brass header, no glass effects and
no icon grid.

## Layout

- **Desktop (≥ 1180 px): three columns, like sitting at the desk.** The spike and
  the reset on the left. The floor in the middle (plates, team map, routing slip,
  memo, time cards, carbon copies). The counter on the right (till, signature
  slips, drafts tray). See `01-initial-desktop.jpg` and
  `03-finished-resolved-desktop.jpg`.
- **Medium widths:** two columns, with the counter moved into a full-width row below.
- **Phone (< 760 px): one stack.** The order is tickets → till, slips and drafts →
  the floor. The first phone build put the till and slips at the very bottom, below
  a long log; I moved them up because they are what a person acts on. See
  `06-refusal-insufficient-cash-phone.jpg`.

## Five colleagues, not five boxes

Each agent differs in **shape, mark, typographic voice and label**. Colour is a
fourth cue, never the only one.

| Agent | Plate shape | Mark (original SVG) | Voice |
|---|---|---|---|
| The Boss | double-ruled rounded plate | a round seal with a star | Zilla Slab small caps |
| Inventory | dashed "stencil" crate outline | a slatted crate | uppercase Plex Mono |
| Accounting | ruled ledger paper with a red margin line | ledger columns | Plex Mono, tabular figures |
| Facilities | key tag with a punched hole | a house-shaped key tag | wide-tracked uppercase Plex Sans |
| Customer Service | speech-note card with one sharp corner | a speech bubble | Zilla Slab italic |

**State is written, not just coloured.** The plates say "At the desk", "Thinking",
"Using check_stock", "Asking Accounting", "Done" or "Stopped" (with the reason).
A small lamp adds a second cue: it pulses for thinking, fills for a tool call,
spins dashed while asking, turns green for done and red-square for stopped.
Active plates lift and get a gold halo. Colleagues who haven't taken part sit
greyed "At the desk". See `02-run-in-progress-desktop.jpg`, where the Boss is
asking Inventory, Inventory is asking Accounting, and Accounting is thinking.

**Delegation reads as teamwork.** The team map draws all ten agent pairs as faint
dashed lines; every colleague can reach every other, so 20 directed links are
open. Each real hand-off is drawn as an ink arrow with its order number
(1, 2, 3…). The routing slip beside it lists the same hand-offs in words, with
"waiting for answer" / "answered" / "refused: …". The list is the accessible
version; the SVG has an `aria-label` that spells out the order.

## How the important moments show up

- **Running:** the ticket gets diagonal "in the press" stripes and reads
  "open · team working". A run line shows the run id and status, and a polite
  live region speaks the latest step at most every 4 seconds (`02-…`).
- **Resolved:** the stamp thumps in (380 ms overshoot), the subject is struck
  through, and the paper darkens slightly. If approvals are still pending, the
  ticket says so: "resolved · 1 signature still needed" (`03-…`).
- **Open, waiting for a human:** a different look from both open and resolved:
  warm yellow paper, a gold "Needs a signature" flag, and the words
  "open, waiting for a human (1 to sign)" (`06a-open-waiting-for-human-desktop.jpg`).
- **The memo:** the Boss's `final_decision`, each action as TAKEN or PROPOSED with
  owner and signature need, and the human-approval line, all copied from the typed
  decision.
- **Signing:** the dialog repeats the exact amount and target and says in plain
  words what will happen ("This will pay $840.00 from checking (invoice 501).").
  It asks for a self-declared name, which the browser remembers as a convenience,
  and the button says exactly what it does: "Sign and pay $840.00"
  (`04-approval-confirmation-desktop.jpg`).
- **Cash drop:** the till figure flashes once, and a receipt tape prints out below
  it: "−$840.00 · was $3,400.00, now $2,560.00", in stamp red. The slip area also
  confirms "Cash $3,400.00 → $2,560.00" (`05-after-approval-cash-drop-desktop.jpg`).
- **Refusal:** the backend's own reason, in red: "Insufficient cash: checking has
  1000.0, payment is 2400.0…", plus "The proposal is back to pending; nothing was
  paid." The slip stays, now showing "Last attempt refused"
  (`06-refusal-insufficient-cash-desktop.jpg`, `06-refusal-insufficient-cash-phone.jpg`).
- **Backend down:** a full-width red-edged banner: "Can't reach the desk server at
  http://localhost:8000. Start it with `uvicorn main:app --reload --port 8000`
  from the backend folder." The lamp in the masthead turns red, the last-known
  board stays visible, and actions are disabled. It retries every 4 s
  (`07-backend-down-desktop.jpg`).
- **Reset:** a danger dialog ("Clear the whole desk?") that explains what will be
  lost and starts focused on "Keep everything" (`08-reset-confirmation-desktop.jpg`).
  After a reset, a note reports that the checksum matches the original and the
  audit trail was kept (`09-after-reset-desktop.jpg`).
- **Stopped / error run:** the memo turns into a red-edged "Run stopped" note with
  the server's reason, and busy plates switch to "Stopped" with that reason. This
  is covered by unit tests; I did not take a screenshot of it, because the demo
  playback always finishes.

**Opening a finished run (`?run=<run_id>`, added in Problem 9).** The board can open one finished run
read-only from the desk server's memory, e.g. `http://localhost:5173/?run=124ecff114e0`. It loads that
run's status, decision and events with GET requests only, and says so in a gold-edged note. Ticket
stamps, approvals, drafts and the till still show the desk *now*, so a screenshot taken later shows the
later cash balance. Only 12-hex-digit run ids are accepted (unit-tested). Runs are lost when the backend
restarts.

## Honesty rules built into the UI

- **No invented text about agents.** State labels come from a fixed vocabulary.
  Every sentence about what an agent did is copied from the API: the Boss's
  `final_decision`, the `summary` a specialist returned to its caller (read from
  the delegation result in the audit trail), or event summaries. The audit writer
  shortens summaries to 240 characters; when that cuts a report summary, the time
  card shows "…" and "(shortened in the audit trail)" rather than guessing the rest.
- **Demo runs are labelled.** A striped banner, "Scripted demo playback on scratch
  data: no model is running", appears whenever the run's events carry run_label
  `dashboard-demo`.
- **Money moves only from the signature dialog.** No automatic approvals and no
  approve shortcut. Enter only submits inside the open confirmation dialog, which
  is the explicit confirmation.
- **Plain text everywhere.** All text is rendered through React (escaped). There is
  no `dangerouslySetInnerHTML` (the lint rule `react/no-danger` is an error) and no
  markdown rendering.

## Accessibility

- **Contrast:** body text on cream is about 13:1. Muted text (`#5a5546`) on cream
  is about 7:1, and stamp red on cream about 6.5:1. Text placed directly on the
  navy mat uses light cream (`#e2dac2`). The first build had too-dim hints on the
  mat and on paper; I fixed both after looking at the screenshots.
- **Focus:** a 3 px navy outline plus a 6 px gold halo, visible on both cream paper
  and the navy mat. A skip link jumps to the floor.
- **Keyboard:** everything is a native `<button>`, `<input>` or `<dialog>`, so Tab,
  Enter and Space work and Escape closes dialogs (the browser traps focus inside).
  I tested keyboard-only operation of run, approve and reset in headless Chrome:
  2 Tabs to ticket 101, 3 to the start button, 3 to "Approve…", 2 to
  "Sign and pay $840.00", 6 to "Clear the desk…", 1 to "Yes, reset the desk".
- **ARIA:**
  - Ticket buttons use `aria-pressed` for the selected ticket.
  - Each panel is a labelled region.
  - One polite, atomic live region announces the latest agent step, throttled to
    one message every 4 s so it doesn't flood a screen reader.
  - Outcomes use `<output>` (status), and refusals and the down banner use
    `role="alert"`.
  - The team map is `role="img"` with a full text label.
- **Reduced motion:** under `prefers-reduced-motion: reduce`, every animation and
  transition is turned off (stamp thump, lamp pulse, tape print, lifts). The
  information stays: the tape still shows −$840.00 and the stamp still appears.
  Tested by emulating the media feature: the stamp's `animation-name` changed from
  `thump` to `none`.
- **Phone:** a single stacked column with 44 px tap targets
  (`01-initial-phone.jpg` and `06-refusal-insufficient-cash-phone.jpg`, 390 px wide).

## Performance

React and React DOM only. There are no UI, chart or icon libraries; the marks are
hand-drawn inline SVG. The production build is about 79 kB gzipped JS and 5 kB
gzipped CSS, plus about 160 kB of local font files across 7 faces. Polling runs
about every 1 s during a run and every 8 s otherwise, with health every 15 s
(every 4 s while the server is down). It all pauses when the tab is hidden.

## Limits (honest list)

- **Approvals and runs:**
  - The approver's name is self-declared; there is no login (see harness Safety).
  - Run history lives in server memory: after a backend restart, the board shows
    the tickets' real status but not the old run's memo.
- **What the screenshots show:**
  - They come from a scripted demo, not a real agent run. They show the UI states
    truthfully, but the agents' words are scripted "[demo]" text.
  - A stopped or errored run has no screenshot; that state is only unit-tested.
  - In the full-page dialog screenshots, the dark backdrop covers only the first
    screen height. That is an artifact of headless full-page capture; in a real
    window it covers the viewport.
- **Text on the board:**
  - The carbon copies show event summaries as the audit trail stores them: compact
    JSON with nested values shown as `<list len=…>`. That is faithful but
    technical.
  - A specialist's final words come from the shortened audit summary, so long
    reports are cut at about 240 characters.
- **Live updates:**
  - The dashboard polls rather than streaming, so a step can appear up to about a
    second late.
  - The live region speaks at most every 4 s, so some steps are never announced
    individually (the carbon log has all of them).
