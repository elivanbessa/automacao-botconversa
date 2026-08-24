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
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768}
        )
        page = context.new_page()

        try:
            print("1. Acessando a pagina de login do BotConversa...")
            page.goto("https://app.botconversa.com.br/login", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(3000)

            print("2. Tirando foto da tela de login...")
            page.screenshot(path="login_page.png")

            print("3. Preenchendo dados de acesso...")
            email_input = page.locator('input[type="email"], input[name="email"], input[placeholder*="email" i]').first
            email_input.wait_for(state="visible", timeout=15000)
            email_input.fill(email)

            senha_input = page.locator('input[type="password"], input[name="password"]').first
            senha_input.fill(senha)

            print("4. Clicando no botao de entrar...")
            btn_login = page.locator('button[type="submit"], button:has-text("Entrar"), button:has-text("Login")').first
            btn_login.click()

            page.wait_for_timeout(8000)

            print("5. Acessando a aba de transmissoes...")
            page.goto("https://app.botconversa.com.br/broadcasts", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(5000)
            page.screenshot(path="transmissoes_page.png")

            if acao == "start":
                print("6. Procurando e clicando no botao Iniciar...")
                btn_play = page.locator('button:has-text("Iniciar"), .btn-play, [data-testid="start-broadcast"]').first
                btn_play.wait_for(state="visible", timeout=15000)
                btn_play.click()
                print("SUCESSO: Transmissao Iniciada!")
            elif acao == "stop":
                print("6. Procurando e clicando no botao Pausar...")
                btn_pause = page.locator('button:has-text("Pausar"), .btn-pause, [data-testid="stop-broadcast"]').first
                btn_pause.wait_for(state="visible", timeout=15000)
                btn_pause.click()
                print("SUCESSO: Transmissao Pausada!")

        except Exception as e:
            print(f"\n--- OCORREU UM ERRO DURANTE A EXECUÇÃO ---")
            print(f"Mensagem de Erro: {e}")
            traceback.print_exc()
            page.screenshot(path="erro_execucao.png")
            sys.exit(1)
        finally:
            browser.close()

if __name__ == "__main__":
    acao = sys.argv[1] if len(sys.argv) > 1 else "start"
    executar_bot(acao)
