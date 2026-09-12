"""Cliente da API pública Comunica, usada para comunicações do DJEN."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

import requests


COMUNICA_URL = "https://comunicaapi.pje.jus.br/api/v1/comunicacao"
REQUEST_TIMEOUT_SECONDS = 20
# A API responde 500 para itensPorPagina muito alto (confirmado experimentalmente
# que 1000 funciona e 5000 já falha), então paginamos em blocos de 1000.
ITENS_POR_PAGINA_MAXIMO = 1000
PAGINAS_MAXIMAS = 20  # trava de segurança: no máximo 20 000 itens por consulta


class ComunicaError(RuntimeError):
    """Erro de comunicação ou resposta inválida da API Comunica."""


class ComunicaClient:
    """Consulta comunicações públicas por processo, OAB/UF e período."""

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        url: str = COMUNICA_URL,
    ):
        self.session = session or requests.Session()
        self.url = url

    def buscar(
        self,
        *,
        numero_processo: Optional[str] = None,
        numero_oab: Optional[str] = None,
        uf_oab: Optional[str] = None,
        nome_parte: Optional[str] = None,
        sigla_tribunal: Optional[str] = None,
        data_inicio: Optional[str | date] = None,
        data_fim: Optional[str | date] = None,
        pagina: Optional[int] = None,
        itens_por_pagina: Optional[int] = None,
    ) -> dict[str, Any]:
        """Consulta a API e retorna a resposta bruta com seus itens (uma página).

        Datas devem estar no formato ISO ``YYYY-MM-DD``. A API é pública e não
        requer header de autenticação. Por padrão a API devolve no máximo 100
        itens por página — use `pagina`/`itens_por_pagina` para outras páginas,
        ou `buscar_todos` para trazer o total completo automaticamente.
        """
        if numero_oab and not uf_oab:
            raise ComunicaError("uf_oab é obrigatória quando numero_oab é informado")
        if uf_oab and not numero_oab:
            raise ComunicaError("numero_oab é obrigatório quando uf_oab é informado")
        if not any((numero_processo, numero_oab, nome_parte, sigla_tribunal, data_inicio, data_fim)):
            raise ComunicaError(
                "Informe numero_processo, numero_oab, nome_parte, sigla_tribunal ou uma janela de datas para consultar"
            )

        params: dict[str, Any] = {}
        if numero_processo:
            params["numeroProcesso"] = self._normalizar_processo(numero_processo)
        if numero_oab:
            params["numeroOab"] = numero_oab.strip()
            params["ufOab"] = uf_oab.strip().upper()
        if nome_parte:
            params["nomeParte"] = nome_parte.strip()
        if sigla_tribunal:
            params["siglaTribunal"] = sigla_tribunal.strip().upper()
        if data_inicio:
            params["dataDisponibilizacaoInicio"] = self._formatar_data(data_inicio)
        if data_fim:
            params["dataDisponibilizacaoFim"] = self._formatar_data(data_fim)
        if pagina:
            params["pagina"] = pagina
        if itens_por_pagina:
            params["itensPorPagina"] = itens_por_pagina
        try:
            resposta = self.session.get(
                self.url,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise ComunicaError(f"Falha de conexão com a API Comunica: {exc}") from exc

        if resposta.status_code != 200:
            raise ComunicaError(
                f"API Comunica retornou {resposta.status_code}: {resposta.text[:500]}"
            )

        try:
            dados = resposta.json()
        except ValueError as exc:
            raise ComunicaError("API Comunica retornou conteúdo que não é JSON") from exc

        if not isinstance(dados, dict) or not isinstance(dados.get("items", []), list):
            raise ComunicaError("Resposta da API Comunica não possui o formato esperado")
        return dados

    def buscar_todos(self, **kwargs: Any) -> dict[str, Any]:
        """Como `buscar`, mas percorre todas as páginas até reunir `count` itens.

        A API limita cada página a no máximo `ITENS_POR_PAGINA_MAXIMO` itens
        (valores maiores retornam erro 500), então resultados com mais itens
        que isso exigem múltiplas chamadas. Uma trava de segurança
        (`PAGINAS_MAXIMAS`) evita loops longos demais em buscas muito amplas.
        """
        kwargs.pop("pagina", None)
        kwargs["itens_por_pagina"] = ITENS_POR_PAGINA_MAXIMO

        primeira_pagina = self.buscar(pagina=1, **kwargs)
        itens = list(primeira_pagina.get("items", []))
        total = primeira_pagina.get("count") or 0

        pagina_atual = 1
        while len(itens) < total and pagina_atual < PAGINAS_MAXIMAS:
            pagina_atual += 1
            resposta = self.buscar(pagina=pagina_atual, **kwargs)
            novos_itens = resposta.get("items", [])
            if not novos_itens:
                break
            itens.extend(novos_itens)

        combinado = dict(primeira_pagina)
        combinado["items"] = itens
        return combinado

    @staticmethod
    def _normalizar_processo(numero_processo: str) -> str:
        numero = "".join(ch for ch in numero_processo if ch.isdigit())
        if len(numero) != 20:
            raise ComunicaError(
                "numero_processo deve conter os 20 dígitos do padrão CNJ"
            )
        return numero

    @staticmethod
    def _formatar_data(valor: str | date) -> str:
        if isinstance(valor, date):
            return valor.isoformat()
        try:
            return date.fromisoformat(valor).isoformat()
        except ValueError as exc:
            raise ComunicaError(
                f"Data inválida {valor!r}; use o formato YYYY-MM-DD"
            ) from exc
