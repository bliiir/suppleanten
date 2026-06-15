# Suppleanten — Stakeholders, Journeys & User Stories

*A working design document. Multi-channel (SMS, Telegram, WhatsApp, email, web) LLM-mediated assistant for Danish foreninger. The backend owns multi-tenancy, documents, invoices, and retrieval; the channels are thin, swappable transports feeding one agent layer.*

---

## 1. How to read this

Every story below traces the same arc: **a person, on a channel, with a need, meeting the system for the first time or the hundredth — and what they're actually trying to reach.** The point isn't the chat UX; it's the journey from "I have a question" to "I have the answer (or a reason I can't have it)."

Three things govern every journey, so they're worth fixing before the stories:

- **The interaction model.** Channel gives a *short* answer plus a deep-link to the web app for anything detailed or sensitive. The channel is the doorway; the web session is the room.
- **The trust model.** Two tiers. **Recognition** = "an inbound identifier *claims* to be a known person" → warm greeting, general/public answers, offer to verify. Nothing member-specific. **Proven** = an outbound round-trip (OTP to the claimed number/email, or a deep-link from an already-authenticated web session) has confirmed channel control → member-specific data, channel binding, actions. Recognition is not authentication. Inbound identifiers are claims, not proof.
- **The identity spine.** One canonical account per human. Channels (Telegram user-id, WhatsApp/SMS number, email, web login) are *verified bindings* hanging off it. Permissions live on the account and its memberships — never on the channel. One human can hold several memberships across several foreninger; a single inbound message resolves in three deliberately separate lookups: **channel → account (who) → active forening context (which tenancy) → role (what they may see).**

---

## 2. Stakeholder map

Each stakeholder has a **trust ceiling** — the most they could *ever* be shown, regardless of how well they authenticate — and a **default acquisition path** (how they first meet Suppleanten).

| Stakeholder | Relationship to forening | Trust ceiling | Default acquisition path |
|---|---|---|---|
| **Bestyrelsesmedlem** (formand, kasserer, menigt medlem, suppleant) | Elected; governs and publishes | Everything for *their* forening, incl. other members' arrears, supplier contracts, persondata, draft referater | Board onboarding (kasserer imports list) → magic link |
| **Medlem** (andelshaver / ejer) | Owns a share or a unit | All member-general material + *their own* economy and cases. Never other members' personal data | Board email blast with magic link |
| **Lejer / framlejetager** (tenant) | Rents from a member; relationship is with the *ejer*, not the forening | Building-info only: husorden, varslinger affecting them, fault reporting. **No** forening economy, **no** member roster | QR code in the stairwell |
| **Leverandør** (vicevært, VVS, gartner, håndværker) | Performs one-shot paid work | Only the specific job/RFQ/invoice they're attached to — tenant-scoped, nothing else | Scoped link inside a work order or RFQ reply |
| **Entreprenør / byggerådgiver** (byggesag) | Long-lived party on a major project (renovation, tag, facade) | Only *their byggesag*: contract sum, tidsplan, their own acontofakturaer, their slice of the byggeregnskab. Never the forening's økonomi, other firms' pricing, or member data | Project invitation → scoped, persistent project workspace |
| **Administrator** (ejendomsadministrator) | Professional firm; bogføring, opkrævning, regnskab | Financial + operational material, scoped per forening they manage | Onboarded as a privileged service account |
| **Revisor** | Audits the årsregnskab | Time-boxed access to financials + bilag for the audit period | Time-boxed document-pack link |
| **Mægler / køber** (agent / prospective buyer) | Handling a sale | Time-boxed **sales pack** only: vedtægter, referater, seneste regnskab, vedligeholdelsesplan, energimærke, nøgleoplysningsskema | Time-boxed link triggered by the seller or board |
| **Forælder** (sport variant) | Parent of a youth member | Their child's hold info, træningstider, kontingent for that child | QR at the klubhus / in the welcome email |

Note the asymmetry that drives the security design: **the people most likely to attack — a neighbour in a dispute, an ex, a member feuding with the board — sit *inside* the recognition tier already.** They know the building. The trust ceiling, not the greeting, is what protects the data.

---

## 3. Material map & sensitivity tiers

What a forening holds, and which trust tier may serve it. This is the bridge between "what they want" and "what tier / channel can give it."

