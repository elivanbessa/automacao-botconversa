import os
import sys
import time
import unicodedata
import google.generativeai as genai
from playwright.sync_api import sync_playwright

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
BOT_EMAIL = os.environ.get("BOT_EMAIL")
BOT_SENHA = os.environ.get("BOT_SENHA")

if not GEMINI_KEY or not BOT_EMAIL or not BOT_SENHA:
    print("ERRO: Faltam credenciais nas Secrets (GEMINI_API_KEY, BOT_EMAIL, BOT_SENHA).")
    sys.exit(1)

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def normalizar_texto(texto):
    """Remove acentos e converte para maiúsculas para evitar falhas de comparação."""
    if not texto:
        return ""
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    ).upper()

def analisar_mensagem(texto):
    prompt = f"""
    Você é um triador de mensagens no WhatsApp.
    Analise a mensagem do cliente e responda ESTRITAMENTE no seguinte formato:

    CLASSIFICACAO: <DUVIDA ou NEUTRO ou SAIR>
    SUGESTAO: <Sugestão de resposta curta se for DUVIDA, ou 'N/A' se for NEUTRO/SAIR>

    Regras:
    - DUVIDA: Se pediu preço, catálogo, frete, localização, tamanho ou tirou dúvidas do produto.
    - NEUTRO: Apenas emojis, figurinhas, 'ok', 'obrigado', saudações curtas ou disparos automáticos.
    - SAIR: Pediu para parar de enviar mensagens, xingou ou pediu cancelamento.

    Mensagem do cliente: "{texto}"
    """
    try:
        res = model.generate_content(prompt)
        return res.text
    except Exception as e:
        print(f"Erro na API do Gemini: {e}")
        return "CLASSIFICACAO: NEUTRO\nSUGESTAO: N/A"

def rodar_triagem():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = browser.new_context(viewport={"width": 1366, "height": 768})
        page = context.new_page()

        try:
            print("1. Logando no BotConversa...")
            page.goto("https://app.botconversa.com.br/login", wait_until="networkidle")
            page.fill('input[type="email"]', BOT_EMAIL)
            page.fill('input[type="password"]', BOT_SENHA)
            page.click('button[type="submit"]')
            page.wait_for_timeout(7000)

            print("2. Abrindo a caixa de entrada (Chat)...")
            page.goto("https://app.botconversa.com.br/chat", wait_until="networkidle")
            page.wait_for_timeout(5000)

            # Tenta garantir que está visualizando todas as conversas/não lidas
            try:
                page.click('text="Todas"', timeout=3000)
                page.wait_for_timeout(2000)
            except:
                pass

            conversas = page.locator('.chat-item, .conversation-item, [data-testid="chat-list-item"]').all()
            print(f"Encontradas {len(conversas)} conversas para análise.")

            for index, conversa in enumerate(conversas[:15]):
                conversa.click()
                page.wait_for_timeout(2000)

                msgs = page.locator('.message-in, .received, [data-outgoing="false"]').all()
                if not msgs:
                    continue
                
                texto_cliente = msgs[-1].text_content().strip()
                print(f"\n--- Conversa {index+1} ---")
                print(f"Texto do Cliente: '{texto_cliente}'")

                analise_raw = analisar_mensagem(texto_cliente)
                analise_norm = normalizar_texto(analise_raw)
                print(f"Resultado Gemini (bruto):\n{analise_raw}")

                if "DUVIDA" in analise_norm and "CLASSIFICACAO:" in analise_norm:
                    sugestao = analise_raw.split("SUGESTAO:")[-1].strip() if "SUGESTAO:" in analise_raw else "Verifique o interesse do cliente."
                    print("--> Ação: Dúvida identificada! Processando ações no chat...")

                    # 1. Atribuição de Etiqueta
                    try:
                        print("    [1/3] Tentando aplicar etiqueta...")
                        btn_tag = page.locator('button:has-text("Etiqueta"), .btn-tag, [data-testid="add-tag"], i.fa-tag, svg.feather-tag').first
                        if btn_tag.is_visible(timeout=4000):
                            btn_tag.click()
                            page.wait_for_timeout(1000)
                            
                            input_tag = page.locator('input[placeholder*="Buscar"], input[placeholder*="etiqueta"], input[placeholder*="Tag"]').first
                            input_tag.fill("[Atendimento] Dúvida")
                            page.wait_for_timeout(1500)
                            
                            # Tenta clicar no item da etiqueta na lista suspensa; se falhar, pressiona Enter
                            try:
                                page.locator('.tag-item, .dropdown-item, li:has-text("[Atendimento] Dúvida")').first.click(timeout=2000)
                            except:
                                page.keyboard.press("Enter")
                                
                            page.wait_for_timeout(1000)
                            print("    --> Etiqueta '[Atendimento] Dúvida' processada.")
                        else:
                            print("    --> AVISO: Botão de etiqueta não visível.")
                    except Exception as e_tag:
                        print(f"    --> AVISO ao aplicar tag: {e_tag}")

                    # 2. Inserção de Nota Interna
                    try:
                        print("    [2/3] Tentando adicionar Nota Interna...")
                        btn_nota = page.locator('button:has-text("Nota"), .btn-note, [data-testid="add-note"]').first
                        if btn_nota.is_visible(timeout=4000):
                            btn_nota.click()
                            campo_nota = page.locator('textarea, [contenteditable="true"]').first
                            campo_nota.fill(f"📌 IA Gemini: Dúvida identificada.\n💡 Sugestão: {sugestao}")
                            page.click('button:has-text("Salvar"), button:has-text("Adicionar")')
                            page.wait_for_timeout(1000)
                            print("    --> Nota interna adicionada.")
                        else:
                            print("    --> AVISO: Botão de Nota não visível.")
                    except Exception as e_nota:
                        print(f"    --> AVISO ao salvar nota: {e_nota}")

                    # 3. Mover para Atendimento Humano
                    try:
                        print("    [3/3] Mover para Atendimento Humano...")
                        btn_humano = page.locator('button:has-text("Atendimento Humano"), .btn-human').first
                        if btn_humano.is_visible(timeout=4000):
                            btn_humano.click()
                            print("    --> Chat movido para Atendimento Humano.")
                        else:
                            print("    --> AVISO: Botão de Atendimento Humano não visível.")
                    except Exception as e_humano:
                        print(f"    --> AVISO ao mover para humano: {e_humano}")

                elif "NEUTRO" in analise_norm or "SAIR" in analise_norm:
                    print("--> Ação: Mensagem genérica/emoji/opt-out. Arquivando conversa...")
                    try:
                        btn_fechar = page.locator('button:has-text("Resolver"), button:has-text("Arquivar"), [data-testid="resolve-chat"]').first
                        if btn_fechar.is_visible(timeout=4000):
                            btn_fechar.click()
                            print("    --> Conversa arquivada.")
                    except Exception as e_close:
                        print(f"    --> AVISO ao arquivar: {e_close}")

        except Exception as e:
            print(f"Erro durante a execução principal: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    rodar_triagem()
