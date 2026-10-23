
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    navegador = p.chromium.launch(headless=False)
    pagina = navegador.new_page()
    pagina.goto("https://www.instagram.com/")
    pagina.wait_for_timeout(5000)

    print("Título de la página:", pagina.title())

    navegador.close()