| Tier | Material | Where it's served |
|---|---|---|
| **Public-ish** (recognition OK, inline on channel) | Husorden, "when is the next generalforsamling", vicevært contact, general "what do the vedtægter say about pets/parking", FAQ | Short answer on-channel, no proof needed |
| **Member-general** (proven tier, deep-link to web) | Full vedtægter + bilag, budget, årsregnskab, mødereferater, generalforsamlingsreferater, vedligeholdelsesplan, forsikringspolice, energimærke | One-line answer + deep-link into authenticated web session |
| **Personal / owner-specific** (proven tier, strong) | Your own restance/boligafgift, your fordelingstal, your sag/case, your andelsværdi, your fakturaer | Always hands off to web; never rendered inline |
| **Board-only** (proven + board role) | *Other* members' arrears, supplier contracts & negotiations, draft referater, member-specific sager, persondata | Web only, role-gated |
| **Supplier-scoped** (separate scoped identity) | The one RFQ / work order / invoice they're attached to | Scoped link; no lateral visibility |
| **Byggesag-scoped** (project workspace) | Entreprisekontrakt, tidsplan, projektmateriale/tegninger, byggetilladelse, aftalesedler (variations), acontobegæringer & -fakturaer, byggeregnskab, afleveringsprotokol, mangelliste, garantier, entrepriseforsikring, 1-/5-års eftersyn | Persistent project workspace; each party sees only their ring (see §3.5) |
| **Sale pack** (time-boxed) | Vedtægter, seneste referater, seneste regnskab, vedligeholdelsesplan, energimærke, nøgleoplysningsskema/andelsvurdering | Expiring link; read-only |

**Rule of thumb baked into the agent:** if a response would reveal one person's money or another person's data, it hands off to a proven web session — never inline on a channel. The recognition tier *is* the inline-answer tier; the proven tier *is* the deep-link-to-web tier. Same boundary your Telegram POC already drew, now named.

### 3.5 The byggesag as a first-class scoping container

A major project (facaderenovering, tagudskiftning, kloak, vinduer) is not a document tier — it's a **container** that owns its own document set, timeline, and budget ledger, and onto which multiple scoped identities attach with different rings of visibility. Three concentric rings:

- **Ring 1 — entreprenør / underentreprenør:** sees only *their* contract sum, the tidsplan, their own acontofakturaer and aftalesedler, and the manglar assigned to them. No sight of other firms' pricing, the forening's reserves, or any member.
- **Ring 2 — byggerådgiver + board project lead:** sees the whole byggesag — all parties, full byggeregnskab (budget vs. actual), all variations, the complete tidsplan. This is the working ring.
- **Ring 3 — forening økonomi:** the byggesag's totals roll up here (financed via opsparing, byggelån, or særligt indskud/lån per member). Only board + administrator. The byggesag is a *scoped view* into this, never the whole of it.

**Authority is separate from access.** Seeing the byggeregnskab is a *proven + board-role* read. *Committing* the forening — signing the entreprisekontrakt, approving an aftalseddel/ekstraarbejde, releasing an acontofaktura for payment — is a distinct **authority check** with its own audit log, and large commitments may require a generalforsamling mandate rather than a board decision alone. The agent must treat "show me" and "approve" as different gates on the same object.

**The byggesag is also a broadcast source.** Scaffolding up, water off, "håndværkerne skal ind i din lejlighed tirsdag" — each is a board→member varsling generated *from* the project and fanned out through the B1 broadcast path. The project workspace and the member-notice stream are two faces of one object.

---

## 4. Acquisition journeys — how they get acquainted

### 4.1 The board email blast (members)
Mette (kasserer) imports the member roster (name, unit, email/phone) into Suppleanten. The system sends each member an intro email: *"AB Søparken bruger nu Suppleanten — tryk her for at komme i gang."* The link carries a single-use, signed token that lands them in an authenticated web session bound to their account and their membership. From there they can connect further channels outward (Telegram, WhatsApp) with deep-links — no cold verification needed, because the proof already happened on web. **This is the happy path and the one to optimise.**

### 4.2 The QR code in the stairwell (tenants + stragglers)
A poster in the opgang: *"Spørgsmål om ejendommen? Scan her."* It serves two populations the email blast misses — **lejere** (whom the forening may not even formally know) and members who weren't in the roster. The QR opens a web onboarding that asks who they are and which unit, then runs a **proof** step appropriate to the claim: a member claim triggers a match-and-OTP; a tenant claim opens only the building-info tier and quietly flags the unit for the board to confirm. The poster is also where the **SMS number** lives, for people who won't scan.

