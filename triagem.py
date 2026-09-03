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
    print("ERRO: Credenciais BOT_EMAIL, BOT_SENHA ou GEMINI_API_KEY ausentes nas Secrets.")
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
    Determine se a conversa precisa de ATENDIMENTO HUMANO / RESPOSTA A DÚVIDA.

    Regras:
    - Responda DUVIDA se o cliente perguntou algo, mandou áudio/mídia, pediu preço/informações ou precisa de suporte.
    - Responda NEUTRO apenas se for mensagem automática do sistema ou confirmação isolada ("ok", "obrigado").

    Mídia/Áudio enviada pelo cliente: {"SIM" if tem_audio_ou_midia else "NÃO"}
    Texto das mensagens: "{texto_conversa}"

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
        print(f"Aviso API Gemini: {e}")
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
            campo_senha.fill(BOT_SENHA, force=True)

            btn_submit = page.locator('button[type="submit"], button:has-text("Entrar"), button:has-text("Login")').first
            btn_submit.click(force=True)

            print("2. Acessando a Caixa de Entrada (Inbox)...")
            page.wait_for_timeout(7000)
            page.goto("https://app.botconversa.com.br/69991/live-chat", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(6000)

            chats = page.locator('div[role="button"], div.chat-item, div:has-text("O Cliente")').all()
            print(f"Total de conversas localizadas na lista: {len(chats)}")

            for index, chat in enumerate(chats[:15]):
                try:
                    if not chat.is_visible():
                        continue

                    print(f"\n--- Processando Conversa #{index + 1} ---")
                    chat.click(force=True)
                    page.wait_for_timeout(2000)

                    # 1. Verifica presença de áudio/mídia
                    tem_audio_midia = False
                    try:
                        elementos_midia = page.locator('audio, video, [data-icon*="mic"], [class*="audio"]').all()
                        if len(elementos_midia) > 0:
                            tem_audio_midia = True
                            print("   [!] Elemento de Áudio/Mídia identificado!")
                    except Exception:
                        pass

                    # 2. Captura textos da conversa
                    texto_cliente = ""
                    try:
                        mensagens_el = page.locator('div[class*="received"], div[class*="bubble"]').all_inner_texts()
                        texto_cliente = " ".join(mensagens_el).strip()
                    except Exception:
                        pass

                    print(f"   Texto Capturado: '{texto_cliente[:100]}...' | Mídia: {tem_audio_midia}")

                    # 3. Classificação Gemini
                    analise_raw = analisar_com_gemini(texto_cliente, tem_audio_ou_midia=tem_audio_midia)
                    analise_norm = normalizar_texto(analise_raw)
                    print(f"   Resultado Gemini: {analise_raw.strip()}")

                    if "DUVIDA" in analise_norm or tem_audio_midia:
                        print("   --> Ação: DUVIDA identificada! Executando sequência de cliques exatamente como no vídeo...")

                        # Passo 1: Clicar no Nome / Avatar do cliente no topo da janela do chat ativo (Abre o Perfil)
                        try:
                            avatar_cliente = page.locator('header img, header div[role="button"], div.chat-header span').first
                            if avatar_cliente.is_visible(timeout=3000):
                                avatar_cliente.click(force=True)
                                print("   --> [Passo 1] Clique no Perfil/Avatar do cliente realizado!")
                        except Exception as e_avatar:
                            print(f"   --> AVISO no Passo 1: {e_avatar}")

                        page.wait_for_timeout(1500)

                        # Passo 2: Clicar no botão "+ Adicionar" na seção de etiquetas
                        btn_add = page.locator('button:has-text("+ Adicionar"), div:has-text("+ Adicionar"), span:has-text("+ Adicionar")').first
                        btn_add.wait_for(state="visible", timeout=5000)
                        btn_add.click(force=True)
                        print("   --> [Passo 2] Botão '+ Adicionar' clicado!")
                        page.wait_for_timeout(1000)

                        # Passo 3: Digitar "atendimento dúvida" caractere por caractere
                        campo_busca = page.locator('input[placeholder*="Pesquisar"], input[placeholder*="Buscar"], input[type="text"]').last
                        campo_busca.wait_for(state="visible", timeout=5000)
                        campo_busca.click(force=True)
                        
                        # Simula a digitação com intervalo humano
                        campo_busca.press_sequentially("atendimento dúvida", delay=100)
                        page.wait_for_timeout(1500)

                        # Passo 4: Clicar no item da lista ou pressionar a tecla Enter
                        opcao_etiqueta = page.locator('div, span, li').filter(has_text="[Atendimento] Dúvida").first
                        if not opcao_etiqueta.is_visible(timeout=2000):
                            opcao_etiqueta = page.locator('div, span, li').filter(has_text="atendimento dúvida").first

                        if opcao_etiqueta.is_visible(timeout=3000):
                            opcao_etiqueta.click(force=True)
                            print("   --> [Passo 4] Clique direto na opção '[Atendimento] Dúvida' efetuado!")
                        else:
                            # Se a opção não receber o clique do mouse, confirma via Teclado (Seta para baixo + Enter)
                            print("   --> [Passo 4] Confirmando seleção da etiqueta via Tecla Enter do teclado...")
                            page.keyboard.press("ArrowDown")
                            page.wait_for_timeout(500)
                            page.keyboard.press("Enter")

                        page.wait_for_timeout(2500)
                        print("   --> SUCESSO: Sequência de etiquetagem concluída com sucesso!")
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
