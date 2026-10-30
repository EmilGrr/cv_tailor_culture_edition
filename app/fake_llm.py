"""Offline stand-in for the Bedrock model, for trying the app without AWS.

Enabled with CV_FAKE_LLM=1. It returns a canned CV for the fictional persona in samples/, so it only makes
sense with those documents. It does NOT test the real prompt or the real model.
"""

import json
import re

# Each text is paired with a key phrase. The source is whichever uploaded document contains that phrase.
TEXT = {
    "sv": {
        "title": "Kulturproducent",
        "summary": (
            "Kulturproducent med tio års erfarenhet av publika program, utställningar och scenkonst. Producerar över "
            "60 publika program per år i samverkan med föreningar och skolor och har arbetat med budget, projektmedel "
            "och tillgänglighet."
        ),
        "summary_short": "Kulturproducent med tio års erfarenhet av publika program, budget och samverkan.",
        "skills": [
            "Produktion av publika program", "Projektledning och budget", "Ansökningar om projektmedel",
            "Samverkan med civilsamhälle och skolor", "Tillgänglighet", "Pedagogik",
        ],
        "jobs": [
            {
                "role": "Producent", "employer": "Kulturhuset Hamnen", "place": "Göteborg", "start": "2020", "end": "",
                "bullets": [
                    ("Producerar 14 utställningar och över 60 publika program per år i samverkan med föreningar och skolor.", "60 publika program"),
                    ("Ansvarar för en projektbudget på 2,4 Mkr, inklusive ansökningar om projektmedel.", "2,4 Mkr"),
                    ("Utvecklade familjedagarna, där besöksantalet ökade från 6 000 till 14 000 på tre år.", "14 000"),
                    ("Införde teckenspråkstolkade visningar och lättläst information.", "teckenspråkstolkade"),
                    ("Leder en grupp på fem projektmedarbetare.", "fem projektmedarbetare"),
                ],
            },
            {
                "role": "Projektledare", "employer": "Scenkonstkollektivet Norrsken", "place": "Göteborg", "start": "2017", "end": "2020",
                "bullets": [
                    ("Planerade och genomförde en turné med tre produktioner och 40 föreställningar i 12 kommuner.", "12 kommuner"),
                    ("Byggde samarbeten med skolor kring ungdomsföreställningar.", "ungdomsföreställningar"),
                ],
            },
            {
                "role": "Museipedagog", "employer": "Västkustmuseet", "place": "Uddevalla", "start": "2014", "end": "2017",
                "bullets": [
                    ("Genomförde cirka 150 skolvisningar per år.", "150 skolvisningar"),
                    ("Tog fram ett skolprogram om sjöfart tillsammans med lärare.", "sjöfart"),
                ],
            },
        ],
        "projects": [
            ("2023", "Sommarscenen Lindholmen", "Producent", "Kulturförvaltningen", "Tre veckors utomhusfestival med 22 föreställningar och 5 200 besökare.", "Sommarscenen"),
            ("2019", "Festivalen Ljus i Mörkret", "Produktionsledare", "Kulturföreningen Fyren", "Fyra dagar med 40 volontärer.", "Ljus i Mörkret"),
        ],
        "education": [
            {"degree": "Kandidatexamen i kulturvetenskap", "institution": "Göteborgs universitet", "period": "2011 – 2014", "details": ""},
            {"degree": "Projektledning i kultursektorn, 15 hp", "institution": "Distans", "period": "2018", "details": ""},
        ],
        "languages": [("Svenska", "Modersmål"), ("Engelska", "Flytande"), ("Tyska", "Grundläggande")],
        "digital": ["Office 365", "Adobe InDesign", "WordPress", "Mailchimp"],
        "volunteer": {"role": "Styrelseledamot", "organisation": "Kulturföreningen Fyren", "period": "2018 – 2021", "details": ""},
        "references": "Referenser lämnas på begäran",
        "gaps": [
            "Hur stor var den totala budgeten för Sommarscenen Lindholmen?",
            "Vilken roll hade du i Kulturföreningen Fyrens verksamhet utöver styrelseuppdraget?",
        ],
        "left_out": ["Podden Hamnens röster (2021)", "Föreläsningar om lättläst information (2022, 2024)"],
        "requirements": [
            (r"publika program", "Erfarenhet av att producera publika program", 0, 0),
            (r"budget", "Budgetansvar", 0, 1),
            (r"projektmedel", "Erfarenhet av att söka projektmedel", 0, 1),
            (r"samverk", "Samverkan med civilsamhälle, föreningar och skolor", 1, 1),
            (r"tillgänglighet", "Kunskap om tillgänglighet", 0, 3),
            (r"pedagog|skolprogram|visningar", "Pedagogisk erfarenhet", 2, 0),
            (r"\bvr\b|digitala format", "Erfarenhet av digitala format och VR", None, None),
        ],
    },
    "en": {
        "title": "Cultural producer",
        "summary": (
            "Cultural producer with ten years of experience in public programmes, exhibitions and performing arts. "
            "Produces over 60 public programmes a year in partnership with associations and schools, and has worked "
            "with budgets, grants and accessibility."
        ),
        "summary_short": "Cultural producer with ten years of experience in public programmes, budgets and partnerships.",
        "skills": [
            "Producing public programmes", "Project management and budgets", "Grant applications",
            "Partnerships with civil society and schools", "Accessibility", "Pedagogy",
        ],
        "jobs": [
            {
                "role": "Producer", "employer": "Kulturhuset Hamnen", "place": "Gothenburg", "start": "2020", "end": "",
                "bullets": [
                    ("Produces 14 exhibitions and over 60 public programmes a year in partnership with associations and schools.", "60 publika program"),
                    ("Responsible for a project budget of SEK 2.4 million, including grant applications.", "2,4 Mkr"),
                    ("Developed the family days, where visitor numbers grew from 6,000 to 14,000 in three years.", "14 000"),
                    ("Introduced sign-language interpreted tours and easy-read information.", "teckenspråkstolkade"),
                    ("Leads a group of five project staff.", "fem projektmedarbetare"),
                ],
            },
            {
                "role": "Project manager", "employer": "Scenkonstkollektivet Norrsken", "place": "Gothenburg", "start": "2017", "end": "2020",
                "bullets": [
                    ("Planned and ran a tour of three productions and 40 performances in 12 municipalities.", "12 kommuner"),
                    ("Built partnerships with schools around productions for young people.", "ungdomsföreställningar"),
                ],
            },
            {
                "role": "Museum educator", "employer": "Västkustmuseet", "place": "Uddevalla", "start": "2014", "end": "2017",
                "bullets": [
                    ("Ran about 150 school tours a year.", "150 skolvisningar"),
                    ("Developed a school programme on seafaring together with teachers.", "sjöfart"),
                ],
            },
        ],
        "projects": [
            ("2023", "Sommarscenen Lindholmen", "Producer", "Cultural administration", "Three-week outdoor festival with 22 performances and 5,200 visitors.", "Sommarscenen"),
            ("2019", "Festivalen Ljus i Mörkret", "Production manager", "Kulturföreningen Fyren", "Four days with 40 volunteers.", "Ljus i Mörkret"),
        ],
        "education": [
            {"degree": "BA in Cultural Studies", "institution": "University of Gothenburg", "period": "2011 – 2014", "details": ""},
            {"degree": "Project management in the cultural sector, 15 credits", "institution": "Distance", "period": "2018", "details": ""},
        ],
        "languages": [("Swedish", "Native"), ("English", "Fluent"), ("German", "Basic")],
        "digital": ["Office 365", "Adobe InDesign", "WordPress", "Mailchimp"],
        "volunteer": {"role": "Board member", "organisation": "Kulturföreningen Fyren", "period": "2018 – 2021", "details": ""},
        "references": "References available on request",
        "gaps": [
            "What was the total budget for Sommarscenen Lindholmen?",
            "What was your role at Kulturföreningen Fyren beyond the board seat?",
        ],
        "left_out": ["The podcast Hamnens röster (2021)", "Talks on easy-read information (2022, 2024)"],
        "requirements": [
            (r"public programme", "Experience of producing public programmes", 0, 0),
            (r"budget", "Budget responsibility", 0, 1),
            (r"grant", "Experience of applying for grants", 0, 1),
            (r"partnership|collaborat", "Partnership with civil society, associations and schools", 1, 1),
            (r"accessib", "Knowledge of accessibility", 0, 3),
            (r"pedagog|school programme|guided tours", "Pedagogical experience", 2, 0),
            (r"\bvr\b|digital formats", "Experience of digital formats and VR", None, None),
        ],
    },
}


