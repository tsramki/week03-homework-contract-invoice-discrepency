"""Entry point: run the contract-vs-invoice discrepancy crew."""

import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))

from crew import ContractInvoiceDiscrepancyCrew  # noqa: E402

load_dotenv()

DEFAULT_CONTRACT_PATH = "data/purchase_terms_conditions.pdf"
DEFAULT_INVOICE_PATH = "data/sample_invoice.pdf"


def run(contract_path: str = DEFAULT_CONTRACT_PATH, invoice_path: str = DEFAULT_INVOICE_PATH) -> None:
    os.makedirs("output", exist_ok=True)
    inputs = {"contract_path": contract_path, "invoice_path": invoice_path}
    result = ContractInvoiceDiscrepancyCrew().crew().kickoff(inputs=inputs)
    print("\n\n===== DISCREPANCY REPORT =====\n")
    print(result.raw)


if __name__ == "__main__":
    contract = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CONTRACT_PATH
    invoice = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_INVOICE_PATH
    run(contract, invoice)
