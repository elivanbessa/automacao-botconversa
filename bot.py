import sys
import os
import datetime
import traceback
from playwright.sync_api import sync_playwright

def dia_permitido(regra_dias):
    agora_utc = datetime.datetime.now(datetime.timezone.utc)
    agora_br = agora_utc - datetime.timedelta(hours=3)
    dia_atual = agora_br.weekday()

    if regra_dias == "todos":
        return True
    elif regra_dias == "seg_a_sab" and dia_atual in [0, 1, 2, 3, 4, 5]:
        return True
    elif regra_dias in ["seg,ter,qua,qui,sex", "seg_a_sex"] and dia_atual in [0, 1, 2, 3, 4]:
        return True
    elif regra_dias == "fim_de_semana" and dia_atual in [5, 6]:
        return True

    return False

def determinar_acao_automatica(hora_inicio, hora_pausa):
    agora_utc = datetime.datetime.now(datetime.timezone.utc)
    agora_br = agora_utc - datetime.timedelta(hours=3)
    hora_atual = agora_br.hour

    int_inicio = int(hora_inicio)
    int_pausa = int(hora_pausa)

    print(f"Horário oficial (Brasília): {agora_br.strftime('%d/%m/%Y %H:%M:%S')} (Hora: {hora_atual}h)")

    if int_inicio < int_pausa:
        if int_inicio <= hora_atual < int_pausa:
            return "start"
        else:
            return "stop"
    else:
        if hora_atual >= int_inicio or hora_atual < int_pausa:
            return "start"
        else:
            return "stop"

def executar_bot(acao, regra_dias="seg_a_sab", forcar=False, hora_inicio="08", hora_pausa="18"):
    if acao == "auto":
        acao = determinar_acao_automatica(hora_inicio, hora_pausa)
        print(f"Ação automática definida: '{acao.upper()}'")

    if not forcar and not dia_permitido(regra_dias):
        print(f"Hoje não é um dia permitido ({regra_dias}). Execução interrompida.")
        return

    email = os.environ.get("BOT_EMAIL")
    senha = os.environ.get("BOT_SENHA")

    if not email or not senha:
        print("ERRO: Credenciais BOT_EMAIL ou BOT_SENHA ausentes nas Secrets!")
        sys.exit(1)

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
            print("1. Acessando página de login...")
            page.goto("https://app.botconversa.com.br/login", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)

            print("2. Preenchendo credenciais...")
            email_locator = page.locator('input[type="email"], input[name="email"], input').first
            email_locator.wait_for(state="visible", timeout=15000)
            email_locator.fill(email, force=True)

            senha_locator = page.locator('input[type="password"], input[name="password"]').first
            senha_locator.fill(senha, force=True)

            print("3. Efetuando login...")
            btn_login = page.locator('button[type="submit"], button:has-text("Entrar"), button:has-text("Login")').first
            btn_login.click(force=True)
            page.wait_for_timeout(7000)

            print("4. Navegando para Transmissões Agendadas...")
            page.goto("https://app.botconversa.com.br/69991/broadcast/scheduled", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(8000)

            if acao == "start":
                print("5. Procurando botão de Play pelo SVG verde (#54C21F)...")

                seletor_svg_play = page.locator('//*[name()="svg"]/*[name()="circle" and @fill="#54C21F"]/.. | //*[name()="svg"]/*[name()="path" and @fill="#54C21F"]/..').first

                if seletor_svg_play.is_visible(timeout=5000):
                    seletor_svg_play.click(force=True)
                    print("--> SUCESSO: Clique direto no SVG verde realizado!")
                else:
                    print("--> Buscando SVG verde via injeção JavaScript DOM...")
                    clicado = page.evaluate("""
                        () => {
                            const svgs = Array.from(document.querySelectorAll('svg'));
                            const target = svgs.find(s => s.outerHTML.includes('#54C21F') || s.outerHTML.includes('clip0_6756'));
                            if (target) {
                                const clickable = target.closest('button') || target.closest('div') || target;
                                clickable.click();
                                return true;
                            }
                            return false;
                        }
                    """)
                    if clicado:
                        print("--> SUCESSO: Clique via script injetado no SVG verde executado!")
                    else:
                        print("--> AVISO: SVG verde não encontrado. A transmissão já pode estar ativa.")

                page.wait_for_timeout(2000)

                btn_confirmar_play = page.locator('button:has-text("Sim"), button:has-text("Iniciar"), button:has-text("Continuar")').last
                if btn_confirmar_play.is_visible(timeout=3000):
                    btn_confirmar_play.click(force=True)
                    print("--> SUCESSO: Modal de início confirmado!")

            elif acao == "stop":
                print("5. Procurando botão de Pause pelo SVG laranja (#DF911D)...")

                seletor_svg_pause = page.locator('//*[name()="svg"]/*[name()="circle" and @fill="#DF911D"]/.. | //*[name()="svg"]/*[name()="path" and @stroke="#DF911D"]/..').first

                clicado_pause = False
                if seletor_svg_pause.is_visible(timeout=5000):
                    seletor_svg_pause.click(force=True)
                    print("   --> Clique direto no SVG laranja efetuado!")
                    clicado_pause = True
                else:
                    print("   --> Buscando SVG laranja via injeção JavaScript DOM...")
                    clicado_pause = page.evaluate("""
                        () => {
                            const svgs = Array.from(document.querySelectorAll('svg'));
                            const target = svgs.find(s => s.outerHTML.includes('#DF911D') || s.outerHTML.includes('clip0_7596'));
                            if (target) {
                                const clickable = target.closest('button') || target.closest('div') || target;
                                clickable.click();
                                return true;
                            }
                            return false;
                        }
                    """)
                    if clicado_pause:
                        print("   --> Clique via script injetado no SVG laranja executado!")

                if clicado_pause:
                    page.wait_for_timeout(2000)
                    btn_confirmar_stop = page.locator('button:has-text("Sim, pausar esta transmissão"), button:has-text("Sim, pausar"), button:has-text("Pausar")').last
                    if btn_confirmar_stop.is_visible(timeout=5000):
                        btn_confirmar_stop.click(force=True)
                        print("--> SUCESSO: Modal de pausa confirmado com sucesso!")
                    else:
                        print("--> SUCESSO: Comando de pausa enviado (modal não exigido ou auto-fechado).")
                else:
                    print("--> AVISO: Botão laranja de Pause não localizado. A transmissão já pode estar pausada.")

            page.wait_for_timeout(4000)

        except Exception as e:
            print("\n--------------------------------------------------")
            print(f"ERRO DE EXECUÇÃO: {e}")
            print("--------------------------------------------------")
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
