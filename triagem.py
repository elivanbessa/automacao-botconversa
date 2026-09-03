import os
import sys
import time
import unicodedata
import traceback
from google import genai
from playwright.sync_api import sync_playwright

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
BOT_EMAIL = os.environ.get("BOT_EMAIL")
BOT_SENHA = os.environ.get("BOT_SENHA")

if not GEMINI_KEY or not BOT_EMAIL or not BOT_SENHA:
    print("ERRO: Credenciais BOT_EMAIL, BOT_SENHA ou GEMINI_API_KEY não encontradas nas Secrets.")
    sys.exit(1)

client = genai.Client(api_key=GEMINI_KEY)

def normalizar_texto(texto):
    if not texto:
        return ""
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    ).upper()

def analisar_mensagem(texto):
    prompt = f"""
    Você é um triador de mensagens de atendimento via WhatsApp de uma loja.
    Analise a mensagem enviada pelo CLIENTE e responda ESTRITAMENTE no seguinte formato:

    CLASSIFICACAO: <DUVIDA ou NEUTRO>

    Regras de Classificação:
    - DUVIDA: O cliente perguntou sobre preço, valores, catálogo, fotos, frete, entrega, localização, disponibilidade ou fez uma pergunta/dúvida de atendimento (ex: 'enviou uma pergunta', 'qual o valor da mesa', 'quero saber o preço').
    - NEUTRO: Apenas emojis, saudações curtas ('oi', 'tudo bem'), 'ok', 'obrigado', mensagens automáticas do sistema ou disparos.

    Mensagem enviada pelo cliente: "{texto}"
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        print(f"Erro na API do Gemini: {e}")
        return "CLASSIFICACAO: NEUTRO"

def rodar_triagem():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ]
        )
        context = browser.new_context(
            viewport={"width": 1366, "height": 768},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo"
        )
        page = context.new_page()

        try:
            print("1. Efetuando Login no BotConversa...")
            page.goto("https://app.botconversa.com.br/login", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)

            campo_email = page.locator('input[type="email"], input[name="email"], input').first
            campo_email.fill(BOT_EMAIL, force=True)

            campo_senha = page.locator('input[type="password"], input[name="password"]').first
            campo_senha.fill(BOT_SENHA, force=True)

            btn_submit = page.locator('button[type="submit"], button:has-text("Entrar"), button:has-text("Login")').first
            btn_submit.click(force=True)

            print("2. Acessando a Caixa de Entrada (Inbox)...")
            page.wait_for_timeout(7000)
            page.goto("https://app.botconversa.com.br/69991/live-chat", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(6000)

            chats = page.locator('div[role="button"], div.chat-item, div:has-text("O Cliente")').all()
            print(f"Encontradas {len(chats)} conversas na lista.")

            for index, chat in enumerate(chats[:15]):
                try:
                    if not chat.is_visible():
                        continue

                    print(f"\n--- Processando Conversa {index + 1} ---")
                    chat.click(force=True)
                    page.wait_for_timeout(2500)

                    # Obtém textos recebidos do cliente na janela de chat
                    mensagens = page.locator('div:has-text("enviou uma pergunta"), div.message-received, div[data-message]').all_inner_texts()
                    texto_cliente = " ".join(mensagens).strip()

                    if not texto_cliente:
                        # Fallback buscando bolhas da conversa
                        todas_msgs = page.locator('div[class*="bubble"], div[class*="message"]').all_inner_texts()
                        texto_cliente = " ".join(todas_msgs).strip()

                    if not texto_cliente:
                        print("   --> Nenhuma mensagem encontrada nesta conversa.")
                        continue

                    print(f"   Texto Capturado: '{texto_cliente[:100]}...'")

                    # Análise Gemini
                    analise_raw = analisar_mensagem(texto_cliente)
                    analise_norm = normalizar_texto(analise_raw)
                    print(f"   Resultado Gemini: {analise_raw.strip()}")

                    if "DUVIDA" in analise_norm:
                        print("   --> Ação: Dúvida identificada! Aplicando etiqueta...")

                        # Passo A: Clica no nome/perfil para abrir a lateral (conforme mostrado no vídeo)
                        try:
                            header_chat = page.locator('header, div.chat-header, div:has-text("Perfil")').first
                            if header_chat.is_visible():
                                header_chat.click(force=True)
                                page.wait_for_timeout(1000)
                        except Exception:
                            pass

                        # Passo B: Clica no botão "+ Adicionar" em Etiquetas
                        btn_add = page.locator('button:has-text("+ Adicionar"), div:has-text("+ Adicionar")').first
                        btn_add.wait_for(state="visible", timeout=5000)
                        btn_add.click(force=True)
                        page.wait_for_timeout(1000)

                        # Passo C: Pesquisa "atendimento dúvida"
                        campo_busca = page.locator('input[placeholder*="Pesquisar"], input[placeholder*="Buscar"], input[type="text"]').last
                        campo_busca.fill("atendimento dúvida")
                        page.wait_for_timeout(1200)

                        # Passo D: Seleciona e clica na etiqueta [Atendimento] Dúvida
                        opcao_etiqueta = page.locator('div, span, li').filter(has_text="[Atendimento] Dúvida").first
                        if not opcao_etiqueta.is_visible():
                            opcao_etiqueta = page.locator('div, span, li').filter(has_text="atendimento dúvida").first

                        if opcao_etiqueta.is_visible(timeout=4000):
                            opcao_etiqueta.click(force=True)
                            print("   --> SUCESSO: Etiqueta '[Atendimento] Dúvida' aplicada com sucesso!")
                        else:
                            print("   --> AVISO: Etiqueta não visível ou já aplicada.")

                        page.wait_for_timeout(2000)
                    else:
                        print("   --> Ação: Mensagem classificada como neutra.")

                except Exception as e_chat:
                    print(f"   --> Aviso na conversa {index + 1}: {e_chat}")

        except Exception as e:
            print(f"Erro principal na triagem: {e}")
            traceback.print_exc()
            sys.exit(1)
        finally:
            browser.close()

if __name__ == "__main__":
    rodar_triagem()
