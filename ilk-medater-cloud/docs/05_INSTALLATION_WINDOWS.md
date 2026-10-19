# Installation sur Windows 11 (PC du Directeur général)

> Ces étapes n'ont **pas encore été exécutées sur le PC de l'entreprise**. Le code a été testé sous Linux avec PostgreSQL 16, et la configuration Docker Compose a été validée, mais le démarrage complet sous Docker Desktop reste à faire et à constater sur place (voir `07_ETAT_DES_FONCTIONNALITES.md`).

## 1. Prérequis
- Windows 11 à jour, virtualisation activée dans le BIOS.
- **Docker Desktop** avec le moteur WSL 2 (Paramètres → General → « Use the WSL 2 based engine »).
- Espace disque : 15 Go minimum (images, base, documents) ; 30 Go de plus pour l'IA locale.
- À vérifier : génération du processeur i5, espace libre réel du SSD.

## 2. Installation
```powershell
# 1. Copier le dossier du projet dans C:\ilk-medater (disque local, pas un dossier synchronisé)
cd C:\ilk-medater

# 2. Générer les secrets (crée .env, lisible uniquement par votre compte Windows)
powershell -ExecutionPolicy Bypass -File scripts\windows\init-secrets.ps1

# 3. Construire et démarrer (la migration de la base s'exécute automatiquement)
docker compose up -d --build
docker compose ps          # db, api, web, backup doivent être « running » ; migrate « exited (0) »

# 4. Créer l'unique compte Directeur général (mot de passe saisi masqué)
powershell -ExecutionPolicy Bypass -File scripts\windows\create-director.ps1 -Email "dg@votre-domaine.dz" -Nom "Nom Prénom"
```
L'étape 4 affiche **une seule fois** la clé MFA et 10 codes de récupération :
1. Ajoutez la clé dans une application d'authentification (Google Authenticator, Microsoft Authenticator, Aegis).
2. Imprimez les codes de récupération et placez-les sous enveloppe scellée, dans un coffre.

Ouvrez ensuite **http://localhost:8080** et connectez-vous (email, mot de passe, code à 6 chiffres).

## 3. Sauvegardes
- Automatiques toutes les 24 h dans `C:\ilk-medater\backups` (base + documents + empreintes SHA-256), conservées 30 jours.
- Sauvegarde immédiate : `scripts\windows\backup-now.ps1`.
- **Test de restauration** (non destructif, base temporaire) : `scripts\windows\restore-test.ps1` → doit afficher « RESTAURATION VALIDÉE ». À faire chaque mois.
- Copier régulièrement `backups\` **et** le fichier `.env` hors du PC (disque externe chiffré). Sans `.env`, les secrets MFA ne sont pas déchiffrables.

## 4. Accès à distance privé (Tailscale)
Ne jamais ouvrir de port sur la box Internet, ni exposer PostgreSQL.
1. Installer Tailscale sur le PC serveur et sur l'ordinateur ou le téléphone du DG, avec le même compte.
2. Sur le PC serveur : `tailscale serve --bg 8080` → l'interface est servie en HTTPS sur l'adresse privée `https://<nom-du-pc>.<tailnet>.ts.net`.
3. Dans `.env`, passer `COOKIE_SECURE=true`, puis `docker compose up -d api`.
4. Dans la console d'administration Tailscale, limiter l'accès au seul appareil du DG (ACL).

## 5. Mises à jour
```powershell
scripts\windows\backup-now.ps1          # toujours sauvegarder avant
docker compose up -d --build            # applique automatiquement les nouvelles migrations
```
Ne jamais utiliser `docker compose down -v` : l'option `-v` efface la base et les documents.

## 6. Récupération du compte Directeur
- Téléphone perdu : se connecter avec un code de récupération, puis reconfigurer la MFA :
  `docker compose run --rm -it migrate python -m app.cli reset-director-mfa`
- Mot de passe oublié : `docker compose run --rm -it migrate python -m app.cli reset-director-password`
- Vérifier l'intégrité du journal : `docker compose run --rm migrate python -m app.cli verify-audit`

Ces commandes exigent un accès administrateur au PC serveur : protéger la session Windows (mot de passe fort, BitLocker).

## 7. Dépannage
| Symptôme | Action |
|---|---|
| `migrate` en erreur | `docker compose logs migrate` (une migration modifiée après application est refusée) |
| Page blanche | `docker compose logs web api` ; vérifier http://localhost:8080/api/health |
| « Compte temporairement verrouillé » | Attendre 15 minutes, ou le Directeur réinitialise le mot de passe |
| 3D absente | Le poste ne prend pas en charge WebGL : la liste des bureaux et le menu restent utilisables |
