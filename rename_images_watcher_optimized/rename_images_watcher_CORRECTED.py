#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de surveillance et renommage automatique d'images PNG, JPG et JPEG (Version corrigée)
Surveille un dossier en continu et renomme automatiquement les nouveaux fichiers PNG, JPG et JPEG.
Version corrigée pour éliminer DÉFINITIVEMENT les problèmes de fichiers fantômes.
"""

import os
import re
import sys
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
        self.last_event_time = {}
        self.debounce_delay = 1.5
        self.temp_files = set()
        self.processing_lock = threading.Lock()
        
    def get_real_image_files(self, directory):
        """Obtient UNIQUEMENT les fichiers images réellement accessibles - méthode ultra-robuste."""
        real_files = []
        
        # Utiliser os.listdir() au lieu de glob() pour éviter les fichiers fantômes Windows
        try:
            all_items = os.listdir(directory)
            for item in all_items:
                file_path = directory / item
                
                # Vérifier que c'est un fichier (pas un dossier)
                if not file_path.is_file():
                    continue
                
                # Vérifier l'extension
                ext = item.lower()
                if not (ext.endswith('.png') or ext.endswith('.jpg') or ext.endswith('.jpeg')):
                    continue
                
                # Test d'accès ultra-robuste
                try:
                    # Test 1: Le fichier existe-t-il vraiment ?
                    if not file_path.exists():
                        continue
                    
                    # Test 2: Peut-on accéder aux métadonnées ?
                    stat_info = file_path.stat()
                    
                    # Test 3: Le fichier a-t-il une taille > 0 ?
                    if stat_info.st_size <= 0:
                        continue
                    
                    # Test 4: Peut-on ouvrir le fichier en lecture ?
                    with open(file_path, 'rb') as f:
                        f.read(1)  # Lecture d'un seul byte pour vérifier l'accès
                    
                    real_files.append(file_path)
                    
                except (OSError, PermissionError, FileNotFoundError, IOError):
                    # Skip tous les fichiers inaccessibles
                    continue
                    
        except Exception as e:
            print(f"❌ Erreur lors de la lecture du dossier: {e}")
            
        return real_files
        
    def _should_process_file(self, file_path):
        """Vérifie si un fichier doit être traité."""
        file_path_lower = file_path.lower()
        if not (file_path_lower.endswith('.png') or file_path_lower.endswith('.jpg') or file_path_lower.endswith('.jpeg')):
            return False
        file_name = Path(file_path).name
        return not (file_name.startswith('TEMP_') or file_name in self.temp_files)
    
    def _handle_file_event(self, file_path, event_type):
        """Gestion unifiée des événements de fichiers."""
        if self._should_process_file(file_path):
            print(f"🔍 Événement détecté - {event_type}: {file_path}")
            self._debounced_process(file_path)
    
    def on_created(self, event):
        if not event.is_directory:
            self._handle_file_event(event.src_path, "Fichier créé")
    
    def on_modified(self, event):
        if not event.is_directory and not self.is_already_renamed(Path(event.src_path).name):
            self._handle_file_event(event.src_path, "Fichier modifié")
    
    def on_moved(self, event):
        if not event.is_directory:
            self._handle_file_event(event.dest_path, "Fichier déplacé")
    
    def _debounced_process(self, file_path):
        """Traitement avec anti-rebond."""
        current_time = time.time()
        
        if file_path in self.last_event_time:
            time_diff = current_time - self.last_event_time[file_path]
            if time_diff < self.debounce_delay:
                print(f"🔄 Événement ignoré (debounce {time_diff:.1f}s): {Path(file_path).name}")
                return
        
        self.last_event_time[file_path] = current_time
        print(f"✅ Événement accepté: {Path(file_path).name}")
        
        threading.Thread(target=self.process_new_file, args=(file_path,), daemon=True).start()
    
    def process_new_file(self, file_path):
        """Traite un nouveau fichier PNG détecté."""
        try:
            file_path = Path(file_path)
            
            # Retry si fichier pas encore disponible
            if not file_path.exists():
                print(f"⚠️ Retry pour: {file_path.name}")
                time.sleep(1.0)
                if not file_path.exists():
                    print(f"⚠️ Fichier introuvable: {file_path.name}")
                    return
                print(f"✅ Fichier trouvé après retry: {file_path.name}")
                
            if self.is_already_renamed(file_path.name):
                print(f"⚠️ Fichier déjà renommé: {file_path.name}")
                return
            
            with self.processing_lock:
                if self.processing:
                    print(f"⚠️ Traitement en cours, ignoré: {file_path.name}")
                    return
                self.processing = True
            
            try:
                print(f"🔄 Attente stabilisation: {file_path.name}")
                if not self._wait_file_stable(file_path):
                    print(f"⚠️ Fichier non stable: {file_path.name}")
                    return
                
                print(f"\n🆕 Nouveau fichier: {file_path.name}")
                self.reorganize_all_files(file_path.parent)
                self._cleanup_cache()
                
            finally:
                with self.processing_lock:
                    self.processing = False
                
        except Exception as e:
            print(f"❌ Erreur traitement {file_path}: {e}")
            with self.processing_lock:
                self.processing = False
    
    def _cleanup_cache(self):
        """Nettoie le cache des événements."""
        cutoff = time.time() - (self.debounce_delay * 5)
        self.last_event_time = {k: v for k, v in self.last_event_time.items() if v > cutoff}
    
    def _wait_file_stable(self, file_path, timeout=5):
        """Attend la stabilité du fichier."""
        start_time = time.time()
        last_size = -1
        stable_count = 0
        
        while time.time() - start_time < timeout:
            try:
                if not file_path.exists():
                    return False
                    
                current_size = file_path.stat().st_size
                if current_size > 0:
                    if current_size == last_size:
                        stable_count += 1
                        if stable_count >= 2:
                            print(f"✅ Fichier stable ({current_size} bytes): {file_path.name}")
                            return True
                    else:
                        stable_count = 0
                
                last_size = current_size
                time.sleep(0.2)
                
            except (OSError, FileNotFoundError):
                return False
        
        # Accepter si taille > 0 même après timeout
        try:
            final_size = file_path.stat().st_size
            if final_size > 0:
                print(f"⚠️ Timeout, fichier accepté ({final_size} bytes): {file_path.name}")
                return True
        except:
            pass
        
        print(f"❌ Fichier non stable après {timeout}s: {file_path.name}")
        return False
    
    def is_already_renamed(self, filename):
        """Vérifie si déjà renommé."""
        return bool(re.match(rf"^{self.prefix}_\d{{2,}}\.(png|jpg|jpeg)$", filename, re.IGNORECASE))
    
    def check_existing_files(self, directory):
        """Vérifie les fichiers existants au démarrage - VERSION ULTRA-ROBUSTE."""
        try:
            # Utiliser la méthode ultra-robuste pour obtenir les vrais fichiers
            existing_files = self.get_real_image_files(directory)
            
            print(f"🔍 Détection robuste: {len(existing_files)} fichiers images réellement accessibles")
            
            if not existing_files:
                print("📂 Aucun fichier image trouvé")
                return 0
            
            new_files = [f for f in existing_files if not self.is_already_renamed(f.name)]
            total_files = len(existing_files)
            new_count = len(new_files)
            
            print(f"📊 Total fichiers réels: {total_files}")
            print(f"📋 Fichiers à réorganiser: {new_count}")
            
            # Toujours réorganiser pour corriger la numérotation discontinue
            if total_files > 0:
                print("🔧 Réorganisation pour garantir une numérotation continue...")
                self.reorganize_all_files(directory)
            
            return new_count
            
        except Exception as e:
            print(f"❌ Erreur vérification initiale: {e}")
            return 0
    
    def reorganize_all_files(self, directory):
        """Réorganise tous les fichiers avec numérotation continue garantie."""
        try:
            # Utiliser la méthode ultra-robuste
            existing_files = self.get_real_image_files(directory)
            
            print(f"🔍 Réorganisation: {len(existing_files)} fichiers réellement accessibles")
            
            if not existing_files:
                print("📂 Aucun fichier image accessible trouvé")
                return
            
            # Trier par date de création pour préserver l'ordre chronologique
            existing_files.sort(key=lambda x: os.path.getctime(x))
            
            # Afficher l'ordre actuel
            print("📋 Ordre actuel des fichiers:")
            for i, f in enumerate(existing_files[:10], 1):  # Afficher les 10 premiers
                print(f"  {i:02d}. {f.name}")
            if len(existing_files) > 10:
                print(f"  ... et {len(existing_files) - 10} autres")
            
            # Préparer les renommages avec numérotation continue
            renames = []
            for i, file_path in enumerate(existing_files):
                # Préserver l'extension originale
                ext = file_path.suffix.lower()
                expected = f"{self.prefix}_{i+1:02d}{ext}"
                
                if file_path.name != expected:
                    temp = f"TEMP_{i+1:02d}_{self.prefix}{ext}"
                    renames.append((file_path, temp, expected))
            
            if not renames:
                print("✅ Fichiers déjà dans le bon ordre avec numérotation continue")
                return
            
            print(f"🔄 Réorganisation de {len(renames)} fichiers...")
            
            # Phase 1: Noms temporaires pour éviter les conflits
            successful_phase1 = []
            
            for file_path, temp, final in renames:
                temp_path = file_path.parent / temp
                self.temp_files.add(temp)
                try:
                    file_path.rename(temp_path)
                    successful_phase1.append((file_path, temp, final))
                    print(f"📦 Phase 1: {file_path.name} → {temp}")
                except Exception as e:
                    print(f"⚠️ Erreur renommage phase 1: {file_path} → {temp}: {e}")
                    continue
            
            # Phase 2: Noms finaux avec numérotation continue
            successful_renames = 0
            for file_path, temp, final in successful_phase1:
                temp_path = file_path.parent / temp
                if not temp_path.exists():
                    continue
                    
                final_path = file_path.parent / final
                
                old_name = file_path.name
                try:
                    temp_path.rename(final_path)
                    self.temp_files.discard(temp)
                    successful_renames += 1
                    
                    creation_time = datetime.fromtimestamp(os.path.getctime(final_path))
                    print(f"✅ {old_name} → {final} (créé le {creation_time.strftime('%Y-%m-%d %H:%M:%S')})")
                except Exception as e:
                    print(f"❌ Erreur finale: {temp} → {final}: {e}")
            
            print(f"✨ {successful_renames} fichiers réorganisés avec numérotation continue!")
            
            # Vérification finale
            final_files = self.get_real_image_files(directory)
            final_files.sort(key=lambda x: os.path.getctime(x))
            
            print("🔍 Vérification finale de la numérotation:")
            for i, f in enumerate(final_files[:10], 1):
                expected_num = f"{i:02d}"
                actual_num = re.search(rf"{self.prefix}_(\d+)", f.name)
                if actual_num:
                    actual_num = actual_num.group(1)
                    status = "✅" if actual_num == expected_num else "❌"
                    print(f"  {status} {f.name} (attendu: {expected_num}, trouvé: {actual_num})")
                else:
                    print(f"  ❓ {f.name} (format inattendu)")
            
        except Exception as e:
            print(f"❌ Erreur réorganisation: {e}")
            import traceback
            traceback.print_exc()


# === CONFIGURATION ===
class ConfigManager:
    """Gestionnaire de configuration centralisé."""
    
    def __init__(self):
        # Déterminer le bon chemin selon l'environnement
        if getattr(sys, 'frozen', False):
            # Mode exécutable PyInstaller
            exe_dir = Path(sys.executable).parent
        else:
            # Mode script Python normal
            exe_dir = Path(__file__).parent
        
        self.config_file = exe_dir / "watcher_config.txt"
        print(f"📁 Fichier de config: {self.config_file}")  # Debug
    
    def load_configs(self):
        """Charge la configuration complète."""
        if not self.config_file.exists():
            self.save_configs({})
            return {}
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                return json.loads(content) if content else {}
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    
    def save_configs(self, configs):
        """Sauvegarde la configuration."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(configs, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Erreur sauvegarde: {e}")
    
    def get_paths(self):
        """Récupère les chemins sauvegardés."""
        configs = self.load_configs()
        return {config.get("name"): config.get("path") 
                for config in configs.values() 
                if config.get("name") and config.get("path")}
    
    def get_prefix(self, path, name):
        """Récupère le préfixe pour un chemin."""
        configs = self.load_configs()
        key = f"{name}_{path}" if name else path
        
        if key in configs:
            return configs[key].get("prefix", name or "Horizon")
        return name or "Horizon"
    
    def save_prefix(self, path, name, prefix):
        """Sauvegarde le préfixe."""
        configs = self.load_configs()
        key = f"{name}_{path}" if name else path
        
        configs[key] = {
            "path": path,
            "name": name,
            "prefix": prefix,
            "last_used": datetime.now().isoformat()
        }
        self.save_configs(configs)


