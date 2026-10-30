import pytest

from app.models import CV


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CV_DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture(autouse=True)
def no_real_bedrock(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Tests must not create a real AWS client.")

    monkeypatch.setattr("app.llm.boto3.client", forbidden)


@pytest.fixture
def sample_cv() -> CV:
    return CV.model_validate(
        {
            "language": "sv",
            "contact": {
                "name": "Anna Exempel",
                "title": "Kulturproducent",
                "email": "anna@example.com",
                "phone": "070-000 00 00",
                "city": "Göteborg",
                "links": ["linkedin.com/in/anna-exempel"],
            },
            "summary": "Kulturproducent med erfarenhet av publika program & samverkan. 100% fokus på publik_.",
            "core_skills": ["Projektledning", "Budget & uppföljning", "Publikarbete"],
            "experience": [
                {
                    "role": "Producent",
                    "employer": "Exempelmuseet",
                    "place": "Göteborg",
                    "start": "2020",
                    "end": "",
                    "bullets": [
                        {"text": "Producerade 12 utställningar i samverkan med lokala aktörer.", "source": "cv.pdf"},
                        {"text": "Ansvarade för budget om $ och #hashtag {test}.", "source": "cv.pdf"},
                    ],
                }
            ],
            "projects": [
                {"year": "2019", "title": "Sommarscenen", "role": "Projektledare", "partner": "Kulturförvaltningen", "scope": "Tre veckors festival.", "source": "cv.pdf"}
            ],
            "education": [
                {"degree": "Kandidatexamen i kulturvetenskap", "institution": "Göteborgs universitet", "period": "2014 – 2017", "details": ""}
            ],
            "languages": [{"name": "Svenska", "level": "Modersmål"}, {"name": "Engelska", "level": "Flytande"}],
            "digital_skills": ["Office 365", "Adobe InDesign"],
            "volunteer": [{"role": "Styrelseledamot", "organisation": "Kulturföreningen", "period": "2018 – 2021", "details": ""}],
        }
    )
