#!/bin/bash
# A collection of tools for managing ST Family modpacks.
# Written by https://github.com/Welsey0 with the help of my good friend Al. :)

### Functions
change_version_num() {
  # Change modpack version number in the configs.
  TOML_FILE="pack.toml" # packwiz
  JSON_FILE1="config/mutils/mutils.json5"  # mutils
  JSON_FILE2="config/yosbr/config/mutils/mutils.json5"  # mutils in yosbr
  PACKINFO_FILE="../packinfo.sh"
  read -p "[CVN] Enter the version you want to apply: " version
  if [ -z "$version" ]; then
    echo "[CVN] No version entered. Exiting."
    exit 1
  fi
  sed -i.bak "s/localVersion: .*/localVersion: \"$version\",/" "$JSON_FILE1" # apply to jsons
  sed -i.bak "s/localVersion: .*/localVersion: \"$version\",/" "$JSON_FILE2"
  sed -i.bak "s/^version\s*=.*/version = \"$version\"/" "$TOML_FILE" # apply to toml
  # update version in packinfo.sh
  sed -i.bak 's/version="[0-9a-zA-Z._-]*"/version="'"$version"'"/' "$PACKINFO_FILE"
  rm -f "$JSON_FILE1.bak" "$JSON_FILE2.bak" "$TOML_FILE.bak" "$PACKINFO_FILE.bak"
  echo "[CVN] JSON files and packinfo.sh updated with version '$version'."
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
  MODLIST_FILE="../packinfo.sh"
  CHANGELOG="../cmp_output.md"

  echo "[CMP] Running Completion Helper..."

  # read packwiz index for mods/<slug>.pw.toml
  index_mods=()
  while IFS= read -r line; do
    index_mods+=("$line")
  done < <(grep 'file = "mods/.*\.pw\.toml"' "$INDEX_FILE" | sed -e 's/file = "mods\///' -e 's/\.pw\.toml"//')

  # read packinfo.sh
  source "$MODLIST_FILE"

  # note incompatible mods
  incompatible_list_mods=()
  # collect commented out mods and their comments
  commented_out_mods=()
  commented_out_comments=()
  while IFS= read -r line; do
    line_trimmed=$(echo "$line" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//') # trim whitespace
    if [[ "$line_trimmed" == *"# Currently incompatible"* ]]; then
      slug=$(echo "$line_trimmed" | awk '{print $1}' | sed 's/#//')
      [ -n "$slug" ] && incompatible_list_mods+=("$slug")
    fi
    # Only count commented out mod if there are two hashtags in the line
    if [[ "$line_trimmed" =~ ^#([a-zA-Z0-9_-]+).*#.*$ ]]; then
      mod_slug=$(echo "$line_trimmed" | sed -E 's/^#([a-zA-Z0-9_-]+).*/\1/')
      mod_comment=$(echo "$line_trimmed" | sed -E 's/^#[a-zA-Z0-9_-]+[[:space:]]*# ?(.*)/\1/')
      commented_out_mods+=("$mod_slug")
      commented_out_comments+=("$mod_comment")
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
    echo "### Mods in index but NOT in modlist (Please add to packinfo.sh modlist)"
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

    echo
    echo "### Mods commented out in modlist"
    echo
    if [ ${#commented_out_mods[@]} -eq 0 ]; then
      echo "- None"
    else
      for i in "${!commented_out_mods[@]}"; do
        mod="${commented_out_mods[$i]}"
        comment="${commented_out_comments[$i]}"
        if [ -n "$comment" ]; then
          echo "- $mod: $comment"
        else
          echo "- $mod"
        fi
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
  CHANGELOG="../mud_output.md"

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

setup_packwiz() {
  PACKWIZ="../../packwiz"
  PACKINFO="../packinfo.sh"
  PACK_TOML="pack.toml"
  INDEX_TOML="index.toml"
  REPORT="../stp_output.md"

  if [ -x "$PACKWIZ" ]; then
    PW_CMD="$PACKWIZ"
  elif command -v packwiz >/dev/null 2>&1; then
    PW_CMD="packwiz"
  else
    echo "[STP] packwiz executable not found at $PACKWIZ or in PATH"
    return 1
  fi

  echo "[STP] Running Setup Packwiz..."

  {
    echo "# Packwiz Setup Report"
    echo
    
    # Check if pack.toml exists
    if [ -f "$PACK_TOML" ]; then
      echo "### Existing pack.toml Found"
      echo
      
      # Source packinfo.sh to get pack metadata
      if [ ! -f "$PACKINFO" ]; then
        echo "⚠️ **ERROR:** $PACKINFO not found. Cannot verify pack metadata."
        echo
      else
        source "$PACKINFO"
        
        # Extract values from pack.toml
        toml_name=$(grep -E '^\s*name\s*=' "$PACK_TOML" | head -1 | sed -E 's/.*=\s*"?([^"]*)"?.*/\1/')
        toml_author=$(grep -E '^\s*author\s*=' "$PACK_TOML" | head -1 | sed -E 's/.*=\s*"?([^"]*)"?.*/\1/')
        toml_version=$(grep -E '^\s*version\s*=' "$PACK_TOML" | head -1 | sed -E 's/.*=\s*"?([^"]*)"?.*/\1/')
        
        # Extract values from info array in packinfo.sh
        info_name=$(grep -oP 'name="\K[^"]+' "$PACKINFO" | head -1)
        info_author=$(grep -oP 'author="\K[^"]+' "$PACKINFO" | head -1)
        info_version=$(grep -oP 'version="\K[^"]+' "$PACKINFO" | head -1)
        
        echo "**pack.toml metadata:**"
        echo "- Name: $toml_name"
        echo "- Author: $toml_author"
        echo "- Version: $toml_version"
        echo
        
        echo "**packinfo.sh metadata:**"
        echo "- Name: ${info_name:-[not set]}"
        echo "- Author: ${info_author:-[not set]}"
        echo "- Version: ${info_version:-[not set]}"
        echo
        
        # Check for mismatches
        mismatch=0
        if [ "$toml_name" != "$info_name" ]; then
          echo "⚠️ **MISMATCH:** Name differs"
          mismatch=1
        fi
        if [ "$toml_author" != "$info_author" ]; then
          echo "⚠️ **MISMATCH:** Author differs"
          mismatch=1
        fi
        if [ "$toml_version" != "$info_version" ]; then
          echo "⚠️ **MISMATCH:** Version differs"
          mismatch=1
        fi
        if [ $mismatch -eq 0 ]; then
          echo "✓ All metadata matches"
        fi
        echo
      fi
    else
      echo "### No pack.toml Found"
      echo "Packwiz has not been initialized in this directory yet."
      echo
    fi
    
    # Check for .zip and .jar files
    echo "### Scanning for .zip and .jar files"
    echo
    zip_jar_files=$(find . -type f \( -name "*.zip" -o -name "*.jar" \) 2>/dev/null)
    if [ -n "$zip_jar_files" ]; then
      echo "⚠️ **WARNING:** Found .zip/.jar files in directory:"
      echo "$zip_jar_files" | while read -r f; do
        echo "- $f"
      done
      echo
    else
      echo "✓ No .zip or .jar files found"
      echo
    fi
    
    # Check .pw.toml files in all folders
    echo "### Validating .pw.toml files"
    echo
    if [ ! -f "$PACKINFO" ]; then
      echo "⚠️ Cannot validate: $PACKINFO not found"
      echo
    else
      source "$PACKINFO"
      
      pw_toml_files=$(find . -name "*.pw.toml" 2>/dev/null | sed -E 's|.*/||; s|\.pw\.toml$||' || true)
      
      toml_only=()
      for toml_mod in $pw_toml_files; do
        if ! contains_element "$toml_mod" "${modlist[@]}"; then
          toml_only+=("$toml_mod")
        fi
      done
      
      if [ ${#toml_only[@]} -gt 0 ]; then
        echo "⚠️ **WARNING:** .pw.toml files found but NOT in modlist:"
        for mod in "${toml_only[@]}"; do
          echo "- $mod"
        done
        echo
      else
        echo "✓ All .pw.toml files match modlist"
        echo
      fi
    fi
    
    echo "### Next Steps (read me)"
    echo
    if [ -f "$PACK_TOML" ] && [ $mismatch -eq 0 ]; then
      echo "Continuing with this script will remove packwiz-added projects in order for you to re-add them.\nIt's intended to help with migrating to a new version of Minecraft.\n\nAfter running this script, run \`../../packwiz init\` and then use the Autofill Modlist tool."
    else
      echo "Run \`../../packwiz init\` and then use the Autofill Modlist tool to rebuild the packwiz files."
    fi
    
  } > "$REPORT"
  
  echo "[STP] Wrote setup report to $REPORT"
  echo "[STP] Please review the report at $REPORT"
  
  read -p "[STP] Delete all .pw.toml files, pack.toml, and index.toml? (y/N): " cleanup_ans
  if [[ "$cleanup_ans" =~ ^[Yy]$ ]]; then
    echo "[STP] Deleting .pw.toml, pack.toml, and index.toml files..."
    find . -name "*.pw.toml" -delete 2>/dev/null
    rm -f "$PACK_TOML" "$INDEX_TOML"
    echo "[STP] Cleanup complete."
  fi
  
  return 0
}

autofill_modlist() {
  MODLIST_FILE="../packinfo.sh"
  PACKWIZ="../../packwiz"
  LOGFILE="../afm.log"

  echo "[AFM] Running Autofill Modlist..."
  # source modlist
  if [ ! -f "$MODLIST_FILE" ]; then
    echo "[AFM] $MODLIST_FILE not found." >&2
    return 1
  fi

  source "$MODLIST_FILE"

  # build list of mods explicitly marked "Currently incompatible" in the file
  incompatible_list_mods=()
  while IFS= read -r line; do
    line_trimmed=$(echo "$line" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
    if [[ "$line_trimmed" == *"Currently incompatible"* ]]; then
      slug=$(printf '%s' "$line_trimmed" | awk '{print $1}' | sed 's/^#//')
      [ -n "$slug" ] && incompatible_list_mods+=("$slug")
    fi
  done < "$MODLIST_FILE"

  : > "$LOGFILE"
  echo "[AFM] Using '$PW_CMD' -- logging to $LOGFILE"

  for mod in "${modlist[@]}"; do
    # skip empty entries
    [ -z "$mod" ] && continue

    echo
    echo "[AFM] Processing mod: $mod" | tee -a "$LOGFILE"

    if contains_element "$mod" "${incompatible_list_mods[@]}"; then
      read -p "[AFM] '$mod' is marked 'Currently incompatible'. Add anyway and attempt version-exception/add? (y/N): " ans
      case "$ans" in
        [Yy]* )
          echo "[AFM] Attempting to add '$mod' despite incompatibility..." | tee -a "$LOGFILE"
          if "$PW_CMD" mr add "$mod" 2>&1 | tee -a "$LOGFILE"; then
            echo "[AFM] Added $mod" | tee -a "$LOGFILE"
          else
            echo "[AFM] Initial add failed for $mod. Asking to retry with --force." | tee -a "$LOGFILE"
            read -p "[AFM] Retry add with --force? (y/N): " forceans
            if [[ "$forceans" =~ ^[Yy]$ ]]; then
              if "$PW_CMD" mr add "$mod" --force 2>&1 | tee -a "$LOGFILE"; then
                echo "[AFM] Added $mod with --force" | tee -a "$LOGFILE"
              else
                echo "[AFM] Adding $mod failed even with --force. Please add manually. See $LOGFILE" | tee -a "$LOGFILE"
              fi
            else
              echo "[AFM] Skipping $mod after failed add." | tee -a "$LOGFILE"
            fi
          fi
          ;;
        * )
          echo "[AFM] Skipping $mod (left incompatible)" | tee -a "$LOGFILE"
          ;;
      esac
    else
      # normal add
      if "$PW_CMD" mr add "$mod" 2>&1 | tee -a "$LOGFILE"; then
        echo "[AFM] Added $mod" | tee -a "$LOGFILE"
      else
        echo "[AFM] Failed to add $mod. See $LOGFILE for details." | tee -a "$LOGFILE"
      fi
    fi
  done

  echo
  echo "[AFM] Autofill complete. See $LOGFILE for detail."
}

### Menu
clear
parent_dir=$(basename $PWD)
if [ "$parent_dir" != "src" ]; then
  echo "[STM] Make sure you're in src."
  exit 1
fi
echo -e "Select a Tool\n1: Completion Helper\n2: Mod Updater\n3: Change Version Number\n4: Autofill Modlist\n5: Setup Packwiz"
read number
case $number in
  1)
    completion_helper
    ;;
  2)
    mod_updater
    ;;
  3)
    change_version_num
    ;;
  4)
    autofill_modlist
    ;;
  5)
    setup_packwiz
    ;;
  *)
    echo "Invalid selection. Please enter a number between 1 and 3."
    ;;
esac