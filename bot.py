import sys
import os
import datetime
import traceback
from playwright.sync_api import sync_playwright

def dia_permitido(regra_dias):
    """Verifica se o dia da semana atual é permitido pela regra selecionada."""
    # 0 = Segunda, 1 = Terça, ..., 5 = Sábado, 6 = Domingo
    dia_atual = datetime.datetime.now().weekday()
    
    if regra_dias == "todos":
        return True
    elif regra_dias == "fim_de_semana" and dia_atual in [5, 6]:
        return True
    elif regra_dias == "seg,ter,qua,qui,sex" and dia_atual in [0, 1, 2, 3, 4]:
        return True
    
    return False

def executar_bot(acao, regra_dias="todos", forcar=False):
    # Checagem de dias da semana
    if not forcar and not dia_permitido(regra_dias):
        print(f"HOJE NAO É UM DIA PERMITIDO PARA RODAR. Regra: '{regra_dias}'. Execução ignorada com sucesso.")
        return

    email = os.environ.get("BOT_EMAIL")
    senha = os.environ.get("BOT_SENHA")

    if not email or not senha:
        print("ERRO: Credenciais BOT_EMAIL ou BOT_SENHA nao encontradas!")
        sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768}
        )
        page = context.new_page()

        try:
            print("1. Acessando a pagina de login do BotConversa...")
            page.goto("https://app.botconversa.com.br/login", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(4000)

            print("2. Preenchendo login e senha...")
            email_locator = page.locator('input[type="email"], input[name="email"], input[placeholder*="mail" i]').first
            email_locator.wait_for(state="attached", timeout=30000)
            email_locator.fill(email)

            senha_locator = page.locator('input[type="password"], input[name="password"]').first
            senha_locator.fill(senha)

            print("3. Autenticando no sistema...")
            btn_login = page.locator('button[type="submit"], button:has-text("Entrar"), button:has-text("Login")').first
            btn_login.click()
            page.wait_for_timeout(8000)

            print("4. Acessando a pagina de Transmissoes...")
            page.goto("https://app.botconversa.com.br/broadcasts", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(5000)

            if acao == "start":
                print("5. Executando comando de INICIAR transmissão...")
                btn_play = page.locator('button:has-text("Iniciar"), button:has-text("Play"), button:has-text("Ativar"), .btn-play, [data-testid="start-broadcast"]').first
                if btn_play.is_visible(timeout=10000):
                    btn_play.click()
                    print("SUCESSO: Transmissão iniciada!")
                else:
                    print("AVISO: Botão de Iniciar não encontrado (a transmissão pode já estar ativa).")
                    
            elif acao == "stop":
                print("5. Executando comando de PAUSAR transmissão...")
                btn_pause = page.locator('button:has-text("Pausar"), button:has-text("Pause"), button:has-text("Parar"), button:has-text("Desativar"), .btn-pause, [data-testid="stop-broadcast"]').first
                if btn_pause.is_visible(timeout=10000):
                    btn_pause.click()
                    print("SUCESSO: Transmissão pausada!")
                else:
                    print("AVISO: Botão de Pausar não encontrado (a transmissão pode já estar parada).")

        except Exception as e:
            print("\n--- OCORREU UM ERRO ---")
            print(f"Detalhes: {e}")
            traceback.print_exc()
            sys.exit(1)
        finally:
            browser.close()

if __name__ == "__main__":
    acao = sys.argv[1] if len(sys.argv) > 1 else "start"
    regra_dias = sys.argv[2] if len(sys.argv) > 2 else "todos"
    forcar = sys.argv[3].lower() == "true" if len(sys.argv) > 3 else False
    
    executar_bot(acao, regra_dias, forcar)