# === INTERFACE UTILISATEUR ===
class UserInterface:
    """Interface utilisateur simplifiée."""
    
    def __init__(self):
        self.config = ConfigManager()
        self.exit_commands = ['annuler', 'cancel', 'q', 'quit', 'exit']
    
    def check_exit(self, user_input):
        """Vérifie si l'utilisateur veut quitter."""
        return user_input.lower() in self.exit_commands
    
    def get_input_with_cancel(self, prompt, allow_empty=False):
        """Saisie avec possibilité d'annulation."""
        try:
            value = input(prompt).strip()
            if self.check_exit(value):
                return None
            if not allow_empty and not value:
                return ""  # Valeur vide mais pas annulation
            return value
        except KeyboardInterrupt:
            print("\n❌ Annulé par l'utilisateur.")
            return None
    
    def display_menu(self, paths_dict):
        """Affiche le menu principal."""
        print("\n📂 Dossiers à surveiller:")
        print("-" * 40)
        
        configs = self.config.load_configs()
        for i, (name, path) in enumerate(paths_dict.items(), 1):
            key = f"{name}_{path}"
            prefix = configs.get(key, {}).get("prefix", name)
            print(f"{i}. {name}")
            print(f"   📁 {path}")
            print(f"   🏷️  Préfixe: {prefix}")
            print()
        
        print(f"{len(paths_dict) + 1}. ➕ Ajouter un nouveau dossier")
        print(f"{len(paths_dict) + 2}. ✏️  Saisir un chemin manuellement")
        print("-" * 40)
    
    def add_new_path(self, paths_dict):
        """Ajoute un nouveau dossier."""
        print("\n➕ Ajout d'un nouveau dossier")
        print("-" * 40)
        print("💡 Tapez 'q' pour annuler")
        print()
        
        # Nom du raccourci
        while True:
            name = self.get_input_with_cancel("Nom du raccourci: ")
            if name is None:
                print("❌ Ajout annulé.")
                return None
            if name == "":
                print("❌ Le nom ne peut pas être vide.")
                continue
            if name in paths_dict:
                print(f"❌ Le nom '{name}' existe déjà.")
                continue
            break
        
        # Chemin du dossier
        while True:
            path = self.get_input_with_cancel("Chemin du dossier: ")
            if path is None:
                print("❌ Ajout annulé.")
                return None
            if path == "":
                print("❌ Le chemin ne peut pas être vide.")
                continue
            
            if Path(path).exists() and Path(path).is_dir():
                break
            
            confirm = self.get_input_with_cancel(f"⚠️ '{path}' n'existe pas. Ajouter quand même ? (o/N): ")
            if confirm is None:
                print("❌ Ajout annulé.")
                return None
            if confirm.lower() in ['o', 'oui', 'y', 'yes']:
                break
        
        # Sauvegarder
        paths_dict[name] = path
        self.config.save_prefix(path, name, name)
        print(f"\n✅ Dossier ajouté: {name}: {path}")
        
        # Utiliser maintenant ?
        use_now = self.get_input_with_cancel("\nUtiliser maintenant ? (O/n): ", allow_empty=True)
        if use_now is None:
            return None
        if use_now.lower() not in ['n', 'non', 'no']:
            return path, name
        
        return None
    
    def get_user_choice(self):
        """Sélection du dossier à surveiller."""
        while True:
            paths_dict = self.config.get_paths()
            
            if not paths_dict:
                print("\n📂 Aucun dossier sauvegardé.")
                print("-" * 40)
                print("1. ➕ Ajouter un nouveau dossier")
                print("2. ✏️  Saisir un chemin manuellement")
                print("0. ❌ Quitter")
                print("-" * 40)
                
                choice = self.get_input_with_cancel("\nVotre choix: ")
                if choice is None or choice == "0":
                    return None, None
                
                if choice == "1":
                    result = self.add_new_path(paths_dict)
                    if result:
                        return result
                elif choice == "2":
                    path = self.get_input_with_cancel("\nChemin du dossier: ")
                    if path and path != "":
                        return path, None
                else:
                    print("❌ Choix invalide.")
            else:
                self.display_menu(paths_dict)
                choice = self.get_input_with_cancel("\nVotre choix (ou 'q' pour quitter): ")
                
                if choice is None:
                    return None, None
                
                if choice.isdigit():
                    choice_num = int(choice)
                    path_items = list(paths_dict.items())
                    
                    if 1 <= choice_num <= len(path_items):
                        name, path = path_items[choice_num - 1]
                        print(f"\n✅ Sélectionné: {name}")
                        return path, name
                    elif choice_num == len(path_items) + 1:
                        result = self.add_new_path(paths_dict)
                        if result:
                            return result
                    elif choice_num == len(path_items) + 2:
                        path = self.get_input_with_cancel("\nChemin du dossier: ")
                        if path and path != "":
                            return path, None
                    else:
                        print("❌ Choix invalide.")
                else:
                    print("❌ Choix invalide.")


