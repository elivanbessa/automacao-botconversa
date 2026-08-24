import sys
import os
import traceback
from playwright.sync_api import sync_playwright

def executar_bot(acao):
    email = os.environ.get("BOT_EMAIL")
    senha = os.environ.get("BOT_SENHA")

    if not email or not senha:
        print("ERRO: Credenciais BOT_EMAIL ou BOT_SENHA nao encontradas nas Secrets!")
        sys.exit(1)

    with sync_playwright() as p:
        # Lança o navegador sem flags restritivas
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage"
            ]
        )
        
        # Simula perfil real de navegador Desktop
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768}
        )
        page = context.new_page()

        try:
            print("1. Acessando a pagina de login do BotConversa...")
            page.goto("https://app.botconversa.com.br/login", wait_until="networkidle", timeout=60000)
            
            # Aguarda 5 segundos adicionais para garantir a renderização completa do React/Vue
            page.wait_for_timeout(5000)

            print("2. Procurando campos de e-mail e senha...")
            # Busca flexível que cobre qualquer formato de input no formulário do BotConversa
            email_locator = page.locator('input[type="email"], input[name="email"], input[placeholder*="mail" i], input[id*="email" i]').first
            email_locator.wait_for(state="attached", timeout=30000)
            
            # Garante que o elemento está visível na tela antes de digitar
            email_locator.scroll_into_view_if_needed()
            email_locator.fill(email)

            senha_locator = page.locator('input[type="password"], input[name="password"]').first
            senha_locator.fill(senha)

            print("3. Clicando no botao de Login...")
            btn_login = page.locator('button[type="submit"], button:has-text("Entrar"), button:has-text("Login")').first
            btn_login.click()

            print("4. Aguardando autenticacao e carregamento do painel...")
            page.wait_for_timeout(10000)

            print("5. Navegando para a aba de Transmissoes...")
            page.goto("https://app.botconversa.com.br/broadcasts", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(5000)

            if acao == "start":
                print("6. Executando acao: Iniciar Transmissao...")
                btn_play = page.locator('button:has-text("Iniciar"), .btn-play, [data-testid="start-broadcast"], button:has-text("Play")').first
                btn_play.wait_for(state="visible", timeout=20000)
                btn_play.click()
                print("SUCESSO: Transmissao Iniciada!")
            elif acao == "stop":
                print("6. Executando acao: Pausar Transmissao...")
                btn_pause = page.locator('button:has-text("Pausar"), .btn-pause, [data-testid="stop-broadcast"], button:has-text("Pause")').first
                btn_pause.wait_for(state="visible", timeout=20000)
                btn_pause.click()
                print("SUCESSO: Transmissao Pausada!")

        except Exception as e:
            print("\n--- OCORREU UM ERRO DURANTE A EXECUCAO ---")
            print(f"Mensagem de Erro: {e}")
            traceback.print_exc()
            sys.exit(1)
        finally:
            browser.close()

if __name__ == "__main__":
    acao = sys.argv[1] if len(sys.argv) > 1 else "start"
    executar_bot(acao)