### 4.3 The supplier reply (leverandører)
The board sends Henrik (vicevært) a work order, or an RFQ goes out to three VVS firms. The supplier's reply (email or SMS) lands them in a **scoped** interaction tied to exactly that job — they can ask about the task, upload a quote or invoice, confirm a time. They see nothing else in the forening. The supplier never becomes a "member"; they hold a job-scoped identity that expires with the job.

### 4.4 The cold SMS (Birgitte, 74, won't scan anything)
Birgitte texts the number from the stairwell poster: *"hvornår er der generalforsamling"*. Inbound, unproven. The system answers the **public** question inline (the GF date is not sensitive) and offers: *"Vil du også kunne se dine egne ting? Så sender jeg lige en kode."* If she says yes, an **outbound OTP** to her number turns "claims to be this SIM" into "controls this SIM," and she's bound — all without a web browser ever opening.

### 4.5 At the generalforsamling
The indkaldelse (and the screen at the meeting) carries a QR. Captive, motivated audience; high-conversion onboarding moment. Same magic-link mechanics as the email blast.

### 4.6 The sale (mægler + buyer)
Birgitte is selling her andel. Either she or the board triggers a **time-boxed sales-pack link** for Sofie (mægler). It's read-only, expires, and exposes only the sale-pack material — never live member data or board internals.

### 4.7 The project invitation (entreprenør joins a byggesag)
The board awards the facade contract. From the byggesag workspace, the project lead invites the winning entreprenør — a scoped invitation (email + OTP, or a deep-link) that drops them into **Ring 1 of that one byggesag**, persistent for the project's life rather than expiring with a single job. The byggerådgiver gets a Ring 2 invitation. Each party proves channel control once, then collaborates inside the project: reading the tidsplan, submitting acontobegæringer, uploading aftalesedler and afleveringsmateriale. Access ends when the byggesag is closed (or, for garantiperioden, narrows to the eftersyn/mangel scope).

---

## 5. User stories

Format per story: a one-line **As a… I want… so that…**, then the **journey** (what actually happens), the **material** reached, and the **mechanics** it exercises.

### Members

**M1 — Birgitte asks a simple question by SMS**
*As an andelshaver who doesn't use apps, I want to text a plain question and get a plain answer, so that I don't have to log into anything.*
Journey: Birgitte texts *"må man have hund i Søparken?"*. Recognition tier (her number matches the roster, but no proof yet). The answer is public, so the agent replies inline: *"Ja — husordenen tillader hunde, men ikke i gården uden snor. Vil du se hele husordenen?"* with a link.
Material: husorden (public-ish). Mechanics: recognition-tier inline answer; no proof required for public material; offer-to-expand.

**M2 — Omar checks his own boligafgift**
*As a new andelshaver, I want to see what I owe and when, so that I don't miss a payment.*
Journey: Omar (already onboarded via the email blast, Telegram bound) DMs the bot *"hvad er min boligafgift i juli?"*. This is personal/financial → the agent does **not** answer inline. It replies: *"Det viser jeg dig sikkert her 👇"* with a deep-link into his authenticated web session showing his own opkrævning.
Material: personal boligafgift (personal tier). Mechanics: proven-tier hand-off; financial data never rendered on-channel even to a bound, proven user.

**M3 — A member reaches the latest referat**
*As a member, I want the minutes from the last board meeting, so that I know what was decided about the facade project.*
Journey: *"hvad blev besluttet om facaden?"*. Agent retrieves over the mødereferater (RAG), gives a two-sentence summary inline, and links to the full referat behind the web session.
Material: mødereferat (member-general). Mechanics: retrieval + short answer + deep-link; member-general material summarised inline but the document itself sits behind proof.

**M4 — Birgitte adds Telegram later**
*As a member who started on SMS, I want to switch to Telegram, so that I can also receive the board's notices there.*
Journey: From her proven SMS thread she says *"kan jeg få det på Telegram?"*. The system SMSes her a short-lived, single-use code and a `t.me/SuppleantenBot?start=<code>` link. She opens a **private DM** with the bot (never a public channel), the code binds her Telegram user-id to her existing account.
Material: n/a (binding). Mechanics: channel binding bootstrapped from an already-proven channel; code is a bearer credential — short TTL, single-use, DM-only.

