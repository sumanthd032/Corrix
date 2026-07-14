# Corrix — Working Instructions

This file is the operating manual for building Corrix. Read it before doing any implementation work. It does not repeat the product design, the data methodology, or the build sequence. Those live in three documents under `docs/` and are the source of truth for what to build and why:

- `docs/CORRIX_PROJECT.md` — what Corrix is, the architecture, the reasoning behind every major decision, the judging-criteria mapping.
- `docs/CORRIX_DATA_METHODOLOGY.md` — the exact formulas, parameters, and generation logic for every data stream, real or simulated.
- `docs/CORRIX_BUILD_PLAN.md` — the ten-step sequence, task by task, with a Definition of Done for each step.

If anything in this file appears to conflict with those three documents on a matter of product design, the three documents win and the conflict should be raised with the user rather than resolved silently. This file governs process: how work gets done, not what gets built.

## 1. How to work through the build

Follow `CORRIX_BUILD_PLAN.md` in order. Its dependency table says which steps can run out of sequence and which cannot. Do not skip ahead into a step whose dependencies are not met, and do not treat a step as finished until its Definition of Done is actually satisfied, not just attempted.

Work in small units within each step. A step's "Key tasks" list is not one unit of work, it is several. Finish one task, verify it, commit it, then move to the next. Do not batch an entire step into one uncommitted block of work and then try to untangle it at the end.

Before starting a step, re-read its section in the build plan and the sections of the other two documents it references. Do not work from memory of an earlier conversation about the project. The documents are the current, authoritative state.

## 2. Ask, do not assume

If a task in the build plan is ambiguous, if a design decision is not covered by the three documents, if two documents seem to disagree, or if a technical choice has more than one reasonable answer and the documents do not pick one, stop and ask the user. Do not pick a default and proceed silently. This applies to small decisions as much as large ones. A wrong guess that is never surfaced is worse than a question that turns out to have an obvious answer.

This also applies to anything outside the three documents' scope: exact copy text for a UI screen, naming for a variable that has no naming convention yet, which of two acceptable libraries to use when the document only named a category. Ask.

## 3. Credentials and things only the user can provide

Corrix depends on external accounts and assets that cannot be created or guessed. Do not invent placeholder values that look like real keys or URLs. Use clearly named placeholders in `.env.example` and stop to ask for the real value when a step actually needs it, not before.

The following are known requirements, gathered from the build plan:

- Groq API key (free tier), for the primary Safety Council inference path.
- Gemini API key (free tier), for the secondary and multimodal inference path.
- Neo4j AuraDB Free instance, connection URI and credentials, for the Regulatory Intelligence substrate.
- A webhook target for the Emergency Response Orchestrator: a Slack incoming webhook URL, a Discord webhook URL, or SMTP credentials. The user should decide which channel to use before Step 9.
- A Render or Railway account, for the public read-only demo instance built in Step 10.
- Selection and verification of the specific DGMS circular document(s) against `dgms.gov.in`, needed before Step 5's regulatory corpus is ingested. This is a judgment call about which circular(s) are appropriate and should be confirmed with the user, not picked unilaterally.
- A webcam or a short sample video clip for the computer vision pipeline in Step 6. If the user has a specific clip in mind, ask for it and its specifications (resolution, format, length, what it should show) rather than sourcing one independently.
- Any brand assets, if the user wants a logo or specific imagery anywhere in the product. Do not generate placeholder branding and treat it as final.

When a step is reached that needs one of these and it has not been provided, stop and ask for it rather than stubbing around it in a way that would need to be unwound later.

## 4. Git and commits

The repository is initialized on branch `main`. Work is committed as it happens, not batched into one commit per step and not left uncommitted across a session boundary.

Commit after each meaningfully complete unit of work: a task from a step's "Key tasks" list, a bug fix, a schema addition, a passing test suite for a component just built. Do not commit half-finished work, and do not let multiple unrelated changes pile into a single commit.

Commit messages follow Conventional Commits: `type(scope): short description`, written in the imperative mood, lower case after the colon, no trailing period. Common types for this project:

- `feat` — new functionality (a new agent, a new endpoint, a new UI panel)
- `fix` — a bug fix
- `docs` — documentation changes, including edits to files in `docs/`, this file, or `memory.md`
- `refactor` — restructuring code with no behavior change
- `test` — adding or changing tests
- `build` — dependency, tooling, or build configuration changes
- `chore` — everything else that does not fit the above (scaffolding, config, cleanup)

