import time
import csv
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from urllib.parse import urljoin

chrome_options = Options()
chrome_options.add_argument("--disable-geolocation")

BASE_URL = "https://www.doctolib.fr"

def trouver_url_fiche(med):
    """
    Retourne l'URL (absolue ou relative) de la fiche praticien depuis une carte résultat.
    Essaie plusieurs sélecteurs / stratégies.
    """
    # 1) Sélecteurs les plus stables
    selecteurs = [
        "a[data-testid='practitioner-name']",
        "a[data-test-id='search-result-card-practitioner-name']",
        "a[href*='/medecin/']",
        "a[href*='/sante/']",
        "a[href*='/centre-']",
        "a[href^='/']",
        "a[href^='/doctors/généraliste/torcy']",
        "a[href^='/cabinet-medical']",
    ]
    for sel in selecteurs:
        try:
            a = med.find_element(By.CSS_SELECTOR, sel)
            href = a.get_attribute("href") or a.get_attribute("data-href")
            if href and not href.startswith("javascript"):
                return href
        except:
            pass

    # 2) Un lien qui entoure un titre (h2/h3)
    try:
        a = med.find_element(By.XPATH, ".//a[.//h1 or .//h2 or .//h3]")
        href = a.get_attribute("href")
        if href:
            return href
    except:
        pass

    # 3) Dernier recours : premier <a> “pertinent” dans la carte
    for a in med.find_elements(By.TAG_NAME, "a"):
        href = a.get_attribute("href") or ""
        if href and not href.startswith("javascript:"):
            if "/medecin/" in href or "/sante/" in href or href.startswith("/"):
                return href

    return None


def ouvrir_fiche_nouvel_onglet(driver, wait, href):
    """
    Ouvre la fiche dans un nouvel onglet, attend le chargement et bascule dessus.
    Retourne True si ok, False sinon.
    """
    url = urljoin(BASE_URL, href)  # gère les URLs relatives
    driver.execute_script("window.open(arguments[0], '_blank');", url)
    driver.switch_to.window(driver.window_handles[-1])
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1")))
        return True
    except:
        return False

def trouver_champ_recherche(wait):
    """Trouver le champ de recherche Doctolib."""
    essais = [
        (By.CSS_SELECTOR, "input[placeholder*='Nom, spécialité, établissement']"),
        (By.CSS_SELECTOR, "input[aria-label*='Rechercher']"),
        (By.TAG_NAME, "input"),
    ]
    for by, sel in essais:
        try:
            return wait.until(EC.presence_of_element_located((by, sel)))
        except:
            continue
    raise Exception("Champ de recherche introuvable sur Doctolib")

def trouver_resultats(driver, wait):
    """
    Essaie plusieurs sélecteurs pour récupérer les cartes médecins sur Doctolib.
    Retourne une liste d'éléments WebElement.
    """
    essais = [
        "div.dl-card"  # fallback générique
    ]

    for sel in essais:
        try:
            # On attend max 10s qu'au moins un résultat apparaisse
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
            medecins = driver.find_elements(By.CSS_SELECTOR, sel)
            if medecins:
                print(f"✅ {len(medecins)} médecins trouvés avec le sélecteur {sel}")
                return medecins
        except:
            print(f"❌ Aucun élément trouvé avec {sel}")

    print("⚠️ Aucun résultat détecté avec les sélecteurs connus.")
    return []

