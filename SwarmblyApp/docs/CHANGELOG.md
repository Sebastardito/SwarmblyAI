# Changelog

## 0.4.0 — Projects (unreleased)

Swarmbly AI 3.1. From the roadmap of 4 November 2026 and the measurement of
3.0.1 on the sealed banks.

- **Projects** (`swarmbly_app/projects.py`, `/api/projects`, a project bar
  above the conversation). A project is a folder of its own, by default
  `Documents/Swarmbly/<Project>`, with `sources/`, `memory/` (glossary and
  notes), `chats/` and `exports/`, and a `swarmbly-project.json` without
  secrets.
  - **Isolation.** A conversation in a project reads only that project's
    documents and memory; the personal sources only if the project allows it
    (`include_personal`); a personal conversation never reads a project.
  - **Chats in the folder.** Each conversation of a project is kept as
    `chats/<id>.json`, rewritten after every change. Opening a project folder
    brings its chats into the app.
  - **`.swarmbly` packages.** Export writes the project file, sources, memory
    and chats with the SHA-256 of each file in a manifest; it stops if a file
    contains one of the user's API keys. Restore verifies every hash, refuses
    extra files and unsafe paths, restores into a new folder, and restores as
    a copy (new ids) when the same project is already open.
  - **Cloud-sync warning** when the folder is under iCloud Drive (including
    Desktop and Documents on macOS), Dropbox, OneDrive, Google Drive and
    similar.
  - Closing a project removes it from the app and keeps its folder.
- **Stable citations.** Each passage carries `doc:<sha12>#p<n>` (content hash
  and paragraph), kept in the answer's metadata and shown in *Explore
  processing*. It resolves after a project is moved or restored on another
  computer; it stops resolving when the file changes.
- **C1 lives in SwarmblyLCE** (`swarmbly_lce.c1`, pin `f053d77`): the adapter
  only decides which folders a request may read. `source_readers.py` remains
  as a re-export.
- **Consent per question for public lookups.** A personal or sensitive
  question, or one your documents answer, gets no public lookup unless you
  say yes for that question (*Also search public sources*, showing the names
  that would be sent). `privacy.public_lookup_consent = "always"` keeps the
  3.0.x behaviour. In the receipt, `consentimiento.otorgado` is now always
  true or false and `base` says what it rests on; the receipt also says its
  scope (`ambito`: personal or the project).
- **"Remember: …" saves to memory.** A message that starts with an explicit
  request to remember ("Recuerda: …", "Memoriza …", "Remember that …"; not a
  question) is written, before the answer, to the project's
  `memory/notas.md` (or `notas.md` in the personal sources folder), dated,
  on this computer only; the answer confirms it, a chip says where, and the
  following answers find it like any document. Such a message never goes to
  the swarm.
- **The project's documents, visible.** *Documents* in the project bar lists
  every file, how many passages it gave and why a file gave none; the model
  receives the list of names, so "which sources do you have?" is not
  invented.
- **PDFs without poppler** are read with `pypdf` (new dependency) through
  SwarmblyLCE; before, a Mac without Homebrew left every PDF out.
- The instructions file the app writes into a new project is now at the
  project root, not in `sources/`: it was retrieved for every question.
- Tests: `tests/test_projects.py` (isolation of two projects and the personal
  space, chats in the folder, export and restore on a second app with its
  citations, damaged and unsafe packages, keys never exported, the API,
  memory notes, the app's own note, the document list).

  Found in the first hands-on test of a project (7 November 2026): a project
  with one PDF answered from its instructions file only, and "memoriza…" was
  answered by the model without saving anything.
- **Citations that keep their meaning, and answers held to the sources**
  (second hands-on test, 7 November 2026: a VPN note cited as the memory
  file, "TRU" expanded from nowhere, invented species and table rows):
  - each passage is labelled `[D<n> p<k>]`: `D<n>` is the document's number
    in this conversation and stays the same on later turns, so a label copied
    from an earlier answer still names the same paragraph (before, `[1]`
    meant a different passage on every turn);
  - the instruction with the passages now says to answer only with what
    they say, to say when the sources do not say something, and not to
    expand acronyms or add names, figures, places or table rows; when a
    project question finds nothing, the model is told so;
  - a short document (up to 6,000 characters) that answers is given whole,
    in order, instead of four scattered paragraphs;
  - a short follow-up ("¿qué aplicaciones necesita este proceso?") is
    searched together with the previous question;
  - with local embeddings, a passage that shares no word with the question
    enters only if it is close in meaning (SwarmblyLCE).
  Small models still invent: these rules reduce it, and grounded composition
  (fact sheet, tables built by code, a verifier) is version 3.2.
- **Memory and glossary with the user's yes** (third hands-on test: "…,
  memorízalo" in the middle of a message saved nothing, "agrégalo a tu
  glosario" neither, and the model said it had done both;
  `swarmbly_app/memory_capture.py`):
  - a request to remember or to add to the glossary anywhere in a message,
    or a definition or correction the user gives ("X significa Y", "X,
    también conocidos como Y", "X no es Y sino Z"), makes the local model
    propose notes and glossary entries; they appear under the answer, editable,
    with *Save to memory* and *Discard*; nothing is written without that yes
    (a message that starts with "Recuerda:" is still saved at once);
  - the model is told it cannot save anything and must not say it did;
  - saved entries go to `memory/glosario.md` (`term = equivalents`) and
    `memory/notas.md`; any one equivalent now brings the term in a search
    (SwarmblyLCE), so the glossary widens later questions.
- **Online search with the user's yes, query in view**
  (`swarmbly_app/web_search.py`): public evidence sends only names of
  species, so "search for recent articles" sent nothing and the model
  invented references with authors and journals. Now:
  - when a question asks for online or recent references and no search was
    made, the model is told so and must not invent any, and the answer offers
    *Search online* with a proposed query (no first-person words) that the user
    edits and approves;
  - only that text is sent, to PubMed (real articles: authors, journal, year,
    link; newest first when "recent" is asked), Wikipedia and the user's
    SearXNG if configured; results are the only online references the model
    may cite ([W1]…), are listed under the answer, and are in the receipt.
- **Citation check**: labels in an answer that name no passage or result of
  the conversation are flagged under it ("1 citation without a source").
- **After the fourth hands-on test and the review of four independent
  "master prompts"** (8 November 2026):
  - *Search that finds something.* The approved query was the local
    model's keywords ("galapagos quails", "Darwin's finches") plus Spanish
    words, and PubMed ANDs every word: nothing came back. The proposed query
    now translates with the user's glossary and keeps the model's keywords
    only when they share a word with the question; PubMed and Wikipedia are
    retried with shorter subsets of the approved text (never other words); a
    configured SearXNG that is not running is skipped; an empty search says
    so under the answer and offers *Search again*.
  - *Memory in the user's words.* Notes are the user's own statements without
    the requests around them (the model wrote them in English and
    paraphrased); glossary entries take their equivalents from the message
    (parentheses, "también conocidos como", genus and family names), so the
    glossary is written (it stayed empty when the model gave no
    equivalents); a definition that repeats the note is not saved twice.
  - *Provenance.* Every memory decision (saved, discarded, "Recuerda:") is
    logged in `memory/registro.jsonl` with date, conversation, message and the
    model that proposed it; it travels with the project and C1 does not read
    it.
  - *Answers that can expand, marked.* The instruction with the passages now
    allows general knowledge when asked to expand, if marked "Outside your
    sources:", never contradicting them, and still no expanded acronyms,
    exact figures, proper names, references or table rows without a source.
    Sources are declared data, not instructions (prompt injection), and the
    answer is asked in the user's language and in its own words (the 3B model
    copied source lines). Spanish is recognised in short questions.
  - *Citation check, wider.* Any label shape is checked ("[C1 p2]" passed
    before), a known label attributed to another file is flagged, and the
    share of sentences that carry a label is measured (*Explore processing →
    Anchoring to sources*; it does not check that the label supports the
    sentence).
  - *Expansion hygiene.* Keywords copied from the prompt's example ("giant
    tortoises, Santa Cruz Island") or echoed from the prompt are dropped.
  - *"The sources do not say" with a way forward:* in a project, when nothing
    is found, the answer offers a search; references found online can be
    saved to memory with the user's yes.
  - *Local telemetry* per answer (`meta.telemetry`): scope, documents and
    passages read, citation measures, memory and online-search decisions,
    route and model. Never sent to peers.
  - Test: orders inside a document (prompt injection) trigger no search, no
    memory write and no send.
