"""T058 — linhas de progresso em português (research R34; contracts/sse-format.md, seção "Fase 7"), puras."""

from __future__ import annotations

import pytest

from axon_ai.http.domain.progress_text import progress_line, queue_line

pytestmark = pytest.mark.us6


@pytest.mark.parametrize(
    ("stage", "detail", "line"),
    [
        ("prepare_context", None, "Preparando o contexto da pergunta…"),
        ("load_capabilities", None, "Carregando as ferramentas…"),
        ("controller", "iteração 2", "Decidindo o próximo passo (iteração 2)…"),
        ("execute_tool", "scouting.search_docs", "Usando a ferramenta scouting.search_docs…"),
        ("retrieve", "1 tool(s) de recuperação", "Consultando os documentos…"),
        ("rerank", "20 candidato(s)", "Ordenando os trechos encontrados…"),
        ("gate", "5 trecho(s)", "Conferindo se os trechos cobrem a pergunta…"),
        ("generate", None, "Escrevendo a resposta…"),
        ("validate_answer", None, "Conferindo a resposta…"),
    ],
)
def test_estagios_publicados_pela_005(stage: str, detail: str | None, line: str) -> None:
    assert progress_line(stage, detail) == line


def test_estagio_desconhecido_cai_na_linha_generica() -> None:
    assert progress_line("novo", None) == "Etapa novo…"
    assert progress_line("novo", "com detalhe") == "Etapa novo…"


@pytest.mark.parametrize("stage", ["controller", "execute_tool"])
def test_estagio_com_detalhe_sem_detalhe_nao_quebra(stage: str) -> None:
    line = progress_line(stage, None)
    assert line.endswith("…") and "{detail}" not in line and "()" not in line


def test_linha_da_fila() -> None:
    assert queue_line(2) == "Aguardando uma vaga (posição 2 na fila)…"
