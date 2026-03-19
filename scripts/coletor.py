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
    "salario minimo", "rescisao", "ferias", "13 salario", "clt",
    "instrucao normativa", "portaria", "admissao", "demissao",
    "holerite", "pis", "pasep", "rais", "caged", "aviso previo",
    "horas extras", "adicional", "insalubridade", "periculosidade",
    "salário mínimo", "rescisão", "férias", "instrução normativa",
    "admissão", "demissão", "aviso prévio",
]
PALAVRAS_MEDIA = [
    "trabalhista", "empregado", "empregador", "contrato de trabalho",
    "beneficio", "afastamento", "licenca", "nr-", "norma regulamentadora",
    "jornada", "hora extra", "teletrabalho", "home office", "sumula",
    "jurisprudencia", "acordo coletivo", "convencao coletiva",
    "benefício", "licença", "súmula", "jurisprudência", "convenção",
]

# Fontes via RSS — URLs reais garantidas
FONTES_RSS = [
    {
        "nome": "Receita Federal",
        "sigla": "RF",
        "url": "https://www.gov.br/receitafederal/pt-br/assuntos/noticias/ultimas-noticias/RSS",
    },
    {
        "nome": "Min. do Trabalho e Emprego",
        "sigla": "MTE",
        "url": "https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/noticias/RSS",
    },
    {
        "nome": "eSocial",
        "sigla": "ES",
        "url": "https://www.gov.br/esocial/pt-br/noticias/RSS",
    },
]

# Fontes via scraping direto (sem RSS disponível)
FONTES_SCRAPING = [
    {
        "nome": "TST",
        "sigla": "TST",
        "url": "https://www.tst.jus.br/web/guest/noticias",
        "base_url": "https://www.tst.jus.br",
    },
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
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


def coletar_rss(fonte):
    """Coleta via RSS — URLs 100% reais e confiáveis."""
    log.info(f"Coletando RSS: {fonte['nome']} ...")
    try:
        r = requests.get(fonte["url"], headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        log.warning(f"  Erro RSS {fonte['nome']}: {e}")
        return []

    soup = BeautifulSoup(r.content, "xml")
    itens = []

    for item in soup.find_all("item")[:20]:
        titulo_el = item.find("title")
        link_el = item.find("link")
        desc_el = item.find("description")
        data_el = item.find("pubDate")

        if not titulo_el or not link_el:
            continue

        titulo = titulo_el.get_text(strip=True)
        url = link_el.get_text(strip=True)
        resumo = ""
        if desc_el:
            desc_text = BeautifulSoup(desc_el.get_text(), "html.parser").get_text(strip=True)
            if len(desc_text) > 20:
                resumo = desc_text[:300]
        data_str = ""
        if data_el:
            data_str = data_el.get_text(strip=True)[:16]

        if url and url.startswith("http") and len(titulo) > 10:
            itens.append({
                "titulo": titulo,
                "url": url,
                "resumo": resumo,
                "data_str": data_str,
            })

    log.info(f"  {len(itens)} itens via RSS")
    return itens


def coletar_scraping(fonte):
    """Coleta via scraping para fontes sem RSS."""
    log.info(f"Coletando scraping: {fonte['nome']} ...")
    try:
        r = requests.get(fonte["url"], headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        log.warning(f"  Erro scraping {fonte['nome']}: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    itens = []
    vistos = set()

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
                and fonte["base_url"] in href):
            vistos.add(href)
            itens.append({
                "titulo": titulo,
                "url": href,
                "resumo": "",
                "data_str": "",
            })

    log.info(f"  {len(itens)} itens via scraping")
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

        novos.append({
            "id": uid,
            "fonte": fonte["nome"],
            "sigla": fonte["sigla"],
            "titulo": item["titulo"],
            "resumo": item.get("resumo", ""),
            "url": item["url"],
            "data_str": item.get("data_str") or datetime.now().strftime("%d/%m/%Y"),
            "data_iso": datetime.now().strftime("%Y-%m-%d"),
            "relevancia": relevancia,
            "lida": False,
            "analise_ia": None,
        })

    log.info(f"  {len(novos)} itens NOVOS para {fonte['nome']}")
    return novos


def coletar():
    existentes = carregar_existentes()
    log.info(f"Base atual: {len(existentes)} itens")
    todos_novos = []

    # RSS — URLs garantidas
    for fonte in FONTES_RSS:
        brutos = coletar_rss(fonte)
        novos = filtrar_e_enriquecer(brutos, fonte, existentes)
        todos_novos.extend(novos)
        existentes.update({n["id"]: n for n in novos})
        time.sleep(1)

    # Scraping — para fontes sem RSS
    for fonte in FONTES_SCRAPING:
        brutos = coletar_scraping(fonte)
        novos = filtrar_e_enriquecer(brutos, fonte, existentes)
        todos_novos.extend(novos)
        existentes.update({n["id"]: n for n in novos})
        time.sleep(2)

    salvar(list(existentes.values()))
    log.info(f"Total novo: {len(todos_novos)} itens")
    return todos_novos


if __name__ == "__main__":
    novos = coletar()
    log.info(f"Concluido. {len(novos)} novos itens.")
