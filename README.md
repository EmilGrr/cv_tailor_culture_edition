# CV Tailor - Culture edition

A local tool that drafts CV text tailored to a job posting, using only facts from your own documents. You edit the text, then generate a PDF through LaTeX.

Only the posting text and your source documents are sent to Claude on AWS Bedrock. Everything else runs on your computer.

## Setup

1. Install dependencies: `uv sync`
2. Install Tectonic (LaTeX engine) into `tools\tectonic\` or put `tectonic.exe` on your PATH. The first PDF run downloads the LaTeX packages it needs, then they are cached.
3. Copy `.env.example` to `.env` and add your AWS credentials. The app only uses credentials from `.env`.

## Run

```powershell
uv run uvicorn app.main:app --port 8000
```

Open http://127.0.0.1:8000.

## Use

1. **About me** (top tab): upload PDF, DOCX, TXT or Markdown files, or write notes directly. Do this once, then keep it up to date.
2. **Job posting** (start page): paste the text or fetch it from a link, then draft the CV. You land in the editor.
3. **Edit**: change any text, regenerate a section with AI, or remove a section (it can be added back from the bar under the sections). Contact details always stay. Under "Missing details", **Add details** opens About me with the questions to answer; answers are saved as a note and the answered questions disappear.
4. **PDF**: pick a template, the PDF is typeset automatically, then download it.

Earlier applications are listed on the start page. Data is stored in `data\` (git-ignored).

## Try it with the sample persona

`samples/` holds a fictional persona, Maja Lindqvist, a culture producer in Göteborg, with an old CV (DOCX), a cover letter (PDF), a profile (Markdown), a project list (TXT) and a note, plus three job postings and two local web pages for testing "Fetch text".

```powershell
uv run python demo.py
```

Open http://127.0.0.1:8000. This starts the app with the persona already loaded, in its own `demo-data\` folder, so it never mixes with your real material (the status bar shows "DEMO data"). Drafts are **real Claude calls** through the credentials in your `.env`, so they adapt to whatever posting you give it. It also serves the sample job pages on http://127.0.0.1:8001.

Things to try:

- **Job posting:** paste `samples\jobs\kulturproducent-sv.txt`, `museipedagog-sv.txt` (same persona, different focus: compare the summaries and skills) or `producer-en.txt`, or fetch `http://127.0.0.1:8001/kulturproducent.html`. `http://127.0.0.1:8001/js-only.html` shows what happens when a page can't be read.
- **About me:** upload the files in `samples\maja-lindqvist\` yourself (delete them first), or paste `samples\note-saker-som-inte-star-i-cv.txt` as a note.
- **Edit and PDF:** edit text, regenerate a section, remove a section, then try all three templates. The CV runs to two pages in Classic and Fun, and the PDF step says so.
- **Honesty checks:** the postings ask for things Maja has not done (VR, knowledge of sign language). They should show up as gaps in the Requirements panel and not be claimed in the CV.

No AWS key, or don't want to spend a call? `uv run python demo.py --offline` uses a canned stand-in for the model that only knows this persona. It returns the same CV for any posting, so use it only to click through the interface.

## Tests

```powershell
uv run pytest
```

Tests never call AWS. The PDF tests are skipped if Tectonic is missing.

See [docs/design.md](docs/design.md) for the design and the reasoning behind the AI prompts. The prompts are in `app/prompts.py`.
