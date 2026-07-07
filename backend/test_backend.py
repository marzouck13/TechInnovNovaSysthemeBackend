import requests
import time
import sys
from datetime import datetime

BASE_URL = "http://localhost:8000"
CHEF_NOM = "NOVA"
CHEF_PRENOM = "ADMIN"
CHEF_CODE = input("🔑 Entrez le code du chef officiel (affiché au démarrage du serveur) : ").strip()

# --- Génération d'un nom d'employé unique basé sur le timestamp ---
timestamp = int(time.time())
NOM_EMPLOYE = f"Dupont_{timestamp}"
PRENOM_EMPLOYE = "Jean"

# --- Couleurs pour les logs ---
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"

def log_ok(msg):
    print(f"{GREEN}✅ {msg}{RESET}")

def log_fail(msg):
    print(f"{RED}❌ {msg}{RESET}")

def log_info(msg):
    print(f"ℹ️  {msg}")

def print_separator(title):
    print("\n" + "="*60)
    print(f" {title}")
    print("="*60)

# --- 1. Connexion du chef officiel ---
print_separator("1 – Connexion du chef officiel")
login_data = {"nom": CHEF_NOM, "prenom": CHEF_PRENOM, "code_acces": CHEF_CODE}
r = requests.post(f"{BASE_URL}/auth/connexion", json=login_data)
assert r.status_code == 200, f"Code attendu 200, reçu {r.status_code}"
token_chef = r.json()["access_token"]
log_ok(f"Connecté en tant que {r.json()['nom_complet']} (rôle: {r.json()['role']})")
headers_chef = {"Authorization": f"Bearer {token_chef}"}

# --- 2. Liste des employés (chef) ---
print_separator("2 – Liste des employés (chef)")
r = requests.get(f"{BASE_URL}/admin/employes", headers=headers_chef)
assert r.status_code == 200
users = r.json()
log_ok(f"Liste des {len(users)} utilisateurs récupérée")

# --- 3. Ajout d'un employé (par chef officiel) ---
print_separator("3 – Ajout d'un employé (par chef officiel)")
employe_data = {"nom": NOM_EMPLOYE, "prenom": PRENOM_EMPLOYE}
r = requests.post(f"{BASE_URL}/admin/employes", json=employe_data, headers=headers_chef)
if r.status_code == 400 and "existe déjà" in r.text:
    log_info("Employé déjà présent, tentative avec un autre nom...")
    NOM_EMPLOYE = f"Dupont_{timestamp}_{int(time.time()*1000)%1000}"
    employe_data["nom"] = NOM_EMPLOYE
    r = requests.post(f"{BASE_URL}/admin/employes", json=employe_data, headers=headers_chef)
assert r.status_code == 200, f"Code attendu 200, reçu {r.status_code}"
code_employe = r.json()["code_acces_employe"]
log_ok(f"Employé ajouté : {PRENOM_EMPLOYE} {NOM_EMPLOYE} – Code = {code_employe}")

# --- 4. Connexion de l'employé ---
print_separator("4 – Connexion de l'employé")
login_emp = {"nom": NOM_EMPLOYE, "prenom": PRENOM_EMPLOYE, "code_acces": code_employe}
r = requests.post(f"{BASE_URL}/auth/connexion", json=login_emp)
assert r.status_code == 200
token_emp = r.json()["access_token"]
log_ok(f"Employé {PRENOM_EMPLOYE} {NOM_EMPLOYE} connecté avec succès")
headers_emp = {"Authorization": f"Bearer {token_emp}"}

# --- 5. Chef officiel : promotion de l'employé en chef (non officiel) ---
print_separator("5 – Chef officiel : promotion de l'employé en chef")
r = requests.get(f"{BASE_URL}/admin/employes", headers=headers_chef)
users = r.json()
emp_id = next(u["id"] for u in users if u["nom"] == NOM_EMPLOYE and u["prenom"] == PRENOM_EMPLOYE)

role_data = {"role": "chef"}
r = requests.patch(f"{BASE_URL}/admin/employes/{emp_id}/role", json=role_data, headers=headers_chef)
assert r.status_code == 200
log_ok("L'employé est devenu chef (non officiel)")

# --- 5bis : Reconnexion du chef non officiel pour obtenir un token frais ---
print_separator("5bis – Reconnexion du chef non officiel pour obtenir un token frais")
r = requests.post(f"{BASE_URL}/auth/connexion", json=login_emp)
assert r.status_code == 200
token_chef_non_officiel = r.json()["access_token"]
headers_chef_non_officiel = {"Authorization": f"Bearer {token_chef_non_officiel}"}
log_ok("Chef non officiel reconnecté, nouveau token obtenu")

# --- 6. Vérification : chef non officiel peut lire les employés ---
print_separator("6 – Vérification : chef non officiel peut lire /admin/employes")
r = requests.get(f"{BASE_URL}/admin/employes", headers=headers_chef_non_officiel)
assert r.status_code == 200, f"Code attendu 200, reçu {r.status_code}"
log_ok("Lecture autorisée pour le chef non officiel")

