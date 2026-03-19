#!/usr/bin/env python3
import json, hashlib, logging, time
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
    },
    {
        "nome": "Min. do Trabalho e Emprego",
        "sigla": "MTE",
        "url": "https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/noticias",
        "base_url": "https://www.gov.br",
    },
    {
        "nome": "eSocial",
        "sigla": "ES",
        "url": "https://www.gov.br/esocial/pt-br/noticias",
        "base_url": "https://www.gov.br",
    },
    {
        "nome": "TST",
        "sigla": "TST",
        "url": "https://www.tst.jus.br/web/guest/noticias",
        "base_url": "https://www.tst.jus.br",
    },
    {
        "nome": "Portal eSocial",
        "sigla": "PES",
        "url": "https://esocial.fazenda.gov.br/",
        "base_url": "https://esocial.fazenda.gov.br",
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def calcular_relevancia(texto):
    t = texto.lower()
    if any(p in t for p in PALAVRAS_ALTA):
        return "Alta"
    if any(p in t for p in PALAVRAS_MEDIA):
        return "Média"
    return "Baixa"


def gerar_id(titulo, fonte):
    return hashlib.md5(f"{fonte}{titulo}".encode()).hexdigest()[:12]


def carregar_existentes():
    if DATA_FILE.exists():
        with open(DATA_FILE, encoding="utf-8") as f:
            items = json.load(f).get("atualizacoes", [])
            return {i["id"]: i for i in items}
    return {}


def salvar(atualizacoes):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ultima_atualizacao": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "total": len(atualizacoes),
        "atualizacoes": sorted(atualizacoes, key=lambda x: x["data_iso"], reverse=True),
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    log.info(f"Salvo: {len(atualizacoes)} itens")


def buscar_resumo_na_pagina(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for seletor in [
            ".field--name-body p",
            ".documentDescription",
            ".content-core p",
            "article p",
            "main p",
        ]:
            el = soup.select_one(seletor)
            if el:
                texto = el.get_text(strip=True)
                if len(texto) > 40:
                    return texto[:300] + ("..." if len(texto) > 300 else "")
        for p in soup.find_all("p"):
            texto = p.get_text(strip=True)
            if len(texto) > 60:
                return texto[:300] + ("..." if len(texto) > 300 else "")
    except Exception as e:
        log.debug(f"Resumo não obtido de {url}: {e}")
    return ""


def coletar_fonte(fonte):
    log.info(f"Coletando: {fonte['nome']} ...")
    try:
        r = requests.get(fonte["url"], headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        log.warning(f"  Erro ao acessar {fonte['nome']}: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    itens = []
    vistos = set()

    # MÉTODO 1 — data-portal-url (atributo específico do gov.br com URL exata)
    for el in soup.find_all(attrs={"data-portal-url": True}):
        url = el.get("data-portal-url", "").strip()
        if not url or url in vistos or url == fonte["url"]:
            continue

        # Título: busca h1/h2/h3 dentro do elemento ou usa texto do link
        titulo_el = el.select_one("h1, h2, h3, a")
        titulo = titulo_el.get_text(strip=True) if titulo_el else el.get_text(strip=True)[:120]

        if len(titulo) > 15:
            vistos.add(url)
            itens.append({"titulo": titulo, "url": url, "resumo": "", "data_str": ""})

    log.info(f"  Método data-portal-url: {len(itens)} itens")

    # MÉTODO 2 — links <a href> com padrão de URL de notícia
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        titulo = a.get_text(strip=True)

        if href.startswith("/"):
            href = fonte["base_url"].rstrip("/") + href
        elif not href.startswith("http"):
            continue

        if (len(titulo) > 20
                and href not in vistos
                and href != fonte["url"]
                and fonte["base_url"] in href
                and any(p in href for p in [
                    "/noticias/20", "/noticia/20",
                    "/assuntos/noticias/20",
                    "noticias/2025", "noticias/2026",
                ])):
            vistos.add(href)
            pai = a.find_parent(["article", "li", "div"])
            resumo = ""
            if pai:
                desc = pai.select_one(".description, .tileBody, p")
                if desc:
                    t = desc.get_text(strip=True)
                    if len(t) > 40 and t != titulo:
                        resumo = t[:300]
            itens.append({"titulo": titulo, "url": href, "resumo": resumo, "data_str": ""})

    log.info(f"  Total após métodos 1+2: {len(itens)} itens")
    return itens[:15]


def filtrar_e_enriquecer(itens, fonte, existentes):
    novos = []
    for item in itens:
        relevancia = calcular_relevancia(item["titulo"])
        if relevancia == "Baixa":
            continue

        uid = gerar_id(item["titulo"], fonte["nome"])
        if uid in existentes:
            continue

        resumo = item.get("resumo", "")
        if not resumo and relevancia == "Alta":
            log.info(f"  Buscando resumo: {item['titulo'][:50]}...")
            resumo = buscar_resumo_na_pagina(item["url"])
            time.sleep(1)

        novos.append({
            "id": uid,
            "fonte": fonte["nome"],
            "sigla": fonte["sigla"],
            "titulo": item["titulo"],
            "resumo": resumo,
            "url": item["url"],
            "data_str": item.get("data_str") or datetime.now().strftime("%d/%m/%Y"),
            "data_iso": datetime.now().strftime("%Y-%m-%d"),
            "relevancia": relevancia,
            "lida": False,
            "analise_ia": None,
        })

    log.info(f"  {len(novos)} itens NOVOS")
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

    salvar(list(existentes.values()))
    return todos_novos


if __name__ == "__main__":
    novos = coletar()
    log.info(f"Concluído. {len(novos)} novos itens coletados.")
