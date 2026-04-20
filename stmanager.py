# A command line tool with multiple options meant to be run from project root

# readInfo <function>
# - read the packinfo.toml file into readable format for every other function

# addRemotes <function>
# - runs the command 'packwiz mr add <id>' for every id provided in each modloader's src folder and proceeds through all of them. keeps the logs in a file called addremotes.log

# Individual Function Option
# Needs an additional arguement, name of function. Allows user to run internal functions seperately from others

# Folder Setup Option
#
# setupFolders <function>
# - delete folders matching 'src-*' if they exist (confirm this with user)
# - check packinfo for fabric and neo, if they are not 'none' than make src a folder for each loader named: src-<fabric/neo>
# - copy the config folder from the src directory to each of these new folders
# - make empty folders in the modloader src folders called 'mods', 'resourcepacks', 'shaderpacks'
# - check for remote exeptions and nonremotes in the packinfo file under the all tag and the corresponding mod loader tag for each folder
# - copy any nonremotes and/or remote-exceptions into their corresponding folders for each modloader folder
# - in each folder, copy a pack.toml from the templates directory and fill out the information with information from the packinfo file, filling the <!MODLOADER!> tag with the name of the modloader whose folder this pack.toml is going in
# updateUpdatables <function>
# - look for updatables in packinfo, if there are any version updatables than look for the listed file in any folder matching 'src-*' and replace the <!VERSION!> tag with version from packinfo

# Update Mods Option
# - run 'packwiz update' in each modloader src folder
# - use packwiz logs to find out how many were updated and list that to the user, also log it to modupdates.log

# Add Remotes Option
# - if there are .pw.toml files anywhere in the modloader 
# - use addRemotes function in  each modloader src folder but not the main one
# - parse resulting log for any errors
# - provide a short output listing the number of remotes successfully and unsuccessfully added, and a percentage
# - provide option to store a list of unsuccessfully added mods in 'unsuccessful.md' with a snippet of the packwiz log explaining why

# Completion Helper/Add Remotes Option
# Check how many of the things listed in packinfo.toml are present in each modloader src folder
#
# - report result to user


# Build Option
# - run 'packwiz refresh' in every folder matching 'src-*'
# - run 'packwiz mr export' in every folder matching 'src-*', in each folder rename the resulting .mrpack from <name>.mrpack to <name>-<name of loader for corresponding folder>.mrpack
# - move all the .mrpacks to project root