### Board

**B1 — Mette broadcasts the GF notice**
*As kasserer, I want to send the indkaldelse to all members, so that the meeting is properly convened.*
Journey: From the board web view, Mette composes the indkaldelse once. The system fans it out per member's preferred channel — Telegram and email send freely; WhatsApp goes as a pre-approved **utility** template (proactive, outside any service window, metered); SMS as a fallback for the Birgittes.
Material: indkaldelse til generalforsamling (member-general, board-initiated). Mechanics: proactive multi-channel broadcast; per-channel send rules; WhatsApp template/cost awareness baked into the send path.

**B2 — Jens checks who's in arrears**
*As formand, I want to see which members are behind on payments, so that the board can act before the regnskab closes.*
Journey: Jens, proven + board role, asks on the web (this never leaves a channel). He sees the restanceoversigt — *other people's* financial data, which only the board ceiling permits.
Material: members' arrears (board-only). Mechanics: role-gated, web-only; the canonical-account role check, not the channel, authorises it.

**B3 — A suppleant steps up mid-term**
*As a suppleant who's just joined the active board, I want my access to widen automatically, so that I can do the work.*
Journey: The board updates roles in the web admin. Because permissions live on the account + membership, the suppleant's ceiling rises across *all* their bound channels at once — no re-onboarding.
Material: widens to board-only. Mechanics: role change on the account propagates to every channel; single source of truth.

### Tenants

**T1 — Lærke reports a leak**
*As a lejer, I want to report a water leak and find the house rules, so that I can live here without contacting my landlord for everything.*
Journey: Lærke scans the stairwell QR. She onboards into the **building-info tier** only. She reports the leak (which opens a sag routed to the vicevært + board) and reads the husorden. She asks *"hvad er min andel af varmeregningen?"* — the agent declines: *"Det hører til din udlejer — jeg har kun ejendommens fælles oplysninger."*
Material: husorden + fault reporting (public-ish / building-info); forening economy **walled off**. Mechanics: tenant ceiling enforced; lejer ↔ udlejer boundary respected; fault report routed without granting forening visibility.

### Suppliers

**S1 — Henrik (vicevært) gets a work order**
*As the vicevært, I want the details of a job and a way to confirm it's done, so that I don't need an account in their system.*
Journey: The board dispatches a work order; Henrik gets a scoped SMS/email link. He sees the task, the unit, the contact — nothing else. He replies with a photo and *"færdig"*, closing the sag.
Material: one work order (supplier-scoped). Mechanics: job-scoped identity, expires with the job; zero lateral visibility into the forening.

**S2 — A VVS firm answers an RFQ**
*As a contractor, I want to submit a quote in reply to the board's request, so that I can win the work.*
Journey: RFQ goes to three firms. Each reply lands in a scoped thread tied to that RFQ; they upload a tilbud. The board compares them in the web view. Firms never see each other or anything else.
Material: the RFQ + their own tilbud (supplier-scoped). Mechanics: per-recipient scoping; board-side aggregation.

### Byggesager (major projects)

**BY1 — The board commits to a contract**
*As the board project lead, I want to sign the entreprisekontrakt within our mandate, so that the work can start and the commitment is logged.*
Journey: The board opens the byggesag, reviews the contract, and signs. The system checks **authority**: is this within the mandate the generalforsamling granted, or does it exceed it? If within mandate, it records the commitment with who/when/amount to the byggesag audit log; if over, it blocks and flags that a GF decision is required.
Material: entreprisekontrakt (byggesag-scoped, Ring 2/3). Mechanics: authority check distinct from read access; commitment audit trail; GF-mandate ceiling on board spend.

**BY2 — Entreprenør submits an acontofaktura**
*As the entreprenør, I want to submit my stage invoice and see where it is, so that I get paid on schedule.*
Journey: From Ring 1 the entreprenør uploads an acontobegæring tied to a tidsplan milestone. The agent confirms receipt and routes it to the board project lead for approval — it does **not** confirm payment. The entreprenør can later ask *"er faktura 3 godkendt?"* and see status only for their own invoices.
Material: their own acontofaktura + status (byggesag-scoped, Ring 1). Mechanics: invoice intake; counterparty sees only own ring; the submit ≠ approve ≠ pay separation begins here.

