import time
import csv
from urllib.parse import urljoin
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

BASE_URL = "https://www.doctolib.fr"

def get_driver():
    opts = Options()
    # désactiver la géolocalisation et quelques options utiles
    prefs = {"profile.default_content_setting_values.geolocation": 2}
    opts.add_experimental_option("prefs", prefs)
    opts.add_argument("--disable-geolocation")
    # opts.add_argument("--headless=new")  # décommente si tu veux headless
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.maximize_window()
    return driver

def click_cookie_if_present(wait):
    # plusieurs IDs possibles -> on essaye de fermer l'avis cookies si présent
    cookie_selectors = [
        (By.ID, "didomi-notice-disagree-button"),
        (By.ID, "didomi-notice-agree-button"),
        (By.CSS_SELECTOR, "button[aria-label='close']"),
    ]
    for by, sel in cookie_selectors:
        try:
            btn = wait.until(EC.element_to_be_clickable((by, sel)))
            btn.click()
            time.sleep(0.5)
        except:
            continue

def find_search_inputs(wait, driver):
    """Retourne (search_input, location_input). Essaie plusieurs sélecteurs."""
    search_input = None
    location_input = None

    # location first — plus fiable d'entrer la localisation avant la requête
    loc_try = [
        (By.CSS_SELECTOR, "input[data-testid='search-bar-location-input']"),
        (By.CSS_SELECTOR, "input[aria-label*='localisation']"),
        (By.CSS_SELECTOR, "input[placeholder*='Votre ville']"),
        (By.CSS_SELECTOR, "input[placeholder*='Code postal']"),
    ]
    for by, sel in loc_try:
        try:
            location_input = wait.until(EC.presence_of_element_located((by, sel)))
            print(f"DEBUG: localisation input trouvé avec {sel}")
            break
        except:
            continue

    search_try = [
        (By.CSS_SELECTOR, "input[placeholder*='Nom, spécialité, établissement']"),
        (By.ID, "search-bar-main"),
        (By.CSS_SELECTOR, "input[aria-label*='Rechercher']"),
        (By.TAG_NAME, "input"),
    ]
    for by, sel in search_try:
        try:
            elem = wait.until(EC.presence_of_element_located((by, sel)))
            # heuristique : choisir l'input visible et enabled
            if elem.is_displayed() and elem.is_enabled():
                search_input = elem
                print(f"DEBUG: search input trouvé avec {sel}")
                break
        except:
            continue

    return search_input, location_input

def type_location(location_input, location, wait):
    """Ecrase la localisation automatique et sélectionne la suggestion si possible."""
    try:
        location_input.clear()
        time.sleep(0.2)
        location_input.send_keys(location)
        time.sleep(0.6)
        # tenter de sélectionner la première suggestion
        location_input.send_keys(Keys.DOWN)
        time.sleep(0.2)
        location_input.send_keys(Keys.ENTER)
        time.sleep(0.8)
        return True
    except Exception as e:
        print("DEBUG: impossible de saisir la localisation:", e)
        return False

def find_result_cards(driver, wait):
    """Essaie plusieurs sélecteurs de cartes résultats et retourne la liste."""
    candidats = [
        "div[data-test-id='search-result-card']",
        "div[data-testid='search-result-card']",
        "div[data-test-id*='search-result']",
        "div[data-testid*='search-result']",
        "div.dl-card",
        "li.search-result",
        "div.search-result-card"
    ]
    for sel in candidats:
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)), timeout=10)
            cards = driver.find_elements(By.CSS_SELECTOR, sel)
            if cards:
                print(f"✅ {len(cards)} médecins trouvés avec le sélecteur {sel}")
                return cards
        except Exception:
            print(f"❌ Aucun élément trouvé avec {sel}")
            continue
    print("⚠️ Aucun résultat détecté avec les sélecteurs connus.")
    return []

