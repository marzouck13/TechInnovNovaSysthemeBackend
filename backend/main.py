from fastapi import FastAPI, Depends, HTTPException, status, Request, WebSocket, WebSocketDisconnect
from fastapi.security import OAuth2PasswordBearer
from typing import List
from datetime import datetime, timedelta, timezone
import json
import asyncio

from database import get_db
from schemas import *
from ml_model import RegresseurLineaire, obtenir_modele, definir_modele
from auth import (
    verifier_code, generer_code_aleatoire, hacher_code,
    creer_token, obtenir_utilisateur_courant, obtenir_chef_courant, obtenir_chef_officiel_courant,
    decoder_token
)

from rate_limiter import limiter, configure_rate_limiter
from logger import logging_middleware, get_logger
from websocket_manager import manager

app = FastAPI(
    title="Nova Systems - Smart Incident Estimator PRO",
    description="Backend IA avec authentification, gestion des rôles, adjoints, suivi des connexions, apprentissage continu, rate limiting et logs structurés.",
    version="2.0.0"
)

configure_rate_limiter(app)
app.middleware("http")(logging_middleware)

@app.middleware("http")
async def suivre_activite(request: Request, call_next):
    response = await call_next(request)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "")
        try:
            payload = decoder_token(token)
            if payload:
                user_id = payload.get("sub")
                if user_id:
                    db = get_db()
                    db.table("users").update({
                        "derniere_activite": datetime.now(timezone.utc).isoformat()
                    }).eq("id", int(user_id)).execute()
        except Exception:
            pass
    return response

@app.on_event("startup")
def initialiser_chef():
    logger = get_logger("startup")
    logger.info("Vérification de la présence du chef officiel...")
    db = get_db()
    try:
        res = db.table("users").select("*").eq("role", "chef").execute()
        if not res.data:
            code_clair = generer_code_aleatoire(7)
            code_hash = hacher_code(code_clair)
            db.table("users").insert({
                "nom": "NOVA",
                "prenom": "ADMIN",
                "code_acces_hash": code_hash,
                "role": "chef",
                "est_actif": True,
                "est_adjoint": False,
                "est_officiel": True,
                "derniere_activite": datetime.now(timezone.utc).isoformat()
            }).execute()
            print("\n" + "="*60)
            print(" CHEF OFFICIEL CRÉÉ AUTOMATIQUEMENT !")
            print(f"    Nom: NOVA")
            print(f"    Prénom: ADMIN")
            print(f"    CODE D'ACCÈS: {code_clair}")
            print("     Gardez ce code précieusement pour la connexion.")
            print("="*60 + "\n")
            logger.info("Chef officiel créé", code=code_clair)
        else:
            officiel = db.table("users").select("*").eq("role", "chef").eq("est_officiel", True).execute()
            if not officiel.data:
                premier = db.table("users").select("*").eq("role", "chef").order("created_at").limit(1).execute()
                if premier.data:
                    db.table("users").update({"est_officiel": True}).eq("id", premier.data[0]["id"]).execute()
                    logger.info("Chef officiel défini (premier chef trouvé).")
            logger.info("Chef déjà présent dans la base.")
    except Exception as e:
        logger.error("Erreur lors de l'initialisation du chef", error=str(e))

@app.get("/")
def lire_racine():
    return {"message": "Bienvenue sur l'API Nova Systems. Rendez-vous sur /docs pour la documentation."}