def _norm(text: str) -> str:
    return " ".join(text.split())


def _sources(corpus_text: str) -> list[tuple[str, str]]:
    parts = re.split(r"=== SOURCE: (.+?) ===\n", corpus_text)
    return [(parts[i], _norm(parts[i + 1])) for i in range(1, len(parts) - 1, 2)]


def _source_for(key: str, sources: list[tuple[str, str]]) -> str:
    key = _norm(key)
    return next((name for name, text in sources if key in text), "")


def _language(job_text: str) -> str:
    lower = job_text.lower()
    if re.search(r"[åäö]", lower) or " och " in lower:
        return "sv"
    return "en" if " and " in lower or " the " in lower else "sv"


def _title_and_employer(job_text: str) -> tuple[str, str]:
    first = next((line.strip() for line in job_text.splitlines() if line.strip()), "")
    for sep in (" till ", " at ", " – ", " - "):
        if sep in first:
            title, employer = first.split(sep, 1)
            return title.strip(), employer.strip()
    return first[:60], ""


def _bullets(job: dict, sources) -> list[dict]:
    return [{"text": text, "source": _source_for(key, sources)} for text, key in job["bullets"]]


def _experience(t: dict, sources) -> list[dict]:
    return [
        {k: job[k] for k in ("role", "employer", "place", "start", "end")} | {"bullets": _bullets(job, sources)}
        for job in t["jobs"]
    ]