def trouver_url_fiche(med):
    """Retourne l'URL (relative ou absolue) de la fiche praticien depuis une carte."""
    selecteurs = [
        "a[data-testid='practitioner-name']",
        "a[data-test-id='search-result-card-practitioner-name']",
        "a[href*='/medecin/']",
        "a[href*='/medecin-generaliste/']",
        "a[href*='/praticien/']",
        "a[href*='/sante/']",
        "a[href^='/']",
    ]
    for sel in selecteurs:
        try:
            a = med.find_element(By.CSS_SELECTOR, sel)
            href = a.get_attribute("href") or a.get_attribute("data-href")
            if href and not href.startswith("javascript"):
                return href
        except:
            continue

    # fallback: chercher premier <a> pertinent
    for a in med.find_elements(By.TAG_NAME, "a"):
        href = a.get_attribute("href") or ""
        if href and not href.startswith("javascript:"):
            if "/medecin/" in href or "/praticien/" in href or "/sante/" in href or href.startswith("/"):
                return href
    return None

def extraire_depuis_fiche(driver, wait):
    """Extrait les infos depuis la fiche ouverte (onglet actif)."""
    nom = None
    dispo = "Non disponible"
    type_consult = None
    secteur_txt = None
    prix = None
    rue = None
    code_postal = None
    ville = None

    # attendre que le h1 (ou main) soit présent
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1")), timeout=10)
    except Exception:
        pass

    # Nom
    for sel in ["h1", "h1[data-testid='practitioner-name']", "h1[itemprop='name']"]:
        try:
            nom = driver.find_element(By.CSS_SELECTOR, sel).text.strip()
            break
        except:
            continue

    # Disponibilité (plusieurs tests)
    dispo_try = [
        "div[data-testid='next-availability']",
        "div[data-test-id='search-result-availability']",
        "div.availability",
        "//div[contains(., 'Prochaine') or contains(., 'Prochain')]"  # XPath fallback
    ]
    for sel in dispo_try:
        try:
            if sel.startswith("//"):
                dispo = driver.find_element(By.XPATH, sel).text.strip()
            else:
                dispo = driver.find_element(By.CSS_SELECTOR, sel).text.strip()
            break
        except:
            continue

    # Type de consultation : chercher le mot "téléconsultation"
    page_text = driver.page_source.lower()
    type_consult = "Téléconsultation" if "téléconsultation" in page_text or "téléconsult" in page_text else "En cabinet"

    # Spécialité / secteur
    spec_try = [
        "div[data-testid='speciality']",
        "div[data-test-id='search-result-card-content']",
        "div.speciality",
        "p.speciality"
    ]
    specialite = None
    for sel in spec_try:
        try:
            specialite = driver.find_element(By.CSS_SELECTOR, sel).text
            break
        except:
            continue
    if specialite:
        if "Secteur 1" in specialite:
            secteur_txt = "1"
        elif "Secteur 2" in specialite:
            secteur_txt = "2"
        elif "Non conventionné" in specialite or "non-conventionné" in specialite.lower():
            secteur_txt = "Non conventionné"

    # Adresse
    addr_try = [
        "div[data-testid='address']",
        "div[data-test-id='search-result-card-address']",
        "address",
        "p.address"
    ]
    adresse_txt = None
    for sel in addr_try:
        try:
            adresse_txt = driver.find_element(By.CSS_SELECTOR, sel).text.strip()
            break
        except:
            continue
    if adresse_txt:
        parts = adresse_txt.split("\n")
        rue = parts[0] if len(parts) >= 1 else None
        if len(parts) >= 2:
            second = parts[1].strip()
            sp = second.split()
            if sp:
                code_postal = sp[0]
                ville = " ".join(sp[1:]) if len(sp) > 1 else None

    # Prix : scanner tous les spans / p à la recherche de "€"
    try:
        for el in driver.find_elements(By.XPATH, "//span|//p|//div"):
            text = el.text.strip()
            if "€" in text and any(ch.isdigit() for ch in text):
                prix = text
                break
    except:
        prix = None

    return {
        "Nom": nom,
        "Disponibilité": dispo,
        "Consultation": type_consult,
        "Secteur": secteur_txt,
        "Prix": prix,
        "Rue": rue,
        "Code postal": code_postal,
        "Ville": ville
    }

