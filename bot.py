import sys
import os
from playwright.sync_api import sync_playwright

def executar_bot(acao):
    email = os.environ.get("BOT_EMAIL")
    senha = os.environ.get("BOT_SENHA")

    if not email or not senha:
        print("ERRO: BOT_EMAIL ou BOT_SENHA não foram encontrados nas Secrets do GitHub!")
        sys.exit(1)

    with sync_playwright() as p:
        # Lança o navegador Chromium
        browser = p.chromium.launch(headless=True)
        # Define uma tela padrão para renderizar corretamente a interface do BotConversa
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        page = context.new_page()

        print("Acessando a página de login...")
        page.goto("https://app.botconversa.com.br/login", wait_until="networkidle")

        # Procura o campo de e-mail por diferentes seletores possíveis
        print("Preenchendo e-mail e senha...")
        email_selector = 'input[name="email"], input[type="email"], input[placeholder*="email" i]'
        page.wait_for_selector(email_selector, timeout=20000)
        page.fill(email_selector, email)

        # Procura o campo de senha
        senha_selector = 'input[name="password"], input[type="password"]'
        page.fill(senha_selector, senha)

        # Clica no botão de Entrar/Login
        print("Enviando formulário de login...")
        submit_button = 'button[type="submit"], button:has-text("Entrar"), button:has-text("Login")'
        page.click(submit_button)

        # Aguarda a navegação após o login
        print("Aguardando carregamento do painel...")
        page.wait_for_timeout(5000)

        # Procura o menu ou texto de Transmissões
        transmissao_selector = 'text="Transmissões", a[href*="broadcast"], [data-testid*="broadcast"]'
        page.wait_for_selector(transmissao_selector, timeout=30000)
        page.click(transmissao_selector)
        page.wait_for_timeout(4000)

        # Executa a ação desejada
        if acao == "start":
            print("Procurando botão Iniciar...")
            play_btn = 'button:has-text("Iniciar"), .btn-play, [data-testid="start-broadcast"]'
            page.wait_for_selector(play_btn, timeout=15000)
            page.click(play_btn)
            print("Transmissão Iniciada com sucesso!")
        elif acao == "stop":
            print("Procurando botão Pausar...")
            pause_btn = 'button:has-text("Pausar"), .btn-pause, [data-testid="stop-broadcast"]'
            page.wait_for_selector(pause_btn, timeout=15000)
            page.click(pause_btn)
            print("Transmissão Pausada com sucesso!")

        browser.close()

if __name__ == "__main__":
    acao = sys.argv[1] if len(sys.argv) > 1 else "start"
    executar_bot(acao)
