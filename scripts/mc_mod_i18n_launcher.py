import sys

from mc_mod_i18n.cli import main


if __name__ == "__main__":
    args = sys.argv[1:] or ["desktop"]
    raise SystemExit(main(args))