def run_interactive_menu(directory_path, prefix, shortcut_name, event_handler):
    """Menu interactif pendant la surveillance."""
    config = ConfigManager()
    
    def print_menu():
        print("\n" + "=" * 50)
        print("📋 MENU DU SERVICE")
        print("=" * 50)
        print("1. 📊 Statut")
        print("2. 📁 Changer dossier (redémarre)")
        print("3. 🏷️  Changer préfixe")
        print("4. 📋 Réorganiser fichiers")
        print("5. ❌ Arrêter")
        print("6. 🔄 Retour surveillance")
        print("=" * 50)
    
    while True:
        print_menu()
        try:
            choice = input("\nChoix (1-6): ").strip()
            
            if choice == "1":
                print(f"\n📊 STATUT:")
                print(f"   📁 Dossier: {directory_path}")
                print(f"   🏷️  Préfixe: {prefix}")
                print(f"   🟢 Service: Actif")
                input("\nEntrée pour continuer...")
                
            elif choice == "2":
                print("\n❌ Redémarrage nécessaire pour changer de dossier.")
                confirm = input("Arrêter maintenant ? (o/N): ").lower()
                if confirm in ['o', 'oui', 'y']:
                    return "stop"
                
            elif choice == "3":
                new_prefix = input(f"\nNouveau préfixe (actuel: '{prefix}'): ").strip()
                if new_prefix:
                    event_handler.prefix = new_prefix
                    config.save_prefix(directory_path, shortcut_name, new_prefix)
                    print(f"✅ Préfixe changé: '{new_prefix}'")
                input("\nEntrée pour continuer...")
                
            elif choice == "4":
                print("\n🔄 Réorganisation...")
                try:
                    event_handler.reorganize_all_files(Path(directory_path))
                    print("✅ Terminé!")
                except Exception as e:
                    print(f"❌ Erreur: {e}")
                input("\nEntrée pour continuer...")
                
            elif choice == "5":
                confirm = input("\n❓ Arrêter le service ? (o/N): ").lower()
                if confirm in ['o', 'oui', 'y']:
                    return "stop"
                    
            elif choice == "6":
                print("\n🔄 Retour surveillance...")
                return "continue"
                
            else:
                print("❌ Choix invalide (1-6).")
                
        except KeyboardInterrupt:
            print("\n🔄 Retour surveillance...")
            return "continue"


