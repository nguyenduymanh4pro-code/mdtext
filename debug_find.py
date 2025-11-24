# debug_find.py
# Usage: python debug_find.py "<path_to_0000>"
import sys, json
from pathlib import Path
from core.asset_finder import AssetFinder

def main(p):
    p = Path(p)
    print("Checking path:", p)
    print("Exists:", p.exists(), "IsDir:", p.is_dir())
    # simple list sample
    print("Sample entries (first 40):")
    for i, item in enumerate(p.iterdir()):
        if i >= 40: break
        print("  ", item.name)
    finder = AssetFinder()
    targets = [
        ("CARD_Desc", "21ae1efa"),
        ("CARD_Indx", "507764bc"),
        ("CARD_Name", "7438cca8"),
        ("Card_Part", "52739c94"),
        ("Card_Pidx", "494e34d0"),
        ("CARD_Prop", "85757744"),
        ("WORD_Text", "f5361426"),
        ("WORD_Indx", "b4d165f3"),
        ("CardPictureFontSetting", "fcd008c9"),
    ]
    print("\nRunning find_many() ... (this may take a little while if full scan needed)")
    res = finder.find_many(str(p), targets)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_find.py <path_to_0000>")
        sys.exit(2)
    sys.exit(main(sys.argv[1]))