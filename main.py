#!/usr/bin/env python3
import logging, sys, json
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
    log.info("=" * 50)
    log.info("MONITOR LEGISLATIVO DP — INÍCIO")
    log.info("=" * 50)

    log.info("Coletando atualizações...")
    from scripts.coletor import coletar
    novos = coletar()
    log.info(f"  → {len(novos)} novos itens coletados")

    log.info("=" * 50)
    log.info(f"CONCLUÍDO — {len(novos)} itens processados")
    log.info("=" * 50)

if __name__ == "__main__":
    main()