# --- 7. Chef non officiel tente de modifier (doit échouer) ---
print_separator("7 – Vérification : chef non officiel ne peut PAS modifier (403 attendu)")
r = requests.patch(f"{BASE_URL}/admin/employes/{emp_id}/activer", headers=headers_chef_non_officiel)
assert r.status_code == 403, f"Code attendu 403, reçu {r.status_code}"
log_ok("Modification refusée (403) comme attendu")

# --- 8. Chef officiel rétrograde l'employé ---
print_separator("8 – Chef officiel rétrograde l'employé en employé")
role_data = {"role": "employe"}
r = requests.patch(f"{BASE_URL}/admin/employes/{emp_id}/role", json=role_data, headers=headers_chef)
assert r.status_code == 200
log_ok("Employé rétrogradé en employé")

# --- 9. Reconnexion de l'employé (rôle redevenu employé) ---
print_separator("9 – Reconnexion de l'employé après rétrogradation")
r = requests.post(f"{BASE_URL}/auth/connexion", json=login_emp)
assert r.status_code == 200
token_emp2 = r.json()["access_token"]
headers_emp2 = {"Authorization": f"Bearer {token_emp2}"}
log_ok("Employé reconnecté avec le bon rôle")

# --- 10. L'employé ne peut plus voir /admin/employes ---
print_separator("10 – L'employé ne peut plus accéder à /admin/employes (403 attendu)")
r = requests.get(f"{BASE_URL}/admin/employes", headers=headers_emp2)
assert r.status_code == 403, f"Code attendu 403, reçu {r.status_code}"
log_ok("Accès refusé (403) comme attendu")

# --- 11. Entraînement du modèle ---
print_separator("11 – Entraînement du modèle")
r = requests.post(f"{BASE_URL}/entrainer", headers=headers_chef)
assert r.status_code == 200
data = r.json()
log_ok(f"Modèle entraîné : pente={data['pente']:.4f}, biais={data['biais']:.4f}, R²={data['r2']:.4f}")

# --- 12. Prédiction ---
print_separator("12 – Prédiction")
pred_data = {"suspicious_activities": 50}
r = requests.post(f"{BASE_URL}/predire", json=pred_data, headers=headers_chef)
assert r.status_code == 200
pred = r.json()
log_ok(f"Pour {pred['suspicious_activities']} activités suspectes, incidents estimés : {pred['confirmed_incidents_estimes']}")

# --- 13. Ajout d'observation avec auto-retrain ---
print_separator("13 – Ajout d'observation avec ré-entraînement auto")
obs = {"suspicious_activities": 85, "confirmed_incidents": 18.5}
r = requests.post(f"{BASE_URL}/donnees?auto_retrain=true", json=obs, headers=headers_chef)
assert r.status_code == 200
log_ok(f"Observation ajoutée : {obs}")

# --- 14. Historique des performances ---
print_separator("14 – Historique des performances")
r = requests.get(f"{BASE_URL}/performances?limit=5", headers=headers_chef)
assert r.status_code == 200
hist = r.json()
log_ok(f"{len(hist['historique'])} enregistrements de performances récupérés")

# --- 15. Statistiques pour graphiques ---
print_separator("15 – Données pour graphiques")
r = requests.get(f"{BASE_URL}/statistiques/observations?limit=50", headers=headers_chef)
assert r.status_code == 200
log_ok(f"{r.json()['total']} observations récupérées")

# --- 16. Dashboard stats ---
print_separator("16 – Statistiques tableau de bord")
r = requests.get(f"{BASE_URL}/statistiques/dashboard", headers=headers_chef)
assert r.status_code == 200
stats = r.json()
log_ok(f"Utilisateurs : {stats['utilisateurs']['total']} (dont {stats['utilisateurs']['actifs']} actifs)")

# --- 17. Désactivation de l'employé (par chef officiel) ---
print_separator("17 – Désactivation de l'employé")
r = requests.patch(f"{BASE_URL}/admin/employes/{emp_id}/activer", headers=headers_chef)
assert r.status_code == 200
log_ok("Employé désactivé")

# --- 18. Tentative de connexion de l'employé désactivé (doit échouer) ---
print_separator("18 – Connexion de l'employé désactivé (403 attendu)")
r = requests.post(f"{BASE_URL}/auth/connexion", json=login_emp)
assert r.status_code == 403, f"Code attendu 403, reçu {r.status_code}"
log_ok("Connexion refusée (403) comme attendu")

# --- Fin des tests ---
print("\n" + "="*60)
print(f"{BOLD}{GREEN}🎉 TOUS LES TESTS SONT PASSÉS AVEC SUCCÈS ! 🎉{RESET}")
print("="*60)