Example: `feat(safety-council): scope each agent to its own MCP server`

Two hard rules on authorship, both non-standard relative to default behavior and both to be followed exactly:

1. Commit author identity comes only from the existing global git configuration on this machine. Never set a repository-local `user.name` or `user.email`, never override the configured identity, never impersonate a different author.
2. Do not add a co-author trailer, a "Generated by" line, or any other attribution to Claude, an AI, or an assistant anywhere in a commit message. Commits should read exactly as if the user made them directly.

Never use `--no-verify`, never force push, never rewrite history that has already been committed in this repository. If a commit needs correcting, make a new commit.

## 5. memory.md

`memory.md`, at the repository root, is an append-only audit log of what has actually been done, kept separate from this file. This file states rules; `memory.md` records history.

After finishing a step, or a substantial task within a step, add an entry to `memory.md` before moving on. Each entry should be honest and specific enough that a future session with no memory of this one could read it and understand exactly what state the project is in and why. An entry that only says a step is "done" without saying what was built, what was decided, and what remains is not useful and should not be written.

Do not edit or delete past entries. If something recorded earlier turns out to be wrong, add a new entry correcting it and explain what changed. The log should show the real history of the project, including mistakes and reversals, not a cleaned-up version of events.

## 6. User interface standard

The UI is the highest priority deliverable in this project, on equal footing with the reasoning system itself, not a wrapper around it. `CORRIX_PROJECT.md` Section 11 defines the visual direction: a dark, glassmorphic, "Industrial Command Center" aesthetic. That direction stands. What changes is the standard of execution against it.

The bar to build against: the data density and mission-control seriousness of Palantir Foundry and Datadog, combined with the spacing discipline, typography restraint, and micro-interaction polish of Linear, Vercel, and Stripe. Corrix should not read as a copy of any one of those products. It should read as though it belongs in that company, with its own visual identity built on the same level of care.

Concretely, this means:

- A single design token source (colors, spacing scale, type scale, radii, shadows) that every component pulls from. No inline hex codes, no one-off pixel values, no component that quietly drifts from the system.
- Consistency across every screen. A safety officer moving from the heatmap to the alert feed to the regulatory chat should never feel like they entered a different product.
- Real motion design where the document calls for it (state transitions, the Council convening, the gas-dispersion overlay), and no motion where it does not earn its place.
- Every interactive element in a finished, considered state: loading, empty, error, and populated, not just the happy path.

If a screen or component does not clear this bar, it is not finished, regardless of whether the underlying logic works.

## 7. Writing and content style

Anything written as part of this project, UI copy, documentation, commit messages, code comments, in-app explanations, should read as though a careful person wrote it directly. It should not read as AI-generated text.

Concretely:

- No em dashes. Use a comma, a period, or restructure the sentence.
- No emojis, anywhere, including in UI copy, commit messages, or documentation.
- No hedging filler ("it's worth noting that," "it's important to remember"). State the point.
- No inflated transition words (moreover, furthermore, additionally) where a plain sentence works.
- No marketing language in functional copy (seamless, robust, leverage, unlock, elevate, cutting-edge, next-generation). Describe what something does in plain terms.
- No "not just X, it's Y" construction.
- Short, direct sentences over long compound ones stitched together with commas and qualifiers.

This applies to everything written from this point forward, including future edits to `docs/`, this file, and `memory.md`. It does not require rewriting the existing three design documents, which the user has confirmed are settled as written.

## 8. Assets

If a task calls for an image, an icon set, a video clip, a real URL to an external resource, or any other asset that cannot be generated or verified independently, stop and ask the user for it, with a clear specification of what is needed (format, dimensions, content, source). Do not invent a URL. Do not use a stock placeholder and treat it as final without flagging it as a placeholder.

## 9. Quick reference

Before touching code: read the relevant sections of the three `docs/` files and the current state of `memory.md`.
Before a decision with no obvious answer: ask.
After a completed unit of work: commit, using the global git identity, Conventional Commits format, no AI attribution.
After a completed step or major task: update `memory.md`.
Before calling a UI screen finished: check it against Section 6 of this file.
Before writing any user-facing or documentation text: check it against Section 7 of this file.
