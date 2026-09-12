"""Aliases oficiais dos endpoints públicos do DataJud.

Fonte: https://datajud-wiki.cnj.jus.br/api-publica/endpoints/

A chave do dicionário é (segmento da Justiça, código do tribunal) conforme a
numeração CNJ. O valor é o alias usado na URL da API Pública do DataJud.
"""

from __future__ import annotations


ALIAS_DATAJUD: dict[tuple[str, str], str] = {
    # Tribunais superiores
    ("3", "00"): "api_publica_stj",
    ("5", "00"): "api_publica_tst",
    ("6", "00"): "api_publica_tse",
    ("7", "00"): "api_publica_stm",

    # Justiça Federal
    ("4", "01"): "api_publica_trf1",
    ("4", "02"): "api_publica_trf2",
    ("4", "03"): "api_publica_trf3",
    ("4", "04"): "api_publica_trf4",
    ("4", "05"): "api_publica_trf5",
    ("4", "06"): "api_publica_trf6",

    # Justiça dos Estados e do Distrito Federal
    ("8", "01"): "api_publica_tjac",
    ("8", "02"): "api_publica_tjal",
    ("8", "03"): "api_publica_tjap",
    ("8", "04"): "api_publica_tjam",
    ("8", "05"): "api_publica_tjba",
    ("8", "06"): "api_publica_tjce",
    ("8", "07"): "api_publica_tjdft",
    ("8", "08"): "api_publica_tjes",
    ("8", "09"): "api_publica_tjgo",
    ("8", "10"): "api_publica_tjma",
    ("8", "11"): "api_publica_tjmt",
    ("8", "12"): "api_publica_tjms",
    ("8", "13"): "api_publica_tjmg",
    ("8", "14"): "api_publica_tjpa",
    ("8", "15"): "api_publica_tjpb",
    ("8", "16"): "api_publica_tjpr",
    ("8", "17"): "api_publica_tjpe",
    ("8", "18"): "api_publica_tjpi",
    ("8", "19"): "api_publica_tjrj",
    ("8", "20"): "api_publica_tjrn",
    ("8", "21"): "api_publica_tjrs",
    ("8", "22"): "api_publica_tjro",
    ("8", "23"): "api_publica_tjrr",
    ("8", "24"): "api_publica_tjsc",
    ("8", "25"): "api_publica_tjse",
    ("8", "26"): "api_publica_tjsp",
    ("8", "27"): "api_publica_tjto",

    # Justiça do Trabalho
    ("5", "01"): "api_publica_trt1",
    ("5", "02"): "api_publica_trt2",
    ("5", "03"): "api_publica_trt3",
    ("5", "04"): "api_publica_trt4",
    ("5", "05"): "api_publica_trt5",
    ("5", "06"): "api_publica_trt6",
    ("5", "07"): "api_publica_trt7",
    ("5", "08"): "api_publica_trt8",
    ("5", "09"): "api_publica_trt9",
    ("5", "10"): "api_publica_trt10",
    ("5", "11"): "api_publica_trt11",
    ("5", "12"): "api_publica_trt12",
    ("5", "13"): "api_publica_trt13",
    ("5", "14"): "api_publica_trt14",
    ("5", "15"): "api_publica_trt15",
    ("5", "16"): "api_publica_trt16",
    ("5", "17"): "api_publica_trt17",
    ("5", "18"): "api_publica_trt18",
    ("5", "19"): "api_publica_trt19",
    ("5", "20"): "api_publica_trt20",
    ("5", "21"): "api_publica_trt21",
    ("5", "22"): "api_publica_trt22",
    ("5", "23"): "api_publica_trt23",
    ("5", "24"): "api_publica_trt24",

    # Justiça Eleitoral: a wiki publica um alias único para os TREs.
    **{("6", f"{codigo:02d}"): "api_publica_tre" for codigo in range(1, 28)},

    # Justiça Militar Estadual
    ("9", "13"): "api_publica_tjmmg",
    ("9", "21"): "api_publica_tjmrs",
    ("9", "26"): "api_publica_tjmsp",
}
