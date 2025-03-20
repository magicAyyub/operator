# Interface Web de Recherche

Transforme un fichier brute txt en csv nettoyé téléchargeable. Chargement dans une base de donnée. Recherche simple, avec CSV ou avec expression régulière sur la base de donnée. 

## Première installation

### 1. Installez les logiciels requis

Avant de commencer, vous devez installer deux logiciels :

1. **Docker Desktop** 
   - Téléchargez-le ici : [Docker Desktop](https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe)
   - Installez-le en suivant les instructions à l'écran
   - Lancez Docker Desktop depuis votre bureau

2. **Node.js**
   - Téléchargez-le ici : [Node.js](https://nodejs.org/)
   - Choisissez la version "LTS" (bouton de gauche)
   - Installez-le en suivant les instructions à l'écran

### 2. Installez l'application

1. Récupérer le code source sur [ici](https://github.com/magicAyyub/data-interface)
2. Extrayez le fichier ZIP où vous voulez
3. Double-cliquez sur `setup.bat`
4. Attendez que l'installation se termine

> 💡 Cette installation n'est à faire qu'une seule fois !

## Utilisation quotidienne

1. Lancez Docker Desktop
2. Double-cliquez sur `start.bat`
3. L'application s'ouvre automatiquement dans votre navigateur !

## Fonctionnalités

### Recherche simple
- Remplissez les champs que vous connaissez
- Utilisez "Recherche flexible" si vous n'êtes pas sûr de l'orthographe
- Cliquez sur "Plus de critères" pour plus d'options

### Recherche par fichier CSV
- Déposez votre fichier CSV dans la zone prévue
- Les résultats se téléchargent automatiquement

### Recherche avancée (Regex)
Pour rechercher des emails avec des critères spécifiques

## Besoin d'aide ?

Si l'application ne démarre pas :
1. Vérifiez que Docker Desktop est bien lancé (icône dans la barre des tâches)
2. Fermez tout et réessayez avec `start.bat`
3. Si le problème persiste, contactez [magicAyyub](https://github.com/magicAyyub)