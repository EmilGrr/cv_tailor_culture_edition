# CV Tailoring Tool — Design

## Goal
A single-user, local Windows tool. The user supplies a job posting (URL or pasted text). The tool drafts tailored CV text using only facts from the user's uploaded documents. The user edits the text, then generates a PDF through LaTeX.

## Decisions
- Input: a URL to a job posting page (fetched locally) or pasted text.
- Sources: PDF, DOCX, Markdown/TXT uploads, plus free-text notes typed in the UI.
- Output language: matches the job posting.
- AI drafts a full CV: profile summary, experience bullets per role, skills, education.
- Single user, one profile, runs on localhost.
- LaTeX engine: Tectonic. 2-3 selectable templates.
- Stack: Python (uv) + FastAPI backend, plain HTML/CSS/JS frontend. No build step.
- The only cloud calls are to AWS Bedrock (Claude Sonnet 5.5). Everything else is local, apart from fetching the job URL.

## Architecture and data flow
1. **Knowledge base:** extracted text is stored as plain files in `data/sources/`. The whole corpus goes into the prompt (no vector DB or RAG).
2. **Job input:** URL fetch (httpx + HTML-to-text) or pasted text. If a fetch fails or the page is JS-rendered, the UI asks for pasted text.
3. **Draft:** one Bedrock call with job text + corpus. Rules: only facts from the sources, nothing invented (employers, dates, degrees), output in the posting's language, structured JSON. Each bullet carries a source-document tag.
4. **Edit:** each section is editable in the UI. A single section can be regenerated with an instruction ("shorter", "emphasise leadership").
5. **PDF:** edited JSON → escaped LaTeX template (Jinja2) → Tectonic → PDF preview and download.
6. **Saved applications:** job + final CV stored locally as JSON.

Privacy: job text and source contents are sent to Bedrock on every draft or regeneration.

## Components
- `app/main.py` — routes, static serving
- `app/ingest.py` — PDF/DOCX/MD/TXT → text, storage
- `app/jobs.py` — URL fetch, HTML cleaning, pasted text
- `app/llm.py` — only Bedrock client; prompts, schema validation, section regeneration
- `app/render.py` — JSON → LaTeX (escaping) → Tectonic → PDF
- `app/templates/` — 2-3 `.tex` templates
- `app/static/` — `index.html`, `style.css`, `app.js`; views: Job posting (start page), Edit, PDF, and an "About me" tab for sources
- `data/` (git-ignored) — sources, applications, PDFs
- `.env` (git-ignored) — AWS credentials and region

