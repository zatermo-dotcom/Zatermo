# ilk.medater Cloud — 1.0.0-rc1

ERP/CRM du groupe **ilk.medater** : **eurl medater** (construction, chantiers, marchés publics) et **cabinet ILK** (architecture, bureau d'études pluridisciplinaire). Interface en français, siège virtuel 3D, tableaux de bord classiques, assistant **ilk.medater AI** hybride (local/cloud, facultatif).

> Version candidate issue de la reprise du prototype V0.8. Lire **`docs/07_ETAT_DES_FONCTIONNALITES.md`** : ce qui est testé, ce qui ne l'est pas encore, ce qui manque.

## Démarrage rapide (Windows 11 + Docker Desktop)
```powershell
cd C:\ilk-medater
powershell -ExecutionPolicy Bypass -File scripts\windows\init-secrets.ps1
docker compose up -d --build
powershell -ExecutionPolicy Bypass -File scripts\windows\create-director.ps1 -Email "dg@domaine.dz" -Nom "Nom Prénom"
# puis http://localhost:8080
```
Guide complet : `docs/05_INSTALLATION_WINDOWS.md`.

## Contenu
```
backend/        API FastAPI, migrations SQL, moteurs de calcul, IA, tests
frontend/       Interface web (JS natif) et siège 3D (Three.js 0.160.1 local)
docker/         Initialisation PostgreSQL, configuration nginx
scripts/        Sauvegarde, test de restauration, scripts Windows, serveur de développement
docs/           Audit, architecture, autorisations, IA et calculs, installation, guide, état des fonctionnalités
```

## Règles clés
- **Seul le Directeur général attribue les droits** (contrôlé par l'API et imposé par un trigger PostgreSQL).
- Refus par défaut, moindre privilège, isolation stricte entre les deux filiales.
- MFA obligatoire pour la direction ; journal d'audit chaîné et non modifiable.
- L'IA ne lit que les données autorisées, cite ses sources et ne remplace ni un calcul d'ingénierie ni un avis juridique.

## Développement et tests
```bash
cd backend
pip install -r requirements-dev.txt
# PostgreSQL 16 local avec un rôle propriétaire (CREATEDB) et le rôle ilk_app (mot de passe « apptest » par défaut)
TEST_OWNER_DSN=postgresql://ilk:motdepasse@localhost:5432 python -m pytest -q
```
Serveur de développement sans Docker (API + interface) : `python ../scripts/dev_server.py --port 8080` (variables d'environnement dans le fichier).
Documentation de l'API : `http://localhost:8080/api/docs`.
