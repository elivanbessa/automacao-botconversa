import os
import sys
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
                print(f"Texto do Cliente: {texto_cliente}")

                analise = analisar_mensagem(texto_cliente)
                print(f"Resultado Gemini:\n{analise}")

                if "CLASSIFICACAO: DUVIDA" in analise:
                    sugestao = analise.split("SUGESTAO:")[-1].strip()
                    print("--> Ação: É Dúvida! Movendo para Atendimento Humano...")

                    # 1. Aplica a etiqueta [Atendimento] Dúvida
                    btn_tag = page.locator('button:has-text("Etiqueta"), .btn-tag, [data-testid="add-tag"]').first
                    if btn_tag.is_visible():
                        btn_tag.click()
                        page.fill('input[placeholder*="Buscar etiqueta"]', '[Atendimento] Dúvida')
                        page.keyboard.press("Enter")

                    # 2. Deixa a Nota Interna Amarela com a sugestão de resposta do Gemini
                    btn_nota = page.locator('button:has-text("Nota"), .btn-note, [data-testid="add-note"]').first
                    if btn_nota.is_visible():
                        btn_nota.click()
                        campo_nota = page.locator('textarea, [contenteditable="true"]').first
                        campo_nota.fill(f"📌 IA Gemini: Dúvida identificada.\n💡 Sugestão: {sugestao}")
                        page.click('button:has-text("Salvar Nota"), button:has-text("Adicionar")')

                    # 3. Muda para Atendimento Humano
                    btn_humano = page.locator('button:has-text("Atendimento Humano"), .btn-human').first
                    if btn_humano.is_visible():
                        btn_humano.click()

                elif "CLASSIFICACAO: NEUTRO" in analise or "CLASSIFICACAO: SAIR" in analise:
                    print("--> Ação: Mensagem genérica/emoji. Arquivando conversa...")
                    btn_fechar = page.locator('button:has-text("Resolver"), button:has-text("Arquivar"), [data-testid="resolve-chat"]').first
                    if btn_fechar.is_visible():
                        btn_fechar.click()

        except Exception as e:
            print(f"Erro durante a execução: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    rodar_triagem()