def sauvegarder_csv(results, filename="medecins.csv"):
    headers = ["Nom","Disponibilité","Consultation","Secteur","Prix","Rue","Code postal","Ville"]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for r in results:
            # s'assurer que toutes les clés existent
            row = {k: r.get(k, "") for k in headers}
            writer.writerow(row)

def rechercher_praticiens():
    driver = get_driver()
    wait = WebDriverWait(driver, 30)

    try:
        driver.get(BASE_URL)
        click_cookie_if_present(wait)

        # Paramètres utilisateur
        nb_max = int(input("Nombre de résultats maximum à afficher : ") or 10)
        requete = input("Requête médicale (ex: dermatologue, généraliste) : ").strip()
        lieu = input("Localisation (code postal ou ville, ex: 75001) : ").strip()
        secteur = input("Type d’assurance (secteur 1, secteur 2, non conventionné) : ").strip()
        consultation = input("Type de consultation (en visio ou sur place) : ").strip()
        prix_min = input("Prix min (€) (laisser vide si non) : ").strip()
        prix_max = input("Prix max (€) (laisser vide si non) : ").strip()
        date_deb = input("Date début (JJ/MM/AAAA) (laisser vide si non) : ").strip()
        date_fin = input("Date fin (JJ/MM/AAAA) (laisser vide si non) : ").strip()

        # trouver inputs
        search_input, location_input = find_search_inputs(wait, driver)
        if location_input and lieu:
            ok_loc = type_location(location_input, lieu, wait)
            if not ok_loc:
                print("DEBUG: échec saisie localisation — on continue avec localisation par défaut du site.")
        else:
            print("DEBUG: champ localisation introuvable ou non renseigné, on laisse valeur par défaut.")

        # taper la requête
        if search_input and requete:
            search_input.clear()
            time.sleep(0.2)
            search_input.send_keys(requete)
            time.sleep(0.5)
            # valider
            search_input.send_keys(Keys.ENTER)
        else:
            print("ERROR: Champ recherche introuvable ou requête vide.")
            return

        # attendre résultats
        time.sleep(2)
        medecins = find_result_cards(driver, wait)
        if not medecins:
            print("❌ Aucun médecin détecté — vérifie la recherche sur le navigateur.")
            # debug : dump un petit extrait du HTML
            print(driver.page_source[:2000])
            return

        results = []
        # parcourir résultats (limité à nb_max)
        for idx, med in enumerate(medecins[:nb_max], start=1):
            print(f"--- Traitement résultat {idx}/{min(nb_max, len(medecins))} ---")
            try:
                href = trouver_url_fiche(med)
                print("DEBUG: href détecté =", href)
                if not href:
                    print("⚠️ Aucun lien pour ce résultat — outerHTML (tronc):")
                    print(med.get_attribute("outerHTML")[:500])
                    continue

                # ouvrir dans nouvel onglet et extraire
                url = urljoin(BASE_URL, href)
                driver.execute_script("window.open(arguments[0], '_blank');", url)
                driver.switch_to.window(driver.window_handles[-1])

                # attendre que la fiche charge (ou timeout)
                try:
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1")), timeout=15)
                except:
                    print("DEBUG: h1 introuvable après ouverture (possible lenteur). On continue l'extraction avec fallback.")

                data = extraire_depuis_fiche(driver, wait)
                print("DEBUG: extrait ->", data)
                results.append(data)

            except Exception as e:
                print("⚠️ Erreur sur un praticien :", e)

            finally:
                # fermer onglet fiche et revenir à la liste
                if len(driver.window_handles) > 1:
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                time.sleep(0.6)

        # sauvegarde CSV
        sauvegarder_csv(results)
        print(f"✅ Terminé — {len(results)} praticiens sauvegardés dans medecins.csv")

    except KeyboardInterrupt:
        print("Interrompu par l'utilisateur — sauvegarde partielle si existante.")
    finally:
        driver.quit()

if __name__ == "__main__":
    rechercher_praticiens()
