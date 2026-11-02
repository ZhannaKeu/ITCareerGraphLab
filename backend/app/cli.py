import argparse
import json
from pathlib import Path
from .db import SessionLocal
from .services.importer import import_dataset, inspect_dataset, ImportFailure

def main():
    parser = argparse.ArgumentParser(description="Validate and import versioned, read-only research CSVs")
    parser.add_argument("command", choices=["validate", "import"])
    parser.add_argument("directory", type=Path)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--activate", action="store_true", help="Switch active version; preserve all prior versions")
    args = parser.parse_args()
    try:
        if args.command == "validate":
            _, report = inspect_dataset(args.directory)
        else:
            with SessionLocal() as session:
                report = import_dataset(session, args.directory, args.demo, args.activate)
        print(json.dumps(report, indent=2, ensure_ascii=False))
    except ImportFailure as exc:
        print(json.dumps(exc.report, indent=2, ensure_ascii=False))
        raise SystemExit(1)
if __name__ == "__main__":
    main()
