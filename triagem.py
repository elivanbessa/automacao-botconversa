import os
import sys
import time
import unicodedata
from google import genai
from playwright.sync_api import sync_playwright

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
BOT_EMAIL = os.environ.get("BOT_EMAIL")
BOT_SENHA = os.environ.get("BOT_SENHA")

if not GEMINI_KEY or not BOT_EMAIL or not BOT_SENHA:
    print("ERRO: Faltam credenciais nas Secrets (GEMINI_API_KEY, BOT_EMAIL, BOT_SENHA).")
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
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        print(f"Erro na API do Gemini: {e}")
        return "CLASSIFICACAO: NEUTRO\nSUGESTAO: N/A"

def rodar_triagem():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--ignore-certificate-errors",
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ]
        )
        context = browser.new_context(
            viewport={"width": 1366, "height": 768},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo"
        )
        
        page = context.new_page()
        
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        """)

        try:
            print("1. Efetuando Login no BotConversa...")
            page.goto("https://app.botconversa.com.br/login", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)

            campo_email = page.locator('input[type="email"], input[name="email"], input[placeholder*="email" i], input').first
            campo_email.fill(BOT_EMAIL, force=True)

            campo_senha = page.locator('input[type="password"], input[name="password"]').first
            campo_senha.fill(BOT_SENHA, force=True)

            btn_submit = page.locator('button[type="submit"], button:has-text("Entrar"), button:has-text("Login")').first
            btn_submit.click(force=True)

            print("2. Login enviado. Navegando para a Caixa de Entrada da Org 69991...")
            page.wait_for_timeout(7000)

            page.goto("https://app.botconversa.com.br/69991/live-chat/all", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(6000)

            seletor_conversas = 'a[href*="live-chat"], div[class*="chat"], div[class*="conversation"], [role="button"]'
            
            conversas = page.locator(seletor_conversas).all()
            if len(conversas) == 0:
                conversas = page.locator('aside div > div, div.flex-1.overflow-y-auto > div').all()

            print(f"Encontradas {len(conversas)} conversas para análise.")

            for index, conversa in enumerate(conversas[:30]):
                try:
                    conversa.click(force=True)
                    page.wait_for_timeout(2500)

                    msgs = page.locator('.message-in, .received, [data-outgoing="false"], div[class*="message-in"]').all()
                    if not msgs:
                        msgs = page.locator('div[class*="bubble"], div[class*="message"]').all()

                    if not msgs:
                        print(f"   [Conversa {index+1}] Sem bolhas de mensagem legíveis.")
                        continue
                    
                    texto_cliente = msgs[-1].text_content().strip()
                    print(f"\n--- Conversa {index+1} ---")
                    print(f"Texto extraído: '{texto_cliente}'")

                    analise_raw = analisar_mensagem(texto_cliente)
                    analise_norm = normalizar_texto(analise_raw)
                    print(f"Resultado Gemini:\n{analise_raw}")

                    if "DUVIDA" in analise_norm and "CLASSIFICACAO:" in analise_norm:
                        sugestao = analise_raw.split("SUGESTAO:")[-1].strip() if "SUGESTAO:" in analise_raw else "Verifique o interesse do cliente."
                        print("--> Ação: Dúvida identificada! Aplicando ações...")

                        # 1. APLICAR ETIQUETA (Mapeado exatamente com base no print do Perfil)
                        try:
                            # Clica no botão "+ Adicionar" da seção Etiquetas
                            btn_add_tag = page.locator('button:has-text("+ Adicionar"), button:has-text("Adicionar")').first
                            if btn_add_tag.is_visible(timeout=4000):
                                btn_add_tag.click(force=True)
                                page.wait_for_timeout(1000)
                                
                                # Localiza o campo de busca com ícone de lupa dentro do balão popover
                                campo_busca_tag = page.locator('input[placeholder*="Busca"], input[placeholder*="busca" i]').first
                                campo_busca_tag.wait_for(state="visible", timeout=3000)
                                campo_busca_tag.focus()
                                campo_busca_tag.fill("")
                                campo_busca_tag.press_sequentially("[Atendimento] Dúvida", delay=80)
                                page.wait_for_timeout(1500)

                                # Procura a opção correspondente gerada na lista do dropdown e clica
                                tag_item = page.locator('div, li, span').filter(has_text="[Atendimento] Dúvida").first
                                if tag_item.is_visible(timeout=3000):
                                    tag_item.click(force=True)
                                    print("    --> Clique efetuado no item da etiqueta do dropdown!")
                                else:
                                    page.keyboard.press("Enter")
                                    print("    --> Pressionado Enter para confirmar etiqueta.")
                                    
                                page.wait_for_timeout(1500)
                        except Exception as e_tag:
                            print(f"    --> Aviso na tag: {e_tag}")

                        # 2. APLICAR NOTA INTERNA (Ícone + na seção Notas do Perfil)
                        try:
                            btn_nota = page.locator('button:has-text("Nota"), .btn-note, [data-testid="add-note"]').first
                            if btn_nota.is_visible(timeout=4000):
                                btn_nota.click(force=True)
                                page.wait_for_timeout(1000)
                                campo_nota = page.locator('textarea, [contenteditable="true"]').first
                                campo_nota.fill(f"📌 IA Gemini: Dúvida identificada.\n💡 Sugestão: {sugestao}", force=True)
                                page.wait_for_timeout(500)
                                page.click('button:has-text("Salvar"), button:has-text("Adicionar")', force=True)
                                page.wait_for_timeout(1000)
                                print("    --> Nota interna salva.")
                        except Exception as e_nota:
                            print(f"    --> Aviso na nota: {e_nota}")

                        # 3. MOVER PARA ATENDIMENTO HUMANO
                        try:
                            btn_humano = page.locator('button:has-text("Atendimento Humano"), .btn-human').first
                            if btn_humano.is_visible(timeout=4000):
                                btn_humano.click(force=True)
                                print("    --> Movido para Atendimento Humano.")
                        except Exception as e_humano:
                            print(f"    --> Aviso no atendimento humano: {e_humano}")

                    elif "NEUTRO" in analise_norm or "SAIR" in analise_norm:
                        print("--> Ação: Mensagem irrelevante. Arquivando conversa...")
                        try:
                            btn_fechar = page.locator('button:has-text("Resolver"), button:has-text("Arquivar"), [data-testid="resolve-chat"]').first
                            if btn_fechar.is_visible(timeout=4000):
                                btn_fechar.click(force=True)
                                print("    --> Conversa arquivada.")
                        except Exception as e_close:
                            print(f"    --> Aviso ao arquivar: {e_close}")

                except Exception as e_item:
                    print(f"    --> Erro na conversa {index+1}: {e_item}")

        except Exception as e:
            print(f"Erro durante a execução principal: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    rodar_triagem()
