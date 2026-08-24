import sys
import os
from playwright.sync_api import sync_playwright

def executar_bot(acao):
    email = os.environ.get("BOT_EMAIL")
    senha = os.environ.get("BOT_SENHA")

    if not email or not senha:
        print("ERRO: Credenciais BOT_EMAIL ou BOT_SENHA nao encontradas nas Secrets!")
        sys.exit(1)

    with sync_playwright() as p:
        # Lança navegador com argumentos para evitar bloqueios de automação
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        
        # Simula um navegador comum no desktop
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768}
        )
        page = context.new_page()

        print("Acessando a pagina de login do BotConversa...")
        page.goto("https://app.botconversa.com.br/login", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        # Preenche o e-mail
        print("Preenchendo credenciais...")
        email_input = page.locator('input[type="email"], input[name="email"], input[placeholder*="email" i]').first
        email_input.wait_for(state="visible", timeout=30000)
        email_input.fill(email)

        # Preenche a senha
        senha_input = page.locator('input[type="password"], input[name="password"]').first
        senha_input.fill(senha)

        # Clica no botão de login
        btn_login = page.locator('button[type="submit"], button:has-text("Entrar"), button:has-text("Login")').first
        btn_login.click()

        print("Aguardando login...")
        page.wait_for_timeout(8000)

        # Navega para Transmissões
        print("Navegando para a aba Transmissoes...")
        if "login" in page.url:
            print("Aviso: Pagina ainda no login. Tentando clicar no link direto de transmissao...")
        
        page.goto("https://app.botconversa.com.br/broadcasts", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)

        # Clica na ação (Play ou Pause)
        if acao == "start":
            print("Procurando botao para Iniciar...")
            btn_play = page.locator('button:has-text("Iniciar"), .btn-play, [data-testid="start-broadcast"]').first
            btn_play.wait_for(state="visible", timeout=20000)
            btn_play.click()
            print("Sucesso: Transmissao Iniciada!")
        elif acao == "stop":
            print("Procurando botao para Pausar...")
            btn_pause = page.locator('button:has-text("Pausar"), .btn-pause, [data-testid="stop-broadcast"]').first
            btn_pause.wait_for(state="visible", timeout=20000)
            btn_pause.click()
            print("Sucesso: Transmissao Pausada!")

        browser.close()

if __name__ == "__main__":
    acao = sys.argv[1] if len(sys.argv) > 1 else "start"
    executar_bot(acao)
