"""Lane refinement: context words need a personal marker in the same clause."""

from swarmbly_app.engine.lane import classify


def test_public_uses_of_context_words_are_public():
    assert classify("4. Inicio de la protección legal del lobo peletero de Galápagos en Ecuador") == "PUBLIC"
    assert classify("¿Qué es la salud pública?") == "PUBLIC"
    assert classify("What does a medical physicist do?") == "PUBLIC"


def test_personal_uses_stay_sensitive():
    assert classify("Mi abogado dice que debo firmar, ¿qué opinas?") == "SENSITIVE"
    assert classify("Tengo un problema de salud y quiero saber qué hacer") == "SENSITIVE"
    assert classify("My medical results came back") == "SENSITIVE"


def test_strong_terms_are_always_sensitive():
    assert classify("¿Cómo se calcula la deuda pública?") == "SENSITIVE"
    assert classify("Explain how a password manager works") == "SENSITIVE"


def test_sanitisable_markers_survive_the_masking():
    assert classify("Consulta legal: escribe a ana@example.com") == "SANITISABLE"
