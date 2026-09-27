"""CrewAI crew that extracts contract and invoice data and reports discrepancies."""

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from models import ContractData, InvoiceData
from tools import LineItemComparisonTool, PDFReadTool


@CrewBase
class ContractInvoiceDiscrepancyCrew:
    """Extracts contract + invoice data and produces a discrepancy report."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def contract_extractor(self) -> Agent:
        return Agent(
            config=self.agents_config["contract_extractor"],
            tools=[PDFReadTool()],
            verbose=True,
        )

    @agent
    def invoice_extractor(self) -> Agent:
        return Agent(
            config=self.agents_config["invoice_extractor"],
            tools=[PDFReadTool()],
            verbose=True,
        )

    @agent
    def discrepancy_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["discrepancy_analyst"],
            tools=[LineItemComparisonTool()],
            verbose=True,
        )

    @agent
    def report_writer(self) -> Agent:
        return Agent(
            config=self.agents_config["report_writer"],
            verbose=True,
        )

    @task
    def extract_contract_task(self) -> Task:
        return Task(
            config=self.tasks_config["extract_contract_task"],
            output_pydantic=ContractData,
        )

    @task
    def extract_invoice_task(self) -> Task:
        return Task(
            config=self.tasks_config["extract_invoice_task"],
            output_pydantic=InvoiceData,
        )

    @task
    def analyze_discrepancy_task(self) -> Task:
        return Task(config=self.tasks_config["analyze_discrepancy_task"])

    @task
    def write_report_task(self) -> Task:
        return Task(config=self.tasks_config["write_report_task"])

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