def rechercher_praticiens():
    # === PARAMÈTRES UTILISATEUR ===
    nb_max = int(input("Nombre de résultats maximum à afficher : "))
    requete = input("Requête médicale (ex: dermatologue, généraliste) : ")
    secteur = input("Type d’assurance (secteur 1, secteur 2, non conventionné) : ")
    consultation = input("Type de consultation (en visio ou sur place) : ")
    filtre_adresse = input("Filtre géographique (mot-clé dans l’adresse) : ")
    date_debut = input("Date de début (JJ/MM/AAAA) : ")
    date_fin = input("Date de fin (JJ/MM/AAAA) : ")
    prix_min = input("Prix minimum (€) : ")
    prix_max = input("Prix maximum (€) : ")

    # Transformation des dates
    try:
        date_debut = datetime.strptime(date_debut, "%d/%m/%Y")
        date_fin = datetime.strptime(date_fin, "%d/%m/%Y")
    except:
        print("⚠️ Format de date incorrect (JJ/MM/AAAA attendu). Les filtres de dates seront ignorés.")
        date_debut = date_fin = None

    # === INITIALISATION SELENIUM ===
    chrome_options = Options()
    chrome_options.add_argument("--disable-geolocation")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.maximize_window()
    driver.get("https://www.doctolib.fr/")

    wait = WebDriverWait(driver, 30)

    # Gestion des cookies
    try:
        reject_btn = wait.until(
            EC.element_to_be_clickable((By.ID, "didomi-notice-disagree-button"))
        )
        reject_btn.click()
    except:
        pass

    # === RECHERCHE ===
    search_input = trouver_champ_recherche(wait)
    search_input.clear()
    search_input.send_keys(requete)
    search_input.send_keys(Keys.ENTER)

    # try:
    #     localisation_input = wait.until(
    #         EC.presence_of_element_located((By.CSS_SELECTOR, "input[data-testid='search-bar-location-input']"))
    #     )
    #     localisation_input.clear()  # supprime la valeur automatique
    #     time.sleep(2)
    #     localisation_input.send_keys(filtre_adresse)  # ou ta ville cible
    #     time.sleep(2)
    #     localisation_input.send_keys(Keys.DOWN)
    #     time.sleep(2)
    #     localisation_input.send_keys(Keys.ENTER)
    # except:
    #     print("⚠️ Impossible de saisir la localisation, la valeur par défaut sera utilisée.")

    time.sleep(5)  # laisse un peu de temps à la page

    # === FILTRES ===
    # Secteur
    if secteur.lower() == "secteur 1":
        try:
            driver.find_element(By.XPATH, "//span[contains(text(),'Secteur 1')]").click()
        except:
            pass
    elif secteur.lower() == "secteur 2":
        try:
            driver.find_element(By.XPATH, "//span[contains(text(),'Secteur 2')]").click()
        except:
            pass
    elif "non" in secteur.lower():
        try:
            driver.find_element(By.XPATH, "//span[contains(text(),'Non conventionné')]").click()
        except:
            pass

    # Consultation
    if consultation.lower() == "en visio":
        try:
            driver.find_element(By.XPATH, "//span[contains(text(),'Téléconsultation')]").click()
        except:
            pass
    elif consultation.lower() == "sur place":
        try:
            driver.find_element(By.XPATH, "//span[contains(text(),'En cabinet')]").click()
        except:
            pass

    # Attente que les cartes soient chargées
    medecins = trouver_resultats(driver, wait)
    print("DEBUG: nombre de cartes trouvées =", len(medecins))

    results = []
    for med in medecins[:nb_max]:
        try:
            href = trouver_url_fiche(med)
            if not href:
                print("⚠️ Aucun lien de fiche détecté pour cette carte. On passe.")
                continue

            if not ouvrir_fiche_nouvel_onglet(driver, wait, href):
                print(f"⚠️ Échec d'ouverture ou de chargement pour {href}")
                # ferme l’onglet s'il a été ouvert mais n'a pas chargé
                if len(driver.window_handles) > 1:
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                continue

            # ---------- Extraction détaillée sur la fiche ----------
            try:
                nom = driver.find_element(By.CSS_SELECTOR, "h1").text.strip()
            except:
                nom = None

            try:
                dispo = driver.find_element(By.CSS_SELECTOR, "div[data-testid='next-availability']").text.strip()
            except:
                dispo = "Non disponible"

            try:
                specialite = driver.find_element(By.CSS_SELECTOR, "div[data-testid='speciality']").text
            except:
                specialite = None

            # Secteur
            if specialite:
                if "Secteur 1" in specialite:
                    secteur_txt = "1"
                elif "Secteur 2" in specialite:
                    secteur_txt = "2"
                elif "Non conventionné" in specialite:
                    secteur_txt = "Non conventionné"
                else:
                    secteur_txt = None
            else:
                secteur_txt = None

            # Adresse
            try:
                adresse_txt = driver.find_element(By.CSS_SELECTOR, "div[data-testid='address']").text.split("\n")
                rue = adresse_txt[0] if adresse_txt else None
                code_postal, ville = None, None
                if len(adresse_txt) > 1:
                    parts = adresse_txt[1].split()
                    code_postal = parts[0]
                    ville = " ".join(parts[1:])
            except:
                rue = code_postal = ville = None

            # Prix : on scanne les spans pour trouver un montant
            prix = None
            try:
                for sp in driver.find_elements(By.TAG_NAME, "span"):
                    text = sp.text.strip()
                    if "€" in text and any(ch.isdigit() for ch in text):
                        prix = text
                        break
            except:
                prix = None

            results.append({
                "Nom": nom,
                "Disponibilité": dispo,
                "Consultation": "Téléconsultation" if "téléconsultation" in driver.page_source.lower() else "En cabinet",
                "Secteur": secteur_txt,
                "Prix": prix,
                "Rue": rue,
                "Code postal": code_postal,
                "Ville": ville,
            })
            print(f"✅ Médecin {nom} enregistré depuis la fiche")

        except Exception as e:
            print("⚠️ Erreur lors du traitement :", e)

        finally:
            # Fermer l’onglet fiche (si ouvert) et revenir à la liste
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(driver.window_handles[0])

    # === SAUVEGARDE CSV ===
    if results:
        with open("medecins.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
        print(f"✅ {len(results)} médecins sauvegardés dans medecins.csv")
    else:
        print("❌ Aucun médecin trouvé avec ces critères.")

    driver.quit()


if __name__ == "__main__":
    rechercher_praticiens()
