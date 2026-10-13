from fastapi import APIRouter, HTTPException

from app.schemas import CapOut, ProfileIn, ProfileOut, ProfileRuleOut, SurveyOption, SurveyOut, SurveyQuestion
from app.services import risk_survey as rs

router = APIRouter(tags=["risk"])


def _question(q: rs.Question) -> SurveyQuestion:
    return SurveyQuestion(id=q.id, topic=q.topic, text=q.text, weight=q.weight, scored=q.scored,
                          options=[SurveyOption(value=i, text=t) for i, t in enumerate(q.options)])


def rule_out(profile: str) -> ProfileRuleOut:
    r = rs.PROFILE_RULES[profile]
    return ProfileRuleOut(profile=profile, label=rs.PROFILE_LABELS[profile], min_score=r.min_score,
                          risk_range=r.risk_range, max_volatility=r.max_volatility, description=r.description)


@router.get("/risk-survey", response_model=SurveyOut)
def survey():
    return SurveyOut(
        questions=[_question(q) for q in rs.QUESTIONS],
        qualified_question=_question(rs.QUALIFIED_QUESTION),
        max_raw=rs.MAX_RAW,
        profiles=[rule_out(p) for p in rs.PROFILES],
    )


@router.post("/risk-profile", response_model=ProfileOut)
def risk_profile(body: ProfileIn):
    """Cevaplardan puan ve profil hesaplar. Kullanıcı girişi olmadığı için hiçbir şey kaydedilmez;
    sonuç tarayıcıda saklanır."""
    try:
        r = rs.evaluate(body.answers, body.qualified)
    except rs.SurveyError as e:
        raise HTTPException(422, str(e)) from e
    rule = r.rule
    return ProfileOut(
        raw=r.raw, score=r.score, profile=r.profile, label=rs.PROFILE_LABELS[r.profile], score_profile=r.score_profile,
        risk_range=rule.risk_range, max_volatility=rule.max_volatility, description=rule.description,
        qualified=r.qualified, caps=[CapOut(rule=c.rule, max_profile=c.max_profile, message=c.message) for c in r.caps],
    )
