
# Behavior Backend

Bienvenue dans la partie backend, elle utilise **FastAPI**, **Docker**, et **Poetry** pour une gestion simplifiée des dépendances et de l'environnement. Le script `setup` est conçu pour automatiser la configuration initiale.

---

## Prérequis

Avant de commencer, assurez-vous d'avoir les outils suivants installés sur votre machine :

- **Python 3.10+** : [Télécharger ici](https://www.python.org/downloads/)
- **Poetry** : [Documentation officielle](https://python-poetry.org/docs/#installation)
- **Docker** et **Docker Compose** : [Télécharger Docker Desktop](https://www.docker.com/products/docker-desktop/)

---

## Installation et Configuration

Le projet est conçu pour être configuré facilement grâce au script `setup`. Voici les étapes à suivre :

1. **Récuperez le zip du code source**

2. **Exécutez le script de configuration :**

   Le script `setup` se charge des étapes suivantes :
   - Installation des dépendances via Poetry.
   - Construction des conteneurs Docker.

   Lancez simplement la commande suivante :

```bash
poetry install
poetry run setup
```

> NB: Vérifiez de docker-desktop est bien en cours d'exécution sur votre machine avant d'exécuter le script `setup`.

3. **Vérifiez que tout est prêt :**

   Une fois le script exécuté, vous devriez voir les conteneurs Docker démarrés et l'application prête à être utilisée.

---

## Exécution de l'Application

### Avec Docker

Si vous avez exécuté le script `setup`, les conteneurs Docker sont déjà construits et lancés. Vous n'avez rien d'autre à faire. Une interface de l'api sera accessible à l'adresse suivante :

```
http://localhost:8000/docs
```

Si vous souhaitez relancer les conteneurs manuellement, utilisez :

```bash
poetry run stop
poetry run docker
```

Si vous souhaitez réinitialiser les conteneurs, utilisez :

```bash
poetry run reset
```


### Localement (sans Docker)

1. Activez l'environnement virtuel Poetry :

```bash
poetry shell
```

2. Lancez l'application :

```bash
poetry install
poetry run startapp
```

L'application et la base de données MongoDB seront accessibles aux mêmes adresses que ci-dessus.
3. Pour arrêter l'application, utilisez :

```bash
poetry run stop
```
---

```bash 
poetry env info --path # Affiche le chemin de l'environnement virtuel
```
---

## Support
En cas de problème, les logs des conteneurs Docker peuvent vous aider à identifier la source du problème. Pour les consulter, utilisez la commande suivante :

```bash
poetry run logs
```