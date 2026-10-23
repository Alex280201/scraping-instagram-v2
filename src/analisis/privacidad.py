import re

PATRON_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
# Secuencias de dígitos con separadores opcionales; solo se enmascaran si tienen >= 8 dígitos
# (así no se tapan años como "2019" ni cantidades pequeñas).
PATRON_TELEFONO = re.compile(r"\+?\d[\d\s().-]{6,}\d")
PATRON_URL = re.compile(r"https?://\S+|www\.\S+")


def anonimizar_texto(texto: str) -> str:
    """Enmascara correos, teléfonos y URLs antes de enviar el texto a la API."""
    if not texto:
        return ""
    t = PATRON_EMAIL.sub("[CORREO_OCULTO]", texto)
    t = PATRON_URL.sub("[ENLACE]", t)

    def _tel(m):
        digitos = re.sub(r"\D", "", m.group(0))
        return "[TELEFONO_OCULTO]" if len(digitos) >= 8 else m.group(0)

    return PATRON_TELEFONO.sub(_tel, t)

