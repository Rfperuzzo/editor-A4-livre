"""Copia avisos e licenças dos pacotes instalados para o bundle portátil."""
from importlib.metadata import distribution
from pathlib import Path
import shutil
import sys


target = Path(sys.argv[1]) / "third_party_licenses"
target.mkdir(parents=True, exist_ok=True)
for package in ("PySide6", "PySide6_Essentials", "PySide6_Addons", "shiboken6", "pypdf", "PyInstaller"):
    dist = distribution(package)
    for entry in dist.files or []:
        name = str(entry).lower()
        if any(word in name for word in ("license", "copying", "copyright")):
            source = Path(dist.locate_file(entry))
            if source.is_file():
                destination = target / package / Path(str(entry))
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
