# Notice d'utilisation de rename_images_watcher.py

Bienvenue ! 🎉

Ce script Python surveille un dossier et renomme automatiquement toutes les images PNG pour toi. Il est pensé pour être simple à utiliser, même si tu n'es pas informaticienne !

---

## ✨ À quoi ça sert ?
- Dès qu'une image PNG arrive dans ton dossier, elle est renommée joliment (ex : `Horizon_01.png`, `Horizon_02.png`, etc.)
- Il range aussi les images déjà présentes pour qu'elles aient toutes un nom propre et dans l'ordre.

---

## 🛠️ Installation (une seule fois)
1. **Installe Python** (si ce n'est pas déjà fait) :
   - Va sur https://www.python.org/downloads/ et installe la version recommandée.
2. **Ouvre l'invite de commandes** (touche Windows, tape "cmd" et Entrée).
3. **Installe les bibliothèques nécessaires** :
   Copie-colle cette ligne puis appuie sur Entrée :
   
   ```sh
   pip install watchdog
   ```

---

## 🚀 Comment l'utiliser ?
1. Place le fichier `rename_images_watcher.py` dans le dossier de ton choix (ou laisse-le où il est).
2. Ouvre l'invite de commandes dans ce dossier (clic droit + "Ouvrir dans le terminal").
3. Lance le script avec :
   
   ```sh
   python rename_images_watcher.py
   ```
4. Laisse-toi guider :
   - Choisis ou ajoute le dossier à surveiller (celui où tu mets tes images PNG)
   - Donne un nom (préfixe) si tu veux, ou laisse celui proposé
   - Tape `menu` à tout moment pour voir les options
   - Tape `quit` ou `q` pour arrêter le programme

C'est tout ! Tant que le programme est ouvert, il s'occupe de tout automatiquement. Tu peux continuer à ajouter des images dans le dossier, il les rangera tout seul.

---

## 📝 Astuces
- Tu peux changer de dossier ou de nom à tout moment via le menu.
- Le programme garde en mémoire tes choix pour la prochaine fois.
- Si tu fermes la fenêtre, la surveillance s'arrête (c'est normal !)

---

## ❓ En cas de souci
- Vérifie que tu as bien mis tes images dans le bon dossier.
- Si tu as une erreur "module introuvable", recommence l'installation avec :
  ```sh
  pip install watchdog
  ```
- Pour toute question, demande-moi !

---

Merci d'utiliser ce script ! 😊
