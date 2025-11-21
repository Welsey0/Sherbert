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

# cmp helper
contains_element() {
  local e match="$1"
  shift
  for e; do [[ "$e" == "$match" ]] && return 0; done
  return 1
}

completion_helper() {
  INDEX_FILE="index.toml"
  MODLIST_FILE="../modlists.sh"
  CHANGELOG="../cmp_output.md"

  echo "[CMP] Running Completion Helper..."

  # read packwiz index for mods/<slug>.pw.toml
  index_mods=()
  while IFS= read -r line; do
    index_mods+=("$line")
  done < <(grep 'file = "mods/.*\.pw\.toml"' "$INDEX_FILE" | sed -e 's/file = "mods\///' -e 's/\.pw\.toml"//')

  # read modlists.sh
  source "$MODLIST_FILE"
  
  # note imcompatible mods
  incompatible_list_mods=()
  while IFS= read -r line; do
    line_trimmed=$(echo "$line" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//') # trim whitespace
    if [[ "$line_trimmed" == *"# Currently incompatible"* ]]; then
      slug=$(echo "$line_trimmed" | awk '{print $1}' | sed 's/#//')
      [ -n "$slug" ] && incompatible_list_mods+=("$slug")
    fi
  done < "$MODLIST_FILE"

  # compare lists
  
  # in index but not in modlist
  in_index_not_list=()
  for mod in "${index_mods[@]}"; do
    if ! contains_element "$mod" "${modlist[@]}"; then
      in_index_not_list+=("$mod")
    fi
  done
  
  # in modlist but not in index
  in_list_not_index=()
  for mod in "${modlist[@]}"; do
    if ! contains_element "$mod" "${index_mods[@]}"; then
      in_list_not_index+=("$mod")
    fi
  done
  
  # categorize missing mods (in_list_not_index)
  missing_mods=()
  incompatible_missing_mods=()
  
  for mod in "${in_list_not_index[@]}"; do
    if contains_element "$mod" "${incompatible_list_mods[@]}"; then
      incompatible_missing_mods+=("$mod")
    else
      missing_mods+=("$mod")
    fi
  done

  # report findings
  num_index_mods=${#index_mods[@]}
  num_incompatible_mods=${#incompatible_list_mods[@]}
  num_list_mods=$(( ${#modlist[@]} - num_incompatible_mods )) # only active mods
  
  found_in_index=0
  for mod in "${modlist[@]}"; do
    if contains_element "$mod" "${index_mods[@]}"; then
      found_in_index=$((found_in_index + 1))
    fi
  done

  percent=0
  if [ $num_list_mods -gt 0 ]; then
    percent=$(awk "BEGIN {printf \"%.0f\", ($found_in_index / $num_list_mods) * 100}")
  fi
  
  {
    echo "# Completion Summary"
    echo
    echo "### Mods in index but NOT in modlist (Please add to modlists.sh)"
    echo
    if [ ${#in_index_not_list[@]} -eq 0 ]; then
      echo "- None"
    else
      for mod in "${in_index_not_list[@]}"; do
        echo "- $mod"
      done
    fi

    echo
    echo "### Mods in modlist but NOT in index (Missing from pack)"
    echo
    if [ ${#missing_mods[@]} -eq 0 ]; then
      echo "- None"
    else
      for mod in "${missing_mods[@]}"; do
        echo "- $mod"
      done
    fi
    
    echo
    echo "### Mods in modlist but NOT in index (Marked as incompatible)"
    echo
    if [ ${#incompatible_missing_mods[@]} -eq 0 ]; then
      echo "- None"
    else
      for mod in "${incompatible_missing_mods[@]}"; do
        echo "- $mod"
      done
    fi

    # summary
    echo
    echo "### Summary"
    echo
    echo "- **Mods in index:** $num_index_mods"
    echo "- **Mods in modlist (active):** $num_list_mods"
    echo "- **Completion:** $percent% ($found_in_index / $num_list_mods active mods from list are in index)"
    echo
  } > "$CHANGELOG"
  
  echo "[CMP] Wrote completion summary to $CHANGELOG"
  exit 0
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
echo -e "Select a Tool\n1: Completion Helper\n2: Mod Updater"
read number
case $number in
  1)
    completion_helper
    ;;
  2)
    mod_updater
    ;;
  *)
    echo "Invalid selection. Please enter a number between 1 and 3."
    ;;
esac