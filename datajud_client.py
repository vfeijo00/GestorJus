"""
GestorJus - Parser de número CNJ e cliente da API pública do DataJud
======================================================================

Contém apenas o que o app Streamlit (`streamlit_app.py`) usa:
1. `NumeroProcessoCNJ`: decompõe um número de processo no padrão CNJ
   (Resolução CNJ 65/2008) e resolve o alias correspondente no DataJud.
2. `DataJudClient`: consulta a API pública do DataJud (CNJ) e extrai o
   histórico de movimentações de um processo.

Autenticação do DataJud: header "Authorization: APIKey <chave>", chave
pública publicada pelo próprio CNJ e sujeita a alteração periódica. Deve
ser definida em DATAJUD_API_KEY ou salva em `datajud_api_key.txt`.
A chave pública vigente fica em:
https://datajud-wiki.cnj.jus.br/api-publica/acesso/
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import requests

from datajud_aliases import ALIAS_DATAJUD

DATAJUD_BASE_URL = "https://api-publica.datajud.cnj.jus.br"
REQUEST_TIMEOUT_SECONDS = 20
DATAJUD_KEY_FILE = Path(
    os.environ.get(
        "DATAJUD_KEY_FILE",
        Path(__file__).with_name("datajud_api_key.txt"),
    )
)


# ---------------------------------------------------------------------------
# 1. Utilitário: número de processo CNJ -> endpoint DataJud
# ---------------------------------------------------------------------------
#
# O número unificado de processo (Resolução CNJ 65/2008) segue o padrão:
#   NNNNNNN-DD.AAAA.J.TR.OOOO
# onde:
#   J  = segmento do Poder Judiciário (1 dígito)
#   TR = tribunal dentro daquele segmento (2 dígitos)
#
# Isso permite descobrir automaticamente qual endpoint do DataJud consultar,
# sem precisar perguntar ao usuário ou manter um cadastro manual por processo.
#
SEGMENTO_NOMES = {
    "1": "Supremo Tribunal Federal",
    "2": "Conselho Nacional de Justiça",
    "3": "Superior Tribunal de Justiça",
    "4": "Justiça Federal",
    "5": "Justiça do Trabalho",
    "6": "Justiça Eleitoral",
    "7": "Justiça Militar da União",
    "8": "Justiça dos Estados e do Distrito Federal",
    "9": "Justiça Militar Estadual",
}


class NumeroProcessoInvalido(ValueError):
    pass


@dataclass(frozen=True)
class NumeroProcessoCNJ:
    """Representa e decompõe um número de processo no padrão CNJ."""

    bruto: str
    sequencial: str
    digito_verificador: str
    ano: str
    segmento: str
    tribunal: str
    origem: str

    _REGEX = re.compile(
        r"^(\d{7})-?(\d{2})\.?(\d{4})\.?(\d)\.?(\d{2})\.?(\d{4})$"
    )

    @classmethod
    def parse(cls, numero: str) -> "NumeroProcessoCNJ":
        limpo = numero.strip()
        m = cls._REGEX.match(limpo)
        if not m:
            raise NumeroProcessoInvalido(
                f"Número de processo fora do padrão CNJ (NNNNNNN-DD.AAAA.J.TR.OOOO): {numero!r}"
            )
        seq, dv, ano, segmento, tribunal, origem = m.groups()
        return cls(
            bruto=limpo,
            sequencial=seq,
            digito_verificador=dv,
            ano=ano,
            segmento=segmento,
            tribunal=tribunal,
            origem=origem,
        )

    @property
    def segmento_nome(self) -> str:
        return SEGMENTO_NOMES.get(self.segmento, f"Segmento desconhecido ({self.segmento})")

    def resolver_alias_datajud(self) -> Optional[str]:
        """Tenta resolver o alias do DataJud a partir de segmento+tribunal.

        Retorna None se a combinação ainda não está mapeada em ALIAS_DATAJUD
        — nesse caso, o chamador deve tratar isso como "precisa completar o
        mapa", não como "processo inválido".
        """
        return ALIAS_DATAJUD.get((self.segmento, self.tribunal))


# ---------------------------------------------------------------------------
# 2. Cliente da API pública do DataJud (enriquecimento)
# ---------------------------------------------------------------------------

class DataJudError(RuntimeError):
    pass


class DataJudConfigError(DataJudError):
    """Erro de configuração (chave ausente, tribunal sem alias mapeado) — não tem relação com rede
    ou com a localização geográfica de onde a requisição parte, diferente das demais DataJudError."""


class DataJudClient:
    """Cliente para a API Pública do DataJud (CNJ).

    Documentação oficial: https://datajud-wiki.cnj.jus.br/api-publica/
    Autenticação: header "Authorization: APIKey <chave>", chave pública
    publicada pelo próprio CNJ e sujeita a alteração periódica.
    """

    def __init__(self, api_key: Optional[str] = None, session: Optional[requests.Session] = None):
        self.api_key = api_key or os.environ.get("DATAJUD_API_KEY") or self._read_key_file()
        if not self.api_key:
            raise DataJudConfigError(
                "Chave do DataJud não encontrada. Defina DATAJUD_API_KEY ou salve a "
                f"chave pública vigente em {DATAJUD_KEY_FILE}."
            )
        self.session = session or requests.Session()

    @staticmethod
    def _read_key_file() -> Optional[str]:
        try:
            chave = DATAJUD_KEY_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        return chave or None

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"APIKey {self.api_key}",
            "Content-Type": "application/json",
        }

    def buscar_por_numero_processo(self, numero: NumeroProcessoCNJ) -> dict[str, Any]:
        alias = numero.resolver_alias_datajud()
        if not alias:
            raise DataJudConfigError(
                f"Não há alias de DataJud mapeado para segmento={numero.segmento} "
                f"tribunal={numero.tribunal}. Complete ALIAS_DATAJUD a partir da "
                f"wiki oficial antes de consultar esse tribunal."
            )

        url = f"{DATAJUD_BASE_URL}/{alias}/_search"
        # Consulta Elasticsearch "match" pelo número de processo, conforme o
        # tutorial oficial do DataJud.
        body = {"query": {"match": {"numeroProcesso": numero.sequencial + numero.digito_verificador
                                     + numero.ano + numero.segmento + numero.tribunal + numero.origem}}}

        try:
            resp = self.session.post(
                url, headers=self._headers(), data=json.dumps(body), timeout=REQUEST_TIMEOUT_SECONDS
            )
        except requests.RequestException as exc:
            raise DataJudError(f"Falha de conexão com o DataJud para {numero.bruto}: {exc}") from exc
        if resp.status_code != 200:
            raise DataJudError(
                f"DataJud retornou {resp.status_code} para {numero.bruto}: {resp.text[:300]}"
            )
        return resp.json()

    @staticmethod
    def extrair_movimentacoes(resposta_datajud: dict[str, Any]) -> list[dict[str, Any]]:
        """Extrai a lista de movimentos de uma resposta bruta do DataJud.

        A resposta segue o formato de busca do Elasticsearch (hits.hits[]._source).
        """
        hits = resposta_datajud.get("hits", {}).get("hits", [])
        movimentos: list[dict[str, Any]] = []
        for hit in hits:
            source = hit.get("_source", {})
            for mov in source.get("movimentos", []) or []:
                movimentos.append(
                    {
                        "numero_processo": source.get("numeroProcesso"),
                        "data_hora": mov.get("dataHora"),
                        "nome": (mov.get("nome") or (mov.get("codigo") and str(mov.get("codigo")))),
                        "complementos": mov.get("complementosTabelados"),
                        "bruto": mov,
                    }
                )
        return movimentos
