# 📦 RENAME - Présentation des outils et exemples concrets

Bienvenue dans le dossier RENAME ! Ici tu trouveras trois outils différents pour renommer et organiser automatiquement tes images PNG. Voici une présentation claire de chaque version, avec des exemples concrets pour bien choisir.

---

## 🟢 ReMaze (exécutable Windows, ultra simple)
- **Pour qui ?** : Pour celles et ceux qui veulent juste double-cliquer et que tout fonctionne, sans rien installer.
- **Ce que ça fait :**
  - Surveille un dossier de ton choix.
  - Renomme automatiquement chaque nouvelle image PNG ajoutée (ex : `Horizon_01.png`, `Horizon_02.png`, ...).
  - Menu interactif pour changer de dossier, de nom, ou réorganiser.
- **Exemple concret :**
  1. Tu ouvres le dossier `ReMaze`.
  2. Tu double-cliques sur `ReMaze.exe`.
  3. Tu choisis le dossier où tu mets tes images (par exemple : `C:\Users\bissi\Pictures\Vacances`).
  4. Tu ajoutes des images dans ce dossier, elles sont renommées automatiquement.

---

## 🟡 rename_images_watcher_optimized (script Python optimisé)
- **Pour qui ?** : Pour ceux qui ont Python et veulent un script rapide, personnalisable, et efficace.
- **Ce que ça fait :**
  - Même principe que ReMaze, mais en version script Python.
  - Plus rapide et gère mieux les gros dossiers.
- **Exemple concret :**
  1. Tu vas dans le dossier `rename_images_watcher_optimized`.
  2. Tu ouvres un terminal ici.
  3. Tu installes la librairie :
     ```sh
     pip install watchdog
     ```
  4. Tu lances le script :
     ```sh
     python rename_images_watcher_optimized.py
     ```
  5. Tu suis les instructions pour choisir le dossier à surveiller.
  6. Tu ajoutes des images dans ce dossier, elles sont renommées automatiquement.

---

## 🟠 rename_images_watcher (script Python classique)
- **Pour qui ?** : Pour ceux qui veulent un script simple, facile à lire et à modifier.
- **Ce que ça fait :**
  - Surveille un dossier et renomme les images PNG automatiquement.
  - Code plus simple, idéal pour apprendre ou adapter à ses besoins.
- **Exemple concret :**
  1. Tu vas dans le dossier `rename_images_watcher`.
  2. Tu ouvres un terminal ici.
  3. Tu installes la librairie :
     ```sh
     pip install watchdog
     ```
  4. Tu lances le script :
     ```sh
     python rename_images_watcher.py
     ```
  5. Tu suis les instructions pour choisir le dossier à surveiller.
  6. Tu ajoutes des images dans ce dossier, elles sont renommées automatiquement.

---

## 📝 Conseils
- Chaque dossier contient un README détaillé pour t'aider pas à pas.
- Si tu veux la solution la plus simple : **ReMaze**.
- Si tu veux personnaliser ou utiliser sur Mac/Linux : prends une version Python.

---

Bonne organisation de tes images ! 😊
