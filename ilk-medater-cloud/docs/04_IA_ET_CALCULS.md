# ilk.medater AI et moteurs de calcul

## Fonctionnement sans dépendance obligatoire
Sans aucun modèle installé, l'assistant fonctionne en **mode règles** : il interroge les données autorisées et renvoie une synthèse factuelle sourcée, sans générer de texte. Les modèles locaux et cloud sont des options.

## Routeur local / cloud
1. Vérifier que l'IA est activée pour l'utilisateur (décision du Directeur) et que l'assistant choisi couvre au moins un module autorisé.
2. Collecter les **sources autorisées** (projets, chantiers, livrables, conflits MEP, marchés, factures, synthèse RH, QHSE, titres de documents, références juridiques vérifiées), numérotées `[S1]`, `[S2]`…
3. Choisir le moteur :
   - **cloud** seulement si : demandé ou jugé complexe (rédaction, analyse), autorisé par le Directeur, configuré, consentement donné pour la demande **et** aucune source confidentielle (finances, RH, document confidentiel) ;
   - sinon **local** (Ollama) s'il est joignable, sinon **règles**.
4. Avant tout envoi cloud : masquage des emails, téléphones algériens, NIF, RIB, IBAN.
5. Après génération : toute citation `[S#]` qui ne correspond à aucune source est retirée et signalée ; une réponse sans citation est signalée « à vérifier ».
6. Journalisation : question, réponse, moteur, sources, nombre de masquages (`ai_requests` + audit).

## Assistants (15)
Direction générale · Coordinateur MEP · MEP 01 Courant fort · MEP 02 Courants faibles · MEP 03 Incendie · MEP 04 Plomberie · MEP 05 HVAC · MEP 06 Aéraulique · Architecture · Génie civil · Juriste (droit algérien) · Conduite de chantier · Études de prix · Finances · RH.

## Garde-fou juridique
L'assistant juridique ne répond **que** s'il existe des références vérifiées et en vigueur dans la « Base juridique ». Sinon il répond qu'aucune référence officielle vérifiée n'est disponible. Une référence n'est vérifiable que si elle porte une source officielle (URL ou Journal officiel), et sa vérification doit être faite par une autre personne que celle qui l'a saisie. Le logiciel n'embarque aucun texte de loi.

## Moteurs de calcul (déterministes, versionnés, tracés dans `calc_runs`)

| Code | Spécialité | Méthode |
|---|---|---|
| `cfo.power_balance` | MEP 01 | P = Σ q·Pu·ku × ks ; Q via tanφ ; S, courant, réserve |
| `cfo.cable_drop` | MEP 01 | ΔU = b(ρ1·L/S·cosφ + λ·L·sinφ)·Ib, section minimale normalisée |
| `cfa.vdi` | MEP 02 | Ports VDI, bornes Wi-Fi, PoE, commutateurs, longueur des liens |
| `fire.extinguishers` | MEP 03 | Extincteurs par niveau, détecteurs selon la couverture saisie |
| `plumb.cold_water` | MEP 04 | Débit probable Qp = y·ΣQb, y = 0,8/√(x−1), diamètre |
| `plumb.rainwater` | MEP 04 | Q = C·i·A (intensité du site obligatoire) |
| `hvac.cooling` | MEP 05 | Bilan frigorifique simplifié en régime permanent |
| `air.duct` | MEP 06 | Diamètre normalisé, Swamee-Jain, pertes linéaires et singulières |
| `air.renewal` | MEP 06 | Débit par occupant ou par taux de renouvellement |
| `gc.column` | Génie civil | Nu = 1,35G + 1,5Q ; section de poteau BA, minimum sismique par zone |

Chaque résultat porte l'avertissement : **pré-dimensionnement indicatif, à vérifier et signer par un ingénieur habilité**. Les valeurs dépendant du site (climat, pluviométrie) ou du texte applicable ne sont jamais inventées : ce sont des entrées, ou des valeurs par défaut marquées « à confirmer ». Les valeurs de chaque moteur sont vérifiées par des tests calculés à la main (`tests/test_engines.py`).

## Installer l'IA locale (facultatif)
```powershell
# dans .env : OLLAMA_URL=http://ollama:11434
docker compose --profile ia-locale up -d
docker compose exec ollama ollama pull qwen2.5:7b-instruct
docker compose up -d api   # relit .env
```
Sur un i5 / 16 Go sans GPU, un modèle 7B quantifié répond en général en plusieurs dizaines de secondes : à mesurer sur le poste réel. Le modèle n'accède jamais directement à la base : il ne reçoit que les sources déjà filtrées.

## Activer l'IA cloud (facultatif)
Renseigner dans `.env` : `CLOUD_AI_PROVIDER=anthropic`, `CLOUD_AI_API_KEY=…` (clé API distincte d'un abonnement grand public), puis `docker compose up -d api`. Par défaut, le modèle est `claude-opus-5-5`, avec la bascule automatique côté serveur en cas de refus. Avant l'activation, faire valider par la Direction et le juriste le transfert de données hors d'Algérie.
