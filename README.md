# Interface Web de Recherche

Faire :

```bash 
pip install PyQt5==5.15.9 --only-binary :all:
pip install poetry
```

et 

```bash
python launcher.py
```

En cas d'erreur de proxy, il faut se rendre dans docker-desktop, en haut à droite cliquer sur l'icône de la roue dentée, puis dans "ressouces", "Proxies". Activer manual proxy, laisser les deux premières cases vides et mettre dans la dernière case :

```bash
registry-1.docker.io,docker.io
```