import numpy as np
from typing import List, Optional
from schemas import ObservationEntree

class RegresseurLineaire:
    """
    Modèle de régression linéaire simple.
    Respecte strictement les formules du hackathon : covariance / variance.
    """
    def __init__(self):
        self.pente: float = 0.0
        self.biais: float = 0.0
        self.erreur_moyenne: float = 0.0  # EQM (Mean Squared Error)
        self.r2: float = 0.0              # Coefficient de détermination
        self.nombre_observations: int = 0
        self._est_entraine: bool = False

    def entrainer(self, observations: List[ObservationEntree]) -> 'RegresseurLineaire':
        """
        Entraîne le modèle à partir d'une liste d'observations.
        """
        if not observations:
            raise ValueError("Impossible d'entraîner le modèle : la liste d'observations est vide.")

        # 1. Extraction des X et Y
        X = np.array([obs.suspicious_activities for obs in observations])
        Y = np.array([obs.confirmed_incidents for obs in observations])
        n = len(X)

        # 2. Calcul des moyennes
        moyenne_x = np.mean(X)
        moyenne_y = np.mean(Y)

        # 3. Calcul de la covariance (s) et de la variance (f)
        s = np.sum((X - moyenne_x) * (Y - moyenne_y))
        f = np.sum((X - moyenne_x) ** 2)

        # 4. Calcul de la pente et du biais
        if f == 0:
            # Cas dégénéré : tous les X sont identiques, on prédit la moyenne
            self.pente = 0.0
            self.biais = moyenne_y
        else:
            self.pente = s / f
            self.biais = moyenne_y - self.pente * moyenne_x

        # 5. Calcul de l'Erreur Quadratique Moyenne (EQM)
        predictions = self._predire_tableau(X)
        self.erreur_moyenne = np.mean((predictions - Y) ** 2)

        # 6. Calcul du R² (Coefficient de détermination) - INNOVATION
        somme_carres_totale = np.sum((Y - moyenne_y) ** 2)
        somme_carres_residuelle = np.sum((predictions - Y) ** 2)
        
        if somme_carres_totale == 0:
            self.r2 = 1.0
        else:
            self.r2 = 1 - (somme_carres_residuelle / somme_carres_totale)

        self.nombre_observations = n
        self._est_entraine = True

        print(f"   Modèle entraîné avec {n} observations.")
        print(f"   Équation : y = {self.pente:.4f}x + {self.biais:.4f}")
        print(f"   EQM : {self.erreur_moyenne:.4f} | R² : {self.r2:.4f}")

        return self

    def _predire_tableau(self, X: np.ndarray) -> np.ndarray:
        return self.pente * X + self.biais

    def predire(self, x: float) -> float:
        if not self._est_entraine:
            raise RuntimeError("Le modèle n'a pas encore été entraîné.")
        return self.pente * x + self.biais

    def to_dict(self) -> dict:
        return {
            "pente": self.pente,
            "biais": self.biais,
            "erreur_moyenne": self.erreur_moyenne,
            "r2": self.r2,
            "nombre_observations": self.nombre_observations
        }

# --- Gestion du Cache Global (Singleton du modèle) ---
_modele_cache: Optional[RegresseurLineaire] = None

def obtenir_modele() -> Optional[RegresseurLineaire]:
    return _modele_cache

def definir_modele(modele: RegresseurLineaire) -> None:
    global _modele_cache
    _modele_cache = modele

    