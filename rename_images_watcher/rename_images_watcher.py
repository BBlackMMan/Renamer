#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de surveillance et renommage automatique d'images PNG, JPG et JPEG en temps réel (Version optimisée)
Surveille un dossier en continu et renomme automatiquement les nouveaux fichiers PNG, JPG et JPEG.
Optimisé pour un usage minimal des ressources système.
"""

import os
import re
import time
import json
import threading
from pathlib import Path
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class ImageRenameHandler(FileSystemEventHandler):
    """Gestionnaire d'événements optimisé pour surveiller les fichiers PNG, JPG et JPEG."""
    
    def __init__(self, prefix="Horizon"):
        self.prefix = prefix
        self.processing = False
        self.last_event_time = {}  # Cache pour éviter les événements multiples
        self.debounce_delay = 1.5  # Délai anti-rebond augmenté pour les captures d'écran
        self.temp_files = set()  # Fichiers temporaires créés par le script
        self.processing_lock = threading.Lock()  # Verrou pour éviter les conflits
        
    def on_created(self, event):
        """Appelé quand un nouveau fichier est créé."""
        if not event.is_directory:
            file_path_lower = event.src_path.lower()
            if file_path_lower.endswith('.png') or file_path_lower.endswith('.jpg') or file_path_lower.endswith('.jpeg'):
                file_name = Path(event.src_path).name
                # Ignorer les fichiers temporaires créés par le script
                if file_name.startswith('TEMP_') or file_name in self.temp_files:
                    return
                print(f"🔍 Événement détecté - Fichier créé: {event.src_path}")
                self._debounced_process(event.src_path)
    
    def on_modified(self, event):
        """Appelé quand un fichier est modifié."""
        if not event.is_directory:
            file_path_lower = event.src_path.lower()
            if file_path_lower.endswith('.png') or file_path_lower.endswith('.jpg') or file_path_lower.endswith('.jpeg'):
                file_name = Path(event.src_path).name
                # Ignorer les fichiers temporaires et les fichiers déjà traités récemment
                if file_name.startswith('TEMP_') or file_name in self.temp_files:
                    return
                # Réduire les événements de modification redondants
                if self.is_already_renamed(file_name):
                    return
                print(f"🔍 Événement détecté - Fichier modifié: {event.src_path}")
                self._debounced_process(event.src_path)
    
    def on_moved(self, event):
        """Appelé quand un fichier est déplacé/renommé."""
        if not event.is_directory:
            file_path_lower = event.dest_path.lower()
            if file_path_lower.endswith('.png') or file_path_lower.endswith('.jpg') or file_path_lower.endswith('.jpeg'):
                file_name = Path(event.dest_path).name
                # Ignorer les fichiers temporaires
                if file_name.startswith('TEMP_'):
                    return
                print(f"🔍 Événement détecté - Fichier déplacé: {event.dest_path}")
                self._debounced_process(event.dest_path)
    
    def _debounced_process(self, file_path):
        """Traitement avec anti-rebond pour éviter les événements multiples."""
        current_time = time.time()
        
        # Vérifier si cet événement est trop récent par rapport au précédent
        if file_path in self.last_event_time:
            time_diff = current_time - self.last_event_time[file_path]
            if time_diff < self.debounce_delay:
                print(f"🔄 Événement ignoré (debounce {time_diff:.1f}s < {self.debounce_delay}s): {Path(file_path).name}")
                return  # Ignorer cet événement (trop récent)
        
        self.last_event_time[file_path] = current_time
        
        print(f"✅ Événement accepté pour traitement: {Path(file_path).name}")
        
        # Traiter le fichier dans un thread séparé pour ne pas bloquer
        threading.Thread(target=self.process_new_file, args=(file_path,), daemon=True).start()
    
    def process_new_file(self, file_path):
        """Traite un nouveau fichier PNG détecté."""
        try:
            file_path = Path(file_path)
            
            # Vérifier si le fichier existe avec système de retry
            if not file_path.exists():
                print(f"⚠️ Fichier pas encore disponible, tentative de retry: {file_path.name}")
                # Attendre un peu plus et re-essayer
                time.sleep(1.0)
                if not file_path.exists():
                    print(f"⚠️ Fichier introuvable après retry: {file_path.name}")
                    return
                print(f"✅ Fichier trouvé après retry: {file_path.name}")
                
            if self.is_already_renamed(file_path.name):
                print(f"⚠️ Fichier déjà renommé: {file_path.name}")
                return
            
            # Vérifier si un autre thread traite déjà ce fichier spécifique
            with self.processing_lock:
                if self.processing:
                    print(f"⚠️ Traitement en cours, fichier ignoré: {file_path.name}")
                    return
                self.processing = True
            
            try:
                # Attendre que le fichier soit stable avec timeout plus long
                print(f"🔄 Attente de stabilisation: {file_path.name}")
                if not self.wait_for_file_stable(file_path, timeout=5):
                    print(f"⚠️ Fichier non stable, ignoré: {file_path.name}")
                    return
                
                print(f"\n🆕 Nouveau fichier détecté: {file_path.name}")
                # Réorganiser tous les fichiers
                self.reorganize_all_files(file_path.parent)
                
                # Nettoyer le cache des événements anciens
                self._cleanup_event_cache()
                
            finally:
                with self.processing_lock:
                    self.processing = False
                
        except Exception as e:
            print(f"❌ Erreur lors du traitement de {file_path}: {e}")
            with self.processing_lock:
                self.processing = False
    
    def _cleanup_event_cache(self):
        """Nettoie le cache des événements anciens pour économiser la mémoire."""
        current_time = time.time()
        cutoff_time = current_time - (self.debounce_delay * 5)  # Garder 5x le délai
        
        self.last_event_time = {
            path: timestamp for path, timestamp in self.last_event_time.items()
            if timestamp > cutoff_time
        }
    
    def wait_for_file_stable(self, file_path, timeout=5):
        """Attend que le fichier soit stable (optimisé pour être plus rapide)."""
        start_time = time.time()
        last_size = -1
        stable_count = 0
        
        while time.time() - start_time < timeout:
            try:
                if not file_path.exists():
                    print(f"⚠️ Fichier disparu pendant l'attente: {file_path.name}")
                    return False
                    
                current_size = file_path.stat().st_size
                
                # Si le fichier a une taille valide
                if current_size > 0:
                    if current_size == last_size:
                        stable_count += 1
                        # Considérer stable après 2 vérifications identiques pour être plus sûr
                        if stable_count >= 2:
                            print(f"✅ Fichier stable ({current_size} bytes): {file_path.name}")
                            return True
                    else:
                        stable_count = 0
                
                last_size = current_size
                time.sleep(0.2)  # Interval adapté
                
            except (OSError, FileNotFoundError) as e:
                print(f"⚠️ Erreur d'accès au fichier {file_path.name}: {e}")
                return False
        
        # Si on sort de la boucle par timeout, accepter le fichier s'il a une taille > 0
        try:
            final_size = file_path.stat().st_size
            if final_size > 0:
                print(f"⚠️ Timeout atteint, fichier accepté ({final_size} bytes): {file_path.name}")
                return True
        except:
            pass
            
        print(f"❌ Fichier non stable après {timeout}s: {file_path.name}")
        return False
    
    def is_already_renamed(self, filename):
        """Vérifie si un fichier a déjà été renommé."""
        pattern = rf"^{self.prefix}_\d{{2,}}\.(png|jpg|jpeg)$"
        return bool(re.match(pattern, filename, re.IGNORECASE))
    
    def get_creation_time(self, file_path):
        """Obtient la date de création d'un fichier."""
        return os.path.getctime(file_path)
    
    def check_existing_files(self, directory):
        """Vérifie et traite les fichiers PNG, JPG et JPEG existants au démarrage."""
        try:
            # Trouver tous les fichiers d'image existants
            image_files = []
            for ext in ["*.png", "*.jpg", "*.jpeg"]:
                image_files.extend(list(directory.glob(ext)))
                image_files.extend(list(directory.glob(ext.upper())))
            
            if not image_files:
                return 0
            
            # Séparer les fichiers déjà renommés des nouveaux
            new_files = []
            for file_path in image_files:
                if not self.is_already_renamed(file_path.name):
                    new_files.append(file_path)
            
            if not new_files:
                return 0
            
            print(f"📋 {len(new_files)} fichiers non renommés trouvés")
            
            # Traiter les fichiers existants (réorganisation complète)
            self.reorganize_all_files(directory)
            
            return len(new_files)
            
        except Exception as e:
            print(f"❌ Erreur lors de la vérification initiale: {e}")
            return 0
    
    def reorganize_all_files(self, directory):
        """Réorganise tous les fichiers PNG, JPG et JPEG du dossier."""
        try:
            # Trouver tous les fichiers d'image
            image_files = []
            for ext in ["*.png", "*.jpg", "*.jpeg"]:
                image_files.extend(list(directory.glob(ext)))
                image_files.extend(list(directory.glob(ext.upper())))
            
            if not image_files:
                return
            
            # Trier par date de création
            all_files = image_files.copy()
            all_files.sort(key=lambda x: self.get_creation_time(x))
            
            # Créer la liste des renommages nécessaires
            temp_names = []
            files_to_rename = []
            
            for i, file_path in enumerate(all_files):
                # Préserver l'extension originale
                ext = file_path.suffix.lower()
                expected_name = f"{self.prefix}_{i+1:02d}{ext}"
                current_name = file_path.name
                
                if current_name != expected_name:
                    temp_name = f"TEMP_{i+1:02d}_{self.prefix}{ext}"
                    temp_names.append((file_path, temp_name, expected_name))
                    files_to_rename.append(file_path)
            
            if not files_to_rename:
                print("✅ Fichiers déjà dans le bon ordre chronologique")
                return
            
            print(f"🔄 Réorganisation de {len(files_to_rename)} fichiers...")
            
            # Phase 1: Noms temporaires
            for file_path, temp_name, final_name in temp_names:
                temp_path = file_path.parent / temp_name
                # Marquer comme fichier temporaire
                self.temp_files.add(temp_name)
                file_path.rename(temp_path)
            
            # Phase 2: Noms finaux
            renamed_count = 0
            for file_path, temp_name, final_name in temp_names:
                temp_path = file_path.parent / temp_name
                final_path = file_path.parent / final_name
                
                old_name = file_path.name
                temp_path.rename(final_path)
                
                # Nettoyer les fichiers temporaires du cache
                self.temp_files.discard(temp_name)
                
                creation_time = datetime.fromtimestamp(self.get_creation_time(final_path))
                creation_str = creation_time.strftime("%Y-%m-%d %H:%M:%S")
                
                print(f"✅ {old_name} → {final_name} (créé le {creation_str})")
                renamed_count += 1
            
            print(f"✨ {renamed_count} fichiers réorganisés avec succès!")
            
        except Exception as e:
            print(f"❌ Erreur lors de la réorganisation: {e}")


