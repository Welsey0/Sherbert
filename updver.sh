#!/bin/bash
# Tiny script to update version numbers in the files.
get_version() {
    read -p "Enter the version you want to apply: " version
    if [ -z "$version" ]; then
        echo "No version entered. Exiting."
        exit 1
    fi
}
TOML_FILE="pack.toml" # packwiz
JSON_FILE1="config/mutils/mutils.json5"  # mutils
JSON_FILE2="config/yosbr/config/mutils/mutils.json5"  # mutils in yosbr
get_version
sed -i.bak "s/localVersion: .*/localVersion: \"$version\",/" "$JSON_FILE1" # apply to jsons
sed -i.bak "s/localVersion: .*/localVersion: \"$version\",/" "$JSON_FILE2"
sed -i.bak "s/^version\s*=.*/version = \"$version\"/" "$TOML_FILE" # apply to toml
rm -f "$JSON_FILE1.bak" "$JSON_FILE2.bak" "$TOML_FILE.bak"
echo "JSON files updated with version '$version'."
