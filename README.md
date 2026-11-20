# KI-Analysten-Team

Neunzehn KI-Analysten schauen sich eine Aktie an. Dreizehn davon arbeiten im Stil bekannter Investoren wie Buffett, Lynch oder Burry, dazu kommen sechs Fach-Analysten für Bewertung, Fundamentaldaten, Wachstum, Charttechnik, Stimmung und Nachrichten. Ein Risiko- und ein Portfolio-Manager fassen alles zusammen. Am Ende hast du ein Urteil je Analyst und ein Gesamtbild.

Das ist eine deutsche Fassung von [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund) (MIT-Lizenz). Die Kurse und Abschlüsse kommen hier über yfinance, ohne eigenen Datenschlüssel, und deutsche Aktien wie `SAP.DE` funktionieren. **Nur zum Lernen. Keine Anlageberatung. Das Programm handelt nicht und gibt keine Orders auf.**

## So startest du

**1 · Projekt holen.** Am besten in einen eigenen Ordner, nicht in ein anderes Projekt.

```bash
git clone https://github.com/MellowMind7/ki-analysten-team.git
cd ki-analysten-team
```

**2 · Schlüssel für das Sprachmodell.** Du brauchst genau einen, den von [OpenRouter](https://openrouter.ai/settings/keys). Darüber erreichst du viele Modelle mit einem Konto. Leg dort einen eigenen Schlüssel für dieses Projekt an und setz ein Ausgabenlimit, zum Beispiel 5 Dollar. Dann legst du im Projektordner eine Datei `.env` mit dieser einen Zeile an und trägst den Schlüssel hinter dem Gleichheitszeichen ein:

```
OPENROUTER_API_KEY=
```

Die `.env` liest das Programm selbst aus dem Ordner, aus dem du es startest. Sie gehört nicht zu GitHub, das verhindert die `.gitignore`.

**3 · Einrichten.** Mit [uv](https://docs.astral.sh/uv/), Poetry brauchst du nicht.

```bash
uv venv --python 3.12
uv pip install -e .
```

**4 · Laufen lassen, ohne Auswahlmenü.** Aus dem Projektordner:

```bash
.venv/bin/python src/main.py --tickers SAP.DE --analysts-all --model deepseek/deepseek-chat --show-reasoning
```

Unter Windows heißt der Anfang `.venv\Scripts\python src\main.py`, der Rest bleibt gleich.

Ohne `--analysts-all` und `--model` fragt das Programm beides über ein Menü ab, und das geht nicht, wenn Claude oder ein Skript es startet. Lass die beiden Angaben also immer drin.

Mit `--save-json reports/SAP.DE-lauf.json` speichert das Programm den ganzen Lauf zusätzlich als Datei: jedes Signal, jede Konfidenz, jede Begründung und die Entscheidung. Daraus lässt sich später ein Report bauen, auch in einem neuen Chat.

## Welches Modell

Bei `--model` gelten nur diese Namen, genau so geschrieben (Liste in `src/llm/api_models.json`):

| Name | Wofür |
|---|---|
| `deepseek/deepseek-chat` | günstig und zuverlässig, der Normalfall. Ein Lauf auf eine Aktie mit allen Analysten kostete im Test im September 2026 unter einen Cent |
| `openai/gpt-5-mini` | günstig, gute Alternative |
| `anthropic/claude-sonnet-5` | formuliert besser, kostet deutlich mehr |
| `meta-llama/llama-4-maverick` | offenes Modell |

Was ein Lauf gekostet hat, siehst du bei OpenRouter unter Activity.

## Aus dem Ergebnis ein PDF

Das Programm schreibt sein Ergebnis ins Terminal und mit `--save-json` in eine Datei. Ein PDF baut es nicht selbst. Das macht Claude für dich aus der gespeicherten Datei, etwa mit dem Satz „Mach mir aus dem Ergebnis ein PDF mit dem Urteil je Analyst und dem Gesamtbild. Wo sind sie sich uneinig?“

## Wenn es hakt

| Das siehst du | Daran liegt es |
|---|---|
| `API Key Error … OPENROUTER_API_KEY` | Die `.env` fehlt im Projektordner, die Zeile ist anders geschrieben oder der Schlüssel ist leer. Programm aus dem Projektordner starten |
| `Model '…' not found` und dann ein Menü | Der Modellname weicht ab. Einen Namen aus der Tabelle oben nehmen |
| `Nachrichten für … nicht verfügbar` | Yahoo liefert gerade keine Nachrichten. Der Rest läuft weiter, der Stimmungs-Analyst hat dann weniger Stoff |
| Insider-Analyst ohne Signal bei deutschen Aktien | Insider-Meldungen gibt es nur für US-Werte (SEC, Form 4). Das ist richtig so |
| Deutsche Aktie wird nicht gefunden | Kürzel mit Börsenendung angeben, etwa `SAP.DE`, `BMW.DE` |

---

## Originalanleitung (englisch)

Ab hier folgt die Anleitung des Originalprojekts. Für diese Fassung gilt der Weg oben: eigenes Repository, nur `OPENROUTER_API_KEY`, Start mit uv statt Poetry.

# AI Hedge Fund

This is a proof of concept for an AI-powered hedge fund.  The goal of this project is to explore the use of AI to make trading decisions.  This project is for **educational** purposes only and is not intended for real trading or investment.

> **🚧 The project is evolving.** We're rebuilding it into a persistent, always-on AI hedge fund — a *fund* as a first-class entity you can backtest, paper-trade, and (opt-in) run live, with the investor agents reimagined as pluggable, backtestable "alpha models." Read the **[Vision →](VISION.md)** and the **[Roadmap →](ROADMAP.md)**.

This system employs several agents working together:

1. Aswath Damodaran Agent - The Dean of Valuation, focuses on story, numbers, and disciplined valuation
2. Ben Graham Agent - The godfather of value investing, only buys hidden gems with a margin of safety
3. Bill Ackman Agent - An activist investor, takes bold positions and pushes for change
4. Cathie Wood Agent - The queen of growth investing, believes in the power of innovation and disruption
5. Charlie Munger Agent - Warren Buffett's partner, only buys wonderful businesses at fair prices
6. Michael Burry Agent - The Big Short contrarian who hunts for deep value
7. Mohnish Pabrai Agent - The Dhandho investor, who looks for doubles at low risk
8. Nassim Taleb Agent - The Black Swan risk analyst, focuses on tail risk, antifragility, and asymmetric payoffs
9. Peter Lynch Agent - Practical investor who seeks "ten-baggers" in everyday businesses
10. Phil Fisher Agent - Meticulous growth investor who uses deep "scuttlebutt" research 
11. Rakesh Jhunjhunwala Agent - The Big Bull of India
12. Stanley Druckenmiller Agent - Macro legend who hunts for asymmetric opportunities with growth potential
13. Warren Buffett Agent - The oracle of Omaha, seeks wonderful companies at a fair price
14. Valuation Agent - Calculates the intrinsic value of a stock and generates trading signals
15. Sentiment Agent - Analyzes market sentiment and generates trading signals
16. Fundamentals Agent - Analyzes fundamental data and generates trading signals
17. Technicals Agent - Analyzes technical indicators and generates trading signals
18. Risk Manager - Calculates risk metrics and sets position limits
19. Portfolio Manager - Makes final trading decisions and generates orders

<img width="1042" alt="Screenshot 2025-03-22 at 6 19 07 PM" src="https://github.com/user-attachments/assets/cbae3dcf-b571-490d-b0ad-3f0f035ac0d4" />

Note: the system does not actually make any trades.

[![Twitter Follow](https://img.shields.io/twitter/follow/virattt?style=social)](https://twitter.com/virattt)

## Disclaimer

This project is for **educational and research purposes only**.

- Not intended for real trading or investment
- No investment advice or guarantees provided
- Creator assumes no liability for financial losses
- Consult a financial advisor for investment decisions
- Past performance does not indicate future results

By using this software, you agree to use it solely for learning purposes.

## Table of Contents
- [How to Install](#how-to-install)
- [How to Run](#how-to-run)
  - [⌨️ Command Line Interface](#️-command-line-interface)
  - [🖥️ Web Application](#️-web-application)
- [How to Contribute](#how-to-contribute)
- [Feature Requests](#feature-requests)
- [License](#license)

---

## Datenquelle: yfinance, ohne API-Schlüssel

Dieser Fork holt Kurse, Abschlüsse, Kennzahlen und Nachrichten über **yfinance**
statt über financialdatasets.ai. Damit brauchst du **keinen Datenschlüssel**, kein
Konto und kein Kontingent, und **deutsche Titel funktionieren** (`SAP.DE`, `BMW.DE`).

Gemessen an den 31 Bilanzfeldern, die die Agenten anfragen:

| Titel | Felder gefüllt | Insider-Meldungen |
|---|---|---|
| `AAPL` | 30 von 31 | 77 |
| `SAP.DE` | 31 von 31 | 0 |

**Insider-Geschäfte gibt es nur für US-Titel.** Das sind SEC-Meldungen nach Form 4,
für den deutschen Markt existiert diese Meldepflicht nicht. Der zuständige Agent
liefert bei DAX-Werten deshalb kein Signal und sagt das auch.

Wer doch financialdatasets nutzen will, setzt vorher:

```bash
export DATA_SOURCE=financialdatasets
export FINANCIAL_DATASETS_API_KEY=dein_schluessel
```

Es bleibt also ein einziger Schlüssel nötig, der fürs Sprachmodell.

## How to Install

Before you can run the AI Hedge Fund, you'll need to install it and set up your API keys. These steps are common to both the full-stack web application and command line interface.

### 1. Clone the Repository

```bash
git clone https://github.com/virattt/ai-hedge-fund.git
cd ai-hedge-fund
```

### 2. Set up API keys

Create a `.env` file for your API keys:
```bash
# Create .env file for your API keys (in the root directory)
cp .env.example .env
```

Open and edit the `.env` file to add your API keys:
```bash
# For running LLMs hosted by openai (gpt-4o, gpt-4o-mini, etc.)
OPENAI_API_KEY=your-openai-api-key

# For getting financial data to power the hedge fund
FINANCIAL_DATASETS_API_KEY=your-financial-datasets-api-key
```

**Important**: You must set at least one LLM API key (e.g. `OPENAI_API_KEY`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY`, or `DEEPSEEK_API_KEY`) for the hedge fund to work. 

## How to Run

### ⌨️ Command Line Interface

You can run the AI Hedge Fund directly via terminal. This approach offers more granular control and is useful for automation, scripting, and integration purposes.

<img width="992" alt="Screenshot 2025-01-06 at 5 50 17 PM" src="https://github.com/user-attachments/assets/e8ca04bf-9989-4a7d-a8b4-34e04666663b" />

#### Quick Start

1. Install Poetry (if not already installed):
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

2. Install dependencies:
```bash
poetry install
```

#### Run the AI Hedge Fund
```bash
poetry run python src/main.py --ticker AAPL,MSFT,NVDA
```

You can also specify a `--ollama` flag to run the AI hedge fund using local LLMs.

```bash
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --ollama
```

You can optionally specify the start and end dates to make decisions over a specific time period.

```bash
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --start-date 2024-01-01 --end-date 2024-03-01
```

#### Run the Backtester
```bash
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA
```

**Example Output:**
<img width="941" alt="Screenshot 2025-01-06 at 5 47 52 PM" src="https://github.com/user-attachments/assets/00e794ea-8628-44e6-9a84-8f8a31ad3b47" />


Note: The `--ollama`, `--start-date`, and `--end-date` flags work for the backtester, as well!

### 🖥️ Web Application

The new way to run the AI Hedge Fund is through our web application that provides a user-friendly interface. This is recommended for users who prefer visual interfaces over command line tools.

Please see detailed instructions on how to install and run the web application [here](https://github.com/virattt/ai-hedge-fund/tree/main/app).

<img width="1721" alt="Screenshot 2025-06-28 at 6 41 03 PM" src="https://github.com/user-attachments/assets/b95ab696-c9f4-416c-9ad1-51feb1f5374b" />


## How to Contribute

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

**Important**: Please keep your pull requests small and focused.  This will make it easier to review and merge.

## Feature Requests

If you have a feature request, please open an [issue](https://github.com/virattt/ai-hedge-fund/issues) and make sure it is tagged with `enhancement`.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
