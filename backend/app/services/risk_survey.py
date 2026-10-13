"""Risk anketi: sorular, puanlama ve profile geçiş.

Her cevap 0-4 puan alır ve sorunun ağırlığıyla çarpılır. Ham puan (en fazla 52) 0-100'e
ölçeklenir. Puan profile çevrildikten sonra sınırlayıcı kurallar uygulanır: kısa vade, kayıp
toleransının olmaması ya da acil durum birikiminin olmaması, toplam puan yüksek olsa bile profili
aşağı çeker. Gerekçeler ve kaynaklar için docs/oneri_sistemi.md.

"Nitelikli yatırımcı" sorusu puana girmez; sadece serbest fonların öneriye alınıp alınmayacağını
belirler (serbest fonlar yalnızca nitelikli yatırımcılara satılabilir).
"""
from __future__ import annotations

from dataclasses import dataclass, field

TEMKINLI, DENGELI, AGRESIF = "temkinli", "dengeli", "agresif"
PROFILES = (TEMKINLI, DENGELI, AGRESIF)
PROFILE_LABELS = {TEMKINLI: "Temkinli", DENGELI: "Dengeli", AGRESIF: "Agresif"}


@dataclass(frozen=True)
class ProfileRule:
    min_score: int  # bu puan ve üstü
    risk_range: tuple[int, int]  # uygun TEFAS risk değeri aralığı (dahil)
    max_volatility: float | None  # fonun ölçülen 1 yıllık volatilitesi için üst sınır
    description: str


PROFILE_RULES = {
    TEMKINLI: ProfileRule(0, (1, 3), 0.05, "Anaparayı korumak öncelikli; kısa vade ya da düşük kayıp toleransı."),
    DENGELI: ProfileRule(40, (2, 5), 0.15, "Getiri ile risk arasında denge; orta vade, sınırlı dalgalanmaya hazır."),
    AGRESIF: ProfileRule(70, (4, 7), None, "Uzun vade; yüksek getiri için büyük dalgalanmayı kabul eder."),
}


@dataclass(frozen=True)
class Question:
    id: str
    topic: str
    text: str
    weight: int
    options: tuple[str, ...]  # sırası puandır: 0, 1, 2, 3, 4
    scored: bool = True


QUESTIONS = (
    Question("vade", "Vade", "Bu parayı ne kadar süre yatırımda tutmayı düşünüyorsun?", 3,
             ("1 yıldan az", "1-2 yıl", "2-3 yıl", "3-5 yıl", "5 yıldan fazla")),
    Question("kayip", "Kayıp toleransı", "Yatırımın bir yıl içinde en fazla ne kadar değer kaybetmesine katlanabilirsin?", 3,
             ("Hiç kayıp istemem", "%5'e kadar", "%10'a kadar", "%20'ye kadar", "%30 ve üstü")),
    Question("davranis", "Davranış", "Yatırımın 3 ayda %15 değer kaybetti. Ne yaparsın?", 2,
             ("Hepsini satarım", "Yarısını satarım", "Düşüş sürerse satarım", "Beklerim", "Fırsat bilip ekleme yaparım")),
    Question("hedef", "Hedef", "Bu yatırımdan beklentin ne?", 2,
             ("Anaparayı korumak", "Enflasyon kadar getiri", "Enflasyonun biraz üstünde getiri",
              "Belirgin büyüme", "Dalgalanma önemli değil, en yüksek getiri")),
    Question("gelir", "Gelir durumu", "Düzenli gelirin ne kadar istikrarlı?", 1,
             ("Düzenli gelirim yok", "Düzensiz", "Düzenli ama değişken", "Düzenli", "Düzenli ve artıyor")),
    Question("birikim", "Birikim", "Bu yatırım dışında kaç aylık giderini karşılayacak birikimin var?", 1,
             ("Yok", "3 aydan az", "3-6 ay", "6-12 ay", "12 aydan fazla")),
    Question("deneyim", "Deneyim", "Daha önce hangi ürünlere yatırım yaptın?", 1,
             ("Hiç ya da sadece mevduat", "Para piyasası, borçlanma araçları fonu", "Karma, değişken fon",
              "Hisse senedi fonu ya da hisse senedi", "Türev ürünler, kaldıraçlı işlemler")),
)

QUALIFIED_QUESTION = Question(
    "nitelikli", "Nitelikli yatırımcı",
    "SPK tanımına göre nitelikli yatırımcı mısın? Serbest fonlar yalnızca nitelikli yatırımcılara satılabilir. "
    "Bu soru puanı etkilemez; sadece serbest fonların öneriye alınıp alınmayacağını belirler.",
    0, ("Hayır / bilmiyorum", "Evet"), scored=False,
)

MAX_RAW = sum(4 * q.weight for q in QUESTIONS)  # 52


@dataclass
class Cap:
    rule: str
    max_profile: str
    message: str


@dataclass
class ProfileResult:
    raw: int
    score: int  # 0-100
    profile: str
    score_profile: str  # sadece puana göre çıkan profil (sınırlar uygulanmadan)
    qualified: bool
    caps: list[Cap] = field(default_factory=list)

    @property
    def rule(self) -> ProfileRule:
        return PROFILE_RULES[self.profile]


class SurveyError(ValueError):
    pass


def profile_for_score(score: int) -> str:
    return max((p for p in PROFILES if score >= PROFILE_RULES[p].min_score), key=lambda p: PROFILE_RULES[p].min_score)


def _lower(a: str, b: str) -> str:
    return a if PROFILES.index(a) <= PROFILES.index(b) else b


def evaluate(answers: dict[str, int], qualified: bool = False) -> ProfileResult:
    """`answers`: soru id -> seçilen cevabın sırası (0-4)."""
    missing = [q.id for q in QUESTIONS if q.id not in answers]
    if missing:
        raise SurveyError(f"Cevaplanmayan soru: {', '.join(missing)}")
    unknown = set(answers) - {q.id for q in QUESTIONS}
    if unknown:
        raise SurveyError(f"Bilinmeyen soru: {', '.join(sorted(unknown))}")
    for q in QUESTIONS:
        if not 0 <= answers[q.id] < len(q.options):
            raise SurveyError(f"'{q.id}' sorusu için geçersiz cevap: {answers[q.id]}")

    raw = sum(answers[q.id] * q.weight for q in QUESTIONS)
    score = round(raw / MAX_RAW * 100)
    score_profile = profile_for_score(score)

    caps = []
    if answers["vade"] == 0:
        caps.append(Cap("vade", TEMKINLI, "Vade 1 yıldan kısa: bu sürede dalgalı fonlardaki bir düşüşten toparlanmaya zaman kalmayabilir."))
    if answers["kayip"] == 0:
        caps.append(Cap("kayip", TEMKINLI, "Kayıp toleransı yok: değer kaybedebilecek fonlar uygun değil."))
    if answers["birikim"] == 0:
        caps.append(Cap("birikim", DENGELI, "Acil durum birikimi yok: beklenmedik bir ihtiyaçta fonu düşük fiyattan satmak gerekebilir."))

    profile = score_profile
    for cap in caps:
        profile = _lower(profile, cap.max_profile)
    applied = [c for c in caps if PROFILES.index(c.max_profile) < PROFILES.index(score_profile)]
    return ProfileResult(raw, score, profile, score_profile, qualified, applied)
