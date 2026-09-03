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

def analisar_com_gemini(texto_conversa, tem_audio_ou_midia=False):
    prompt = f"""
    Você é um assistente de triagem de atendimento ao cliente via WhatsApp.
    Sua missão é determinar se a conversa precisa de ATENDIMENTO HUMANO / RESPOSTA A DÚVIDA.

    Regras de Classificação:
    - Responda DUVIDA se o cliente:
      * Enviou uma dúvida, pergunta sobre preço, valores, fotos, catálogo, produto, frete, localização, etc.
      * Enviou um áudio, imagem ou documento solicitando suporte/atendimento.
      * Expressou intenção de compra ou pediu ajuda.
    - Responda NEUTRO apenas se:
      * For estritamente uma mensagem automática do próprio sistema/bot.
      * For apenas uma confirmação simples encerrada sem pendências (ex: "ok", "obrigado").

    Presença de Áudio/Mídia enviado pelo cliente: {"SIM" if tem_audio_ou_midia else "NÃO"}
    Texto das mensagens recentes do cliente: "{texto_conversa}"

    Responda ESTRITAMENTE em uma única linha no formato:
    CLASSIFICACAO: <DUVIDA ou NEUTRO>
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        print(f"Erro na API do Gemini: {e}")
        # Se contiver áudio/mídia ou texto relevante, em caso de erro na IA define como dúvida por segurança
        return "CLASSIFICACAO: DUVIDA" if (tem_audio_ou_midia or len(texto_conversa) > 5) else "CLASSIFICACAO: NEUTRO"

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
            senha = BOT_SENHA
            campo_senha.fill(senha, force=True)

            btn_submit = page.locator('button[type="submit"], button:has-text("Entrar"), button:has-text("Login")').first
            btn_submit.click(force=True)

            print("2. Acessando a Caixa de Entrada (Inbox)...")
            page.wait_for_timeout(7000)
            page.goto("https://app.botconversa.com.br/69991/live-chat", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(6000)

            # Seleciona as conversas da coluna esquerda
            chats = page.locator('div[role="button"], div.chat-item, div:has-text("O Cliente")').all()
            print(f"Total de conversas localizadas na lista: {len(chats)}")

            for index, chat in enumerate(chats[:15]):
                try:
                    if not chat.is_visible():
                        continue

                    print(f"\n--- Processando Conversa #{index + 1} ---")
                    chat.click(force=True)
                    page.wait_for_timeout(2500)

                    # 1. Verifica se há áudio/mídia na janela do chat
                    tem_audio_midia = False
                    elementos_midia = page.locator('audio, video, [data-icon*="mic"], [class*="audio"], [class*="media"], svg path[d*="M12"]').all()
                    if len(elementos_midia) > 0:
                        tem_audio_midia = True
                        print("   [!] Elemento de Áudio/Mídia identificado na conversa!")

                    # 2. Captura textos das mensagens do chat
                    mensagens_el = page.locator('div[class*="received"], div[class*="bubble"], div[data-message]').all_inner_texts()
                    texto_cliente = " ".join(mensagens_el).strip()

                    if not texto_cliente and not tem_audio_midia:
                        # Tenta capturar qualquer texto dentro da área central de mensagens
                        texto_cliente = page.locator('div.chat-body, div.messages-container').inner_text()

                    print(f"   Texto Capturado: '{texto_cliente[:120]}...' | Mídia/Áudio Presente: {tem_audio_midia}")

                    # 3. Análise no Gemini
                    analise_raw = analisar_com_gemini(texto_cliente, tem_audio_ou_midia=tem_audio_midia)
                    analise_norm = normalizar_texto(analise_raw)
                    print(f"   Resultado Gemini: {analise_raw.strip()}")

                    if "DUVIDA" in analise_norm or tem_audio_midia:
                        print("   --> Ação: DUVIDA identificada! Aplicando etiqueta no perfil...")

                        # Passo A: Clica na área de perfil para garantir que a lateral está aberta
                        try:
                            header_chat = page.locator('header, div.chat-header, div:has-text("Perfil")').first
                            if header_chat.is_visible():
                                header_chat.click(force=True)
                                page.wait_for_timeout(1000)
                        except Exception:
                            pass

                        # Passo B: Clica em "+ Adicionar" na seção de etiquetas
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
                            print("   --> AVISO: Etiqueta não visível no menu ou já aplicada.")

                        page.wait_for_timeout(2000)
                    else:
                        print("   --> Ação: Conversa classificada como NEUTRO.")

                except Exception as e_chat:
                    print(f"   --> Aviso na conversa #{index + 1}: {e_chat}")

        except Exception as e:
            print(f"Erro principal na triagem: {e}")
            traceback.print_exc()
            sys.exit(1)
        finally:
            browser.close()

if __name__ == "__main__":
    rodar_triagem()
