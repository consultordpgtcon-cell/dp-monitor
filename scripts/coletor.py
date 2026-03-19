#!/usr/bin/env python3
"""
Monitor Legislativo — Coletor de Atualizações
Coleta notícias da Receita Federal, MTE, eSocial, TST e Portal eSocial
"""

import os, json, hashlib, logging, time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DATA_FILE = Path("data/atualizacoes.json")

PALAVRAS_ALTA = [
    "folha de pagamento", "inss", "fgts", "esocial", "dirf", "dctf",
    "salário mínimo", "rescisão", "férias", "13 salário", "clt",
    "instrução normativa", "portaria mte", "admissão", "demissão",
    "holerite", "pis", "pasep", "rais", "caged", "aviso prévio",
    "horas extras", "adicional", "insalubridade", "periculosidade",
]
PALAVRAS_MEDIA = [
    "trabalhista", "empregado", "empregador", "contrato de trabalho",
    "benefício", "afastamento", "licença", "nr-", "norma regulamentadora",
    "jornada", "hora extra", "teletrabalho", "home office", "súmula",
    "jurisprudência", "acordo coletivo", "convenção coletiva",
]

FONTES = [
    {
        "nome": "Receita Federal",
        "sigla": "RF",
        "url": "https://www.gov.br/receitafederal/pt-br/assuntos/noticias",
        "base_url": "https://www.gov.br",
        "seletor_itens": "article, .tileItem",
        "seletor_resumo": ".description, .tileBody p, article p",
    },
    {
        "nome": "Min. do Trabalho e Emprego",
        "sigla": "MTE",
        "url": "https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/noticias",
        "base_url": "https://www.gov.br",
        "seletor_itens": "article, .tileItem",
        "seletor_resumo": ".description, .tileBody p, article p",
    },
    {
        "nome": "eSocial",
        "sigla": "ES",
        "url": "https://www.gov.br/esocial/pt-br/noticias",
        "base_url": "https://www.gov.br",
        "seletor_itens": "article, .tileItem",
        "seletor_resumo": ".description, .tileBody p, article p",
    },
    {
        "nome": "TST",
        "sigla": "TST",
        "url": "https://www.tst.jus.br/web/guest/noticias",
        "base_url": "https://www.tst.jus.br",
        "seletor_itens": ".portlet-body article, .noticias-item, li.item",
        "seletor_resumo": ".portlet-body p, .resumo, .summary",
    },
    {
        "nome": "Portal eSocial",
        "sigla": "PES",
        "url": "https://esocial.fazenda.gov.br/",
        "base_url": "https://esocial.fazenda.gov.br",
        "seletor_itens": ".noticia, article, .item-noticia",
        "seletor_resumo": ".resumo, .descricao, p",
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


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
        "atualizacoes": sorted(
            atualizacoes, key=lambda x: x["data_iso"], reverse=True
        ),
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    log.info(f"Salvo: {len(atualizacoes)} itens em {DATA_FILE}")


def buscar_resumo_na_pagina(url: str, fonte: dict) -> str:
    """Acessa a página da notícia e extrai o primeiro parágrafo como resumo."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # Tenta seletores específicos primeiro
        for seletor in [
            ".field--name-body p",
            ".noticia-texto p",
            ".content-core p",
            ".documentDescription",
            ".description",
            "article p",
            ".texto p",
            "main p",
        ]:
            el = soup.select_one(seletor)
            if el:
                texto = el.get_text(strip=True)
                if len(texto) > 40:
                    # Limita a 300 caracteres para o resumo
                    return texto[:300] + ("..." if len(texto) > 300 else "")

        # Fallback: primeiro parágrafo com conteúdo relevante
        for p in soup.find_all("p"):
            texto = p.get_text(strip=True)
            if len(texto) > 60:
                return texto[:300] + ("..." if len(texto) > 300 else "")

    except Exception as e:
        log.debug(f"Não foi possível buscar resumo em {url}: {e}")

    return ""


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

    for el in soup.select("article, .item, .noticia, li.item, .tileItem")[:15]:
        link = el.select_one("a[href]")
        if not link:
            continue
        titulo = link.get_text(strip=True)
        if len(titulo) < 15:
            continue

        href = link.get("href", "")
        if href.startswith("/"):
            href = fonte["base_url"] + href
        if not href.startswith("http"):
            continue

        # Tenta pegar resumo direto na listagem
        resumo = ""
        for sel in [".description", ".tileBody p", ".resumo", "p"]:
            rel = el.select_one(sel)
            if rel:
                texto = rel.get_text(strip=True)
                if len(texto) > 40 and texto != titulo:
                    resumo = texto[:300]
                    break

        data_el = el.select_one(
            "span.documentPublicationDate, time, .data, .date, .published"
        )
        data_str = data_el.get_text(strip=True) if data_el else ""

        itens.append({
            "titulo": titulo,
            "url": href,
            "data_str": data_str,
            "resumo_listagem": resumo,
        })

    log.info(f"  {len(itens)} itens encontrados")
    return itens


def filtrar_e_enriquecer(itens: list, fonte: dict, existentes: dict) -> list:
    novos = []
    for item in itens:
        relevancia = calcular_relevancia(item["titulo"])
        if relevancia == "Baixa":
            continue

        uid = gerar_id(item["titulo"], fonte["nome"])
        if uid in existentes:
            continue

        # Busca resumo na página da notícia se não veio na listagem
        resumo = item.get("resumo_listagem", "")
        if not resumo and relevancia == "Alta":
            log.info(f"  Buscando resumo: {item['titulo'][:50]}...")
            resumo = buscar_resumo_na_pagina(item["url"], fonte)
            time.sleep(1)  # gentileza com o servidor

        novos.append({
            "id": uid,
            "fonte": fonte["nome"],
            "sigla": fonte["sigla"],
            "titulo": item["titulo"],
            "resumo": resumo,
            "url": item["url"],
            "data_str": item["data_str"] or datetime.now().strftime("%d/%m/%Y"),
            "data_iso": datetime.now().strftime("%Y-%m-%d"),
            "relevancia": relevancia,
            "lida": False,
            "analise_ia": None,
        })

    log.info(f"  {len(novos)} itens NOVOS após filtro")
    return novos


def coletar():
    existentes = carregar_existentes()
    log.info(f"Base atual: {len(existentes)} itens")

    todos_novos = []
    for fonte in FONTES:
        brutos = coletar_fonte(fonte)
        novos = filtrar_e_enriquecer(brutos, fonte, existentes)
        todos_novos.extend(novos)
        existentes.update({n["id"]: n for n in novos})
        time.sleep(2)

    todos = list(existentes.values())
    salvar(todos)
    return todos_novos


if __name__ == "__main__":
    novos = coletar()
    log.info(f"Concluído. {len(novos)} novos itens coletados.")