- **After the fifth hands-on test** (8 November 2026):
  - *Search terms that define the topic.* "Search for recent paper about
    cucujos" sent "cucujos recent papers paper": PubMed ignored the unknown
    word and returned the newest papers on biosensors, which were then saved
    to memory. Now the proposed query drops intent words (paper, recent,
    review, artículos…), merges the same word in two languages (endogamy /
    endogamia), and defines the topic from the user's own material: the
    scientific names next to the topic word in the retrieved passages or notes
    ("Pyrophorus Elateridae cucujos"). "Recent" is the last five years by
    relevance, not the newest first. A result is kept only if its title (or
    an encyclopaedia snippet) carries one of the query's specific words;
    variants never drop those words.
  - *Corrections the model follows.* "No es introgradión, el término correcto
    es introgresión" was saved as "introgresión = introgradión", which made
    the wrong form an equivalent, and the model kept saying "introgradión". A
    correction is now detected as such: the glossary line becomes
    `introgresión = … | no: introgradión` (an older line equating both is
    replaced), the note is clean ("El término correcto es «introgresión», no
    «introgradión»."), the relevant glossary entries go to the model with the
    forms to avoid, and the answer is corrected by code if the wrong form
    still appears ("1 term corrected by your glossary").
  - The memory notes file is never given whole (it is a list of unrelated
    notes), the same note is not saved twice, and discourse fillers ("Bueno,
    debo corregirte") are not kept in notes.
- **After the sixth hands-on test** (8 November 2026): *search terms as
  concepts, chosen by the user.*
  - "Endogamia en cucuves" was sent as "endogamy cucuves": "endogamy" is
    marriage within a group (the biological term is "inbreeding") and
    "cucuves" is unknown to search engines, so the results were about
    sociology. Translating words, by the model or by rules, cannot tell
    homonyms apart and does not scale to other languages.
  - The search dialog has a **"Review terms"** step. Each word of the query
    (at most six, four letters or more) is looked up as a *concept*: the
    user's glossary first (nothing sent), then Wikidata (labels in the user's
    language and in English, a description that tells homonyms apart, the
    scientific name of a taxon, the MeSH heading) and GBIF vernacular names
    for organisms. The user picks one concept per word or keeps the word; the
    query is rebuilt from the chosen concepts (English label, scientific
    name). Only those single words are sent, on click, and each request is
    in the receipt (`meta.term_lookups`).
  - A choice can be saved to the glossary with its Wikidata id
    (`term = inbreeding | wd: Q38978`), so the next search, in any language,
    starts from the concept.
  - A rate-limited service (HTTP 429, as Wikimedia does on shared addresses)
    is retried once; a service that does not answer is named in the dialog.
  - *Concepts kept apart.* "X no es un nombre de Y" / "X y Y son distintos"
    is proposed as `| distinto:` on both entries; the model is told not to
    give one the traits of the other, and an answer that still does (a
    sentence naming both without a negation) gets a visible warning
    (`term_conflicts`).
  - Pin: SwarmblyLCE 9a80a64 (glossary metadata is never an equivalent).
- **From the first automated test run on the user's computer** (8 November 2026,
  qwen2.5:7b, project Testing):
  - "cucuves" (plural) found nothing in Wikidata or GBIF; a plural now falls
    back to its singular. When several species share a genus for one common
    name (cucuve: *Mimus parvulus*, *M. macdonaldi*, *M. trifasciatus*), the
    genus is offered first, with its English common name ("mockingbird"),
    which is saved to the glossary too: the model rendered "Galápagos
    mockingbirds" as "galgapos de Groenlandia" and said the sources did not
    mention cucuves.
  - "Recuerda que el cucujo no es un nombre de los cucuves: …" was saved as a
    note and nothing else; it now also proposes the glossary entries
    (`| distinto:` both ways). Scientific names go to the term of their own
    clause ("cucujos … Elateridae y cucuves … género Mimus" gave Elateridae to
    both before; "género Mimus" was not recognised).
  - An encyclopaedia entry needs two of the query's specific words when the
    query has three or more ("inbreeding Mimus Galapagos" brought "Galápagos
    tortoise").
  - "Agrega a tu glosario: …" is not kept in the note; a note is not glued to
    a notes file edited by hand without a final newline.
  - Second run, with the glossary in place: "galgapos" and the Elateridae mix-up
    were gone and the proposed queries were built from concepts ("Mimus
    inbreeding mockingbird", "Elateridae inbreeding"). Remaining:
    - the model said the sources did not mention "endogamia" while they
      discussed *inbreeding*: the glossary block now says each line is one
      concept and a source using an equivalent speaks of the user's term; an
      answer that still says so gets a visible warning (`missed_sources`);
    - a second glossary line for the same concept ("cucuve" after "cucuves")
      is merged into the first;
    - results: two names of one concept count once (glossary groups); a web
      page needs a concept in its title and both concepts in title and
      snippet ("MockingBird: code translation", "Cooper's hawk" dropped);
    - an approved search makes no other public lookup in the same answer
      (both were labelled [W1]…), and the fusion template takes the language
      from the same rule as the rest of the answer (a Spanish question got
      English headings).
  - Third run (and the dialog driven in the browser): answers now cited the
    mockingbird genomes for "endogamia en cucuves", and searches kept only the
    relevant papers. Remaining:
    - "Review terms" offered albums, singles, a TV episode and a 1919 book
      for "mockingbird" and "inbreeding": creative works and documents
      (Wikidata P31) are never candidates;
    - a word that is already a glossary term or equivalent is not looked up
      again (nothing sent for it);
    - "la inbreeding" in a Spanish answer becomes "la endogamia" (article
      agreeing with the term; quotes and titles untouched), reported with the
      other glossary corrections;
    - the request pipeline notes ("the router judged the request not
      decomposable") are shown in Spanish; the "save these equivalences" box
      appears only after reviewing the terms.
  - Fourth run: English questions, a wrong form in the question
    ("introgradión", replaced five times in the answer) and the receipts.
    - The user's term is written next to its equivalent in the passages the
      model reads ("Inbreeding («endogamia»)"); the 7B model still wrote "no
      se menciona directamente la endogamia".
    - The missed-sources warning matched "cucujo" through "cucuves" (a shared
      prefix); it now needs the question's own word.
    - A clear correction ("se escribe X, no Y", two spellings of one word)
      and two concepts kept apart ("los cucujos y los cucuves son distintos")
      are proposed for the glossary without being asked; "la respuesta es
      correcta, no hay problema" is not a correction.
    - Receipts: the words sent by "Review terms" are added to the message's
      receipt; an approved search says what was approved ("el texto de
      búsqueda que aprobaste: «…»") and labels its sends as the approved text
      or as result identifiers, not as "public names".
  - Fifth run: "endogamia en los cucuves" was answered affirmatively and cited
    ("han experimentado endogamia (inbreeding)…"). Remaining:
    - the browser reused an old `es.json` after an update (no Cache-Control,
      so heuristic caching): the web UI's files are now revalidated on every
      load and the page itself is never cached;
    - a spelling correction mid-conversation got "Lo siento por el error" and
      the previous answer again: the model is told to acknowledge it in one
      sentence; a glossary definition the local model wrote that is not in
      the user's words is dropped;
    - the receipt labels shortened variants of the approved text as "part of
      the text you approved"; the local-answer note is translated in the
      processing explorer and the activity panel.
- **Provenance of each sentence** (sixth run, at the user's request): a
  sentence with no citation, not under "Fuera de tus fuentes:", not about the
  sources and not taken from a passage it was given (most of its words) is
  listed in `citations.unsupported`, underlined in the answer (CSS Custom
  Highlights; the rendered Markdown is untouched) and counted in a chip
  ("N frases sin respaldo en tus fuentes"). The app shows where a claim comes
  from, not whether it is true: "los cucuves… en otras partes de América del
  Sur" is right (cucuve names the whole genus *Mimus*), but did not come from
  the user's documents.
  - A correction made in a message applies to that same answer ("Gracias por
    la corrección" followed by the wrong form three times).
  - When the user says two terms are different, the model is told not to
    agree out of politeness ("los cucuves y los sinsontes son distintos" got
    "Sí, tienes razón"; they are synonyms).
  - The glossary file is written as a Markdown list ("- term = …"): plain lines
    one under another are one paragraph in Markdown, so any viewer showed the
    glossary run together. The app always read it line by line; older plain
    lines are rewritten as list items on the next save.
- **Long compositions** (diagnosis of the sealed-bank measurement of
  9 November 2026, done on an open fictitious battery, never on the bank):
  - With 3.1 the model reads short documents whole, so prompts for
    compositions grew from about 900 to 2,000–4,400 tokens. Key data improved
    on the open battery (a two-table comparison: 6/6 against 1–3/6), but the
    instructions at the top of the block were followed less: no citation at
    all at 4,400 prompt tokens, and answers shorter than asked.
  - The sources block now ends, next to the question, with a short citation
    reminder and the requested length ("Extensión pedida: entre 300 y 400
    palabras"). Open battery, qwen2.5:7b, 7 tasks: citations per answer up in
    6 of 7 tasks, answers without any citation 2 → 1 (of 21), key data equal
    or better, lengths closer to the request (n = 2–3 seeds per task).
  - The answer budget uses the answer's language rule (Spanish requests got
    the English token rate).
  - "No search was made" goes after the sources: before a long block it was
    forgotten and an answer claimed a public lookup that never happened.
- **Retrieval**: a short document is given whole only if it holds the best
  passage or two of them (a manual matched weakly was added to unrelated
  answers); a follow-up is expanded with the previous question; the blocks
  about the question go right before it, not at the top of the history.

## 0.3.1 — Destinations and privacy receipts (2026-11-07)

First release since 0.2.0. It also contains 0.2.1 and 0.3.0 below, which
were not released on their own. Measured with the sealed S2/S3 banks of
Swarmbly AI on commit `9f60aab` (one run per bank); the receipt fix of
`de5d342` came after that measurement and is verified by tests and by the
harness on a fictitious bank, not by the sealed banks.

From the review of 4 November 2026 and the sealed-bank baseline of
7 November 2026 (Swarmbly AI 3.0.1).

- **Where each call goes.** Every model server, public source and peer is
  classified from its address: `local` (this computer), `red_propia` (the
  user's own network: private and link-local addresses, `.local`,
  single-label names) or `terceros` (an organisation outside the user's
  control). An "OpenAI-compatible" server is not local for that reason.
  `SWARMBLY_LOCAL_HOSTS` names hosts that are this computer in a given
  installation (the Docker services).
- **Outbound policy before every call** (`swarmbly_app/egress.py`), at the
  point where the bytes leave: answers, query expansion, embeddings, the
  orchestrator's local steps, worker execution, retries and fallbacks. A
  third-party model receives nothing unless its host is listed in
  `privacy.third_party_models`; passages of the user's documents need
  `privacy.third_party_passages` as well (otherwise the question goes alone
  and the answer says the documents were not sent). A failure never changes
  the destination.
  - Fixed: with an OpenAI-compatible server configured, the "local" path sent
    LCE passages to it and recorded `executed: local` (found in the review of
    4 November 2026).
  - Fixed: embeddings of the user's documents went to `backend_url` even when
    it was not local.
  - Fixed: a node serving the swarm used the configured backend, so other
    nodes' fragments could reach a third-party service. A node whose model is
    a third-party service now never serves the swarm (`E_POLICY`) and
    advertises no task kinds.
- **Privacy receipt per answer** (`meta.receipt`, schema
  `swarmbly.privacy_receipt/1.0`): lane (personal, sensible, público, also in
  local mode), route, where the answer was computed, consent, every send with
  destination, class, kind and bytes, blocked attempts, passages and personal
  names sent, fragments created, and the answer's hash. Sends are recorded
  where they happen, so a public lookup shows the query actually sent (the
  baseline found extra terms that the evidence metadata did not report).
  "Explore processing" shows it as "What left this computer".
  - Fixed before release: lookups and model calls made from worker threads
    (parallel public lookups, the orchestrator's local steps, the local
    worker) left the computer without reaching the receipt, because context
    variables do not cross into thread pools. `egress.carry()` binds those
    calls to their request. Found by the sealed-bank measurement of 3.0.1:
    one public query observed on the network was missing from the app's
    receipt. The policy itself was not bypassed: in a worker thread an
    unknown purpose is treated as the strictest one (passages).
- **API keys out of `config.json`.** Keys go to the system keychain
  (`keyring`), or to a protected file (0600) where there is none or with
  `SWARMBLY_KEYRING=off`; existing keys are moved on start-up. `GET
  /api/config` never returns them, only whether and where one is stored.
- The OpenAI-compatible adapter sends the key when listing models and
  checking availability (authenticated providers showed no models).
- Local SearXNG with Docker: current images bind to IPv6 by default and fail
  where Docker has no IPv6; the container now listens on IPv4.
- `docs/LIMITATIONS.md` no longer says that C1 does not feed the chat.
- Tests: `tests/test_egress.py` (synthetic leak test with a marker in a
  source and a mocked third-party transport; worker, embeddings, receipt,
  keys).

## 0.3.0 — Composition planner (unreleased)

**Heterogeneous swarms** (21 October 2026, from P3b on four machines: macOS,
Windows, Debian; 0.5 B to 8 B models)
- Capability-aware routing: per node and family the scheduler now picks the
  largest model (parameter count from the tag) and sends it as
  `constraints.model`; workers honour it and otherwise run the largest shared
  model of the wanted family (the first one listed was taken, e.g.
  llama3.2:1b instead of llama3.1:8b). Models below
  `swarm.min_model_params_b` (1.5) are skipped while larger ones exist.
- Quality check before acceptance: a batch replica that answers fewer than
  half of its items (e.g. echoes the Spanish words it should translate) or a
  composition section far below its length is `rejected` (`E_QUALITY`) and
  retried on another node within `k_max`; if every replica is rejected the
  best is used and marked `degraded`.
- Batches keep at least `swarm.min_items_per_fragment` (3) items per
  fragment; answers are normalised to one `n. value` line per item (no code
  fences, bullets or added periods).
- The composition outline gets back an explicit requirement of the request
  that the local model dropped (the presenter, in the Galápagos request).
- Resilience (P3b.3, 22 October 2026: the largest node was shut down
  mid-request): a task whose remote attempts all fail is run on this
  device's model instead of failing the whole answer
  (`local_fallback_tasks` in the metadata); hedges only go to workers with a
  free slot (queued hedges made every remaining task miss its deadline).
  Rejected replicas keep a 160-character preview for auditing.
- Cancellation: when the requester gives up on an attempt (its timeout, a
  hedge that won, the user stopping) it sends a `cancel` message; the worker
  stops generating between tokens. Only the node that sent a task can cancel
  it; older nodes ignore the message. The requester also keeps that worker's
  slot for 2 s, so it does not send work the worker would refuse as "at
  concurrency limit" — the actual cause of the `E_POLICY` refusals in P3b,
  not the idle-only setting. Failure details are kept in the attempt's note.
- With a local model available, a retry that would wait behind busy workers
  fails fast and the task runs locally (P3b.3': queued retries waited about
  50 s and then timed out anyway). A fence's language tag left alone on a
  section's first line ("markdown") is removed.
- Speed-aware routing: tokens per second are learned per node and model from
  accepted results (a timeout records an upper bound) and kept across
  requests; a model expected to miss the deadline for the task's budget
  ranks below one that can finish, even if smaller (P3b.3'': llama3.1:8b on
  a server CPU timed out on a section that phi3.5 finished in 21–36 s).
- From P3c (five machines, 22 October 2026), audited with the new rejection
  previews:
  - batch answers without numbers ("Reptil / Ave / Pez") are read in item
    order when the line count matches, and answers renumbered from 1 for
    items 19–24 are mapped to their items when the labels are exactly 1..k;
    both were correct answers rejected by the quality check;
  - a node that just failed (backend unreachable, execution error,
    deadline) ranks below healthy ones for five minutes;
  - when every remote replica of a task is rejected, this device's model is
    tried before accepting a degraded answer.
- From P3d (same five machines, 22 October 2026):
  - a label left inside an answer ("1. 7. libro", "7.* Asunción") is
    removed before the answer is read, so a renumbered echo is rejected
    instead of accepted as a translation;
  - answers are read by position only when no line carries a label (a
    labelled echo plus "En formato markdown…" had become an answer);
  - an item without an answer is shown as "(sin respuesta verificada)" (in
    the request's language), and the raw text of a rejected replica is
    never shown;
  - the local rescue tries the bare task after the packet: the same 3B
    model echoed a fragment wrapped in the contract header and answered it
    without; `local_fallback_rejected` lists tasks where both failed;
  - composition sections prefer a replica within ±30 % of the section's
    word target (after language, requirements and completeness);
  - the outline keeps the number of sections the request asks for ("una
    introducción, tres secciones y una conclusión" → 5): the local model is
    told, and the outline is corrected (extra middle sections folded into
    the previous one, missing ones added before the closing).
- From P3e (same network, 22 October 2026):
  - hedges use the learned time of each attempt's node and model for this
    kind of task: an attempt is hedged once it runs past twice that time
    (plus 1 s, never sooner than 2 s), when that comes before the p95 or the
    30 s fallback (`speed` in `hedge_timer`); each attempt triggers at most
    one such hedge;
  - a worker that missed a deadline or refused a task as "at concurrency
    limit" is marked busy for 15 s, across requests: hedges skip it and
    other choices rank it last (the old Mac refused five tries in a row, one
    per model family);
  - a retry after a quality rejection may wait for a busy worker (two echoes
    with no free worker used to end in a degraded answer);
  - the upstream suffix glued to the last item ("8. 7000 m Close the
    answer; …") is removed from the item list;
  - a table section the request did not ask for is removed from the
    outline.
- From P3f (same network, 22 October 2026):
  - a worker that answers "backend unavailable" (its Ollama is down) is a
    last resort for a minute, before diversity of machines and families;
  - an attempt cancelled as slow teaches a floor for its node and model and
    marks the node busy for 8 s (a slow CPU may not stop mid-prompt); a
    model whose learned time reaches the hedge fallback counts as too slow;
  - composition: outside the ±30 % band the replica closest to the
    section's target wins (195 and 83 words for 144: the 83 was chosen);
    table sections have no word target.
- From P3g (same network with the old Mac healthy, 23 October 2026):
  - when the two replicas of a batch fragment disagree on an item, one more
    replica on another family breaks the tie (`swarm.tie_break`, on;
    `tie_breaks` in the metadata): "carro / leite / vermelho" had won over
    "car / milk / red" as the better-ranked replica;
  - in the item vote, numbered answers win ties over answers read by
    position (a model listed "6. Pez / 5. Aves / 4. Reptil"; without the
    numbers that order maps to the wrong items);
  - composition selection: required names first, then length within the
    band, then the other requirement words (they favoured the longest
    replica: +37 % and +41 % texts); short sections are asked for fewer
    words (×0.75–1.0 below 200 words, provisional);
  - a rejected batch replica's note starts with what the check read
    ("items 4-6: read [5], need 2").
- From P3h (23 October 2026):
  - "respond in Spanish" is no longer added to a task that names the
    language of the answer ("traducción al inglés"): with it qwen2.5:3b
    echoed the Spanish words, without it translated them — the main source
    of echo rejections since P3b;
  - votes compare numbers by value and one-word answers by their singular
    ("1.5" = "1.5 km", "Aves" = "ave"): every fragment of the length batch
    had gone to a tie-break over units;
  - an answer on the line after its repeated item ("4. Iguana marina /
    - reptil") is read;
  - format words the request did not ask for (tables, lists, headings) are
    removed from the outline's style line, and prose sections are told to
    write paragraphs without tables (and without lists unless requested);
  - tie-break attempts are labelled `tie_break`; an unreadable rejected
    replica's note keeps its first characters escaped.
- From P3i (23 October 2026), the echo traced to the packet itself:
  - the batch directive is reworded in all four languages ("For each item,
    write one line with its number and your answer (for example: “1.
    answer”). Do not repeat the item."): with "answer only the numbered
    items …, keeping each item's number", phi3.5 and qwen2.5:3b re-listed
    the Spanish words; with the new wording both translated them (n = 1 per
    model and wording). Batch ρ figures change slightly;
  - lower-case words returned by the upstream entity extractor are no
    longer sent as names ("usa exactamente estos nombres: para, cada, una"
    in every batch packet);
  - a style line copied from the outline schema's placeholder is dropped.
- From P3j (23 October 2026):
  - the batch directive loses its example line ("1. answer"): workers
    renumbered from 1 or wrote "respuesta: table". Compared on this Mac
    (4 models × 2 fragments, n = 1 each), the plain wording "For each item,
    write one line with its number and your answer. Do not repeat the item."
    was the only one read and translated in all eight cells;
  - renumbered answers repeated in a code fence are read (only the first
    1..k run counts); bold markers inside an answer are removed
    ("**12.5** km");
  - a composition table section must contain a Markdown table (≥ 3 rows)
    to be accepted;
  - nodes advertise their app version and build, operating system,
    architecture and free memory (shown in the Monitor's node tooltip).
- From P3k (all five machines on `6762e76`, 23 October 2026):
  - Ollama's first chunk may take up to 90 s (a cold model load): with a
    30 s read timeout every cold load on a Windows node failed as "timed
    out" (needs the update on each worker);
  - workers report the model load time (`load_ms`), and the requester
    subtracts it before learning speed: a cold load had made the largest
    models look too slow;
  - a model rejected by the quality check ranks after the others for the
    rest of the request;
  - tie-breaks only go to a worker that is free now (one queued behind a
    cold load added 60 s and failed).
- From P3l (23 October 2026): batch answers given as a Markdown table whose
  first cell is the item number ("| 7 | Pingüino | Ave |") are read.

**Public evidence for batch items (P2 prototype, off by default)**
- `evidence.enabled` (default off): for an enumerated batch of a PUBLIC
  request, items that name something (several words, or capitalised) are
  looked up on Wikipedia in the request's language; the first two sentences
  of the lead are added to that item's fragment under "Contexto público
  (Wikipedia)…; úsalo solo si es pertinente". Only item texts are sent to
  the provider — never the request — and nothing is sent for SENSITIVE or
  SANITISABLE requests.
- A result is used only if its title or lead shares a word with the item
  (titles are often scientific names); disambiguation pages are skipped.
- `evidence` in the request metadata: items queried, sources used (title
  and URL, for attribution), errors and time.
- Motivation: several models agreed on the same wrong answer ("piquero →
  pez", "pingüino → mamífero"), which no vote can correct. Measured in
  P2a (5 repetitions, R2): batch A went from 7.0/8 to 8/8 on average, the
  total from 46.8 to 48/48, with no change in B, C or D and ~0.7 s of
  lookups per batch. One battery only; kept off by default.
- P2c (six varied batteries, 3 repetitions): with evidence the total rose
  from 51–54 to 55–56/60, all of it from authors of books (3–5 → 9/10),
  while the other batteries lost 2–3/50: homonym articles ("Cecilia" as a
  first name) and neighbouring facts (atomic number instead of symbol,
  largest city instead of capital) misled answers the network already got
  right. The setting's help text says so; it stays off by default.
- Operation-aware lookups (P2d; `evidence.operation_aware`, on; off gives
  the P2a/P2c behaviour): the batch operation gives a topic ("animal",
  "país", "elemento químico") and focus terms ("anfibio", "capital",
  "símbolo", "autor", "año"). A result must mention one of them (or a year /
  a writer when that is what is asked); a homonym fails and the search is
  repeated with the topic ("Cecilia" → "Cecilia animal" → Gymnophiona). The
  snippet is the first sentence plus the one carrying the asked fact ("…su
  capital es Abuya"), cut around that fact when long. Implicit
  disambiguation pages ("puede hacer referencia a") are skipped, and
  translation batches are not looked up.
  Measured (3 repetitions): total 55/59/56 against 54/56/51 without
  evidence; the chemical-symbol battery still dropped (7/10/7) because the
  atomic number sits in the same sentence as the symbol.
- Unasked figures are dropped from the snippet: when the operation asks for
  neither a year nor a quantity, clauses with digits that do not carry the
  asked fact are removed ("…con el símbolo Hg y número atómico 80" → "…con
  el símbolo Hg"; "Nigeria tiene 220 millones de habitantes. Su capital es
  Abuya" → "Su capital es Abuya"). Years and quantities stay when they are
  what is asked, or when the clause carries the fact (the author).
- Settings → Privacy → "Public evidence (Wikipedia)": the switch, with what
  is sent and what was measured; timeout, length and number of lookups in
  the Advanced profile.
- Answers show a "Wikipedia · n" chip, and "Explore processing" lists the
  Wikipedia sources used (attribution, CC BY-SA 4.0); answers that used LCE
  C1 passages show "Local sources · n" and list the files.

**LCE C1 across languages, and public evidence for local answers (P2e)**
- Measured first (24 October 2026, local `qwen2.5:3b`, 16 questions about a
  local knowledge base of a PhD thesis and papers in English plus profiles
  and notes in Spanish, 44 key elements, 3 repetitions): without sources
  0/1/0, with P2b C1 7/7/7. Every point came from Spanish files: the BM25
  index never returned a paragraph of the English thesis or papers for a
  Spanish question.
- Query expansion (`lce.query_expansion`, on): the local model turns the
  question into English keywords and the public names it mentions (one short
  generation on this device); the keywords join the retrieval query.
- Personal glossary: any source file named `glosario*` / `glossary*` with
  lines `término = equivalent, equivalent` adds the equivalents of the terms
  present in the question (both directions; long single terms also match
  inflections, "muestrear" ~ "muestrearon"). It carries the user's own
  vocabulary across languages ("cucuve = mockingbird, Mimus") where a 3B
  model fails (it rendered "cucuve" as "cuckoo" and "rascón" as "rat" in a
  trial). Glossary files are not retrieved as passages.
- Added terms (model keywords, glossary equivalents) weigh half of the
  question's own words in BM25, so they widen the search without taking it
  over. The expansion prompt carries one worked example (a 3B model ignored
  the format without it).
- The index folds accents, drops function words (es/en/pt/fr) and plurals,
  and indexes each paragraph with its file path words, document title and
  nearest heading ("mi artículo de 2024 sobre el rascón" reaches that file);
  headings are no longer retrieved on their own, long paragraphs are cut at
  sentence ends, identical paragraphs are returned once, and the number of
  passages is `lce.retrieval_k` (4).
- Public evidence for local answers (`evidence.local_answers`, on when
  public evidence is on): up to `evidence.local_max_entities` (3) names are
  looked up on Wikipedia (`evidence.local_lang`, en): scientific names and
  the names the local model listed from the question, and as a bridge one
  scientific name from the retrieved passages; names listed by the model are
  sent only when each of their words appears in the question, the passages
  or the glossary equivalents. Only names are sent, never the
  question or a passage; the metadata lists each name and where it came
  from. The whole article is read and reduced to its first sentence plus the
  sentences carrying the question's terms (status sections sit outside the
  intro). The answer gets the local sources as [1], [2] and the public
  evidence as [W1], [W2], with the instruction to give both when they differ.

- Round 2 (same 16 questions, 3 repetitions): C1 with expansion and
  glossary 21/17/20 of 44 (the P2b C1 had 7/7/7); with public evidence
  22/18/19, but no public fact was gained: the 3B model's names were wrong
  ("Galapagos Cuckoo", "Canis", "Panthera"), the passage bridge sent
  unrelated species (a guppy from a paper's introduction, "Supernova
  assembler" → an unrelated article) and the model ignored the evidence block.
- Public names for local answers are now chosen without the model: scientific
  names in the question, common names "<term> de <Place>" rendered through the
  glossary ("cucuve de Floreana" → "Floreana mockingbird"), proper names the
  user listed in the glossary ("Proyecto Isabela = Project Isabela"), and only
  when the question names none of these, a scientific name repeated in the
  retrieved passages. The model's names are never sent (an employer named in
  a question must not leave the device). Public evidence is fetched only when
  the question asks for something public or current ("actual", "fuentes
  públicas", "current"); questions about the user's own documents send
  nothing. Two names that resolve to the same article are used once; the
  passage keeps the article's first two sentences, the focus sentences and the
  sentence after each; and the turn asks for local facts [1], public facts
  [W1] and both versions when they differ.
- Short blocks of up to four words ("Acme Labs Inc.") are headings, not
  passages; the glossary also matches Spanish gender ("extinto" ~ "extinta").

- Round 3: C1 21/20/20 of 44, with public evidence 25/25/25; public facts
  gained in 3 of the 6 questions that ask for them (current IUCN status of
  two mockingbirds; the fur seal's size and legal protection since 1934). The
  3B model cited the public evidence as "my local sources".
- Fusion template: when public evidence is present, the local passages and
  the evidence go into the user's turn under labels ("MIS DOCUMENTOS",
  "WIKIPEDIA"), followed by the question and a three-part answer (my
  documents, Wikipedia, comparison).
- Retrieval: abbreviated species names are indexed in full when the file
  spells the genus out ("M. melanotis" → "Mimus melanotis"); one file fills at
  most two of the passages; the passage bridge also counts abbreviated forms.
- Public passages: a question that asks for a year or a date ("¿en qué
  año…?") brings the article's sentences with years; glossary acronyms
  ("UICN = IUCN") are not sent as names.

- Round 4: C1 20/19/19, with public evidence 27/27/25 of 44; public facts in
  5 of the 6 questions that ask for them (with the fusion template the
  attribution was mostly right). Two passages per file cut a needed third
  passage (a course list, a paper's conclusion): the cap is now three. The
  passages shown to the model spell abbreviated genera out ("M. trifasciatus"
  → "Mimus trifasciatus"), which the 3B model otherwise skipped.

- Round 5: C1 23/21/23 of 44, with public evidence 27/26/31; the contrast
  "your thesis said X, today it is Y" appeared in 2 of 3 repetitions.
- `evidence.fusion_model` (Settings → Privacy → advanced): a larger local
  model writes only the answers that fuse local sources with public
  evidence; other answers keep the conversation's model. Query keywords now
  come from the default model (`lce.expansion_model`, "" = `model.model_name`)
  even when the conversation uses a large one: a reasoning model returned no
  keywords in 90 tokens (round 6, aborted), and the retrieval lost the
  English passages. Reasoning blocks are stripped from the expansion.

- Shared network (round 7, LAN, five machines): the 16 personal questions
  all stayed on this device (the router does not fragment single questions;
  one was classified SENSITIVE), so the network changed nothing and no local
  passage left. The public half sent as a batch (current IUCN category of
  eight Galápagos species) was distributed, but the evidence did not help:
  the Spanish Wikipedia articles carry no IUCN status, and the network
  answered "Critically Endangered" for almost every species.
- Batch evidence falls back to English Wikipedia when the article in the
  request's language lacks the asked fact: the focus terms are translated
  (`EN_FOCUS`), and an IUCN status sentence must name its assessor (IUCN,
  Red List, BirdLife), so "more vulnerable to disease" is not taken as a
  status.
- An enumerated PUBLIC batch answered on this device (too small to fragment,
  or no workers) gets the same item evidence as fragments, when the request
  could have left (PUBLIC lane, tier allowing egress).

- Round 8: with `evidence.fusion_model` set to a 27B local model (the 3B
  writes everything else), 30/32/30 of 44; the "thesis then, status now"
  contrast was right in 6 of 6 answers, no attribution error in the 15 fused
  answers, 52 s per fused answer against 1.8 s for the rest. On the network,
  the IUCN batch with the English fallback rose from 3/2/1 to 4/6/4 of 8.
  A batch of years stayed local because the lane classifier marked it
  SENSITIVE ("death of Lonesome George"): a false positive upstream.

- Hybrid retrieval (`lce.dense_retrieval`, on): BM25 is fused (reciprocal
  ranks) with vectors from the local embedding model (`model.embed_model`,
  Ollama `/api/embed`, cached per paragraph). In P2e the right paragraph was
  often 6th–26th by BM25 (a long paragraph loses to short ones sharing a
  name). Any failure falls back to BM25 for five minutes.
- Lane refinement: "legal", "abogado", "salud", "médico" (and English) put a
  request in the SENSITIVE lane only with a first-person marker in the same
  clause ("mi abogado", "tengo un problema de salud"); strong terms
  (password, card, IBAN, passport, diagnosis, salary, debt) stay SENSITIVE
  anywhere. "Inicio de la protección legal del lobo peletero" kept a public
  batch off the network (P2e round 8b).

- Round 9: the hybrid retrieval found the paragraph with the asked fact in
  11 of 16 questions in every repetition (BM25 alone: 9), and the key score
  rose from 28/28/27 to 30/33/29 of 44 with the 3B model; the parasite of the
  2021 paper is now found, so its public history is looked up. The batch of
  years now counts as PUBLIC and is distributed, but its items are event
  descriptions with no article to match (0 of 5 either way). With the
  fusion model as well: 30/29/35, and one fused answer came back empty.
- A fused answer gets twice the token budget (a reasoning model thinks
  first); if it is still empty, the conversation's model answers the same
  prompt (`fusion_fallback` in the metadata).

- Round 10a (one repetition each; the hit is deterministic): with the hybrid
  retrieval, 6 passages found the asked fact in 12 of 16 questions, 4 in 11
  and 8 in 12; the score was 33/44 with 6. `lce.retrieval_k` is now 6.
- Batch evidence for events ("Inicio del Proyecto Isabela", "Muerte del
  Solitario George"): the English fallback is searched with the item's proper
  names only (Project Isabela, Lonesome George), and a sentence counts only
  with a year and the event's verb in English (`EN_EVENT`: muerte →
  died/death, inicio → began/initiated…), so an article full of dates does
  not answer with the wrong one; without an event word nothing is added.

- More public sources (`evidence.providers`, default wikidata, wikipedia,
  pubmed): Wikidata gives structured facts in one sentence (IUCN status P141;
  dates of death, birth, inception, start, end, discovery, publication — the
  property chosen by the operation and the event word: "muerte" → date of
  death); PubMed (NCBI E-utilities) gives abstract sentences with the asked
  terms or a year; `web` uses the user's SearXNG instance (`searxng_url`,
  which queries DuckDuckGo, Google, Bing or Google Scholar) or Google Custom
  Search (`google_cse_key`, `google_cse_cx`). Batches take the Wikidata fact
  when the operation asks for a status or a date and fall back to Wikipedia;
  local answers get every provider that has something, labelled. Only names
  (and generic English focus words for PubMed and web search) are sent. In a
  dry run Wikidata had the right IUCN status for 7 of 8 Galápagos species.
  Google Scholar has no API (scraping breaks its terms), so it is reachable
  only through SearXNG.
- Round 10b: years of events with Wikipedia only, 1/1/1 of 5 (wrong years
  from articles about the island and the archipelago); IUCN statuses 4/4/3
  of 8. Round 10c: the effective-size paragraph was dropped by the per-file
  cap.
- Optional local SearXNG installed from the app (Settings → Privacy → Web
  search), with consent and only when internet access is allowed: the
  official Docker image when Docker is running, otherwise SearXNG's source in
  the data folder with its own virtual environment (Python ≥ 3.11, or `uv` to
  provide one; the system Python is never changed). It listens on 127.0.0.1
  only, with JSON output and engines DuckDuckGo, Google, Bing, Brave, Mojeek,
  Wikipedia, Google Scholar, PubMed, Semantic Scholar, OpenAlex, Crossref and
  arXiv; it starts and stops with the app (`evidence.searxng_managed`), and
  on success `searxng_url` is set and `web` is added to the providers.
  Uninstall removes it and its files. Web searches ask the `general` and
  `science` categories. "Test web search" runs one fixed public query and
  reports the results and the engines that answered. The Google Custom Search
  JSON API is closed to new customers and ends on 1 January 2027, so Google
  and Google Scholar are reached through SearXNG; an existing key still works
  until then. Tested end to end on Linux (download, environment, start, stop,
  restart).
- Round 11 (measured with `0a88555`): on the LAN, IUCN statuses went from
  4/4/3 (Wikipedia only) to 8/8/8 of 8 with Wikidata; event years 2/2/2 of 5
  (Lonesome George from Wikidata), historical years unchanged at 10/10.
  Locally (hybrid, k = 6, evidence, 27B fusion) 37 and 36 of 44, with every
  public fact labelled by its source. PubMed rarely added anything here.
- Round 11c, with the local SearXNG: web results appeared in 11 of the 12
  answers with evidence and the score stayed at 37 and 36 of 44 (graded by
  hand where the automatic key missed a correct phrasing). Half of the web
  hits were the Wikipedia article already asked, so web results from hosts
  of providers that are enabled (Wikipedia, PubMed, Wikidata) are now skipped.
  The doctor names the pinned commit when the installed one differs.
- Event years in batches: the event's subject ("cucuve de Floreana",
  "lobo peletero de Galápagos", the phrase after "del/de la…" without a
  trailing place) is looked up in the request language's Wikipedia and
  followed to its English article through the interlanguage link, only when
  every content word of the subject is in that article's title or lead
  ("Proyecto Isabela" does not follow "Provincia de Isabela"). The year comes
  from the first sentence in article order with a year and the English verb
  of the event nearest the subject ("protección" over "inicio"), so the lead's
  date wins over side events ("between 1997 and 2006, initiated…" over
  "brought into action in 1999"). Wikidata gives no date when an event noun
  without a property sits inside the item ("Inicio de la protección…"). In a
  dry run the subjects resolved to Floreana mockingbird (extirpated by 1888)
  and Galápagos fur seal (protected since 1934).
- Round 12 (LAN, three repetitions): Galápagos event years 5/5/5 of 5 with
  evidence (round 11a: 2/2/2; without evidence 1/0/0); IUCN statuses stay at
  8/8 and historical years at 10/10.
- Public evidence is now on by default (`evidence.enabled`): it fixed what
  the models lacked (IUCN statuses 8/8, event years 5/5) and no longer
  worsened what they knew (historical years 10/10). Only item texts or
  entity names leave the device, never the request or local documents, and
  nothing for SENSITIVE requests; Settings → Privacy turns it off. Saved
  configurations keep their explicit value.
- LCE C1, passages: the heading right above a paragraph is shown with it,
  stacked headings together ("Gerente de I+D (R&D Manager) — Sep 2024 ·
  NRGene Canada Inc. (NAIC) — Lideré…"): a job title in a heading was never
  shown to the model (K6). Pieces cut from a long paragraph are indexed with
  the previous piece's last sentence, an overlap as between reads ("…the two
  remnant populations of M. trifasciatus on Champion and Gardner" before
  "These two populations, Champion (Ne ~30)…", K3). "ne" is no longer a stop
  word (Ne, effective population size). Offline BM25 check: the passage with
  the fact is now among the six for 12 of 16 questions (10 before), K3 first.
  CV title lines (up to 160 characters, parts joined by dashes, no sentence
  end: "Entomólogo Jefe de I+D (Investigador Principal) — … — Nov 2022 – Sep
  2024") count as headings too, so the role is shown with the duties under
  it; author lists joined by "|" stay passages. Offline check: 13 of 16.
- Round 13 (measured with `8aac98a`): the effective-size passage is now
  retrieved for K3 in both repetitions (the thesis gives two estimates, ~14/~62
  in the results and ~30/~120 in the discussion; both answers quote one), and
  every source file is read; 12 of 16 retrieval hits, 35 and 38 of 44 by hand.
  K6 failed until the title-line change.
- Round 13c (measured with `c9b08bd`), the preregistered C1 closing check:
  the passage with the fact is among the six for 13 of 16 questions in both
  repetitions; K6 now answers "Gerente de I+D (R&D Manager)… mosca soldado
  negra (BSF)" and K3 "~30, ~120, ancestral Ne ~15 000"; 39 and 38 of 44
  (rounds 11b/11c: 37 and 36). LCE C1 is closed. Known limits: an answer is
  as good as the model that writes it, crossing languages relies on the
  glossary, and a fact in a passage that ranks seventh for its question
  (F3, F7) is missed.
- Requests about the user stay on this device: with C1 active, a first-person
  request about the user's own material ("mi carrera", "mis publicaciones",
  "my thesis") that matches the user's sources is answered locally even in
  LAN or auto mode (`lce.keep_personal_local`, on by default), with a note.
  In an October 2026 test such a request went to four nodes without the
  user's passages (which never leave the device) and came back as generic,
  invented text ("investigador de materiales"), carrying the user's name to
  other machines. A bare "me" (¿me traduces…?) does not count. "internet",
  "web", "en línea" and "busca" now also ask for public evidence.
- Chat: a swarm answer that finished while the WebSocket was down (a long
  request, sleep, a network change) only showed after a reload. Pending
  messages with no recent event are now read from the database every few
  seconds and right after a reconnection; the server's WebSocket ping
  timeout is 90 s.
- Personal requests: a possessive personal topic ("mi carrera", "mis
  publicaciones", "my thesis", "mi salud"…) keeps the request local even
  with no source folder; in the 25 Oct retest C1 was on without sources and
  the request went to the swarm again with the user's name. "Mis 3
  animales" in a batch is not a personal topic.
- Funding campaign: Settings → System shows how to support the project
  (buymeacoffee.com/swarmbly), and the README and `.github/FUNDING.yml` link
  to it. Support never buys influence over the roadmap, licence or governance.
- LCE C1, formats: Word (.docx), HTML and PDF (with `pdftotext` from poppler,
  on the PATH or in Homebrew's folders; ligatures normalised) are read, not
  only text files. Memory → Your sources lists every file with its passages,
  or why it cannot be read (no pdftotext, no text layer), shows the glossary,
  and lets the user add other folders read in place (`lce.sources_dirs`).

**LCE C1: retrieval over your sources, for local answers (P2b)**
- With LCE enabled at C1, answers produced on this device get the most
  relevant paragraphs of the user's sources (LCE source folder plus
  `lce.sources_dirs`; BM25 over ≤ 600-character paragraphs, the scoring of
  SwarmblyLCE) as a system message, and the answer is asked to cite them
  as [1], [2]. The metadata lists the sources used (`lce.sources`).
- Passages never leave the device: requests answered by the swarm do not
  use them. Projection into Γ needs digested claims (C2) and stays empty.
- Following WP LCE v0.2 §11.7–11.8 (R13): retrieval runs over raw sources,
  not over the digested wiki.

A single composition of a stated length (an essay, a speech, a report of N
words) is no longer sent whole to one model or to whole-request replicas: the
**local model plans it** and the swarm writes it section by section.

- **Outline on this device**: the local model reads the whole request and
  returns a JSON outline (title, topic, style line, 3–6 sections with purpose,
  word budget, key points, the explicit requirements that belong to each,
  prose or table). The code validates it (sections, word budgets rescaled to
  the requested length, tables never open or close the text); an unusable
  outline falls back to a deterministic one, and the monitor says which.
- **Decontextualised sections**: each packet carries Γ, the title, the topic
  and one section's brief and position — never the request, its instruction
  list or rubric. Γ's objective is the title, not the request's first
  sentence (which states the length of the whole text).
- **Transitions by the workers**: every section after the first opens with a
  transition from the previous heading; no bridges (the upstream bridge
  prompt is English). Seam similarity is still measured.
- **Requirement check**: each requirement of the outline is checked against
  the final text (lexical presence, not a quality judgement) and reported
  with the outline in the response metadata.
- Settings: `swarm.composer_enabled` (on), `swarm.composer_min_words` (400),
  `swarm.composer_max_sections` (6). Applies only when a local model and at
  least one worker (remote or local pool) are available.
- Fixes from the first live comparison (P3.2, 2026-10-16): a requested table
  is added when the outline omits it; repeated section headings are dropped;
  transitions no longer repeat the previous heading; a section cut at its
  budget loses its unfinished last sentence and stray `---` rules. Batch
  voting also matches unnumbered bullets by the item's own text.
- Second live round (P3.2b): a malformed outline is retried at temperature 0
  and an outline cut mid-section is repaired; a section's mandatory
  requirement comes first in its brief; replica selection prefers the replica
  that meets the section's requirements (e.g. the presenter's name); a table
  requirement is checked against the table itself; words asked of each
  section are scaled by `swarm.composer_length_factor` (0.8, provisional:
  sections overshot by +16 to +44 % in six runs).
- 197 tests (23 new in `tests/test_p1_composer.py`, including a two-node
  end-to-end run over real TLS).

**Windows install and a quieter terminal** (17 October 2026)
- SwarmblyLCE pin moved to `b659ac4`: the previous pin tracked 18 cache
  files whose names contained `:` (Ollama model tags), which Windows forbids,
  so `git clone` — and with it `pip install` — failed on Windows.
- The terminal no longer prints every WebSocket attempt. A browser tab left
  open from an earlier launch holds a stale session token; its reconnections
  were logged twice each, with the token in clear text. They are now dropped
  (one note a minute at most), tokens are redacted from any log line, and
  the web client reloads itself once to pick up the new token, with
  exponential back-off while the server is down.
- Network outcomes on the terminal: node found (once), connected and
  authenticated, left; authentication failures once per address; a single
  "no nodes found" line after an empty search, and a summary after
  “Search again”.

## 0.2.1 — Distributed answers that follow the request (unreleased)

Fixes from the diagnosis of 2026-10-15: a Spanish essay request came back as
mixed English/Spanish, partial answers that echoed the contract.

- **Admission**: numbered lines are a batch only when they are data items
  with a stated operation. The criteria, instructions, steps or rules of one
  task, and single compositions (essay, speech, text of N words), are no
  longer split; they run as one task. Each packet used to carry ~95 % of such
  a request, so every worker wrote the whole essay.
- **The user's closing instructions travel with every fragment**
  (`answer_sheet=False`); the English `[NN] value` directive is gone. Batches
  get a short directive in the request's language.
- **Language**: the request's language is detected on-device and carried as
  the Γ extension `lang`. Workers render the contract and task headings in
  that language; a "respond in <language>" line inside the task covers
  workers on older versions. English packets are unchanged.
- **Conversation context**: a follow-up in a distributed mode is rewritten by
  the local model into a self-contained request; the history never leaves the
  device. Without a local rewrite it is answered locally with the
  conversation.
- **Consensus for compositions**: one whole replica is selected (request
  language, then complete, then document medoid); per-unit alignment is kept
  as the divergence report. Batches vote per numbered item (majority, ties
  to the best-ranked replica); per-unit alignment had appended a second
  replica's re-listed items to the answer in a live smoke test.
- **Length**: requested lengths in words are read in es/en/pt/fr; output
  budgets follow them (whole-request replicas and the local answer included).
  Workers report `finish_reason`; truncated tasks are listed and noted.
- **Contract**: neutral audience when none is stated; capitalised verbs at
  line or bullet starts are no longer canonical entities; English default
  forbidden phrases are not sent with non-English requests.
- **Monitor**: largest share of the request carried by one packet
  (`max_packet_prompt_fraction`).
- 174 tests (34 new in `tests/test_p0_quality.py`).

## 0.2.0 — Phase 2.5: guided setup and new interface (2026-10-12)

Software DOI: [10.5281/zenodo.23322639](https://doi.org/10.5281/zenodo.23322639)
(all versions: [10.5281/zenodo.23322638](https://doi.org/10.5281/zenodo.23322638)).

**Setup that explains itself**
- Recommended configuration from measured hardware: a memory budget
  (unified memory, VRAM or RAM, with its derivation), chat model, local
  parallelism, multi-model, worker limits and LCE level. Every value says why
  and whether it is measured or estimated; applying it keeps a backup and can
  be reverted. It never turns on the network, sharing or a privacy tier.
- First-run assistant: welcome, system check, recommended configuration,
  models, permissions, memory, ready. Each step can be skipped.
- Explicit permissions for local-network discovery and model downloads,
  recorded with their date; internet swarms stay off until Phase 3.
- System check ("doctor"): Python packages (including the pinned upstream
  commits), Ollama, ports. Missing Python packages can be installed into the
  app's own virtual environment after consent; nothing system-wide.
- Model downloads through Ollama only, after the download permission and a
  per-model confirmation showing size and licence (catalog verified
  2026-10-12); progress streamed, cancellable.

**One-command launcher**
- `./launch.sh` (macOS / Linux), `Swarmbly.command` (macOS double-click) and
  `launch.bat` (Windows) run `scripts/launch.py`: Python, git, `.venv`,
  packages, Ollama and port, asking before every change; installs only inside
  `.venv`, never installs Ollama, reinstalls when requirements change, opens
  an already-running app instead of starting a second one. `--check`,
  `--setup-only`, `--headless`, `--yes`, `--port` and more.
- `scripts/dev_setup.sh` now uses the launcher.

**Fixes found by the first macOS CI run**
- mDNS announcements failed on computers whose name does not fit a DNS label
  (longer than 63 bytes, or with spaces, apostrophes or accents, e.g.
  "Sebastián's MacBook Pro"): zeroconf refused the host record and the node
  was never discovered. The host label is now sanitised and capped; identity
  is unaffected (it is the node key). Regression tests added.

**Documentation and repository**
- README rewritten with screenshots; new user guide (`docs/USER_GUIDE.md`),
  `CONTRIBUTING.md`, `SECURITY.md`, issue and pull-request templates, and a
  test workflow (Linux, Python 3.10–3.13; macOS).
- Installation guide rebuilt around the launcher (ports, data locations,
  updating, uninstalling, troubleshooting).

**Several local models**
- Multi-model mode: replicas of a request can run on different local model
  families (a local pool alongside remote workers), with the same consensus
  and reporting as the swarm. Whole requests that cannot be fragmented can
  still be answered by several local models and aligned.
- `constraints.model_family` honoured by workers when they have that family.

**Interface**
- New interface: conversation list, streaming chat with text attachments,
  mode and model per message, "How this answer was made" (pipeline as a DNA
  strand, attempts, consensus units, seams, caveats, reports), swarm map with
  real dispatch pulses, health and contribution, memory levels, settings by
  topic with profiles, light and dark themes, phone layout.
- Every readout is labelled measured, estimated or unknown.
- `scripts/ui_preview.py`: interface preview with a fake swarm on loopback
  (canned answers, never announced on the network).


## 0.1.1 — Phase 1.5 hardening (2026-10-12)

Fixes the findings of `docs/AUDIT_FASE0_ES.md`.

**Network**
- mDNS discovery rewritten on zeroconf's asyncio API: it now discovers peers
  (it never did), filters its own announcement, handles goodbyes, keeps a TTL
  cache with first-seen / last-verified / expiry, and runs an active query per
  request. Discovery starts and stops at runtime (H1, H2, H14, H15, H19, H23).
- Handshake revision 2: Ed25519 identities bound to the TLS certificate
  fingerprint; initiator advertisement authenticated; signed advertisement
  updates on live sessions (H9).
- One session per peer (deterministic tie-break); tasks served outside the
  read loop; keepalive with RTT; per-peer replay window and queue cap;
  graceful shutdown in < 1 s (H6, H26).
- TLS private key written 0600 (H27).

**Engine**
- Plan admission: only structural partitions are fragmented; inline lists are
  normalised losslessly into labelled items (H3).
- Wire packets built from fields: no session id, no complete request, minimal
  Γ; privacy self-check blocks dispatch on any leak (H4, H5).
- Asynchronous scheduler: parallel dispatch by readiness (statement edges do
  not wait), family-diverse replicas, `k_min` up front, hedges/retries up to
  `k_max`, per-worker capacity respected, results verified before assembly
  (H6, H12, H13).
- Upstream `consensus()` reused; lane classification (LCE) before dispatch;
  E_SWARM_UNKNOWN never falls back to GLOBAL; relative deadlines; worker cuts
  generation at its deadline (H11, H24, H25).
- Enumerated answers are spliced without transition bridges.

**Local API and UI**
- Host allowlist, Origin checks, per-launch session token, CSP and security
  headers; config changes validated (`api.*` is CLI-only) (H7).
- Every remote or model-provided string escaped; remote images never
  auto-loaded (H8).
- Events from the P2P thread reach the UI (H16).
- Processing reports fixed (they crashed) with minimal/standard/full detail;
  saved only on request.

**Packaging and metrics**
- The UI ships inside the Python package (wheel installs had no UI) (H17).
- CLI shutdown fixed (H18); orchestrator rebuilt on configuration changes (H20).
- Contribution separates served-to-others from consumed-locally (H22).

## 0.1.0 — Phases 1–2 (2026-10-11)

Initial local app, LAN prototype and monitor.
