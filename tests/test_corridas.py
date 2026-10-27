import os
import tempfile
from pathlib import Path

from src import corridas
from src import config


def test_nueva_corrida_crea_carpeta_fecha(tmp_path, monkeypatch):
    datos = tmp_path / "datos"
    datos.mkdir()
    monkeypatch.setattr(corridas, "DATOS", str(datos))
    monkeypatch.setattr(config, "DATOS_DIR", str(datos))

    usuario = "testuser"
    ruta = corridas.nueva_corrida(usuario)
    assert os.path.isdir(ruta)
    nombre = os.path.basename(ruta)
    import re

    assert re.match(r"^\d{4}-\d{2}-\d{2}_\d{4}$", nombre)


def test_buscar_corrida_mas_reciente(tmp_path, monkeypatch):
    datos = tmp_path / "datos"
    datos.mkdir()
    monkeypatch.setattr(corridas, "DATOS", str(datos))
    monkeypatch.setattr(config, "DATOS_DIR", str(datos))

    usuario = "testuser"
    base_u = datos / usuario
    base_u.mkdir(parents=True)
    (base_u / "2025-01-01_1000").mkdir()
    (base_u / "2025-01-02_0900").mkdir()
    # más reciente
    rec = corridas.buscar_corrida(usuario)
    assert rec.endswith("2025-01-02_0900")


def test_buscar_corrida_indicada(tmp_path, monkeypatch):
    datos = tmp_path / "datos"
    datos.mkdir()
    monkeypatch.setattr(corridas, "DATOS", str(datos))
    monkeypatch.setattr(config, "DATOS_DIR", str(datos))

    usuario = "testuser"
    base_u = datos / usuario
    base_u.mkdir(parents=True)
    (base_u / "2025-01-01_1000").mkdir()
    encontrada = corridas.buscar_corrida(usuario, "2025-01-01_1000")
    assert encontrada.endswith("2025-01-01_1000")
    # no existe
    assert corridas.buscar_corrida(usuario, "noexiste") is None


def test_compatibilidad_raw_sin_fecha(tmp_path, monkeypatch):
    datos = tmp_path / "datos"
    datos.mkdir()
    monkeypatch.setattr(corridas, "DATOS", str(datos))
    monkeypatch.setattr(config, "DATOS_DIR", str(datos))

    usuario = "testuser"
    base_u = datos / usuario
    base_u.mkdir(parents=True)
    (base_u / "raw").mkdir()
    rec = corridas.buscar_corrida(usuario)
    assert rec == str(base_u)