**BY3 — The invoice-approval loop**
*As kasserer, I want to check a stage invoice against the contract and tidsplan before it's paid, so that we don't overpay or pay for unfinished work.*
Journey: Mette gets the routed acontofaktura, sees it against the contract sum, the milestone, and budget-vs-actual. She either queries it back to the entreprenør (scoped thread) or approves it — and **releasing it for payment** is a money-moving action, so it steps up to a web-session confirmation and writes to the byggeregnskab and audit log. Payment itself is handed to the administrator/bank, never executed by the agent.
Material: byggeregnskab + the invoice (board-only / Ring 2). Mechanics: money-moving step-up; budget-vs-actual read; the agent orchestrates approval but does not move funds.

**BY4 — An ekstraarbejde (variation) arrives**
*As the board, I want variations handled as explicit decisions, so that scope creep doesn't silently blow the budget.*
Journey: The entreprenør submits an aftalseddel for unforeseen work. It does not auto-approve. It surfaces to the board as a decision with its budget impact shown against remaining contingency; approval is an authority-checked, logged commitment. Members affected by cost or timeline see a downstream varsling only after the decision.
Material: aftalseddel + budget impact (byggesag-scoped, Ring 2). Mechanics: variation = explicit authority gate + audit; contingency tracking; the classic budget-killer made non-silent.

**BY5 — Members hear about the scaffolding**
*As a member, I want to know when work affects my apartment, so that I can plan around it.*
Journey: The project lead schedules "stillads op i opgang B, uge 34" in the byggesag. This generates a board→member varsling fanned out via B1 — Telegram/email free, WhatsApp as a utility template, SMS to the Birgittes. Omar replies *"skal de ind i min lejlighed?"*; the agent answers from the tidsplan inline (public-ish, building-info) and links to detail if needed.
Material: project-derived varsling (public-ish / building-info). Mechanics: byggesag as broadcast source; reuses the broadcast send rules; reactive Q&A off the project timeline.

**BY6 — Aflevering and the mangelliste**
*As the byggerådgiver, I want to run the afleveringsforretning and track manglar to closure, so that we don't release the final payment with defects open.*
Journey: At aflevering, the rådgiver (Ring 2) records the afleveringsprotokol and a mangelliste; each mangel is assigned to the responsible entreprenør, who sees only their own items (Ring 1). Slutafregning is gated on mangel closure + garanti documentation. When the byggesag closes, party access narrows to the garantiperiode/eftersyn scope rather than vanishing.
Material: afleveringsprotokol, mangelliste, garantier (byggesag-scoped). Mechanics: per-party mangel assignment; final payment gated on closure; access lifecycle from active → garanti → closed.

### Sale / external

**SA1 — Sofie (mægler) pulls the sales pack**
*As an estate agent, I want the documents a buyer needs, so that I can prepare the salgsopstilling.*
Journey: Birgitte triggers a time-boxed sales-pack link. Sofie downloads vedtægter, seneste referater, seneste årsregnskab, vedligeholdelsesplan, energimærke, and the nøgleoplysningsskema. The link expires; it never exposed live member data or board internals.
Material: sale pack (time-boxed). Mechanics: expiring, read-only, content-scoped link; no standing identity created.

### Sport variant

