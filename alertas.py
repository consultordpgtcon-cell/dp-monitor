#!/usr/bin/env python3
"""
Alertas — envia e-mail diário com resumo das novidades
"""

import os, json, smtplib, logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

log = logging.getLogger(__name__)
DATA_FILE = Path("data/atualizacoes.json")


def gerar_html(novos: list, url_painel: str) -> str:
    hoje = datetime.now().strftime("%d/%m/%Y")
    altas = [n for n in novos if n["relevancia"] == "Alta"]
    medias = [n for n in novos if n["relevancia"] == "Média"]

    def card(item):
        cor = {"Alta": "#DC2626", "Média": "#D97706", "Baixa": "#6B7280"}.get(item["relevancia"], "#6B7280")
        analise_html = ""
        if item.get("analise_ia"):
            a = item["analise_ia"]
            analise_html = f"""
            <div style="background:#F0FDF4;border-left:3px solid #16A34A;padding:10px 14px;margin-top:10px;border-radius:0 6px 6px 0;">
              <div style="font-size:11px;font-weight:600;color:#15803D;margin-bottom:6px;text-transform:uppercase;letter-spacing:.04em">Análise IA</div>
              <div style="font-size:13px;color:#166534;line-height:1.5">
                <strong>Impacto:</strong> {a.get('impacto_dp','—')}<br>
                <strong>Ação:</strong> {a.get('acao_necessaria','—')}<br>
                <strong>Prazo:</strong> {a.get('prazo','Não especificado')}
              </div>
            </div>"""
        return f"""
        <div style="background:#fff;border:1px solid #E5E7EB;border-radius:8px;padding:16px;margin-bottom:12px;">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;">
            <span style="font-size:12px;font-weight:600;color:{cor};background:{cor}18;padding:2px 10px;border-radius:99px;">{item['relevancia']}</span>
            <span style="font-size:11px;color:#9CA3AF;">{item['fonte']} · {item['data_str']}</span>
          </div>
          <a href="{item['url']}" style="font-size:14px;font-weight:600;color:#1D4ED8;text-decoration:none;line-height:1.4;display:block;margin-bottom:4px;">{item['titulo']}</a>
          {analise_html}
        </div>"""

    secao_alta = ""
    if altas:
        secao_alta = f"""
        <div style="margin-bottom:24px;">
          <h3 style="font-size:15px;color:#DC2626;margin:0 0 12px;padding-bottom:8px;border-bottom:2px solid #FEE2E2;">
            Relevância Alta — {len(altas)} atualização(ões)
          </h3>
          {"".join(card(n) for n in altas)}
        </div>"""

    secao_media = ""
    if medias:
        secao_media = f"""
        <div style="margin-bottom:24px;">
          <h3 style="font-size:15px;color:#D97706;margin:0 0 12px;padding-bottom:8px;border-bottom:2px solid #FEF3C7;">
            Relevância Média — {len(medias)} atualização(ões)
          </h3>
          {"".join(card(n) for n in medias)}
        </div>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#F9FAFB;padding:24px;margin:0;">
  <div style="max-width:640px;margin:0 auto;">
    <div style="background:#1E3A5F;border-radius:10px 10px 0 0;padding:20px 24px;">
      <h1 style="color:#fff;font-size:18px;margin:0;">Monitor Legislativo — DP</h1>
      <p style="color:#93C5FD;font-size:13px;margin:4px 0 0;">{hoje} · {len(novos)} nova(s) atualização(ões)</p>
    </div>
    <div style="background:#fff;border:1px solid #E5E7EB;border-top:none;border-radius:0 0 10px 10px;padding:24px;">
      {secao_alta}
      {secao_media}
      <div style="text-align:center;margin-top:24px;padding-top:20px;border-top:1px solid #F3F4F6;">
        <a href="{url_painel}" style="background:#1E3A5F;color:#fff;padding:12px 28px;border-radius:6px;text-decoration:none;font-size:14px;font-weight:600;">
          Ver painel completo
        </a>
        <p style="font-size:11px;color:#9CA3AF;margin:16px 0 0;">
          Monitor Legislativo DP · Gerado automaticamente via GitHub Actions
        </p>
      </div>
    </div>
  </div>
</body>
</html>"""


def enviar_email(novos: list, url_painel: str):
    remetente = os.getenv("EMAIL_REMETENTE")
    senha = os.getenv("EMAIL_SENHA_APP")
    destinatarios_str = os.getenv("EMAIL_DESTINATARIOS", "")

    if not all([remetente, senha, destinatarios_str]):
        log.warning("Credenciais de e-mail não configuradas — pulando envio")
        return

    destinatarios = [d.strip() for d in destinatarios_str.split(",") if d.strip()]
    hoje = datetime.now().strftime("%d/%m/%Y")

    altas = sum(1 for n in novos if n["relevancia"] == "Alta")
    assunto = f"[DP Monitor] {hoje} — {len(novos)} atualização(ões)"
    if altas:
        assunto += f" · {altas} de alta relevância"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"] = f"Monitor DP <{remetente}>"
    msg["To"] = ", ".join(destinatarios)

    html = gerar_html(novos, url_painel)
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(remetente, senha)
            s.sendmail(remetente, destinatarios, msg.as_string())
        log.info(f"E-mail enviado para {destinatarios}")
    except Exception as e:
        log.error(f"Erro ao enviar e-mail: {e}")
        raise


if __name__ == "__main__":
    # Teste: envia com os últimos 5 itens
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            dados = json.load(f)
        enviar_email(dados["atualizacoes"][:5], "https://seu-usuario.github.io/dp-monitor")