def _projects(t: dict, sources) -> list[dict]:
    return [
        {"year": y, "title": title, "role": role, "partner": partner, "scope": scope, "source": _source_for(key, sources)}
        for y, title, role, partner, scope, key in t["projects"]
    ]


def _section_values(t: dict, sources) -> dict:
    return {
        "summary": t["summary"],
        "core_skills": t["skills"],
        "experience": _experience(t, sources),
        "projects": _projects(t, sources),
        "education": t["education"],
        "languages": [{"name": n, "level": lvl} for n, lvl in t["languages"]],
        "digital_skills": t["digital"],
        "volunteer": [t["volunteer"]],
    }


def _split_user_message(user: str) -> tuple[str, str]:
    job = re.search(r"JOB POSTING\n-----\n(.*?)\n-----", user, re.S)
    corpus = re.search(r"APPLICANT DOCUMENTS\n-----\n(.*?)\n-----", user, re.S)
    return (job.group(1) if job else ""), (corpus.group(1) if corpus else "")


def _draft(user: str) -> str:
    job_text, corpus = _split_user_message(user)
    lang = _language(job_text)
    t = TEXT[lang]
    sources = _sources(corpus)
    title, employer = _title_and_employer(job_text)
    lower = job_text.lower()

    requirements = []
    for pattern, label, job_idx, bullet_idx in t["requirements"]:
        if not re.search(pattern, lower):
            continue
        if job_idx is None:
            requirements.append({"text": label, "evidence": "", "source": ""})
            continue
        text, key = t["jobs"][job_idx]["bullets"][bullet_idx]
        requirements.append({"text": label, "evidence": text, "source": _source_for(key, sources)})

    cv = {
        "language": lang,
        "contact": {
            "name": "Maja Lindqvist", "title": t["title"], "email": "maja.lindqvist@example.com",
            "phone": "070-000 00 00", "city": "Göteborg" if lang == "sv" else "Gothenburg", "links": [],
        },
        **_section_values(t, sources),
        "references": t["references"],
        "gaps_and_questions": t["gaps"],
        "left_out": t["left_out"],
    }
    analysis = {"title": title, "employer": employer, "language": lang, "requirements": requirements, "keywords": []}
    return json.dumps({"analysis": analysis, "cv": cv}, ensure_ascii=False)


def _section(user: str) -> str:
    section = re.search(r'Rewrite the section "(\w+)"', user).group(1)
    instruction = (re.search(r"Instruction from the applicant: (.*)", user) or [None, ""])[1].lower()
    lang = "en" if '"language":"en"' in user else "sv"
    _, corpus = _split_user_message(user)
    t = TEXT[lang]
    values = _section_values(t, _sources(corpus))
    if section == "summary" and any(w in instruction for w in ("kort", "short")):
        values["summary"] = t["summary_short"]
    return json.dumps({section: values[section]}, ensure_ascii=False)


def complete(system: str, user: str) -> str:
    return _section(user) if system.startswith("You rewrite ONE section") else _draft(user)