**SP1 — Thomas (parent) finds training times and pays kontingent**
*As the parent of a youth player, I want my kid's training schedule and a way to pay the kontingent, so that we're set for the season.*
Journey: Thomas scans the QR in the welcome email. He's bound to his child's hold. He asks *"hvornår træner U12?"* (answered inline, public-ish) and *"hvad skylder jeg i kontingent?"* (hands off to a proven web view, since it's his own economy).
Material: træningstider (public-ish) + own kontingent (personal). Mechanics: same two-tier split in a non-housing forening; the "tenant" slot becomes "parent/guardian," the "unit" becomes "hold."

---

## 6. Antagonist & edge-case stories

These exist to make the security model concrete. Each one *should* fail safely.

**X1 — The feuding neighbour (spoofed SMS).** A resident in a dispute spoofs Jens's number and texts in, hoping to read his arrears. Recognition tier greets warmly but reveals nothing personal; the moment sensitive data is requested, an **outbound OTP** goes to the real SIM — which the attacker doesn't hold. Fails at the proof step. *(Knowledge questions wouldn't have helped: the neighbour knows the building. The OTP does, because they don't have the SIM.)*

**X2 — The SIM-swapper.** A remote attacker has port-stolen a member's number, so they pass the OTP. For a money-moving action (changing the bank account a fee is drawn from), the agent steps up to a **web-session confirmation** and optionally a transactional knowledge question ("roughly what was your last fee payment") — private-but-verifiable, not socially knowable. KBA and OTP fail against opposite attackers; here KBA patches OTP's one hole.

**X3 — The membership-enumeration probe.** Someone texts a range of numbers hoping the bot will confirm "Hej Jens, du er medlem af Søparken." It never does. Unverified responses stay generic ("I can help once I confirm it's you"); knowledge questions, if posed, fail non-informatively and are hard rate-limited so they can't be turned into an oracle.

**X4 — The departed member.** Birgitte completes her sale. The board revokes *one membership*. Because access lives on the account + membership, her Telegram, SMS, email, and web access to Søparken's data all drop in a single write — while any membership she holds in another forening is untouched.

**X5 — The double-hatted human.** Omar is an andelshaver in Søparken *and* the elected formand of Valby Boldklub, same Telegram account. An inbound message needs an **active forening context**: the agent disambiguates with a quick-reply when the question is ambiguous, remembers the current context, and infers it when the content makes it obvious ("hvornår træner U12" can only be the boldklub).

**X6 — The curious entreprenør.** A contractor in Ring 1 asks *"hvad bød de andre firmaer?"* or *"hvor mange penge har foreningen?"*. Both are outside their ring. The agent declines without revealing that the data exists for someone else — competitive pricing and forening reserves never leak across the ring boundary, even to a fully proven, legitimately-attached project party.

**X7 — The unauthorised commitment.** The board project lead tries to approve an aftalseddel that pushes the byggesag past its GF mandate, or releases an acontofaktura for a milestone the tidsplan shows as unfinished. The **authority gate** (separate from read access) blocks it: over-mandate spend routes to a GF decision; an out-of-sequence payment surfaces the mismatch before release. Every attempt — blocked or allowed — is in the audit log. *Access let them see it; authority is what stops them committing it.*

---

## 7. Cross-cutting requirements that fall out of these stories

A starter backlog, implied by the journeys above:

- **Identity spine**: canonical account; channel bindings as verified aliases; permissions on account + membership, never on channel.
- **Proof primitives**: outbound OTP (SMS/email), magic link from web session, deep-link channel binding (single-use, short TTL, DM-only).
- **Two-tier response policy** in the agent: every answer classified *inline-safe* vs *hand-off-to-web*; anything touching one person's money or another's data hands off.
- **Material sensitivity labels** on every document/data type, driving tier + channel.
- **Per-channel send rules** for proactive board broadcasts (free on Telegram/email; templated + metered on WhatsApp; SMS fallback).
- **Scoped identities** for suppliers and time-boxed packs for mæglere/revisor — no standing accounts.
- **Active-forening-context resolution** for multi-membership humans.
- **Lifecycle**: one-write revocation on membership end; role changes propagate to all channels.
- **Anti-enumeration**: generic unverified responses; rate-limited, non-informative KBA; step-up only on elevated risk signals.
- **Tenant wall**: building-info tier strictly separated from forening economy and member roster; lejer ↔ udlejer boundary respected.
- **Byggesag as scoping container**: first-class project object owning its document set, tidsplan, and byggeregnskab; concentric rings (entreprenør → rådgiver+board → forening økonomi) with no cross-ring leakage.
- **Authority gates separate from access**: commit/approve/release-for-payment are distinct from read; each is authority-checked, logged, and bounded by GF mandate where applicable.
- **Submit ≠ approve ≠ pay**: invoice intake, board approval, and fund release are three steps; the agent orchestrates the first two and hands payment to the administrator/bank — it never moves money.
- **Project lifecycle**: party access transitions active → garantiperiode (narrowed to eftersyn/mangel) → closed; final payment gated on mangel closure + garanti docs.

---

*Next reasonable step: turn §5 + §6 into tickets, and §3 into the actual sensitivity schema on your document model — that schema is the thing the agent reads at runtime to decide inline-vs-handoff, so it's the highest-leverage piece to nail first.*
