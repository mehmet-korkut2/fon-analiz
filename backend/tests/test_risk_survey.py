import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import risk_survey as rs


def answers(**over):
    base = {q.id: 2 for q in rs.QUESTIONS}  # hepsi orta cevap
    base.update(over)
    return base


def test_max_raw_and_scaling():
    assert rs.MAX_RAW == 60
    assert rs.evaluate({q.id: 4 for q in rs.QUESTIONS}).score == 100
    assert rs.evaluate({q.id: 0 for q in rs.QUESTIONS}).score == 0
    mid = rs.evaluate(answers())
    assert mid.raw == 30 and mid.score == 50 and mid.profile == rs.DENGELI


@pytest.mark.parametrize("score,profile", [(0, "temkinli"), (39, "temkinli"), (40, "dengeli"), (69, "dengeli"), (70, "agresif"), (100, "agresif")])
def test_profile_boundaries(score, profile):
    assert rs.profile_for_score(score) == profile


def test_caps_lower_profile_and_explain():
    top = {q.id: 4 for q in rs.QUESTIONS}
    r = rs.evaluate({**top, "vade": 0})
    assert r.score_profile == rs.AGRESIF and r.profile == rs.TEMKINLI
    assert [c.rule for c in r.caps] == ["vade"]
    r = rs.evaluate({**top, "birikim": 0})
    assert r.profile == rs.DENGELI and [c.rule for c in r.caps] == ["birikim"]
    # birikiminin neredeyse tamamını yatıran: en fazla dengeli
    r = rs.evaluate({**top, "birikim_payi": 0})
    assert r.score_profile == rs.AGRESIF and r.profile == rs.DENGELI and [c.rule for c in r.caps] == ["birikim_payi"]
    # sınır profilden zaten düşük değilse "uygulandı" sayılmaz
    low = {q.id: 0 for q in rs.QUESTIONS}
    assert rs.evaluate(low).caps == []


def test_invalid_answers():
    with pytest.raises(rs.SurveyError, match="Cevaplanmayan"):
        rs.evaluate({"vade": 2})
    with pytest.raises(rs.SurveyError, match="geçersiz"):
        rs.evaluate(answers(vade=5))
    with pytest.raises(rs.SurveyError, match="Bilinmeyen"):
        rs.evaluate({**answers(), "yas": 1})


def test_api_survey_and_profile():
    c = TestClient(app)
    s = c.get("/api/risk-survey").json()
    assert len(s["questions"]) == 8 and s["max_raw"] == 60
    assert s["qualified_question"]["scored"] is False
    assert [p["risk_range"] for p in s["profiles"]] == [[1, 3], [2, 5], [4, 7]]
    # diğer cevaplar en yüksek, vade 1 yıldan kısa: puan agresif ama profil temkinliye iner
    r = c.post("/api/risk-profile", json={"answers": {**{q.id: 4 for q in rs.QUESTIONS}, "vade": 0}, "qualified": True}).json()
    assert r["score_profile"] == "agresif"
    assert r["profile"] == "temkinli" and r["qualified"] is True and r["risk_range"] == [1, 3]
    assert r["caps"][0]["rule"] == "vade"
    assert c.post("/api/risk-profile", json={"answers": {"vade": 1}}).status_code == 422
