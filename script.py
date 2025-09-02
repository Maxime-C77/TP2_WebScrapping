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

chrome_options = Options()
chrome_options.add_argument("--disable-geolocation")


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

    wait = WebDriverWait(driver, 20)

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

    localisation_input = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='Où ?']"))
    )
    localisation_input.clear()  # supprime la valeur automatique
    localisation_input.send_keys(filtre_adresse)  # ou ta ville cible
    localisation_input.send_keys(Keys.ENTER)

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
        # Nom
        try:
            nom = med.find_element(By.CSS_SELECTOR, "a[data-testid='practitioner-name']").text.strip()
        except:
            nom = None

        # Disponibilité
        try:
            dispo = med.find_element(By.CSS_SELECTOR, "div[data-testid='next-availability']").text.strip()
        except:
            dispo = "Non disponible"

        # Type de consultation
        type_consult = "Téléconsultation" if "téléconsultation" in med.text.lower() else "En cabinet"

        # Secteur d'assurance
        try:
            specialite = med.find_element(By.CSS_SELECTOR, "div[data-testid='speciality']").text
            if "Secteur 1" in specialite:
                secteur_txt = "1"
            elif "Secteur 2" in specialite:
                secteur_txt = "2"
            elif "Non conventionné" in specialite:
                secteur_txt = "Non conventionné"
            else:
                secteur_txt = None
        except:
            secteur_txt = None

        # Prix
        try:
            prix = None
            for sp in med.find_elements(By.TAG_NAME, "span"):
                if "€" in sp.text:
                    prix = sp.text.strip()
                    break
        except:
            prix = None

        # Adresse
        try:
            adresse_txt = med.find_element(By.CSS_SELECTOR, "div[data-testid='address']").text.split("\n")
            rue = adresse_txt[0] if adresse_txt else None
            code_postal, ville = None, None
            if len(adresse_txt) > 1:
                parts = adresse_txt[1].split()
                code_postal = parts[0]
                ville = " ".join(parts[1:])
        except:
            rue = code_postal = ville = None

        # Filtre adresse
        if filtre_adresse:
            texte_adresse = " ".join([rue or "", ville or ""]).lower()
            if filtre_adresse.lower() not in texte_adresse:
                continue

        results.append({
            "Nom": nom,
            "Disponibilité": dispo,
            "Consultation": type_consult,
            "Secteur": secteur_txt,
            "Prix": prix,
            "Rue": rue,
            "Code postal": code_postal,
            "Ville": ville,
        })

        print(f"DEBUG: Médecin {nom} → adresse trouvée = {rue}, {ville}")



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
