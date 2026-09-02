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
        # Configurações para burlar bloqueios de Headless na nuvem
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--window-size=1366,768",
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ]
        )
        context = browser.new_context(
            viewport={"width": 1366, "height": 768},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo"
        )
        
        # Oculta propriedades do webdriver para evitar telas de bloqueio
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            print("1. Acessando a página inicial de Login do BotConversa...")
            page.goto("https://app.botconversa.com.br/login", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(3000)

            print(f"   URL atual após carregamento: {page.url}")

            # Procura por qualquer campo de input visível (geralmente o e-mail é o primeiro)
            print("   Procurando campos de formulário na tela...")
            campos_input = page.locator('input').all()
            print(f"   Total de campos de input encontrados na página: {len(campos_input)}")

            if len(campos_input) == 0:
                print("   AVISO: Nenhum campo de input encontrado. Verificando possibilidade de iframe...")
                # Tenta buscar em frames internos caso o login esteja embarcado
                for frame in page.frames:
                    inputs_frame = frame.locator('input').all()
                    if len(inputs_frame) > 0:
                        print(f"   Encontrado formulário em Frame interno: {frame.url}")
                        campo_email = frame.locator('input').first
                        campo_email.fill(BOT_EMAIL)
                        campo_senha = frame.locator('input[type="password"]').first
                        campo_senha.fill(BOT_SENHA)
                        frame.locator('button[type="submit"], button:has-text("Entrar")').first.click()
                        break
            else:
                # Preenchimento direto na página principal
                campo_email = page.locator('input[type="email"], input[name="email"], input').first
                campo_email.fill(BOT_EMAIL)

                campo_senha = page.locator('input[type="password"], input[name="password"]').first
                campo_senha.fill(BOT_SENHA)

                btn_submit = page.locator('button[type="submit"], button:has-text("Entrar"), button:has-text("Login")').first
                btn_submit.click()

            print("2. Login enviado. Aguardando redirecionamento para o Chat...")
            page.wait_for_timeout(7000)

            page.goto("https://app.botconversa.com.br/chat", wait_until="networkidle", timeout=60000)
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
                print(f"Texto do Cliente: '{texto_cliente}'")

                analise_raw = analisar_mensagem(texto_cliente)
                analise_norm = normalizar_texto(analise_raw)
                print(f"Resultado Gemini:\n{analise_raw}")

                if "DUVIDA" in analise_norm and "CLASSIFICACAO:" in analise_norm:
                    sugestao = analise_raw.split("SUGESTAO:")[-1].strip() if "SUGESTAO:" in analise_raw else "Verifique o interesse do cliente."
                    print("--> Ação: Dúvida identificada! Aplicando ações...")

                    # 1. Aplicar Etiqueta
                    try:
                        btn_tag = page.locator('button:has-text("Etiqueta"), .btn-tag, [data-testid="add-tag"], i.fa-tag, svg.feather-tag').first
                        if btn_tag.is_visible(timeout=4000):
                            btn_tag.click()
                            page.wait_for_timeout(1000)
                            
                            input_tag = page.locator('input[placeholder*="Buscar"], input[placeholder*="etiqueta"], input[placeholder*="Tag"]').first
                            input_tag.fill("[Atendimento] Dúvida")
                            page.wait_for_timeout(1500)
                            
                            try:
                                page.locator('.tag-item, .dropdown-item, li:has-text("[Atendimento] Dúvida")').first.click(timeout=2000)
                            except:
                                page.keyboard.press("Enter")
                                
                            page.wait_for_timeout(1000)
                            print("    --> Etiqueta '[Atendimento] Dúvida' adicionada.")
                    except Exception as e_tag:
                        print(f"    --> Aviso na tag: {e_tag}")

                    # 2. Nota Interna
                    try:
                        btn_nota = page.locator('button:has-text("Nota"), .btn-note, [data-testid="add-note"]').first
                        if btn_nota.is_visible(timeout=4000):
                            btn_nota.click()
                            campo_nota = page.locator('textarea, [contenteditable="true"]').first
                            campo_nota.fill(f"📌 IA Gemini: Dúvida identificada.\n💡 Sugestão: {sugestao}")
                            page.click('button:has-text("Salvar"), button:has-text("Adicionar")')
                            page.wait_for_timeout(1000)
                            print("    --> Nota interna salva.")
                    except Exception as e_nota:
                        print(f"    --> Aviso na nota: {e_nota}")

                    # 3. Mover para Atendimento Humano
                    try:
                        btn_humano = page.locator('button:has-text("Atendimento Humano"), .btn-human').first
                        if btn_humano.is_visible(timeout=4000):
                            btn_humano.click()
                            print("    --> Movido para Atendimento Humano.")
                    except Exception as e_humano:
                        print(f"    --> Aviso no atendimento humano: {e_humano}")

                elif "NEUTRO" in analise_norm or "SAIR" in analise_norm:
                    print("--> Ação: Mensagem irrelevante. Arquivando conversa...")
                    try:
                        btn_fechar = page.locator('button:has-text("Resolver"), button:has-text("Arquivar"), [data-testid="resolve-chat"]').first
                        if btn_fechar.is_visible(timeout=4000):
                            btn_fechar.click()
                            print("    --> Conversa arquivada.")
                    except Exception as e_close:
                        print(f"    --> Aviso ao arquivar: {e_close}")

        except Exception as e:
            print(f"Erro durante a execução principal: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    rodar_triagem()
