from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

# --- Données du modèle ---
class ObservationEntree(BaseModel):
    suspicious_activities: float
    confirmed_incidents: float

class RequetePrediction(BaseModel):
    suspicious_activities: float

class ReponsePrediction(BaseModel):
    suspicious_activities: float
    confirmed_incidents_estimes: float
    unite: str = "incidents"

class ReponseEntrainement(BaseModel):
    message: str
    pente: float
    biais: float
    erreur_moyenne: float
    r2: float
    nombre_observations: int

# --- Authentification ---
class UserLogin(BaseModel):
    nom: str
    prenom: str
    code_acces: str

class UserCreate(BaseModel):
    nom: str
    prenom: str
    role: str = "employe"

class UserOut(BaseModel):
    id: int
    nom: str
    prenom: str
    role: str
    est_actif: bool
    est_adjoint: bool
    est_officiel: bool             
    derniere_activite: Optional[datetime]
    en_ligne: Optional[bool] = False

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    nom_complet: str

# --- Modification de rôle ---
class RequeteChangementRole(BaseModel):
    role: str  # "chef" ou "employe"