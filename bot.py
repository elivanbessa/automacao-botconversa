import sys
import os
from playwright.sync_api import sync_playwright

def executar_bot(acao):
    email = os.environ.get("BOT_EMAIL")
    senha = os.environ.get("BOT_SENHA")

    with sync_playwright() as p:
        # Abre o navegador Chromium na nuvem
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 1. Login no BotConversa
        page.goto("https://app.botconversa.com.br/login")
        page.fill('input[type="email"]', email)
        page.fill('input[type="password"]', senha)
        page.click('button[type="submit"]')

        # Aguarda carregar o painel principal
        page.wait_for_selector('text="Transmissões"', timeout=30000)

        # 2. Navega até a aba Transmissão
        page.click('text="Transmissões"')
        page.wait_for_timeout(3000)

        # 3. Executa a ação (Play ou Pause)
        if acao == "start":
            page.click('button:has-text("Iniciar"), .btn-play, [data-testid="start-broadcast"]')
            print("Transmissão Iniciada com sucesso!")
        elif acao == "stop":
            page.click('button:has-text("Pausar"), .btn-pause, [data-testid="stop-broadcast"]')
            print("Transmissão Pausada com sucesso!")

        browser.close()

if __name__ == "__main__":
    acao = sys.argv[1] if len(sys.argv) > 1 else "start"
    executar_bot(acao)
