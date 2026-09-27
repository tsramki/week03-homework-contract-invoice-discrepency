"""Custom tools for the contract/invoice discrepancy crew."""

import json
from difflib import SequenceMatcher
from typing import List, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from pypdf import PdfReader


class PDFReadToolInput(BaseModel):
    file_path: str = Field(description="Path to the PDF file to read, relative or absolute")


class PDFReadTool(BaseTool):
    name: str = "read_pdf_text"
    description: str = (
        "Reads a PDF file from disk and returns its full plain-text contents. "
        "Use this to load the contract or invoice PDF before extracting structured data."
    )
    args_schema: Type[BaseModel] = PDFReadToolInput

    def _run(self, file_path: str) -> str:
        reader = PdfReader(file_path)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        if not text.strip():
            return f"ERROR: no extractable text found in {file_path}"
        return text


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _to_float(value) -> float:
    """Coerce numbers that may arrive as currency-formatted strings (e.g. '$1,234.56')."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = str(value).replace("$", "").replace(",", "").strip()
    return float(cleaned) if cleaned else 0.0


class LineItemComparisonInput(BaseModel):
    contract_json: str = Field(
        description="JSON string matching the ContractData schema (vendor, payment_terms, "
        "payment_method, items: [{name, unit_price}])"
    )
    invoice_json: str = Field(
        description="JSON string matching the InvoiceData schema (invoice_number, ... "
        "line_items: [{description, quantity, unit_price, amount}], subtotal, tax, total_due)"
    )


class LineItemComparisonTool(BaseTool):
    name: str = "compare_contract_and_invoice"
    description: str = (
        "Deterministically compares structured contract data against structured invoice data. "
        "Matches invoice line items to contract items by name similarity, and computes exact "
        "numeric discrepancies for unit price, line amount, invoice arithmetic (qty*price=amount, "
        "subtotal, total), and payment terms/method mismatches. Always use this tool to check "
        "numbers instead of computing them yourself, so the report is arithmetically exact."
    )
    args_schema: Type[BaseModel] = LineItemComparisonInput

    def _run(self, contract_json: str, invoice_json: str) -> str:
        contract = json.loads(contract_json)
        invoice = json.loads(invoice_json)

        contract_items = contract.get("items", [])
        matched_contract_names = set()
        findings: List[dict] = []

        for line in invoice.get("line_items", []):
            desc = line.get("description", "")
            qty = _to_float(line.get("quantity", 0) or 0)
            unit_price = _to_float(line.get("unit_price", 0) or 0)
            amount = _to_float(line.get("amount", 0) or 0)

            best_match, best_score = None, 0.0
            for item in contract_items:
                score = _similar(desc, item.get("name", ""))
                if score > best_score:
                    best_match, best_score = item, score

            item_findings = []
            if best_match is None or best_score < 0.5:
                item_findings.append(
                    {
                        "type": "ITEM_NOT_IN_CONTRACT",
                        "detail": f"Invoice item '{desc}' has no matching item in the contract "
                        f"(best similarity {best_score:.2f}).",
                    }
                )
            else:
                matched_contract_names.add(best_match.get("name"))
                contract_price = _to_float(best_match.get("unit_price", 0) or 0)
                if round(contract_price, 2) != round(unit_price, 2):
                    diff = round(unit_price - contract_price, 2)
                    item_findings.append(
                        {
                            "type": "UNIT_PRICE_MISMATCH",
                            "detail": (
                                f"'{desc}' billed at ${unit_price:.2f}/unit vs contracted "
                                f"${contract_price:.2f}/unit (matched contract item "
                                f"'{best_match.get('name')}'), difference ${diff:+.2f} per unit, "
                                f"${diff * qty:+.2f} total over qty {qty:g}."
                            ),
                        }
                    )

            expected_amount = round(qty * unit_price, 2)
            if round(expected_amount, 2) != round(amount, 2):
                item_findings.append(
                    {
                        "type": "LINE_MATH_ERROR",
                        "detail": (
                            f"'{desc}': qty {qty:g} x unit price ${unit_price:.2f} = "
                            f"${expected_amount:.2f}, but invoice shows amount ${amount:.2f}."
                        ),
                    }
                )

            findings.append(
                {
                    "invoice_item": desc,
                    "matched_contract_item": best_match.get("name") if best_match else None,
                    "match_confidence": round(best_score, 2),
                    "issues": item_findings,
                }
            )

        # Items in the contract that were never billed
        for item in contract_items:
            if item.get("name") not in matched_contract_names:
                findings.append(
                    {
                        "invoice_item": None,
                        "matched_contract_item": item.get("name"),
                        "match_confidence": 0.0,
                        "issues": [
                            {
                                "type": "CONTRACTED_ITEM_NOT_BILLED",
                                "detail": f"Contract item '{item.get('name')}' at "
                                f"${_to_float(item.get('unit_price', 0)):.2f}/unit was never invoiced.",
                            }
                        ],
                    }
                )

        # Invoice-level arithmetic
        summary_issues = []
        line_items = invoice.get("line_items", [])
        computed_subtotal = round(sum(_to_float(li.get("amount", 0) or 0) for li in line_items), 2)
        stated_subtotal = invoice.get("subtotal")
        if stated_subtotal is not None and round(_to_float(stated_subtotal), 2) != computed_subtotal:
            summary_issues.append(
                {
                    "type": "SUBTOTAL_MISMATCH",
                    "detail": f"Sum of line amounts is ${computed_subtotal:.2f} but invoice states "
                    f"subtotal ${_to_float(stated_subtotal):.2f}.",
                }
            )

        tax = invoice.get("tax")
        total_due = invoice.get("total_due")
        if stated_subtotal is not None and tax is not None and total_due is not None:
            expected_total = round(_to_float(stated_subtotal) + _to_float(tax), 2)
            if expected_total != round(_to_float(total_due), 2):
                summary_issues.append(
                    {
                        "type": "TOTAL_MISMATCH",
                        "detail": f"Subtotal ${_to_float(stated_subtotal):.2f} + tax ${_to_float(tax):.2f} = "
                        f"${expected_total:.2f}, but invoice states total due ${_to_float(total_due):.2f}.",
                    }
                )

        contract_terms = (contract.get("payment_terms") or "").strip().lower()
        invoice_terms = (invoice.get("payment_terms") or "").strip().lower()
        terms_equivalent = (
            contract_terms == invoice_terms
            or contract_terms in invoice_terms
            or invoice_terms in contract_terms
        )
        if contract_terms and invoice_terms and not terms_equivalent:
            summary_issues.append(
                {
                    "type": "PAYMENT_TERMS_MISMATCH",
                    "detail": f"Contract payment terms '{contract.get('payment_terms')}' differ from "
                    f"invoice payment terms '{invoice.get('payment_terms')}'.",
                }
            )

        contract_method = (contract.get("payment_method") or "").strip().lower()
        invoice_method = (invoice.get("payment_method") or "").strip().lower()
        if contract_method and invoice_method and contract_method not in invoice_method and invoice_method not in contract_method:
            summary_issues.append(
                {
                    "type": "PAYMENT_METHOD_MISMATCH",
                    "detail": f"Contract payment method '{contract.get('payment_method')}' differs from "
                    f"invoice payment method '{invoice.get('payment_method')}'.",
                }
            )

        contract_invoice_ref = contract.get("referenced_invoice_number")
        if contract_invoice_ref and contract_invoice_ref != invoice.get("invoice_number"):
            summary_issues.append(
                {
                    "type": "INVOICE_REFERENCE_MISMATCH",
                    "detail": f"Contract references invoice '{contract_invoice_ref}' but this invoice "
                    f"number is '{invoice.get('invoice_number')}'.",
                }
            )

        result = {
            "line_item_findings": findings,
            "invoice_level_findings": summary_issues,
        }
        return json.dumps(result, indent=2)