@app.post("/auth/connexion", response_model=Token)
@limiter.limit("5/minute")
async def connexion(login_data: UserLogin, request: Request):
    db = get_db()
    try:
        response = db.table("users") \
            .select("*") \
            .eq("nom", login_data.nom) \
            .eq("prenom", login_data.prenom) \
            .execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur base de données : {str(e)}")
    if not response.data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Identifiants incorrects (nom, prénom ou code invalide).")
    user = response.data[0]
    if not verifier_code(login_data.code_acces, user["code_acces_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Identifiants incorrects.")
    if not user["est_actif"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Compte désactivé. Veuillez contacter le chef officiel.")
    db.table("users").update({
        "derniere_activite": datetime.now(timezone.utc).isoformat()
    }).eq("id", user["id"]).execute()
    token = creer_token({"sub": str(user["id"]), "role": user["role"]})
    return Token(
        access_token=token,
        token_type="bearer",
        role=user["role"],
        nom_complet=f"{user['prenom']} {user['nom']}"
    )

@app.get("/admin/employes", response_model=List[UserOut])
async def lister_employes(chef = Depends(obtenir_chef_courant)):
    db = get_db()
    response = db.table("users").select("*").order("id").execute()
    users = response.data
    maintenant = datetime.now(timezone.utc)
    seuil = maintenant - timedelta(minutes=5)
    for user in users:
        derniere = user.get("derniere_activite")
        if derniere:
            if isinstance(derniere, str):
                if derniere.endswith('Z'):
                    derniere = derniere.replace('Z', '+00:00')
                derniere = datetime.fromisoformat(derniere)
            user["en_ligne"] = derniere > seuil
        else:
            user["en_ligne"] = False
        user.setdefault("est_adjoint", False)
        user.setdefault("est_officiel", False)
    return users

@app.get("/admin/employes/en-ligne", response_model=List[UserOut])
async def get_utilisateurs_en_ligne(chef = Depends(obtenir_chef_courant)):
    db = get_db()
    response = db.table("users").select("*").order("id").execute()
    users = response.data
    maintenant = datetime.now(timezone.utc)
    seuil = maintenant - timedelta(minutes=5)
    for user in users:
        derniere = user.get("derniere_activite")
        if derniere:
            if isinstance(derniere, str):
                if derniere.endswith('Z'):
                    derniere = derniere.replace('Z', '+00:00')
                derniere = datetime.fromisoformat(derniere)
            user["en_ligne"] = derniere > seuil
        else:
            user["en_ligne"] = False
        user.setdefault("est_adjoint", False)
        user.setdefault("est_officiel", False)
    return users

@app.post("/admin/employes", response_model=dict)
@limiter.limit("10/minute")
async def ajouter_employe(employe: UserCreate, request: Request, chef = Depends(obtenir_chef_officiel_courant)):
    db = get_db()
    existant = db.table("users") \
        .select("*") \
        .eq("nom", employe.nom) \
        .eq("prenom", employe.prenom) \
        .execute()
    if existant.data:
        raise HTTPException(status_code=400, detail="Cet employé existe déjà.")
    code_clair = generer_code_aleatoire(7)
    code_hash = hacher_code(code_clair)
    try:
        db.table("users").insert({
            "nom": employe.nom,
            "prenom": employe.prenom,
            "code_acces_hash": code_hash,
            "role": "employe",
            "est_actif": True,
            "est_adjoint": False,
            "est_officiel": False,
            "derniere_activite": datetime.now(timezone.utc).isoformat()
        }).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur insertion : {str(e)}")
    return {
        "message": f"Employé {employe.prenom} {employe.nom} ajouté avec succès.",
        "code_acces_employe": code_clair,
        "consigne": "Transmettez ce code de 7 caractères à l'employé pour sa connexion."
    }

@app.patch("/admin/employes/{user_id}/activer", response_model=dict)
async def basculer_etat_employe(user_id: int, chef = Depends(obtenir_chef_officiel_courant)):
    db = get_db()
    user = db.table("users").select("*").eq("id", user_id).execute()
    if not user.data:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    user_data = user.data[0]
    if user_data["role"] == "chef" and user_data.get("est_officiel"):
        raise HTTPException(status_code=403, detail="Impossible de désactiver le chef officiel.")
    nouveau_statut = not user_data["est_actif"]
    db.table("users").update({"est_actif": nouveau_statut}).eq("id", user_id).execute()
    return {
        "message": f"Compte de {user_data['prenom']} {user_data['nom']} mis à jour.",
        "est_actif": nouveau_statut
    }

@app.patch("/admin/employes/{user_id}/role", response_model=dict)
async def modifier_role_employe(
    user_id: int,
    requete: RequeteChangementRole,
    chef = Depends(obtenir_chef_officiel_courant)
):
    db = get_db()
    user = db.table("users").select("*").eq("id", user_id).execute()
    if not user.data:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    user_data = user.data[0]
    if user_data["id"] == chef["id"]:
        raise HTTPException(status_code=403, detail="Vous ne pouvez pas modifier votre propre rôle.")
    nouveau_role = requete.role
    if nouveau_role not in ("chef", "employe"):
        raise HTTPException(status_code=400, detail="Le rôle doit être 'chef' ou 'employe'.")
    if nouveau_role == "chef":
        db.table("users").update({
            "role": "chef",
            "est_officiel": False
        }).eq("id", user_id).execute()
    else:
        db.table("users").update({
            "role": "employe",
            "est_officiel": False
        }).eq("id", user_id).execute()
    return {
        "message": f"Le rôle de {user_data['prenom']} {user_data['nom']} a été changé en '{nouveau_role}'.",
        "user_id": user_id,
        "nouveau_role": nouveau_role
    }

@app.patch("/admin/employes/{user_id}/adjoint", response_model=dict)
async def basculer_statut_adjoint(
    user_id: int,
    chef = Depends(obtenir_chef_officiel_courant)
):
    db = get_db()
    user = db.table("users").select("*").eq("id", user_id).execute()
    if not user.data:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    user_data = user.data[0]
    if user_data.get("est_officiel"):
        raise HTTPException(status_code=403, detail="Impossible de modifier le statut du chef officiel.")
    nouveau_statut = not user_data.get("est_adjoint", False)
    db.table("users").update({"est_adjoint": nouveau_statut}).eq("id", user_id).execute()
    return {
        "message": f"Le statut adjoint de {user_data['prenom']} {user_data['nom']} est maintenant {nouveau_statut}.",
        "user_id": user_id,
        "est_adjoint": nouveau_statut
    }

@app.post("/entrainer", response_model=ReponseEntrainement)
@limiter.limit("2/minute")
async def entrainer_modele(request: Request, user = Depends(obtenir_utilisateur_courant)):
    db = get_db()
    try:
        response = db.table("observations").select("*").execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur Supabase : {str(e)}")
    if not response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Aucune donnée trouvée dans la table 'observations'.")
    observations = [ObservationEntree(**row) for row in response.data]
    modele = RegresseurLineaire()
    modele.entrainer(observations)
    try:
        db.table("model_performances").insert({
            "pente": modele.pente,
            "biais": modele.biais,
            "erreur_moyenne": modele.erreur_moyenne,
            "r2": modele.r2,
            "nombre_observations": modele.nombre_observations,
            "trained_at": datetime.now(timezone.utc).isoformat()
        }).execute()
    except Exception as e:
        logger = get_logger("ml")
        logger.error("Erreur lors de la sauvegarde des métriques", error=str(e))
    definir_modele(modele)
    return ReponseEntrainement(
        message="Modèle entraîné avec succès.",
        pente=modele.pente,
        biais=modele.biais,
        erreur_moyenne=modele.erreur_moyenne,
        r2=modele.r2,
        nombre_observations=modele.nombre_observations
    )

@app.post("/predire", response_model=ReponsePrediction)
@limiter.limit("30/minute")
async def predire_incident(requete: RequetePrediction, request: Request, user = Depends(obtenir_utilisateur_courant)):
    modele = obtenir_modele()
    if modele is None:
        try:
            db = get_db()
            response = db.table("observations").select("*").execute()
            if response.data:
                observations = [ObservationEntree(**row) for row in response.data]
                modele = RegresseurLineaire()
                modele.entrainer(observations)
                definir_modele(modele)
            else:
                raise HTTPException(status_code=503, detail="Aucune donnée pour entraîner le modèle.")
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Impossible d'entraîner : {str(e)}")
    if requete.suspicious_activities < 0:
        raise HTTPException(status_code=400, detail="La valeur ne peut pas être négative.")
    prediction = modele.predire(requete.suspicious_activities)
    prediction_arrondie = round(max(0, prediction), 2)
    return ReponsePrediction(
        suspicious_activities=requete.suspicious_activities,
        confirmed_incidents_estimes=prediction_arrondie
    )

@app.post("/donnees")
@limiter.limit("10/minute")
async def ajouter_observation(
    observation: ObservationEntree,
    request: Request,
    auto_retrain: bool = True,
    user = Depends(obtenir_utilisateur_courant)
):
    db = get_db()
    if observation.suspicious_activities < 0 or observation.confirmed_incidents < 0:
        raise HTTPException(status_code=400, detail="Les valeurs ne peuvent pas être négatives.")
    try:
        db.table("observations").insert({
            "suspicious_activities": observation.suspicious_activities,
            "confirmed_incidents": observation.confirmed_incidents,
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur Supabase : {str(e)}")
    if auto_retrain:
        try:
            response = db.table("observations").select("*").execute()
            if response.data:
                observations = [ObservationEntree(**row) for row in response.data]
                modele = RegresseurLineaire()
                modele.entrainer(observations)
                definir_modele(modele)
                db.table("model_performances").insert({
                    "pente": modele.pente,
                    "biais": modele.biais,
                    "erreur_moyenne": modele.erreur_moyenne,
                    "r2": modele.r2,
                    "nombre_observations": modele.nombre_observations,
                    "trained_at": datetime.now(timezone.utc).isoformat()
                }).execute()
                message = "Observation ajoutée et modèle ré-entraîné instantanément."
            else:
                message = "Observation ajoutée mais impossible de ré-entraîner."
        except Exception as e:
            message = f"Observation ajoutée, mais le ré-entraînement a échoué : {str(e)}"
    else:
        message = "Observation ajoutée. Lancez /entrainer pour mettre à jour le modèle."
    return {"message": message, "donnee": observation.dict()}

@app.get("/performances")
async def lire_historique_performances(limit: int = 10, user = Depends(obtenir_utilisateur_courant)):
    db = get_db()
    try:
        response = db.table("model_performances") \
                        .select("*") \
                        .order("trained_at", desc=True) \
                        .limit(limit) \
                        .execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur Supabase : {str(e)}")
    return {"historique": response.data}

@app.get("/sante")
async def verifier_sante():
    modele = obtenir_modele()
    db = get_db()
    try:
        db.table("users").select("count").limit(1).execute()
        base_ok = True
    except:
        base_ok = False
    return {
        "statut": "opérationnel",
        "modele_charge": modele is not None,
        "base_connectee": base_ok
    }

@app.get("/statistiques/observations")
async def get_observations_graphiques(limit: int = 100, user = Depends(obtenir_utilisateur_courant)):
    db = get_db()
    try:
        response = db.table("observations") \
                        .select("id, suspicious_activities, confirmed_incidents, created_at") \
                        .order("created_at", desc=False) \
                        .limit(limit) \
                        .execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur Supabase : {str(e)}")
    return {
        "donnees": response.data,
        "total": len(response.data),
        "message": "Données prêtes pour les graphiques."
    }

@app.get("/statistiques/dashboard")
async def get_dashboard_stats(user = Depends(obtenir_utilisateur_courant)):
    db = get_db()
    obs_count = db.table("observations").select("id", count="exact").execute()
    total_observations = obs_count.count if hasattr(obs_count, 'count') else 0
    perf = db.table("model_performances") \
               .select("*") \
               .order("trained_at", desc=True) \
               .limit(1) \
               .execute()
    derniere_performance = perf.data[0] if perf.data else None
    users = db.table("users").select("*").execute()
    total_utilisateurs = len(users.data)
    actifs = sum(1 for u in users.data if u["est_actif"])
    chefs = sum(1 for u in users.data if u["role"] == "chef")
    employes = sum(1 for u in users.data if u["role"] == "employe")
    return {
        "observations": {"total": total_observations},
        "modele": {
            "dernier_r2": derniere_performance["r2"] if derniere_performance else None,
            "dernier_eqm": derniere_performance["erreur_moyenne"] if derniere_performance else None,
            "derniere_pente": derniere_performance["pente"] if derniere_performance else None,
            "dernier_biais": derniere_performance["biais"] if derniere_performance else None,
            "derniere_date": derniere_performance["trained_at"] if derniere_performance else None
        },
        "utilisateurs": {
            "total": total_utilisateurs,
            "actifs": actifs,
            "chefs": chefs,
            "employes": employes
        }
    }

@app.websocket("/ws/en-ligne")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            db = get_db()
            users_response = db.table("users").select("*").execute()
            maintenant = datetime.now(timezone.utc)
            seuil = maintenant - timedelta(minutes=5)
            en_ligne = []
            for u in users_response.data:
                derniere = u.get("derniere_activite")
                if derniere:
                    if isinstance(derniere, str):
                        if derniere.endswith('Z'):
                            derniere = derniere.replace('Z', '+00:00')
                        derniere = datetime.fromisoformat(derniere)
                    if derniere > seuil:
                        en_ligne.append({
                            "id": u["id"],
                            "nom": u["nom"],
                            "prenom": u["prenom"],
                            "role": u["role"]
                        })
            await websocket.send_text(json.dumps({
                "type": "users_update",
                "data": en_ligne,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }))
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# FIN DU FICHIER