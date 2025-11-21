# Forking For Your Own Use
I encourage you to fork and use ST Family tooling for your own projects. I love Minecraft modding and find that the biggest barrier to playing modded with friends is the intracacies that can be required to set up a modpack. I hope my work here can make it just that little bit easier for you. If you plan to fork or copy ST Family tooling, please link back here or give credit in some way. Here are some instructions to set up properly.

## Step 1: Development Environment
Please see DEVELOPING.md to set up a development environment.

## Step 2: Setting Up Packwiz Pack

### If you want to keep Sherbert's existing content:
It would probably be easier to install Sherbert and then add the mods you want in your Minecraft launcher. I do not recommend this as much of Sherbert's content is tailored for specific use here. If you still want to do this, find `pack.toml` in the `src` folder and edit the information accordingly. Please do not distribute a pack containing Sherbert's colors or branding.

### If you want to start a new pack:
Delete the contents of the `src` folder but not the folder itself, Then make sure you are located in the `src` folder and run `../../packwiz init`. Follow the prompts to set up your new modpack! From there should delete the content of `modlists.sh` and fill it with your own mods if you want to use STM's Completion Helper. Add new mods with Packwiz.

## Step 3: Modrinth
The tooling included here is build to distribute this modpack on the [Modrinth platform](https://modrinth.com). Here are two support articles on making a modpack:
- [Modpacks on Modrinth - Modrinth Support](https://support.modrinth.com/en/articles/8802250-modpacks-on-modrinth)
- [Sharing Modpacks - Modrinth Support](https://support.modrinth.com/en/articles/8797522-sharing-modpacks)

## Step 4: API Keys
The GitHub Actions workflows included here require some Modrinth API keys as GitHub secrets in order to work properly. Head to the [Modrinth Personal Access Token page in your settings](https://modrinth.com/settings/pats) to create these keys. When creating a new PAT for your modpack, give it the following scopes:
- Create versions
- Write projects
- Write versions
After you have aquired a PAT, head to Settings > Secrets and variables > Actions and create a new repository secret. Name it `MODRINTH_TOKEN` and paste in your PAT. Hop back to the Modrinth page of your new modpack and find the three dots `More options` menu. Copy your modpack's ID and turn it into another GitHub secret called `MODRINTH_PID`.

## Step 5: Finishing Touches
In your GitHub repository settings, head to Actions > General, down to Workflow Permissions, and select `Read and write permissions`. Head over to `.github/workflows/publish.yml` and set the `PACK_NAME` variable to your own.

Congratulations, you've got a new modpack!

## Tips
- Refer to the [Packwiz documentation](https://packwiz.infra.link/) for more information on its use.