def load_saved_paths():
    """Charge les chemins sauvegardés depuis le fichier de configuration unifié."""
    configs = load_saved_configs()
    paths_dict = {}
    
    for key, config in configs.items():
        name = config.get("name")
        path = config.get("path")
        if name and path:
            paths_dict[name] = path
    
    return paths_dict


def save_paths(paths_dict):
    """Cette fonction n'est plus nécessaire car save_prefix gère tout."""
    # Fonction conservée pour compatibilité mais ne fait plus rien
    # Toutes les données sont maintenant gérées par watcher_config.txt
    pass


def load_saved_configs():
    """Charge la configuration complète (chemins + préfixes)."""
    config_file = Path(__file__).parent / "watcher_config.txt"
    
    if not config_file.exists():
        save_configs({})
        return {}
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if content:
                return json.loads(content)
            else:
                return {}
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def save_configs(configs_dict):
    """Sauvegarde la configuration complète."""
    config_file = Path(__file__).parent / "watcher_config.txt"
    
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(configs_dict, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Erreur lors de la sauvegarde de la configuration: {e}")


def get_saved_prefix(path, name):
    """Récupère le préfixe sauvegardé pour un chemin donné."""
    configs = load_saved_configs()
    key = f"{name}_{path}" if name else path
    
    if key in configs:
        return configs[key].get("prefix", name if name else "Horizon")
    
    return name if name else "Horizon"


def save_prefix(path, name, prefix):
    """Sauvegarde le préfixe pour un chemin donné."""
    configs = load_saved_configs()
    key = f"{name}_{path}" if name else path
    
    configs[key] = {
        "path": path,
        "name": name,
        "prefix": prefix,
        "last_used": datetime.now().isoformat()
    }
    
    save_configs(configs)


def display_paths_menu(paths_dict):
    """Affiche le menu des chemins disponibles."""
    print("\n📂 Dossiers à surveiller:")
    print("-" * 40)
    
    configs = load_saved_configs()
    path_items = list(paths_dict.items())
    
    for i, (name, path) in enumerate(path_items, 1):
        # Récupérer le préfixe sauvegardé
        key = f"{name}_{path}"
        saved_prefix = "Horizon"
        
        if key in configs:
            saved_prefix = configs[key].get("prefix", name)
        elif name:
            saved_prefix = name
            
        print(f"{i}. {name}")
        print(f"   📁 {path}")
        print(f"   🏷️  Préfixe: {saved_prefix}")
        print()
    
    print(f"{len(path_items) + 1}. ➕ Ajouter un nouveau dossier")
    print(f"{len(path_items) + 2}. ✏️  Saisir un chemin manuellement")
    print("-" * 40)


def get_user_choice():
    """Gère la sélection du dossier à surveiller."""
    paths_dict = load_saved_paths()
    
    while True:
        if not paths_dict:
            print("\n📂 Aucun dossier sauvegardé trouvé.")
            print("-" * 40)
            print("1. ➕ Ajouter un nouveau dossier")
            print("2. ✏️  Saisir un chemin manuellement")
            print("0. ❌ Quitter")
            print("-" * 40)
            print("💡 Vous pouvez aussi taper 'q' ou 'quit' pour quitter")
            
            try:
                choice = input("\nVotre choix (numéro): ").strip()
                
                # Gestion de la sortie
                if choice.lower() in ['q', 'quit', 'exit'] or choice == "0":
                    print("❌ Arrêt du service.")
                    return None, None
                
                if choice == "1":
                    result = add_new_path(paths_dict)
                    if result:
                        return result
                    continue
                    
                elif choice == "2":
                    try:
                        manual_path = input("\nEntrez le chemin du dossier à surveiller (ou 'annuler' pour revenir): ").strip()
                        if manual_path.lower() in ['annuler', 'cancel', 'q', 'quit', 'exit']:
                            print("❌ Saisie annulée.")
                            continue
                        if manual_path:
                            return manual_path, None
                        continue
                    except KeyboardInterrupt:
                        print("\n❌ Saisie annulée par l'utilisateur.")
                        continue
                    
                else:
                    print("❌ Choix invalide. Veuillez choisir 1, 2 ou 0.")
                    
            except KeyboardInterrupt:
                print("\n\n❌ Arrêt du service.")
                return None, None
                
        else:
            display_paths_menu(paths_dict)
            
            try:
                choice = input("\nVotre choix (numéro ou 'q' pour quitter): ").strip()
                
                # Gestion de la sortie
                if choice.lower() in ['q', 'quit', 'exit']:
                    print("❌ Arrêt du service.")
                    return None, None
                
                if not choice.isdigit():
                    print("❌ Veuillez entrer un numéro valide ou 'q' pour quitter.")
                    continue
                
                choice_num = int(choice)
                path_items = list(paths_dict.items())
                
                if 1 <= choice_num <= len(path_items):
                    selected_name, selected_path = path_items[choice_num - 1]
                    print(f"\n✅ Dossier sélectionné: {selected_name}")
                    print(f"📁 {selected_path}")
                    return selected_path, selected_name
                    
                elif choice_num == len(path_items) + 1:
                    result = add_new_path(paths_dict)
                    if result:
                        return result
                    continue
                    
                elif choice_num == len(path_items) + 2:
                    try:
                        manual_path = input("\nEntrez le chemin du dossier à surveiller (ou 'annuler' pour revenir): ").strip()
                        if manual_path.lower() in ['annuler', 'cancel', 'q', 'quit', 'exit']:
                            print("❌ Saisie annulée.")
                            continue
                        if manual_path:
                            return manual_path, None
                        continue
                    except KeyboardInterrupt:
                        print("\n❌ Saisie annulée par l'utilisateur.")
                        continue
                    
                else:
                    print(f"❌ Choix invalide. Veuillez choisir entre 1 et {len(path_items) + 2} ou 'q' pour quitter.")
                    
            except ValueError:
                print("❌ Veuillez entrer un numéro valide ou 'q' pour quitter.")
            except KeyboardInterrupt:
                print("\n\n❌ Arrêt du service.")
                return None, None
                    
            except ValueError:
                print("❌ Veuillez entrer un numéro valide ou 'q' pour quitter.")
            except KeyboardInterrupt:
                print("\n\n❌ Arrêt du service.")
                return None, None


def add_new_path(paths_dict):
    """Ajoute un nouveau dossier à surveiller."""
    print("\n➕ Ajout d'un nouveau dossier à surveiller")
    print("-" * 40)
    print("💡 Tapez 'annuler' ou 'q' pour annuler à tout moment")
    print()
    
    while True:
        try:
            name = input("Nom du raccourci (ex: 'Screenshots', 'Téléchargements'): ").strip()
            
            # Vérifier l'annulation
            if name.lower() in ['annuler', 'cancel', 'q', 'quit', 'exit']:
                print("❌ Ajout de dossier annulé.")
                return None
                
            if name:
                if name in paths_dict:
                    print(f"❌ Le nom '{name}' existe déjà. Choisissez un autre nom.")
                    continue
                break
            print("❌ Le nom ne peut pas être vide.")
            
        except KeyboardInterrupt:
            print("\n❌ Ajout de dossier annulé par l'utilisateur.")
            return None
    
    while True:
        try:
            path = input("Chemin du dossier: ").strip()
            
            # Vérifier l'annulation
            if path.lower() in ['annuler', 'cancel', 'q', 'quit', 'exit']:
                print("❌ Ajout de dossier annulé.")
                return None
                
            if path:
                if Path(path).exists() and Path(path).is_dir():
                    break
                else:
                    print(f"⚠️ Le dossier '{path}' n'existe pas.")
                    confirm = input("Voulez-vous l'ajouter quand même ? (o/N/annuler): ").strip().lower()
                    if confirm in ['annuler', 'cancel', 'q']:
                        print("❌ Ajout de dossier annulé.")
                        return None
                    if confirm in ['o', 'oui', 'y', 'yes']:
                        break
                    continue
            print("❌ Le chemin ne peut pas être vide.")
            
        except KeyboardInterrupt:
            print("\n❌ Ajout de dossier annulé par l'utilisateur.")
            return None
    
    paths_dict[name] = path
    # Sauvegarder dans le fichier unifié avec le nom comme préfixe par défaut
    save_prefix(path, name, name)
    
    print(f"\n✅ Nouveau dossier ajouté:")
    print(f"📌 {name}: {path}")    
    try:
        use_now = input("\nUtiliser ce dossier maintenant ? (O/n/annuler): ").strip().lower()
        if use_now in ['annuler', 'cancel', 'q']:
            print("❌ Annulé.")
            return None
        if use_now in ['', 'o', 'oui', 'y', 'yes']:
            return path, name
    except KeyboardInterrupt:
        print("\n❌ Annulé par l'utilisateur.")
        return None
    
    return None


def main():
    """Fonction principale du service de surveillance."""
    print("🖼️  Service de surveillance et renommage PNG, JPG et JPEG")
    print("=" * 55)
    print("📡 Ce service surveille un dossier et renomme automatiquement")
    print("   les nouveaux fichiers PNG, JPG et JPEG dès qu'ils apparaissent.")
    print()
      # Sélection du dossier à surveiller
    result = get_user_choice()
    
    if not result or result == (None, None):
        print("❌ Aucun dossier sélectionné. Arrêt du service.")
        return
    
    directory_path, shortcut_name = result
    
    # Vérifier que le dossier existe
    watch_dir = Path(directory_path)
    if not watch_dir.exists():
        print(f"❌ Le dossier {directory_path} n'existe pas.")
        return
    
    if not watch_dir.is_dir():
        print(f"❌ {directory_path} n'est pas un dossier.")
        return
      # Demander le préfixe
    saved_prefix = get_saved_prefix(directory_path, shortcut_name)
    
    print(f"\nPréfixe sauvegardé pour ce dossier: '{saved_prefix}'")
    
    try:
        prefix_input = input(f"Préfixe pour les fichiers (par défaut '{saved_prefix}', Entrée = conserver, 'annuler' = quitter): ").strip()
        
        if prefix_input.lower() in ['annuler', 'cancel', 'q', 'quit', 'exit']:
            print("❌ Configuration annulée.")
            return
            
        if prefix_input:
            # L'utilisateur a saisi un nouveau préfixe
            prefix = prefix_input
            # Sauvegarder le nouveau préfixe
            save_prefix(directory_path, shortcut_name, prefix)
            print(f"✅ Nouveau préfixe '{prefix}' sauvegardé pour ce dossier")
        else:
            # Utiliser le préfixe sauvegardé
            prefix = saved_prefix
            
    except KeyboardInterrupt:
        print("\n❌ Configuration annulée par l'utilisateur.")
        return
    
    print(f"\n🎯 Configuration du service:")
    print(f"   📁 Dossier surveillé: {directory_path}")
    print(f"   🏷️  Préfixe: {prefix}")
    print()
    
    # Créer le gestionnaire d'événements et l'observateur
    event_handler = ImageRenameHandler(prefix)
    observer = Observer()
    observer.schedule(event_handler, directory_path, recursive=False)
    
    # Vérifier et traiter les fichiers existants AVANT de démarrer la surveillance
    print("🔍 Vérification des fichiers existants...")
    initial_check_result = event_handler.check_existing_files(Path(directory_path))
    
    if initial_check_result:
        print(f"✅ {initial_check_result} fichiers traités au démarrage")
    else:
        print("✅ Aucun fichier à traiter au démarrage")
      # Démarrer la surveillance
    observer.start()
    
    print("🟢 Service démarré !")
    print("📡 Surveillance en cours...")
    print()
    print("💡 Instructions:")
    print("   • Le service renomme automatiquement les nouveaux fichiers PNG, JPG et JPEG")
    print("   • Ajoutez des fichiers PNG dans le dossier surveillé")
    print("   • Tapez 'menu' pour afficher les options")
    print("   • Appuyez sur Ctrl+C ou tapez 'quit' pour arrêter le service")
    print()
    print("-" * 55)
    
    def print_interactive_menu():
        print("\n" + "=" * 50)
        print("📋 MENU DU SERVICE DE SURVEILLANCE")
        print("=" * 50)
        print("1. 📊 Voir le statut du service")
        print("2. 📁 Changer de dossier surveillé")
        print("3. 🏷️  Changer le préfixe")
        print("4. 📋 Réorganiser tous les fichiers")
        print("5. ❌ Arrêter le service")
        print("6. 🔄 Retourner à la surveillance")
        print("=" * 50)
    
    def handle_interactive_menu():
        while True:
            print_interactive_menu()
            try:
                choice = input("\nVotre choix (1-6): ").strip()
                
                if choice == "1":
                    print(f"\n📊 STATUT DU SERVICE:")
                    print(f"   📁 Dossier surveillé: {directory_path}")
                    print(f"   🏷️  Préfixe actuel: {prefix}")
                    print(f"   🟢 Service: Actif")
                    input("\nAppuyez sur Entrée pour continuer...")
                    
                elif choice == "2":
                    print("\n❌ Pour changer de dossier, vous devez redémarrer le service.")
                    confirm = input("Voulez-vous arrêter le service maintenant ? (o/N): ").strip().lower()
                    if confirm in ['o', 'oui', 'y', 'yes']:
                        return "stop"
                    
                elif choice == "3":
                    try:
                        new_prefix = input(f"\nNouveau préfixe (actuel: '{prefix}'): ").strip()
                        if new_prefix:
                            # Mettre à jour le préfixe
                            event_handler.prefix = new_prefix
                            save_prefix(directory_path, shortcut_name, new_prefix)
                            print(f"✅ Préfixe changé pour '{new_prefix}'")
                        input("\nAppuyez sur Entrée pour continuer...")
                    except KeyboardInterrupt:
                        print("\n❌ Changement annulé.")
                        
                elif choice == "4":
                    print("\n🔄 Réorganisation en cours...")
                    try:
                        event_handler.reorganize_all_files(Path(directory_path))
                        print("✅ Réorganisation terminée!")
                    except Exception as e:
                        print(f"❌ Erreur lors de la réorganisation: {e}")
                    input("\nAppuyez sur Entrée pour continuer...")
                    
                elif choice == "5":
                    confirm = input("\n❓ Êtes-vous sûr de vouloir arrêter le service ? (o/N): ").strip().lower()
                    if confirm in ['o', 'oui', 'y', 'yes']:
                        return "stop"
                        
                elif choice == "6":
                    print("\n🔄 Retour à la surveillance...")
                    return "continue"
                    
                else:
                    print("❌ Choix invalide. Veuillez choisir entre 1 et 6.")
                    
            except KeyboardInterrupt:
                print("\n🔄 Retour à la surveillance...")
                return "continue"
    
    try:
        print("💬 Tapez 'menu' pour les options, 'quit' pour quitter, ou Ctrl+C pour arrêter")
        while True:
            try:
                # Attendre une entrée utilisateur avec timeout
                user_input = input("\n> ").strip().lower()
                
                if user_input in ['menu', 'm']:
                    result = handle_interactive_menu()
                    if result == "stop":
                        break
                    elif result == "continue":
                        print("📡 Surveillance reprise...")
                        continue
                        
                elif user_input in ['quit', 'q', 'exit', 'stop']:
                    confirm = input("❓ Êtes-vous sûr de vouloir arrêter le service ? (o/N): ").strip().lower()
                    if confirm in ['o', 'oui', 'y', 'yes']:
                        break
                    else:
                        print("📡 Surveillance continue...")
                        
                else:
                    print("💡 Commandes disponibles: 'menu' (options), 'quit' (arrêter)")
                    
            except EOFError:
                # Gestion des inputs vides ou Ctrl+D
                time.sleep(0.5)
                continue
                
    except KeyboardInterrupt:
        print("\n\n🔴 Arrêt du service demandé...")
    
    observer.stop()
    print("✅ Service arrêté avec succès.")
    
    observer.join()


if __name__ == "__main__":
    main()
