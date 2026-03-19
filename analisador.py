#!/usr/bin/env python3
"""
Analisador de IA — usa Claude para classificar e resumir atualizações novas
"""

import json, os, logging
from pathlib import Path
import anthropic

log = logging.getLogger(__name__)
DATA_FILE = Path("data/atualizacoes.json")

SYSTEM_PROMPT = """Você é um especialista sênior em Departamento Pessoal e legislação trabalhista brasileira com 20 anos de experiência.

Analise a atualização legislativa fornecida e responda SOMENTE com JSON válido, sem markdown, sem texto adicional.

Formato obrigatório:
{
  "resumo": "resumo em 2 linhas do que mudou",
  "impacto_dp": "impacto prático direto no Departamento Pessoal",
  "acao_necessaria": "o que a equipe de DP deve fazer",
  "prazo": "prazo para adequação, se houver",
  "risco_inacao": "consequência de não agir",
  "processos_afetados": ["lista", "de", "processos", "do", "DP"]
}"""


def analisar_item(titulo: str, url: str, fonte: str) -> dict | None:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        log.warning("ANTHROPIC_API_KEY não definida — pulando análise IA")
        return None

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""Fonte: {fonte}
Título: {titulo}
URL: {url}

Analise esta atualização legislativa e seus impactos no Departamento Pessoal."""

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        texto = msg.content[0].text.strip()
        # Remove blocos markdown se o modelo incluir
        if texto.startswith("```"):
            texto = texto.split("```")[1]
            if texto.startswith("json"):
                texto = texto[4:]
        return json.loads(texto)
    except json.JSONDecodeError as e:
        log.warning(f"IA retornou JSON inválido: {e}")
        return None
    except Exception as e:
        log.warning(f"Erro na API Claude: {e}")
        return None


def analisar_novos(ids_novos: list[str]):
    """Analisa somente os itens com ids_novos que ainda não têm análise."""
    if not DATA_FILE.exists():
        log.warning("Arquivo de dados não encontrado.")
        return

    with open(DATA_FILE, encoding="utf-8") as f:
        dados = json.load(f)

    atualizados = 0
    for item in dados["atualizacoes"]:
        if item["id"] not in ids_novos:
            continue
        if item.get("analise_ia"):
            continue
        if item["relevancia"] == "Baixa":
            continue

        log.info(f"Analisando: {item['titulo'][:60]}...")
        analise = analisar_item(item["titulo"], item["url"], item["fonte"])
        if analise:
            item["analise_ia"] = analise
            atualizados += 1

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

    log.info(f"Análise IA concluída: {atualizados} itens atualizados")


if __name__ == "__main__":
    # Analisa todos os itens sem análise (uso manual)
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            dados = json.load(f)
        ids = [i["id"] for i in dados["atualizacoes"] if not i.get("analise_ia")]
        analisar_novos(ids)
