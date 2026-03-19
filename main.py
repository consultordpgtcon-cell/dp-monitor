#!/usr/bin/env python3
"""
main.py — Orquestrador principal
Chamado pelo GitHub Actions toda manhã
"""

import logging, os, sys, json
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("data/log_execucao.txt", mode="a", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


def main():
    log.info("=" * 60)
    log.info("MONITOR LEGISLATIVO DP — INÍCIO DA EXECUÇÃO")
    log.info("=" * 60)

    # 1. Coleta
    log.info("ETAPA 1: Coletando atualizações...")
    from scripts.coletor import coletar
    novos = coletar()
    log.info(f"  → {len(novos)} novos itens coletados")

    if not novos:
        log.info("Nenhuma novidade. Encerrando sem enviar alertas.")
        return

    # 2. Análise IA
    log.info("ETAPA 2: Analisando com IA...")
    ids_novos = [n["id"] for n in novos]
    from scripts.analisador import analisar_novos
    analisar_novos(ids_novos)

    # 3. Alertas por e-mail
    log.info("ETAPA 3: Enviando alertas...")
    usuario_github = os.getenv("GITHUB_REPOSITORY", "usuario/dp-monitor").split("/")[0]
    repo_github = os.getenv("GITHUB_REPOSITORY", "usuario/dp-monitor").split("/")[-1]
    url_painel = f"https://{usuario_github}.github.io/{repo_github}"

    # Recarrega novos com análise já preenchida
    from pathlib import Path
    data_file = Path("data/atualizacoes.json")
    with open(data_file, encoding="utf-8") as f:
        todos = json.load(f)["atualizacoes"]
    novos_completos = [i for i in todos if i["id"] in ids_novos]

    from scripts.alertas import enviar_email
    enviar_email(novos_completos, url_painel)

    log.info("=" * 60)
    log.info(f"EXECUÇÃO CONCLUÍDA — {len(novos)} itens processados")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
