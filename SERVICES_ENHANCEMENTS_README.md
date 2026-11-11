# System Monitoring Center – Services-forbedringer

Dette er lokale tilpasninger til [System Monitoring Center](https://github.com/hakandundar34coding/system-monitoring-center) v3.4.1 i [gausus2-forken](https://github.com/gausus2/system-monitoring-center). Endringene ligger på grenen `services-enhancements` og er ikke en del av originalprosjektet.

## Hva er endret?

- **Services lastes uten Python multiprocessing:** I `src/Libsysmon.py` bruker `get_services_information()` den eksisterende enkeltprosess-løsningen ved å sette `number_of_logical_cores = 2` lokalt i funksjonen. Dette løste et konkret problem med lasting av Services på Xubuntu 24.04.5 / Ryzen 7 5700G. Det endrer ikke antall CPU-kjerner systemet har, og påvirker ikke CPU-overvåkingen ellers.
- **To nye høyreklikkvalg i Services:** `Edit override` og `Edit full unit` i `src/Services.py`. Begge åpner Xfce Terminal og `nano` gjennom `sudo systemctl edit`. Endringen er laget for Xubuntu/Xfce, ikke testet på alle skrivebordsmiljøer.

## Hent forken første gang (SSH)

```bash
git clone git@github.com:gausus2/system-monitoring-center.git
cd system-monitoring-center
git fetch origin
git switch --track origin/services-enhancements
```

Hvis grenen allerede eksisterer lokalt, bruk `git switch services-enhancements`.

## Hent senere oppdateringer fra din fork

Kjør fra repositorykatalogen:

```bash
git switch services-enhancements
git pull --ff-only origin services-enhancements
```

Hvis du har egne lokale endringer som hindrer oppdatering, sjekk først `git status` og commit eller stash dem. Ikke kjør `git reset --hard` uten å forstå konsekvensene.

## Installer endringene i System Monitoring Center

Disse kommandoene passer en installasjon med Python-filene under `/usr/share/system-monitoring-center/systemmonitoringcenter/`. Kjør dem fra roten av repositoryet. Lukk programmet før du kopierer filene.

```bash
DEST=/usr/share/system-monitoring-center/systemmonitoringcenter
test -f "$DEST/Services.py" && test -f "$DEST/Libsysmon.py" || { echo "Finner ikke installasjonen"; exit 1; }

# Lag sikkerhetskopier bare første gang – ikke overskriv backup ved senere oppdateringer.
for file in Services.py Libsysmon.py; do
    if [ ! -e "$DEST/$file.pre-services-enhancements" ]; then
        sudo cp -a "$DEST/$file" "$DEST/$file.pre-services-enhancements"
    fi
done

# Sjekk Python-syntaks uten å skrive __pycache__ i systemkatalogen.
python3 - <<'PY'
from pathlib import Path
for name in ("Services.py", "Libsysmon.py"):
    path = Path("src") / name
    compile(path.read_bytes(), str(path), "exec")
    print(f"{name}: syntax OK")
PY

sudo install -m 644 src/Services.py "$DEST/Services.py"
sudo install -m 644 src/Libsysmon.py "$DEST/Libsysmon.py"
```

Start programmet på nytt og åpne **Services**.

**Ved senere oppdateringer:** Kjør først `git pull --ff-only` som ovenfor, og installer deretter de oppdaterte filene på nytt.

## Bruk av nye høyreklikkvalg

Høyreklikk på en systemd-tjeneste i **Services**:

| Menyvalg | Tilsvarer | Effekt |
| --- | --- | --- |
| **Edit override** | `sudo systemctl edit TJENESTE.service` | Oppretter/redigerer vanligvis en drop-in under `/etc/systemd/system/TJENESTE.service.d/`. Anbefalt for lokale tilpasninger. |
| **Edit full unit** | `sudo systemctl edit --full TJENESTE.service` | Redigerer en full lokal kopi av unit-filen under `/etc/systemd/system/`. Kan overstyre fremtidige endringer i leverandørens unit-fil. |

Begge valg åpner `xfce4-terminal` med `nano` som editor. Du kan avslutte uten å lagre med `Ctrl+X` (svar **N** om editoren spør om lagring). Ved lagring utfører `systemctl edit` normalt `daemon-reload`, men starter **ikke** tjenesten på nytt.

Du trenger `xfce4-terminal`, `sudo` og `nano` installert. Programmet forutsetter at Xfce Terminal kan åpnes i den grafiske økten.

**Merk:** `Edit full unit` er mer inngripende enn en override. Ta vare på endringene dine og foretrekk **Edit override** der det er mulig. Test med en ufarlig tjeneste først.

## Gjenopprett tidligere installasjon

Lukk programmet og kjør:

```bash
DEST=/usr/share/system-monitoring-center/systemmonitoringcenter
sudo cp -a "$DEST/Services.py.pre-services-enhancements" "$DEST/Services.py"
sudo cp -a "$DEST/Libsysmon.py.pre-services-enhancements" "$DEST/Libsysmon.py"
```

Gjenoppretting virker bare dersom sikkerhetskopiene finnes. En pakkeoppdatering kan overskrive de installerte filene; endringene kan da installeres på nytt fra forken.

## Hent endringer fra originalprosjektet (upstream)

Dette er **ikke** det samme som å hente oppdateringer fra `origin` (din egen fork).

```bash
git remote add upstream git@github.com:hakandundar34coding/system-monitoring-center.git
git fetch upstream
```

Legg til `upstream` bare én gang (se `git remote -v`). Sammenlign før du fletter:

```bash
git log --oneline --left-right services-enhancements...upstream/master
git diff services-enhancements..upstream/master -- src/Services.py src/Libsysmon.py
```

For å integrere nye upstream-endringer: gjør det i en separat testgren og gjennomgå eventuelle konflikter, spesielt i `Services.py` og `Libsysmon.py`. Ikke anta at denne v3.4.1-tilpasningen fortsatt passer uendret til senere versjoner.

## Status

- Bekreftet: Services-fanen fungerer med enkeltprosess-workaround på Xubuntu 24.04.5.
- Bekreftet av bruker: nytt høyreklikkvalg åpner editor.
- Ikke fullstendig testet: alle tjenester, alle skrivebordsmiljøer og fremtidige upstream-versjoner.

Originalkoden er lisensiert under **GNU GPL v3**. Behold copyright- og lisensinformasjonen ved videre distribusjon.