def main():
    """Fonction principale optimisée."""
    print("🖼️  Service de surveillance et renommage PNG, JPG et JPEG")
    print("=" * 55)
    print("📡 Surveillance automatique des nouveaux fichiers PNG, JPG et JPEG")
    print()
    
    ui = UserInterface()
    config = ConfigManager()
    
    # Sélection du dossier
    result = ui.get_user_choice()
    if not result or result == (None, None):
        print("❌ Aucun dossier sélectionné.")
        return
    
    directory_path, shortcut_name = result
    
    # Vérification du dossier
    watch_dir = Path(directory_path)
    if not watch_dir.exists():
        print(f"❌ Dossier inexistant: {directory_path}")
        return
    if not watch_dir.is_dir():
        print(f"❌ Pas un dossier: {directory_path}")
        return
    
    # Configuration du préfixe
    saved_prefix = config.get_prefix(directory_path, shortcut_name)
    print(f"\nPréfixe sauvegardé: '{saved_prefix}'")
    
    prefix_input = ui.get_input_with_cancel(
        f"Préfixe (Entrée='{saved_prefix}', 'q'=quitter): ", 
        allow_empty=True
    )
    if prefix_input is None:
        print("❌ Configuration annulée.")
        return
    
    prefix = prefix_input if prefix_input else saved_prefix
    if prefix_input:
        config.save_prefix(directory_path, shortcut_name, prefix)
        print(f"✅ Préfixe sauvegardé: '{prefix}'")
    
    print(f"\n🎯 Configuration:")
    print(f"   📁 Dossier: {directory_path}")
    print(f"   🏷️  Préfixe: {prefix}")
    
    # Démarrage du service
    event_handler = ImageRenameHandler(prefix)
    observer = Observer()
    observer.schedule(event_handler, directory_path, recursive=False)
    
    print("\n🔍 Vérification fichiers existants...")
    initial_count = event_handler.check_existing_files(Path(directory_path))
    print(f"✅ {initial_count} fichiers traités" if initial_count else "✅ Aucun fichier à traiter")
    
    observer.start()
    print("\n🟢 Service démarré!")
    print("💬 Tapez 'menu' ou 'quit', ou Ctrl+C pour arrêter")
    
    # Boucle interactive
    try:
        while True:
            try:
                user_input = input("\n> ").strip().lower()
                
                if user_input in ['menu', 'm']:
                    result = run_interactive_menu(directory_path, prefix, shortcut_name, event_handler)
                    if result == "stop":
                        break
                elif user_input in ['quit', 'q', 'exit', 'stop']:
                    confirm = input("❓ Arrêter ? (o/N): ").lower()
                    if confirm in ['o', 'oui', 'y']:
                        break
                    print("📡 Surveillance continue...")
                else:
                    print("💡 Commandes: 'menu', 'quit'")
                    
            except EOFError:
                time.sleep(0.5)
                
    except KeyboardInterrupt:
        print("\n\n🔴 Arrêt demandé...")
    
    observer.stop()
    print("✅ Service arrêté.")
    observer.join()


if __name__ == "__main__":
    main()