## Error handling
- Bedrock errors (credentials, throttling, model access): clear UI message and retry; edits are never lost.
- Malformed JSON from the model: validate, retry once, then show the raw text.
- URL fetch failure: prompt for pasted text.
- LaTeX failure: show the compile log; special characters (`& % $ # _ { } ~ ^ \`) are escaped up front.
- Fact guard: per-bullet source tags are shown in the UI so invented claims are easy to spot.

## Testing
- pytest unit tests: ingest, URL cleaning, LaTeX escaping, JSON validation.
- LLM calls mocked in tests; one manual smoke test against real Bedrock.
- A render test per template that checks Tectonic produces a non-empty PDF.

## Build order
1. Skeleton, Tectonic install, one template renders a hard-coded CV to PDF.
2. Source ingestion and the Sources UI.
3. Bedrock draft generation from pasted job text.
4. URL fetching, editing UI, section regeneration.
5. Remaining templates, saved applications, polish.

## Implementation notes
- Credentials: the app uses only AWS credentials from `.env` (Bedrock API key or IAM keys), never an ambient AWS profile.
- Tectonic downloads LaTeX packages from the internet the first time it compiles, then caches them. This is the only network use besides Bedrock and the job-posting fetch.
- Flow: the start page is the job posting. Drafting goes straight to Edit, then to PDF, which is typeset automatically. Sources live under the "About me" tab.
- Sections can be removed from the CV (stored as `hidden_sections`, so the content is kept and can be added back). Contact details cannot be removed.
- There is no mandatory review step. The edit step remains the place where the user takes ownership of the text.
- Fonts for the UI are bundled in `app/static/fonts`, so the frontend makes no external requests.
- Deep links: `#about`, `#app/<id>` (edit) and `#app/<id>/pdf` open those views.
- Offline demo: `CV_FAKE_LLM=1` swaps the Bedrock call for a canned answer (`app/fake_llm.py`). It is used by the automated tests (which must never call AWS) and by `demo.py --offline`. `demo.py` on its own uses the real model with the persona's data in `demo-data\` (`CV_DEMO=1` only drives the "DEMO data" indicator).
- PDF text must be machine-readable for applicant-tracking systems: common ligatures are switched off (so "Office" is not extracted as "Oﬀice"), and the document language (Swedish or English) is set for correct hyphenation.
- The PDF step reports the page count (`X-Page-Count`) and suggests the Compact template or removing a section when the CV is longer than one page.

## Model
Bedrock inference profile ID: `eu.anthropic.claude-sonnet-5-5` (EU cross-region profile). It is set via config (`BEDROCK_MODEL_ID`), not hard-coded. The first milestone includes a smoke test that calls it with the user's credentials. The `eu.` profile must be enabled in the user's AWS account and region.

## AI content design: Swedish culture-sector CV

Research basis. General Swedish CV guidance is well documented. Culture-sector-specific guidance is thin: the only official source found is Konstnärsnämnden's CV page, which targets artists applying for grants. Points marked *[inferred]* are synthesis, not sourced guidance, and should be checked against a few real Swedish museum, scenkonst and cultural-authority job ads.

Sources:
- Arbetsförmedlingen, CV and cover letter: https://arbetsformedlingen.se/for-arbetssokande/cv-ansokan-och-intervju/skriva-cv and https://arbetsformedlingen.se/for-arbetssokande/cv-ansokan-och-intervju/skriva-personligt-brev
- Vision, CV: https://vision.se/lon-utveckling/soka-jobb/cv
- Konstnärsnämnden, what a CV should contain: https://www.konstnarsnamnden.se/vad-ska-ett-cv-innehalla/
- Myndigheten för kulturanalys, labour market: https://kulturanalys.se/digital-publikation/lagesbild-over-kulturarbetsmarknaden-2025/
- IMY, recruitment systems and GDPR: https://www.imy.se/verksamhet/dataskydd/dataskydd-pa-olika-omraden/arbetsliv/rekryteringssystem-och-kompetensdatabaser/
- Lag (1994:260) om offentlig anställning, 4 § (skicklighet och förtjänst); Fackförbundet ST explainer: https://www.st.org/rad-och-stod/fortjanst-och-skicklighet
- Resume Earth, Swedish CV guide (commercial, lower reliability): https://www.resumeearth.com/skriva-cv

Key findings
- Length is 1-2 A4 pages, reverse-chronological, simple structure with clear headings. Tailor to the job; leave out what does not help.
- Standard sections: Kontaktuppgifter, Sammanfattning, Erfarenhet, Utbildning, plus own headings such as Språk, Datorkunskaper, Föreningsliv/Ideellt engagemang. "Referenser lämnas på begäran".
- Tone: concrete, modest, evidence over adjectives and clichés, no insider jargon that not everyone understands. Mirror the ad's wording where it is true. *(Lagom/Jantelagen as such is not sourced; evidence-over-superlatives is the proxy.)*
- The culture labour market is shifting from employment to freelancing and project work (Kulturanalys, 2023-2025). Fragmented histories are normal and should read as a coherent thread.
- Konstnärsnämnden: group by activity type (utställningar, föreställningar, konserter...), give year, place and *your role* in each project.
- Public employers hire on skicklighet (education, experience, personal qualities) and förtjänst (LOA 4 §, state employers). The CV should make skills checkable against the ad's krav and meriter.
- AI use: Arbetsförmedlingen accepts AI drafts but warns that fully AI-generated text risks being filtered and that the applicant must make it their own. Hence the human edit step is mandatory in the workflow.
- GDPR: leave out personnummer, age, marital status, religion, health. Photo is optional and defaults to off. IMY: purely automated rejection in e-recruitment is generally prohibited.
- Employers often use ATS (e.g. Teamtailor, Varbi). Use one column, standard headings, selectable text. (No primary source on specific ATS products.)

Design rules derived from this

1. **Output schema** (JSON, validated): `language`, `summary` (2-4 lines), `core_skills`, `experience[]` (role, employer, place, start, end, bullets[] with `source`), `projects[]` (year, title, role, partner/organisation, scope, `source`), `education[]`, `languages[]` (plain-language levels), `digital_skills`, `volunteer[]`, `references` (fixed text), plus `gaps_and_questions[]`.
2. **Sections for the culture sector:** an optional `Uppdrag/Projekt` section (or Produktioner/Utställningar) for freelance and project work, listed by year, role, partner and scope. Experience bullets are 3-5 per role, outcome- and collaboration-focused.
3. **Facts only from sources.** Figures (publik, budget, bidrag, number of productions) are used only if present in the user's documents. If a number would help but is missing, the model lists a question in `gaps_and_questions` instead of inventing one. The UI shows these as prompts for the user to fill in.
4. **Selection, not completeness:** the model picks and orders material by relevance to the ad (max 2 pages) and records what it left out, so the user can bring it back.
5. **Tone rules in the system prompt:** sober, specific, no superlatives or clichés ("driven", "stresstålig"), no unexplained sector jargon. Mirror ad terms (e.g. publik, samverkan, tillgänglighet) only where the user's experience supports it.
6. **Ad analysis step:** extract krav, meriter, keywords and language from the posting first, then map them to evidence in the sources. The mapping is shown in the UI as a "krav → evidence" checklist, which is also useful for public-sector ads where skills must be verifiable.
7. **Fragmented histories:** group freelance work under a descriptive title (e.g. "Frilansande kulturproducent") and list clients/partners. Gaps are explained briefly only if the user's sources do.
8. **Language:** the posting's language; Swedish as default when unclear. Plain-language proficiency levels rather than CEFR unless the ad is formal or academic.
9. **Privacy defaults:** no personnummer, age or other sensitive data; no photo unless the user enables it per template.
10. **Templates:** all are ATS-friendly (single column, standard headings, selectable text, simple left-aligned layout, 1-2 pages, restrained design). They differ in typography and accent, not in structure.
11. **Human-in-the-loop:** the flow always passes through the edit step before the PDF, and the user is told to make the text their own. There is no mandatory review gate.
12. **Out of scope for now:** the cover letter (personligt brev). The research suggests it matters in Sweden, so it is a candidate for a later iteration; it must complement, not repeat, the CV.

Validation plan
- Collect 5-10 real Swedish culture-sector job ads (museum, scenkonst, cultural authority, freelance/project) with the user, and run the draft step on them to check that the sector rules above give good results.
- Review the outputs with the user and adjust the system prompt.
