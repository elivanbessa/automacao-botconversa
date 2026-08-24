import sys
import os
import datetime
import traceback
from playwright.sync_api import sync_playwright

def dia_permitido(regra_dias):
    """
    Verifica o dia da semana atual no fuso de Brasília (UTC-3).
    0 = Segunda, 1 = Terça, 2 = Quarta, 3 = Quinta, 4 = Sexta, 5 = Sábado, 6 = Domingo
    """
    agora_utc = datetime.datetime.now(datetime.timezone.utc)
    agora_br = agora_utc - datetime.timedelta(hours=3)
    dia_atual = agora_br.weekday()

    if regra_dias == "todos":
        return True
    elif regra_dias == "seg_a_sab" and dia_atual in [0, 1, 2, 3, 4, 5]:  # Segunda a Sábado
        return True
    elif regra_dias in ["seg,ter,qua,qui,sex", "seg_a_sex"] and dia_atual in [0, 1, 2, 3, 4]:  # Segunda a Sexta
        return True
    elif regra_dias == "fim_de_semana" and dia_atual in [5, 6]:  # Sábado e Domingo
        return True

    return False

def determinar_acao_automatica(hora_inicio, hora_pausa):
    """Verifica se a hora atual do Brasil bate com a hora de Início ou Pausa."""
    agora_utc = datetime.datetime.now(datetime.timezone.utc)
    agora_br = agora_utc - datetime.timedelta(hours=3)
    hora_atual = agora_br.hour

    int_inicio = int(hora_inicio)
    int_pausa = int(hora_pausa)

    if hora_atual == int_inicio:
        return "start"
    elif hora_atual == int_pausa:
        return "stop"
    else:
        return None

def executar_bot(acao, regra_dias="seg_a_sab", forcar=False, hora_inicio="08", hora_pausa="18"):
    # Se for execução automática, determina se deve dar start, stop ou ignorar
    if acao == "auto":
        acao = determinar_acao_automatica(hora_inicio, hora_pausa)
        if not acao:
            print(f"Horário atual não coincide com o horário de início ({hora_inicio}h) nem de pausa ({hora_pausa}h). Execução ignorada.")
            return

    # Validação do Dia da Semana
    if not forcar and not dia_permitido(regra_dias):
        print(f"Hoje não é um dia permitido para rodar. Regra selecionada: '{regra_dias}'. Execução ignorada.")
        return

    email = os.environ.get("BOT_EMAIL")
    senha = os.environ.get("BOT_SENHA")

    if not email or not senha:
        print("ERRO: Credenciais BOT_EMAIL ou BOT_SENHA não encontradas nas Secrets!")
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
            print("1. Acessando a página de login do BotConversa...")
            page.goto("https://app.botconversa.com.br/login", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(4000)

            print("2. Preenchendo credenciais de acesso...")
            email_locator = page.locator('input[type="email"], input[name="email"], input[placeholder*="mail" i]').first
            email_locator.wait_for(state="attached", timeout=30000)
            email_locator.fill(email)

            senha_locator = page.locator('input[type="password"], input[name="password"]').first
            senha_locator.fill(senha)

            print("3. Realizando login...")
            btn_login = page.locator('button[type="submit"], button:has-text("Entrar"), button:has-text("Login")').first
            btn_login.click()
            page.wait_for_timeout(8000)

            print("4. Entrando na aba de Transmissões...")
            page.goto("https://app.botconversa.com.br/broadcasts", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(5000)

            if acao == "start":
                print("5. Executando comando de INICIAR transmissão...")
                btn_play = page.locator('button:has-text("Iniciar"), button:has-text("Play"), button:has-text("Ativar"), .btn-play, [data-testid="start-broadcast"]').first
                if btn_play.is_visible(timeout=10000):
                    btn_play.click()
                    print("SUCESSO: Transmissão iniciada!")
                else:
                    print("AVISO: Botão de Iniciar não encontrado (a transmissão já pode estar ativa).")

            elif acao == "stop":
                print("5. Executando comando de PAUSAR transmissão...")
                btn_pause = page.locator('button:has-text("Pausar"), button:has-text("Pause"), button:has-text("Parar"), button:has-text("Desativar"), .btn-pause, [data-testid="stop-broadcast"]').first
                if btn_pause.is_visible(timeout=10000):
                    btn_pause.click()
                    print("SUCESSO: Transmissão pausada!")
                else:
                    print("AVISO: Botão de Pausar não encontrado (a transmissão já pode estar parada).")

        except Exception as e:
            print("\n--- OCORREU UM ERRO DURANTE A EXECUÇÃO ---")
            print(f"Detalhes: {e}")
            traceback.print_exc()
            sys.exit(1)
        finally:
            browser.close()

if __name__ == "__main__":
    acao = sys.argv[1] if len(sys.argv) > 1 else "auto"
    regra_dias = sys.argv[2] if len(sys.argv) > 2 else "seg_a_sab"
    forcar = sys.argv[3].lower() == "true" if len(sys.argv) > 3 else False
    hora_inicio = sys.argv[4] if len(sys.argv) > 4 else "08"
    hora_pausa = sys.argv[5] if len(sys.argv) > 5 else "18"

    executar_bot(acao, regra_dias, forcar, hora_inicio, hora_pausa)
