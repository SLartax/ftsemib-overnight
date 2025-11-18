# FTSEMIB Overnight — Pattern Analyzer

**Auto-updating FTSEMIB backtest system using GitHub Actions + GitHub Pages**

## 🚀 Architettura

- **Python Compute** (`src/compute.py`): scarica dati live da Yahoo Finance, esegue backtest, esporta JSON
- **GitHub Actions** (`.github/workflows/update.yml`): esegue Python ogni 2:00 UTC (Lunedì–Venerdì)
- **GitHub Pages** (`docs/index.html`): frontend statico che legge i dati dal JSON e auto-aggiorna ogni 60s
- **JSON output** (`docs/data/status.json`): metriche, equity curve, ultime operazioni

## 📊 Funzionamento

1. **Ogni 2:00 UTC** (lunedì–venerdì):
   - GitHub Actions avvia il workflow
   - Scarica FTSEMIB.MI, SPY, VIX da Yahoo Finance
   - Esegue backtest con pattern TOP3
   - Genera `docs/data/status.json`
   - Effettua auto-commit e push

2. **Il sito** (`https://SLartax.github.io/ftsemib-overnight`):
   - Legge `data/status.json` ogni 60 secondi
   - Mostra equity curve, metriche, segnale per domani
   - Tabella ultime 100 operazioni

## 🎯 Pattern

- **TOP3 Logic**: Gap minimo + SPY flat + VIX ribasso + volumi bassi
- **Filtri**: SPY negativo (-0.5%) scarta il segnale
- **Esclusioni**: Venerdì escluso
- **Operazione**: Overnight FTSEMIB (close → open next)

## 📦 Struttura

```
ftsemib-overnight/
├── .github/
│   └── workflows/
│       └── update.yml          # CI/CD scheduler
├── docs/
│   ├── index.html              # Frontend statico
│   └── data/
│       └── status.json         # Output JSON (generato)
├── src/
│   ├── compute.py              # Script backtest
│   └── requirements.txt          # Dipendenze
├── .gitignore
└── README.md
```

## 🌐 Accesso

**URL Live**:
- https://slartax.github.io/ftsemib-overnight

**Aggiornamenti**:
- Automatici ogni 2:00 UTC (lunedì–venerdì)
- Manuale: GitHub Actions → Trigger workflow (dispatch)

## ⚙️ Setup Locale

```bash
pip install -r src/requirements.txt
python src/compute.py
```

Genera `docs/data/status.json` che il frontend legge.

## 📝 Note

- Nessun server sempre acceso, tutto su GitHub gratis
- Auto-aggiornamento garantito da GitHub Actions
- GitHub Pages serve il sito staticamente
- JSON ricompilato ogni 24h (schedule)

---
**FAI QUANT SUPERIOR** — Overnight FTSEMIB Pattern Analyzer  
Auto-aggiornante con GitHub Actions + GitHub Pages ✅
