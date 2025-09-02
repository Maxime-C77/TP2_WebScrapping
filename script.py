import time
import csv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


def trouver_champ_recherche(wait):
    # Tente plusieurs sélecteurs possibles
    essais = [
        (By.ID, "searchbar-input"),
        (By.CSS_SELECTOR, "input.searchbar-input.searchbar-place-input"),
        (By.CSS_SELECTOR, "input[placeholder*='Nom, spécialité, établissement,...']")
    ]
    for by, sel in essais:
        try:
            return wait.until(EC.presence_of_element_located((by, sel)))
        except:
            continue
    raise Exception("Champ de recherche introuvable sur Doctolib")

def rechercher_praticiens():
    # === PARAMÈTRES UTILISATEUR (saisis au clavier) ===
    nb_max = int(input("Nombre de résultats maximum à afficher : "))
    requete = input("Requête médicale (ex: dermatologue, généraliste) : ")
    secteur = input("Type d’assurance (secteur 1, secteur 2, non conventionné) : ")
    consultation = input("Type de consultation (en visio ou sur place) : ")
    filtre_adresse = input("Filtre géographique (mot-clé dans l’adresse, ex: 75015, Boulogne, rue de Vaugirard) : ")

    # === INITIALISATION SELENIUM ===
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)
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

    # Recherche
    # === RECHERCHE ===
    search_input = wait.until(
        EC.presence_of_element_located((By.ID, ":r1:"))
    )
    search_input = trouver_champ_recherche(wait)
    search_input.clear()
    search_input.send_keys(requete)
    search_input.send_keys(Keys.ENTER)

    time.sleep(3)

    # === FILTRES ===
    # Filtrer par secteur
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

    # Filtrer par type de consultation
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

    time.sleep(5)

    # === EXTRACTION DES DONNÉES ===
    medecins = driver.find_elements(By.CSS_SELECTOR, "div.dl-search-result-presentation")
    results = []

    for med in medecins[:nb_max]:
        try:
            # Nom complet
            nom = med.find_element(By.CSS_SELECTOR, "a.dl-search-result-name").text.strip()
        except:
            nom = None

        try:
            # Prochaine disponibilité
            dispo = med.find_element(By.CSS_SELECTOR, "div.dl-search-result-availability").text.strip()
        except:
            dispo = "Non disponible"

        try:
            # Type consultation
            type_consult = "Téléconsultation" if "Téléconsultation" in med.text else "En cabinet"
        except:
            type_consult = None

        try:
            # Secteur d’assurance
            secteur_txt = med.find_element(By.CSS_SELECTOR, "div.dl-search-result-speciality").text
            if "Secteur 1" in secteur_txt:
                secteur_txt = "1"
            elif "Secteur 2" in secteur_txt:
                secteur_txt = "2"
            else:
                secteur_txt = "Non conventionné"
        except:
            secteur_txt = None

        try:
            # Prix (si indiqué)
            prix = med.find_element(By.XPATH, ".//span[contains(text(),'€')]").text
        except:
            prix = None

        try:
            # Adresse complète
            adresse = med.find_element(By.CSS_SELECTOR, "input.searchbar-input.searchbar-place-input").text.split("\n")
            rue, code_postal, ville = None, None, None
            if adresse:
                rue = adresse[0]
            if len(adresse) > 1:
                parts = adresse[1].split()
                if parts:
                    code_postal = parts[0]
                    ville = " ".join(parts[1:])
        except:
            rue, code_postal, ville = None, None, None

        # Vérifier si l’adresse correspond au filtre
        if filtre_adresse and filtre_adresse.lower() not in (rue or "").lower() and filtre_adresse.lower() not in (ville or "").lower():
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
