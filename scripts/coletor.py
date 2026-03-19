#!/usr/bin/env python3
"""
Monitor Legislativo — Coletor de Atualizações
Coleta notícias da Receita Federal, MTE, eSocial e DOU
"""

import os, json, hashlib, logging, time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DATA_FILE = Path("data/atualizacoes.json")

# ---------------------------------------------------------------------------
# Palavras-chave que indicam relevância para o DP
# ---------------------------------------------------------------------------
PALAVRAS_ALTA = [
    "folha de pagamento", "inss", "fgts", "esocial", "dirf", "dctf",
    "salário mínimo", "rescisão", "férias", "13 salário", "clt",
    "instrução normativa", "portaria mte", "portaria mte", "admissão",
    "demissão", "holerite", "pis", "pasep", "rais", "caged",
]
PALAVRAS_MEDIA = [
    "trabalhista", "empregado", "empregador", "contrato de trabalho",
    "benefício", "afastamento", "licença", "nr-", "norma regulamentadora",
    "jornada", "hora extra", "teletrabalho", "home office",
]

FONTES = [
    {
        "nome": "Receita Federal",
        "sigla": "RF",
        "url": "https://www.gov.br/receitafederal/pt-br/assuntos/noticias",
        "seletor_itens": "article.tileItem, div.tileItem",
        "seletor_titulo": "h2 a, h3 a, .tileHeadline a",
        "base_url": "https://www.gov.br",
    },
    {
        "nome": "Min. do Trabalho e Emprego",
        "sigla": "MTE",
        "url": "https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/noticias",
        "seletor_itens": "article.tileItem, div.tileItem",
        "seletor_titulo": "h2 a, h3 a, .tileHeadline a",
        "base_url": "https://www.gov.br",
    },
    {
        "nome": "eSocial",
        "sigla": "ES",
        "url": "https://www.gov.br/esocial/pt-br/noticias",
        "seletor_itens": "article.tileItem, div.tileItem",
        "seletor_titulo": "h2 a, h3 a, .tileHeadline a",
        "base_url": "https://www.gov.br",
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def calcular_relevancia(texto: str) -> str:
    t = texto.lower()
    if any(p in t for p in PALAVRAS_ALTA):
        return "Alta"
    if any(p in t for p in PALAVRAS_MEDIA):
        return "Média"
    return "Baixa"


def gerar_id(titulo: str, fonte: str) -> str:
    return hashlib.md5(f"{fonte}{titulo}".encode()).hexdigest()[:12]


def carregar_existentes() -> dict:
    if DATA_FILE.exists():
        with open(DATA_FILE, encoding="utf-8") as f:
            items = json.load(f).get("atualizacoes", [])
            return {i["id"]: i for i in items}
    return {}


def salvar(atualizacoes: list):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ultima_atualizacao": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "total": len(atualizacoes),
        "atualizacoes": sorted(atualizacoes, key=lambda x: x["data_iso"], reverse=True),
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    log.info(f"Salvo: {len(atualizacoes)} itens em {DATA_FILE}")


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

def coletar_fonte(fonte: dict) -> list:
    log.info(f"Coletando: {fonte['nome']} ...")
    try:
        r = requests.get(fonte["url"], headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        log.warning(f"  Erro ao acessar {fonte['nome']}: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    itens = []

    # Tenta seletores genéricos do portal gov.br
    for el in soup.select("article, .item, .noticia, li.item")[:20]:
        link = el.select_one("a[href]")
        if not link:
            continue
        titulo = link.get_text(strip=True)
        if len(titulo) < 15:
            continue

        href = link.get("href", "")
        if href.startswith("/"):
            href = fonte["base_url"] + href

        data_el = el.select_one("span.documentPublicationDate, time, .data, .date")
        data_str = data_el.get_text(strip=True) if data_el else ""

        itens.append({
            "titulo": titulo,
            "url": href,
            "data_str": data_str,
        })

    log.info(f"  {len(itens)} itens encontrados (antes do filtro)")
    return itens


def filtrar_e_enriquecer(itens: list, fonte: dict, existentes: dict) -> list:
    novos = []
    for item in itens:
        relevancia = calcular_relevancia(item["titulo"])
        if relevancia == "Baixa":
            continue  # descarta irrelevantes

        uid = gerar_id(item["titulo"], fonte["nome"])
        if uid in existentes:
            continue  # já conhecemos

        novos.append({
            "id": uid,
            "fonte": fonte["nome"],
            "sigla": fonte["sigla"],
            "titulo": item["titulo"],
            "url": item["url"],
            "data_str": item["data_str"] or datetime.now().strftime("%d/%m/%Y"),
            "data_iso": datetime.now().strftime("%Y-%m-%d"),
            "relevancia": relevancia,
            "lida": False,
            "analise_ia": None,
        })
    log.info(f"  {len(novos)} itens NOVOS após filtro")
    return novos


# ---------------------------------------------------------------------------
# Entrada principal
# ---------------------------------------------------------------------------

def coletar():
    existentes = carregar_existentes()
    log.info(f"Base atual: {len(existentes)} itens")

    todos_novos = []
    for fonte in FONTES:
        brutos = coletar_fonte(fonte)
        novos = filtrar_e_enriquecer(brutos, fonte, existentes)
        todos_novos.extend(novos)
        existentes.update({n["id"]: n for n in novos})
        time.sleep(2)  # gentileza com os servidores

    # Mantém histórico completo (novos + antigos)
    todos = list(existentes.values())
    salvar(todos)
    return todos_novos


if __name__ == "__main__":
    novos = coletar()
    log.info(f"Concluído. {len(novos)} novos itens coletados.")
