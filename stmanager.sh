#!/bin/bash
# A collection of tools for managing ST Family modpacks.
# Written by https://github.com/Welsey0

### Functions
change_version_num() {
  # Change modpack version number in the configs.
  TOML_FILE="pack.toml" # packwiz
  JSON_FILE1="config/mutils/mutils.json5"  # mutils
  JSON_FILE2="config/yosbr/config/mutils/mutils.json5"  # mutils in yosbr
  read -p "[CVN] Enter the version you want to apply: " version
  if [ -z "$version" ]; then
    echo "[CVN] No version entered. Exiting."
    exit 1
  fi
  sed -i.bak "s/localVersion: .*/localVersion: \"$version\",/" "$JSON_FILE1" # apply to jsons
  sed -i.bak "s/localVersion: .*/localVersion: \"$version\",/" "$JSON_FILE2"
  sed -i.bak "s/^version\s*=.*/version = \"$version\"/" "$TOML_FILE" # apply to toml
  rm -f "$JSON_FILE1.bak" "$JSON_FILE2.bak" "$TOML_FILE.bak"
  echo "[CVN] JSON files updated with version '$version'."
  exit 0
}
update_compat_checker() {
  # USE ONLY ON NV BRANCHES
  # Assist in converting modpack to new Minecraft versions.
  exit 1
}
completion_helper() {
  # Check modlist for missing/currently incompatible mods
  #   Read packwiz index to find all included mods
  #   Read modlist to find all listed mods
  #   If mod is in index but not modlist:
  #     Warn user and provide slug so they can fix that
  #   If mod is in modlist but not index:
  #     Check compatibility and add to list of missings
  #   At end, list (mods in index/mods in list) as numbers and percent, list missing/incompatible mods
  exit 1
}
mod_updater() {
  PACKWIZ="../../packwiz"
  OUTFILE="../packwiz_update.log"

  if [ -x "$PACKWIZ" ]; then
    PW_CMD="$PACKWIZ"
  elif command -v packwiz >/dev/null 2>&1; then
    PW_CMD="packwiz"
  else
    echo "[MUD] packwiz executable not found at $PACKWIZ or in PATH"
    return 1
  fi

  echo "[MUD] Running $PW_CMD update --all, logging to $OUTFILE"
  # stdout stderr capture
  "$PW_CMD" update --all 2>&1 | tee "$OUTFILE"
  rc=${PIPESTATUS[0]:-0}

  parse_packwiz_output

  return $rc
}

parse_packwiz_output() {
  # Parse ../packwiz_update.log and emit a markdown summary similar to README.md formatting.
  LOGFILE="../packwiz_update.log"
  CHANGELOG="../MUD_output.md"

  if [ ! -f "$LOGFILE" ]; then
    echo "[MUD] No packwiz log found at $LOGFILE. Run update first."
    return 1
  fi

  WARNINGS=$(grep -E '^Warning:' "$LOGFILE" | sed 's/^Warning: //g' || true)
  UPDATES=$(awk 'BEGIN{p=0} /Updates found:/{p=1; next} /Do you want to update\?/{p=0} p' "$LOGFILE" | sed '/^[[:space:]]*$/d' || true)
  # were updates applied?
  APPLIED=$(grep -F 'Files updated!' "$LOGFILE" || true)

  {
    echo "# Packwiz Update Summary"
    echo
    if [ -n "$WARNINGS" ]; then
      echo "### Warnings"
      echo
      echo "$WARNINGS" | while IFS= read -r w; do
        echo "- $w"
      done
      echo
    fi

    echo "### Updated Mods"
    echo
    if [ -n "$UPDATES" ]; then
      # formatting
      echo "$UPDATES" | while IFS= read -r line; do
        [ -z "$line" ] && continue
        modname=$(printf '%s' "$line" | cut -d: -f1)
        rest=$(printf '%s' "$line" | cut -d: -f2- | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')
        if printf '%s' "$rest" | grep -q '->'; then
          old=$(printf '%s' "$rest" | awk -F'->' '{print $1}' | sed 's/[[:space:]]*$//')
          new=$(printf '%s' "$rest" | awk -F'->' '{print $2}' | sed 's/^[[:space:]]*//')
          echo "- $modname: \`$old\` → \`$new\`"
        else
          # add raw lines if they dont have an arrow
          echo "- $modname: \`$rest\`"
        fi
      done
    else
      echo "- None"
    fi

    echo
    if [ -n "$APPLIED" ]; then
      echo "**Result:** Files updated!"
    else
      if grep -q "Do you want to update" "$LOGFILE"; then
        echo "**Result:** Update prompt shown; no confirmation found in log."
      else
        echo "**Result:** No updates applied."
      fi
    fi
  } > "$CHANGELOG"

  echo "[MUD] Wrote update summary to $CHANGELOG"
  return 0
}
### Menu
clear
parent_dir=$(basename $PWD)
if [ "$parent_dir" != "src" ]; then
  echo "[STM] Make sure you're in src."
  exit 1
fi
echo -e "Select a Tool\n1: Change Version Number\n2: Update Compat Checker\n3: Mod Updater"
read number
case $number in
  1)
    change_version_num
    ;;
  2)
    update_compat_checker
    ;;
  3)
    mod_updater
    ;;
  *)
    echo "Invalid selection. Please enter a number between 1 and 3."
    ;;
esac

