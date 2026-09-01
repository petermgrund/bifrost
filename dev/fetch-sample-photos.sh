set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/samples/photos"

UA="bifrost-dev-samples/0.1 (local development fixtures)"
fetch() { # fetch NAME URL
  if [ -s "$1" ]; then echo "have   $1"; return; fi
  echo "fetch  $1"
  curl -fsSL -A "$UA" --retry 3 -o "$1.part" "$2" && mv "$1.part" "$1"
}

fetch 1883-family-group-jones.jpg          "https://upload.wikimedia.org/wikipedia/commons/a/a7/A_family_group_%28Jones%29_%281883%29_NLW3364618.jpg"
fetch 1875-family-outside-a-house.jpg      "https://upload.wikimedia.org/wikipedia/commons/d/de/A_family_outside_a_house_NLW3364910.jpg"
fetch 1875-man-woman-five-children.jpg     "https://upload.wikimedia.org/wikipedia/commons/c/c7/A_group_including_a_man%2C_a_woman_and_five_children_NLW3364706.jpg"
fetch 1920-family-in-dining-room.jpg       "https://upload.wikimedia.org/wikipedia/commons/a/a2/Familie_poseert_in_de_eetkamer_rond_de_eettafel%2C_circa_1920%2C_SFA001005163.jpg"
fetch 1910-family-portrait-garden.jpg      "https://upload.wikimedia.org/wikipedia/commons/f/f4/Familieportret_in_een_tuin%2C_begin_20ste_eeuw%2C_SFA001007321.jpg"
fetch 1888-familjen-bergner.jpg            "https://upload.wikimedia.org/wikipedia/commons/2/23/Familjen_Bergner.jpg"
fetch 1886-krafft-ebing-family.jpg         "https://upload.wikimedia.org/wikipedia/commons/c/cd/Richard_von_Kraft-Ebing_mit_Familie_1886.jpg"

echo "done: $(ls *.jpg | wc -l | tr -d ' ') photos in dev/samples/photos; now run dev/bifrost-dev.sh seed"
