# Componenti esterni

La [MIT](LICENSE) della repo riguarda il codice originale di AI Job Hunter. I componenti vengono scaricati dai rispettivi distributori e mantengono le proprie condizioni; non sono tutti MIT. Controlla licenza e notice della versione/tag effettivamente utilizzati, anche per le dipendenze transitive delle immagini.

| Componente | Riferimento principale |
|---|---|
| n8n | Modello fair-code: [Sustainable Use License e parti Enterprise](https://github.com/n8n-io/n8n/blob/master/LICENSE.md). Non è MIT/Apache. Un futuro servizio commerciale condiviso richiederebbe verifica separata. |
| SearXNG | [AGPL-3.0 e notice upstream](https://github.com/searxng/searxng/blob/master/LICENSE). |
| Crawl4AI | [Licenza e condizioni upstream](https://github.com/unclecode/crawl4ai/blob/main/LICENSE), comprese attribuzioni applicabili; questo progetto usa Crawl4AI per estrazione HTML. |
| Ollama | [MIT del runtime](https://github.com/ollama/ollama/blob/main/LICENSE); licenza dei pesi separata. |
| Qwen 3.5 4B | [Tag/modello e licenza pubblicata](https://ollama.com/library/qwen3.5:4b), Apache-2.0 nel tag consultato. Ogni modello alternativo va controllato separatamente. |
| OpenStreetMap/Nominatim | Dati ODbL, [attribuzione](https://www.openstreetmap.org/copyright) e [policy del servizio pubblico](https://operations.osmfoundation.org/policies/nominatim/). |
| FastAPI / Pydantic / Beautiful Soup | Licenze MIT dei rispettivi progetti; versioni dirette bloccate in `pyproject.toml`. |
| HTTPX / Uvicorn / pypdf | Licenze BSD dei rispettivi progetti; verificare notice dei pacchetti installati. |
| Python | Licenza PSF; immagine base e sistema Debian hanno componenti con licenze proprie. |
| Stirling PDF / Nextcloud | Solo integrazioni facoltative: consulta licenze, disponibilità delle API e condizioni della versione già installata. Nessuna copia di questi servizi viene inclusa nel Compose. |

Le immagini Docker sono versionate; SearXNG è bloccato anche per digest. Le dipendenze Python dirette e transitive runtime/test sono vincolate in `requirements.lock` per Python 3.11. Per un rilascio riproducibile byte per byte occorrono anche hash delle wheel e digest per la propria architettura; questa versione garantisce contratti target e versioni testate, non identità binaria tra build a distanza di mesi.
