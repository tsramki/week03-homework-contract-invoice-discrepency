# week03-homework-contract-invoice-discrepency

A CrewAI multi-agent pipeline that reads a purchase contract and an invoice
(both PDFs), extracts structured data from each, and produces a Markdown
discrepancy report highlighting pricing, quantity, arithmetic, and terms
mismatches between the two.

## Source documents

- `data/purchase_terms_conditions.pdf` — contract terms (from
  [purchase_terms_conditions.pdf](https://github.com/bhoga01ai/week3-llamaindex-crewai-agents/blob/main/purchase_terms_conditions.pdf))
- `data/sample_invoice.pdf` — invoice to audit (from
  [sample_invoice.pdf](https://github.com/bhoga01ai/week3-llamaindex-crewai-agents/blob/main/sample_invoice.pdf))

## Crew design

Four agents run sequentially (`src/crew.py`, `src/config/agents.yaml`,
`src/config/tasks.yaml`):

1. **Contract Extractor** — reads the contract PDF (`read_pdf_text` tool) and
   extracts vendor, payment terms/method, and each item's contracted unit
   price into structured JSON.
2. **Invoice Extractor** — reads the invoice PDF and extracts invoice
   metadata, every line item (qty, unit price, amount), subtotal, tax, and
   total due into structured JSON.
3. **Discrepancy Analyst** — calls a deterministic `compare_contract_and_invoice`
   tool (plain Python, no LLM math) that matches invoice line items to
   contract items by name similarity and computes exact numeric discrepancies:
   unit price mismatches, qty×price arithmetic errors, subtotal/total
   mismatches, items billed but not contracted, contracted items never
   billed, and payment terms/method/reference mismatches.
4. **Report Writer** — turns the analyst's findings into a Markdown report
   with an executive summary, a per-item discrepancy table, invoice-level
   issues, and a recommendation.

Keeping the numeric comparison in a plain Python tool (rather than asking the
LLM to do the arithmetic) means the dollar amounts in the final report are
always exact.

## Setup

```bash
uv venv --python 3.12 .venv   # crewai's deps (tiktoken) need Python <=3.13
uv pip install -r requirements.txt
cp .env.example .env          # then add your OPENAI_API_KEY (or configure another LLM)
```

## Run

```bash
uv run src/main.py                                         # uses the sample PDFs in data/
uv run src/main.py path/to/contract.pdf path/to/invoice.pdf # or pass your own
```

Outputs are written to `output/`:

- `contract_data.json` — structured contract extraction
- `invoice_data.json` — structured invoice extraction
- `discrepancy_report.md` — final report

## Known discrepancies in the sample data

Running against the bundled sample PDFs is expected to surface:

- Homepage wireframe and revisions billed at $220.00/unit vs. $210.00 contracted
- Product photo retouching package billed at $145.00/unit vs. $150.00 contracted
- Monthly hosting setup billed at $60.00/unit vs. $65.00 contracted
