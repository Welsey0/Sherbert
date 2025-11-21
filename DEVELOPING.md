# Developing for ST Family Modpacks
Here are some instructions to properly set up a development environment for modpacks that use ST Family tooling.

## Step 1: Packwiz
Grab the latest Packwiz executable for your platform; instructions are at [the repository](https://github.com/packwiz/packwiz).

## Step 2: Clone Repo
Find a place to put your development environment. Mine is in a folder called Modpacks. Drop your packwiz executable in that folder, and then run the following command from your folder:
``` 
git clone https://github.com/Welsey0/Sherbert.git
```

## Step 3: Ensure Organization
Make sure your folders are organized as depicted below:
```
Root Folder (In my case called Modpacks)
├── packwiz executable
└── Pack Name (In my case Sherbert)
    ├── .github
    ├── src
    └── (etc.)
```

## Tips
- Always work from your `src` folder.
- Run packwiz by typing `../../packwiz`
- Run ST Manager by typing `../stmanager.sh` or `bash ../stmanager.sh`.
- Pushing to `changelog.md` will release a new version.
- Pushing to `README.md` will update the Modrinth description to follow suit.
- Remember to update the version number with ST Manager for each new version.