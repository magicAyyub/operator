#!/usr/bin/env python3
import os
import sys
import subprocess
import threading
import time
import platform
import webbrowser
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QPushButton, QLabel, QTextEdit, QProgressBar, QGroupBox, 
                            QMessageBox, QSplitter, QFrame)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QObject
from PyQt5.QtGui import QFont, QIcon, QTextCursor, QColor, QPalette

# Détection du système d'exploitation
SYSTEM = platform.system()
IS_WINDOWS = SYSTEM == "Windows"
IS_MAC = SYSTEM == "Darwin"
IS_LINUX = SYSTEM == "Linux"

# Chemins relatifs
BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")

# Couleurs et styles
PRIMARY_COLOR = "#4f46e5"  # Indigo plus doux
SUCCESS_COLOR = "#22c55e"  # Vert plus doux
ERROR_COLOR = "#ef4444"    # Rouge
WARNING_COLOR = "#f59e0b"  # Orange
INFO_COLOR = "#64748b"     # Gris bleuté
BORDER_COLOR = "#e2e8f0"   # Gris très clair
BG_COLOR = "#f8fafc"       # Fond presque blanc

# État global
backend_process = None
frontend_process = None
docker_running = False
frontend_running = False

class CommandRunner(QObject):
    """Classe pour exécuter des commandes en arrière-plan avec une meilleure gestion des threads"""
    output_received = pyqtSignal(str)
    command_finished = pyqtSignal(int)
    
    def __init__(self, command, cwd=None, env=None):
        super().__init__()
        self.command = command
        self.cwd = cwd
        self.env = env
        self.process = None
        self.thread = None
        self.running = False
    
    def start(self):
        """Démarre l'exécution de la commande dans un thread séparé"""
        self.running = True
        self.thread = threading.Thread(target=self._run_command)
        self.thread.daemon = True  # Le thread s'arrêtera quand le programme principal s'arrête
        self.thread.start()
    
    def _run_command(self):
        """Exécute la commande et émet les signaux appropriés"""
        try:
            # Créer un environnement avec les variables actuelles
            current_env = os.environ.copy()
            if self.env:
                current_env.update(self.env)
                
            self.process = subprocess.Popen(
                self.command,
                cwd=self.cwd,
                env=current_env,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Lire la sortie ligne par ligne
            for line in iter(self.process.stdout.readline, ''):
                if not self.running:
                    break
                self.output_received.emit(line.rstrip())
            
            # Fermer les flux et attendre la fin du processus
            if self.process.stdout:
                self.process.stdout.close()
            
            return_code = self.process.wait()
            if self.running:  # Émettre le signal seulement si on n'a pas été arrêté manuellement
                self.command_finished.emit(return_code)
            
        except Exception as e:
            if self.running:
                self.output_received.emit(f"Erreur: {str(e)}")
                self.command_finished.emit(1)
    
    def terminate_process(self):
        """Arrête proprement le processus en cours d'exécution"""
        self.running = False
        if self.process:
            try:
                if IS_WINDOWS:
                    # Sur Windows, on doit utiliser taskkill pour tuer le processus et ses enfants
                    subprocess.run(f"taskkill /F /PID {self.process.pid} /T", shell=True)
                else:
                    # Sur Unix, on peut utiliser terminate ou kill
                    self.process.terminate()
                    # Donner un peu de temps au processus pour se terminer proprement
                    time.sleep(0.5)
                    if self.process.poll() is None:  # Si le processus est toujours en vie
                        self.process.kill()  # Force kill
            except Exception as e:
                print(f"Erreur lors de la terminaison du processus: {e}")

class LogDisplay(QTextEdit):
    """Widget personnalisé pour afficher les logs avec coloration"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Consolas" if IS_WINDOWS else "Menlo", 9))
        self.setLineWrapMode(QTextEdit.WidgetWidth)
        self.setStyleSheet(f"background-color: #ffffff; border: 1px solid {BORDER_COLOR}; border-radius: 6px;")
        
    def append_message(self, message, color=None):
        self.moveCursor(QTextCursor.End)
        if color:
            self.setTextColor(QColor(color))
        else:
            self.setTextColor(QColor("black"))
        self.insertPlainText(message + "\n")
        self.moveCursor(QTextCursor.End)

class ServiceStatusWidget(QWidget):
    """Widget pour afficher l'état d'un service"""
    def __init__(self, service_name, parent=None):
        super().__init__(parent)
        self.service_name = service_name
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        
        self.status_indicator = QLabel()
        self.status_indicator.setFixedSize(10, 10)
        self.status_indicator.setStyleSheet(f"background-color: {INFO_COLOR}; border-radius: 5px;")
        
        self.name_label = QLabel(service_name)
        self.name_label.setFont(QFont("Arial", 10))
        
        self.status_label = QLabel("En attente")
        self.status_label.setFont(QFont("Arial", 9))
        self.status_label.setStyleSheet(f"color: {INFO_COLOR};")
        
        layout.addWidget(self.status_indicator)
        layout.addWidget(self.name_label)
        layout.addStretch()
        layout.addWidget(self.status_label)
        
    def update_status(self, status, color):
        self.status_label.setText(status)
        self.status_label.setStyleSheet(f"color: {color};")
        self.status_indicator.setStyleSheet(f"background-color: {color}; border-radius: 5px;")

class LauncherApp(QMainWindow):
    """Application principale"""
    def __init__(self):
        super().__init__()
        self.backend_runner = None
        self.frontend_runner = None
        self.stop_runner = None
        self.init_ui()
        
        # Timers pour la progression
        self.docker_progress_timer = QTimer(self)
        self.docker_progress_timer.timeout.connect(self.update_docker_progress)
        self.docker_progress_value = 0
        
        self.npm_progress_timer = QTimer(self)
        self.npm_progress_timer.timeout.connect(self.update_npm_progress)
        self.npm_progress_value = 0
        
        self.frontend_progress_timer = QTimer(self)
        self.frontend_progress_timer.timeout.connect(self.update_frontend_progress)
        self.frontend_progress_value = 0
        
        # Vérifier les prérequis après l'initialisation de l'interface
        QTimer.singleShot(100, self.check_prerequisites)
        
    def init_ui(self):
        """Initialise l'interface utilisateur"""
        self.setWindowTitle("Lanceur - Tableau de Bord Opérateur")
        self.setMinimumSize(800, 600)
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # En-tête
        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        title = QLabel("Tableau de Bord Opérateur")
        title.setFont(QFont("Arial", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #1e293b;")
        
        subtitle = QLabel("Lanceur d'application")
        subtitle.setFont(QFont("Arial", 10))
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(f"color: {INFO_COLOR};")
        
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        
        main_layout.addWidget(header)
        
        # Séparateur
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet(f"background-color: {BORDER_COLOR};")
        main_layout.addWidget(separator)
        
        # Statut des services
        status_group = QGroupBox("État des services")
        status_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {BORDER_COLOR};
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
        """)
        status_layout = QVBoxLayout(status_group)
        
        self.backend_status = ServiceStatusWidget("Backend (API & Base de données)")
        self.frontend_status = ServiceStatusWidget("Frontend (Interface utilisateur)")
        
        status_layout.addWidget(self.backend_status)
        status_layout.addWidget(self.frontend_status)
        
        main_layout.addWidget(status_group)
        
        # Actions
        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(0, 10, 0, 10)
        
        self.start_button = QPushButton("Démarrer l'application")
        self.start_button.setMinimumHeight(40)
        self.start_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #4338ca;
            }}
            QPushButton:disabled {{
                background-color: #94a3b8;
            }}
        """)
        
        self.stop_button = QPushButton("Arrêter les services")
        self.stop_button.setMinimumHeight(40)
        self.stop_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {ERROR_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #dc2626;
            }}
            QPushButton:disabled {{
                background-color: #94a3b8;
            }}
        """)
        self.stop_button.setEnabled(False)
        
        actions_layout.addWidget(self.start_button)
        actions_layout.addWidget(self.stop_button)
        
        main_layout.addLayout(actions_layout)
        
        # Progression
        progress_group = QGroupBox("Progression")
        progress_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {BORDER_COLOR};
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
        """)
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_label = QLabel("En attente de démarrage...")
        self.progress_label.setFont(QFont("Arial", 10))
        self.progress_label.setAlignment(Qt.AlignCenter)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {BORDER_COLOR};
                border-radius: 4px;
                text-align: center;
                height: 20px;
                background-color: white;
            }}
            QProgressBar::chunk {{
                background-color: {PRIMARY_COLOR};
                border-radius: 3px;
            }}
        """)
        
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        
        main_layout.addWidget(progress_group)
        
        # Logs
        logs_group = QGroupBox("Logs")
        logs_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {BORDER_COLOR};
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
        """)
        logs_layout = QVBoxLayout(logs_group)
        
        self.log_display = LogDisplay()
        logs_layout.addWidget(self.log_display)
        
        main_layout.addWidget(logs_group, 1)
        
        # Instructions
        instructions = QLabel("""
Cliquez sur "Démarrer l'application" pour lancer le backend et le frontend.
L'application s'ouvrira automatiquement dans votre navigateur une fois prête.
Pour arrêter l'application, cliquez sur "Arrêter les services".
        """)
        instructions.setFont(QFont("Arial", 9))
        instructions.setWordWrap(True)
        instructions.setStyleSheet(f"color: {INFO_COLOR}; background-color: #f1f5f9; padding: 10px; border-radius: 6px;")
        
        main_layout.addWidget(instructions)
        
        # Connexion des signaux
        self.start_button.clicked.connect(self.start_all)
        self.stop_button.clicked.connect(self.stop_all)
        
    def check_prerequisites(self):
        """Vérifie si tous les prérequis sont installés"""
        self.log_display.append_message("Vérification des prérequis...", INFO_COLOR)
        
        missing = []
        
        # Vérifier Poetry
        try:
            result = subprocess.run(
                ["python","-m","poetry", "--version"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True
            )
            if result.returncode == 0:
                self.log_display.append_message(f"Poetry: Installé ({result.stdout.strip()})", SUCCESS_COLOR)
            else:
                missing.append("Poetry")
                self.log_display.append_message("Poetry: Non installé ou non accessible", ERROR_COLOR)
        except (subprocess.SubprocessError, FileNotFoundError):
            missing.append("Poetry")
            self.log_display.append_message("Poetry: Non installé", ERROR_COLOR)
        
        # Vérifier Node.js
        try:
            result = subprocess.run(
                ["node", "--version"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True
            )
            if result.returncode == 0:
                self.log_display.append_message(f"Node.js: Installé ({result.stdout.strip()})", SUCCESS_COLOR)
            else:
                missing.append("Node.js")
                self.log_display.append_message("Node.js: Non installé ou non accessible", ERROR_COLOR)
        except (subprocess.SubprocessError, FileNotFoundError):
            missing.append("Node.js")
            self.log_display.append_message("Node.js: Non installé", ERROR_COLOR)
        
        # Vérifier Docker
        try:
            result = subprocess.run(
                ["docker", "--version"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True
            )
            if result.returncode == 0:
                self.log_display.append_message(f"Docker: Installé ({result.stdout.strip()})", SUCCESS_COLOR)
            else:
                missing.append("Docker")
                self.log_display.append_message("Docker: Non installé ou non accessible", ERROR_COLOR)
        except (subprocess.SubprocessError, FileNotFoundError):
            missing.append("Docker")
            self.log_display.append_message("Docker: Non installé", ERROR_COLOR)
        
        if missing:
            self.log_display.append_message(
                f"Attention: Les logiciels suivants sont requis mais non installés: {', '.join(missing)}", 
                WARNING_COLOR
            )
            QMessageBox.warning(
                self, 
                "Prérequis manquants", 
                f"Les logiciels suivants sont requis mais non installés:\n\n{', '.join(missing)}\n\nVeuillez les installer avant de continuer."
            )
        else:
            self.log_display.append_message("Tous les prérequis sont installés", SUCCESS_COLOR)
            self.log_display.append_message("Prêt à démarrer l'application", SUCCESS_COLOR)
    
    def start_all(self):
        """Démarre tous les services"""
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress_bar.setValue(0)
        
        # Démarrer le backend
        self.start_backend()
    
    def start_backend(self):
        """Configure et démarre le backend"""
        global backend_process, docker_running
        
        self.log_display.clear()
        self.log_display.append_message("Configuration du backend en cours...", INFO_COLOR)
        self.progress_label.setText("Configuration du backend...")
        self.progress_bar.setValue(10)
        self.backend_status.update_status("Démarrage...", WARNING_COLOR)
        
        # Exécuter poetry install si nécessaire
        poetry_install_cmd = "python -m poetry install"
        self.log_display.append_message(f"Exécution de: {poetry_install_cmd}", INFO_COLOR)
        
        self.backend_runner = CommandRunner(poetry_install_cmd, cwd=BACKEND_DIR)
        self.backend_runner.output_received.connect(lambda msg: self.log_display.append_message(msg))
        self.backend_runner.command_finished.connect(self.on_poetry_install_finished)
        self.backend_runner.start()
    
    def on_poetry_install_finished(self, return_code):
        """Callback après l'installation des dépendances backend"""
        if return_code != 0:
            self.log_display.append_message("Erreur lors de l'installation des dépendances backend", ERROR_COLOR)
            self.backend_status.update_status("Erreur", ERROR_COLOR)
            self.progress_label.setText("Erreur lors de la configuration du backend")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            
            # Afficher un message d'aide
            self.log_display.append_message("\nConseil de dépannage:", WARNING_COLOR)
            self.log_display.append_message("1. Vérifiez que Poetry est correctement installé", WARNING_COLOR)
            self.log_display.append_message("2. Vérifiez les permissions d'accès au dossier backend", WARNING_COLOR)
            return
        
        # Exécuter le setup Docker
        self.log_display.append_message("Démarrage de Docker...", INFO_COLOR)
        self.progress_label.setText("Démarrage de Docker...")
        self.progress_bar.setValue(20)
        
        # Utiliser la commande Poetry
        setup_cmd = "python -m poetry run setup"
        self.log_display.append_message(f"Exécution de: {setup_cmd}", INFO_COLOR)
        
        self.backend_runner = CommandRunner(setup_cmd, cwd=BACKEND_DIR)
        self.backend_runner.output_received.connect(lambda msg: self.log_display.append_message(msg))
        self.backend_runner.command_finished.connect(self.on_docker_setup_finished)
        self.backend_runner.start()
        
        # Simuler la progression pendant le démarrage de Docker
        self.docker_progress_value = 20
        self.docker_progress_timer.start(500)
    
    def update_docker_progress(self):
        """Met à jour la barre de progression pendant le démarrage de Docker"""
        if self.docker_progress_value < 40:
            self.docker_progress_value += 1
            self.progress_bar.setValue(self.docker_progress_value)
    
    def on_docker_setup_finished(self, return_code):
        """Callback après le démarrage de Docker"""
        global docker_running
        
        self.docker_progress_timer.stop()
        
        if return_code != 0:
            self.log_display.append_message("Erreur lors du démarrage de Docker", ERROR_COLOR)
            self.backend_status.update_status("Erreur", ERROR_COLOR)
            self.progress_label.setText("Erreur lors du démarrage de Docker")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            
            # Afficher un message d'aide
            self.log_display.append_message("\nConseil de dépannage:", WARNING_COLOR)
            self.log_display.append_message("1. Vérifiez que Docker est en cours d'exécution", WARNING_COLOR)
            self.log_display.append_message("2. Essayez d'exécuter manuellement 'poetry run setup' dans le dossier backend", WARNING_COLOR)
            self.log_display.append_message("3. Vérifiez les logs Docker pour plus d'informations", WARNING_COLOR)
            return
        
        docker_running = True
        self.backend_status.update_status("En cours d'exécution", SUCCESS_COLOR)
        self.log_display.append_message("Backend démarré avec succès", SUCCESS_COLOR)
        self.progress_bar.setValue(40)
        
        # Démarrer le frontend
        self.start_frontend()
    
    def start_frontend(self):
        """Configure et démarre le frontend"""
        global frontend_process, frontend_running
        
        self.log_display.append_message("Configuration du frontend en cours...", INFO_COLOR)
        self.progress_label.setText("Configuration du frontend...")
        self.frontend_status.update_status("Démarrage...", WARNING_COLOR)
        
        # Exécuter npm install si nécessaire
        npm_install_cmd = "npm install"
        self.log_display.append_message(f"Exécution de: {npm_install_cmd}", INFO_COLOR)
        
        self.frontend_runner = CommandRunner(npm_install_cmd, cwd=FRONTEND_DIR)
        self.frontend_runner.output_received.connect(lambda msg: self.log_display.append_message(msg))
        self.frontend_runner.command_finished.connect(self.on_npm_install_finished)
        self.frontend_runner.start()
        
        # Simuler la progression pendant l'installation npm
        self.npm_progress_value = 40
        self.npm_progress_timer.start(500)
    
    def update_npm_progress(self):
        """Met à jour la barre de progression pendant l'installation npm"""
        if self.npm_progress_value < 60:
            self.npm_progress_value += 1
            self.progress_bar.setValue(self.npm_progress_value)
    
    def on_npm_install_finished(self, return_code):
        """Callback après l'installation des dépendances frontend"""
        self.npm_progress_timer.stop()
        
        if return_code != 0:
            self.log_display.append_message("Erreur lors de l'installation des dépendances frontend", ERROR_COLOR)
            self.frontend_status.update_status("Erreur", ERROR_COLOR)
            self.progress_label.setText("Erreur lors de la configuration du frontend")
            self.start_button.setEnabled(True)
            
            # Afficher un message d'aide
            self.log_display.append_message("\nConseil de dépannage:", WARNING_COLOR)
            self.log_display.append_message("1. Vérifiez que npm est correctement installé", WARNING_COLOR)
            self.log_display.append_message("2. Essayez d'exécuter manuellement 'npm install' dans le dossier frontend", WARNING_COLOR)
            self.log_display.append_message("3. Vérifiez les permissions d'accès au dossier frontend", WARNING_COLOR)
            return
        
        # Démarrer le frontend
        self.log_display.append_message("Démarrage du frontend...", INFO_COLOR)
        self.progress_label.setText("Démarrage du frontend...")
        self.progress_bar.setValue(60)
        
        npm_run_cmd = "npm run dev"
        self.log_display.append_message(f"Exécution de: {npm_run_cmd}", INFO_COLOR)
        
        self.frontend_runner = CommandRunner(npm_run_cmd, cwd=FRONTEND_DIR)
        self.frontend_runner.output_received.connect(lambda msg: self.log_display.append_message(msg))
        self.frontend_runner.command_finished.connect(self.on_frontend_started)
        self.frontend_runner.start()
        
        # Simuler la progression pendant le démarrage du frontend
        self.frontend_progress_value = 60
        self.frontend_progress_timer.start(500)
    
    def update_frontend_progress(self):
        """Met à jour la barre de progression pendant le démarrage du frontend"""
        if self.frontend_progress_value < 90:
            self.frontend_progress_value += 1
            self.progress_bar.setValue(self.frontend_progress_value)
        elif self.frontend_progress_value == 90:
            self.frontend_progress_value += 1
            self.progress_bar.setValue(100)
            self.frontend_progress_timer.stop()
            
            # Ouvrir le navigateur après un court délai
            QTimer.singleShot(2000, self.open_browser)
            
            global frontend_running
            frontend_running = True
            self.frontend_status.update_status("En cours d'exécution", SUCCESS_COLOR)
            self.log_display.append_message("Frontend démarré avec succès", SUCCESS_COLOR)
            self.progress_label.setText("Application prête - Navigateur ouvert")
    
    def on_frontend_started(self, return_code):
        """Callback après le démarrage du frontend"""
        self.frontend_progress_timer.stop()
        
        if return_code != 0:
            self.log_display.append_message("Le frontend s'est arrêté de manière inattendue", ERROR_COLOR)
            self.frontend_status.update_status("Arrêté", ERROR_COLOR)
            self.progress_label.setText("Erreur: Le frontend s'est arrêté")
            global frontend_running
            frontend_running = False
    
    def stop_all(self):
        """Arrête tous les services"""
        global backend_process, frontend_process, docker_running, frontend_running
        
        self.log_display.clear()
        self.log_display.append_message("Arrêt des services en cours...", INFO_COLOR)
        self.progress_label.setText("Arrêt des services...")
        self.progress_bar.setValue(0)
        
        # Arrêter le frontend
        if frontend_running:
            self.log_display.append_message("Arrêt du frontend...", INFO_COLOR)
            self.frontend_status.update_status("Arrêt...", WARNING_COLOR)
            
            if self.frontend_runner:
                self.frontend_runner.terminate_process()
            
            frontend_running = False
            self.frontend_status.update_status("Arrêté", INFO_COLOR)
            self.progress_bar.setValue(50)
        
        # Arrêter Docker
        if docker_running:
            self.log_display.append_message("Arrêt de Docker...", INFO_COLOR)
            self.backend_status.update_status("Arrêt...", WARNING_COLOR)
            
            # Utiliser la commande Poetry
            stop_cmd = "python -m poetry run stop"
            self.log_display.append_message(f"Exécution de: {stop_cmd}", INFO_COLOR)
            
            self.stop_runner = CommandRunner(stop_cmd, cwd=BACKEND_DIR)
            self.stop_runner.output_received.connect(lambda msg: self.log_display.append_message(msg))
            self.stop_runner.command_finished.connect(self.on_docker_stopped)
            self.stop_runner.start()
        else:
            self.on_all_stopped()
    
    def on_docker_stopped(self, return_code):
        """Callback après l'arrêt de Docker"""
        global docker_running
        
        if return_code != 0:
            self.log_display.append_message("Avertissement: Problème lors de l'arrêt de Docker", WARNING_COLOR)
        
        docker_running = False
        self.backend_status.update_status("Arrêté", INFO_COLOR)
        self.progress_bar.setValue(100)
        
        self.on_all_stopped()
    
    def on_all_stopped(self):
        """Callback après l'arrêt de tous les services"""
        self.log_display.append_message("Tous les services ont été arrêtés", SUCCESS_COLOR)
        self.progress_label.setText("Services arrêtés")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
    
    def open_browser(self):
        """Ouvre l'application dans le navigateur"""
        webbrowser.open("http://localhost:3000")
        self.log_display.append_message("Application ouverte dans le navigateur", SUCCESS_COLOR)
    
    def closeEvent(self, event):
        """Gère l'événement de fermeture de la fenêtre"""
        if docker_running or frontend_running:
            reply = QMessageBox.question(
                self, 
                "Confirmation", 
                "Des services sont en cours d'exécution. Voulez-vous les arrêter et quitter?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Arrêter proprement tous les threads et processus avant de quitter
                if self.frontend_runner:
                    self.frontend_runner.terminate_process()
                if self.backend_runner:
                    self.backend_runner.terminate_process()
                if self.stop_runner:
                    self.stop_runner.terminate_process()
                
                # Attendre un peu pour laisser le temps aux processus de se terminer
                QTimer.singleShot(500, self.close)
                event.ignore()
            else:
                event.ignore()
        else:
            event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Définir le style global
    app.setStyle("Fusion")
    
    # Créer et afficher l'application
    launcher = LauncherApp()
    launcher.show()
    
    sys.exit(app.exec_())
