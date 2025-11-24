# quick test script for AssetFinder.find_many
# Usage (from project root):
#   python -m core.test_find "D:\\path\\to\\0000"
import sys
from pathlib import Path
from core.asset_finder import AssetFinder

def main():
    if len(sys.argv) < 2:
        print("Usage: python -m core.test_find <path_to_0000_folder>")
        return 1
    path = sys.argv[1]
    print("Testing AssetFinder on:", path)
    finder = AssetFinder()
    targets = [
        ("CARD_Desc","21ae1efa"),
        ("CARD_Indx","507764bc"),
        ("CARD_Name","7438cca8"),
        ("Card_Part","52739c94"),
        ("Card_Pidx","494e34d0"),
        ("CARD_Prop","85757744"),
        ("WORD_Text","f5361426"),
        ("WORD_Indx","b4d165f3"),
        ("CardPictureFontSetting","fcd008c9"),
    ]
    results = finder.find_many(path, targets)
    print("Results:")
    for r in results:
        print(r)
    # Also print some quick diagnostics: first 10 files under path (to confirm filesystem access)
    p = Path(path)
    if p.exists():
        print("\nSample files under the folder (first 20):")
        i = 0
        for f in p.rglob("*"):
            if f.is_file():
                print(f)
                i += 1
                if i >= 20:
                    break
    else:
        print("Provided path does not exist:", path)
    return 0

if __name__ == "__main__":
    sys.exit(main())