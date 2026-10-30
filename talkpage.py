r"""Run talkpage from a clone or a downloaded zip without installing it, with any Python 3.9+:
python talkpage.py serve <root> ...  (the same commands as the installed `talkpage`)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))
from talkpage import main  # noqa: E402  (the package in src/, not this file)

main()
