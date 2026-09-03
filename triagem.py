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
        # Atualizado para o modelo suportado na API pública
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        print(f"Aviso API Gemini: {e}")
        # Se contiver áudio ou mídia, assume DUVIDA para não perder o atendimento
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

                    # 1. Verifica presença de áudio/mídia sem dar timeout
                    tem_audio_midia = False
                    try:
                        elementos_midia = page.locator('audio, video, [data-icon*="mic"], [class*="audio"]').all()
                        if len(elementos_midia) > 0:
                            tem_audio_midia = True
                            print("   [!] Elemento de Áudio/Mídia identificado!")
                    except Exception:
                        pass

                    # 2. Captura textos sem timeout alto (usando timeout de 2000ms)
                    texto_cliente = ""
                    try:
                        mensagens_el = page.locator('div[class*="received"], div[class*="bubble"]').all_inner_texts()
                        texto_cliente = " ".join(mensagens_el).strip()
                    except Exception:
                        pass

                    print(f"   Texto Capturado: '{texto_cliente[:100]}...' | Mídia: {tem_audio_midia}")

                    # 3. Classificação com a IA Gemini
                    analise_raw = analisar_com_gemini(texto_cliente, tem_audio_ou_midia=tem_audio_midia)
                    analise_norm = normalizar_texto(analise_raw)
                    print(f"   Resultado Gemini: {analise_raw.strip()}")

                    if "DUVIDA" in analise_norm or tem_audio_midia:
                        print("   --> Ação: DUVIDA identificada! Abrindo painel e aplicando etiqueta...")

                        # Passo A: Clica no topo do chat / ícone de perfil à direita para exibir as etiquetas
                        page.evaluate("""
                            () => {
                                let el = document.querySelector('header') || document.querySelector('.chat-header') || document.querySelector('div[class*="header"]');
                                if (el) el.click();
                            }
                        """)
                        page.wait_for_timeout(1500)

                        # Passo B: Clica no botão "+ Adicionar" (com fallback JS caso o seletor visual mude)
                        clicado_add = False
                        try:
                            btn_add = page.locator('button:has-text("Adicionar"), button:has-text("+ Adicionar"), div:has-text("+ Adicionar")').first
                            if btn_add.is_visible(timeout=3000):
                                btn_add.click(force=True)
                                clicado_add = True
                        except Exception:
                            pass

                        if not clicado_add:
                            clicado_add = page.evaluate("""
                                () => {
                                    let elementos = Array.from(document.querySelectorAll('button, div, span'));
                                    let alvo = elementos.find(e => e.innerText && e.innerText.includes('Adicionar'));
                                    if (alvo) { alvo.click(); return true; }
                                    return false;
                                }
                            """)

                        page.wait_for_timeout(1500)

                        # Passo C: Pesquisa "atendimento dúvida"
                        campo_busca = page.locator('input[placeholder*="Pesquisar"], input[placeholder*="Buscar"], input[type="text"]').last
                        if campo_busca.is_visible(timeout=3000):
                            campo_busca.fill("atendimento dúvida")
                            page.wait_for_timeout(1200)

                        # Passo D: Seleciona e clica na etiqueta [Atendimento] Dúvida
                        opcao_etiqueta = page.locator('div, span, li').filter(has_text="[Atendimento] Dúvida").first
                        if not opcao_etiqueta.is_visible(timeout=2000):
                            opcao_etiqueta = page.locator('div, span, li').filter(has_text="atendimento dúvida").first

                        if opcao_etiqueta.is_visible(timeout=3000):
                            opcao_etiqueta.click(force=True)
                            print("   --> SUCESSO: Etiqueta '[Atendimento] Dúvida' aplicada com sucesso!")
                        else:
                            # Tentativa direta via DOM
                            page.evaluate("""
                                () => {
                                    let itens = Array.from(document.querySelectorAll('div, span, li'));
                                    let item = itens.find(e => e.innerText && e.innerText.includes('Dúvida'));
                                    if (item) item.click();
                                }
                            """)
                            print("   --> Comando de seleção da etiqueta executado no DOM.")

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
