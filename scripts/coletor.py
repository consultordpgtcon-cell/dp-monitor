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
        "tipo": "govbr",
    },
    {
        "nome": "Min. do Trabalho e Emprego",
        "sigla": "MTE",
        "url": "https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/noticias",
        "base_url": "https://www.gov.br",
        "tipo": "govbr",
    },
    {
        "nome": "eSocial",
        "sigla": "ES",
        "url": "https://www.gov.br/esocial/pt-br/noticias",
        "base_url": "https://www.gov.br",
        "tipo": "govbr",
    },
    {
        "nome": "TST",
        "sigla": "TST",
        "url": "https://www.tst.jus.br/web/guest/noticias",
        "base_url": "https://www.tst.jus.br",
        "tipo": "tst",
    },
    {
        "nome": "Portal eSocial",
        "sigla": "PES",
        "url": "https://esocial.fazenda.gov.br/",
        "base_url": "https://esocial.fazenda.gov.br",
        "tipo": "govbr",
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


def coletar_govbr(soup, base_url, url_listagem):
    """
    Extrai notícias do portal gov.br usando data-base-url
    que contém a URL exata de cada notícia.
    """
    resultados = []
    vistos = set()

    # Método 1: data-base-url no body (URL da notícia atual visível)
    for el in soup.find_all(attrs={"data-base-url": True}):
        url_noticia = el.get("data-base-url", "").strip()
        if not url_noticia or url_noticia == url_listagem:
            continue

        # Busca título dentro do elemento
        titulo_el = el.select_one("h1, h2, h3, .documentFirstHeading")
        titulo = titulo_el.get_text(strip=True) if titulo_el else ""

        if not titulo:
            titulo = el.get_text(strip=True)[:100]

        if len(titulo) > 15 and url_noticia not in vistos:
            vistos.add(url_noticia)
            resultados.append({
                "titulo": titulo,
                "url": url_noticia,
                "resumo": "",
                "data_str": "",
            })

    # Método 2: links diretos com padrão de URL de notícia
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        titulo = a.get_text(strip=True)

        # Normaliza URL
        if href.startswith("/"):
            href = base_url.rstrip("/") + href
        elif not href.startswith("http"):
            continue

        # Filtra: deve ser URL de notícia do mesmo domínio
        if (len(titulo) > 20
                and href not in vistos
                and href != url_listagem
                and base_url in href
                and any(p in href for p in ["/noticias/", "/noticia/", "/assuntos/"])):

            vistos.add(href)

            # Tenta pegar resumo do elemento pai
            pai = a.find_parent(["article", "li", "div"])
            resumo = ""
            if pai:
                desc = pai.select_one(".description, .tileBody, p, .resumo")
                if desc:
                    t = desc.get_text(strip=True)
                    if len(t) > 40 and t != titulo:
                        resumo = t[:300]

            resultados.append({
                "titulo": titulo,
                "url": href,
                "resumo": resumo,
                "data_str": "",
            })

    log.info(f"  Método govbr: {len(resultados)} links encontrados")
    return resultados[:15]


def coletar_tst(soup, base_url, url_listagem):
    """Extrai notícias do TST."""
    resultados = []
    vistos = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        titulo = a.get_text(strip=True)

        if href.startswith("/"):
            href = base_url.rstrip("/") + href
        elif not href.startswith("http"):
            continue

        if (len(titulo) > 20
                and href not in vistos
                and href != url_listagem
                and base_url in href
                and href != url_listagem):

            vistos.add(href)
            resultados.append({
                "titulo": titulo,
                "url": href,
                "resumo": "",
                "data_str": "",
            })

    return resultados[:15]


def coletar_fonte(fonte):
    log.info(f"Coletando: {fonte['nome']} ...")
    try:
        r = requests.get(fonte["url"], headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        log.warning(f"  Erro ao acessar {fonte['nome']}: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")

    if fonte["tipo"] == "tst":
        itens = coletar_tst(soup, fonte["base_url"], fonte["url"])
    else:
        itens = coletar_govbr(soup, fonte["base_url"], fonte["url"])

    log.info(f"  {len(itens)} itens após extração")
    return itens


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
