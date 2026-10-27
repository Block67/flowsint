import io
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from openpyxl import Workbook
from pydantic import ValidationError

from flowsint_core.imports.transactions import (
    AccountSide,
    TransactionImportService,
    TransactionMapping,
    parse_amount,
    parse_date,
    parse_transactions,
    read_table,
    suggest_columns,
    suggest_mode,
)
from flowsint_types import BankAccount, Merchant, MobileMoneyAccount

MOMO_CSV = (
    "Export Orange Money;;;;;\n"
    "Période : janvier 2024;;;;;\n"
    "Référence;Date opération;Expéditeur;Destinataire;Montant;Frais\n"
    "OM001;02/01/2024 10:15;77 123 45 67;78 765 43 21;1 500;50\n"
    "OM002;03/01/2024 08:00;78 765 43 21;76 000 11 22;25 000,50;\n"
    ";;;;;\n"
    "OM003;04/01/2024;77 123 45 67;;300;\n"
).encode("cp1252")


def momo_mapping(**overrides):
    side = {
        "account_type": "MobileMoneyAccount",
        "provider": "Orange Money",
        "country": "SN",
    }
    data = {
        "mode": "ledger",
        "source": {**side, "column": "Expéditeur"},
        "target": {**side, "column": "Destinataire"},
        "transaction_id_column": "Référence",
        "date_column": "Date opération",
        "amount_column": "Montant",
        "fees_column": "Frais",
        "currency": "XOF",
        "channel": "mobile_money",
    }
    data.update(overrides)
    return TransactionMapping(**data)


class TestReadTable:
    def test_csv_skips_title_lines_and_detects_semicolon(self):
        table = read_table(MOMO_CSV, "export.csv")
        assert table.headers == [
            "Référence",
            "Date opération",
            "Expéditeur",
            "Destinataire",
            "Montant",
            "Frais",
        ]
        assert len(table.rows) == 3  # empty line dropped
        assert table.line_numbers == [4, 5, 7]
        assert table.rows[0]["Montant"] == "1 500"

    def test_duplicate_and_empty_headers(self):
        table = read_table(b"a,a,\n1,2,3\n", "x.csv")
        assert table.headers == ["a", "a_2", "column_3"]

    def test_xlsx(self):
        wb = Workbook()
        ws = wb.active
        ws.append(["Date", "Montant", "Compte"])
        ws.append([datetime(2024, 1, 2), 1500.0, 221771234567])
        buffer = io.BytesIO()
        wb.save(buffer)

        table = read_table(buffer.getvalue(), "releve.xlsx")
        assert table.headers == ["Date", "Montant", "Compte"]
        assert table.rows[0]["Date"] == datetime(2024, 1, 2)
        assert table.rows[0]["Montant"] == 1500

    def test_unsupported_extension(self):
        with pytest.raises(ValueError, match="Unsupported"):
            read_table(b"x", "file.xls")

    def test_empty_file(self):
        with pytest.raises(ValueError, match="no data"):
            read_table(b"\n;;\n", "empty.csv")


class TestParseAmount:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("1 500", 1500),
            ("1 500,50", 1500.5),
            ("1.500,50", 1500.5),
            ("1,500.50", 1500.5),
            ("1,500", 1500),
            ("12,5", 12.5),
            ("0.125", 0.125),
            ("1,234,567", 1234567),
            ("-200 XOF", -200),
            ("200-", -200),
            ("(200)", -200),
            ("25 000 FCFA", 25000),
            (12.5, 12.5),
        ],
    )
    def test_formats(self, raw, expected):
        assert parse_amount(raw) == pytest.approx(expected)

    def test_explicit_decimal_separator(self):
        assert parse_amount("1,500", decimal_separator=",") == 1.5

    @pytest.mark.parametrize("raw", ["", "abc", None])
    def test_invalid(self, raw):
        with pytest.raises(ValueError):
            parse_amount(raw)


class TestParseDate:
    def test_day_first_default(self):
        assert parse_date("02/01/2024 10:15") == datetime(2024, 1, 2, 10, 15)

    def test_month_first(self):
        assert parse_date("02/01/2024", day_first=False) == datetime(2024, 2, 1)

    def test_iso(self):
        assert parse_date("2024-01-02T03:04:05Z") == datetime(
            2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc
        )

    def test_epoch_seconds_and_millis(self):
        expected = datetime(2023, 11, 14, 22, 13, 20, tzinfo=timezone.utc)
        assert parse_date("1700000000") == expected
        assert parse_date(1700000000000) == expected

    def test_explicit_format(self):
        assert parse_date("20240102", date_format="%Y%m%d") == datetime(2024, 1, 2)

    def test_unrecognized(self):
        with pytest.raises(ValueError, match="unrecognized"):
            parse_date("hier")


class TestSuggest:
    def test_french_ledger_headers(self):
        headers = [
            "Référence",
            "Date opération",
            "Expéditeur",
            "Destinataire",
            "Montant",
            "Frais",
        ]
        s = suggest_columns(headers)
        assert s["transaction_id"] == "Référence"
        assert s["date"] == "Date opération"
        assert s["source"] == "Expéditeur"
        assert s["target"] == "Destinataire"
        assert s["amount"] == "Montant"
        assert s["fees"] == "Frais"
        assert suggest_mode(s) == "ledger"

    def test_bank_statement_headers(self):
        headers = ["Date", "Libellé", "Débit", "Crédit", "Solde"]
        s = suggest_columns(headers)
        assert s["debit"] == "Débit"
        assert s["credit"] == "Crédit"
        assert s["description"] == "Libellé"
        assert s["amount"] is None
        assert suggest_mode(s) == "statement"


class TestMappingValidation:
    def test_account_needs_column_or_value(self):
        with pytest.raises(ValidationError):
            AccountSide(account_type="BankAccount")

    def test_ledger_needs_both_sides(self):
        with pytest.raises(ValidationError):
            TransactionMapping(
                mode="ledger",
                source={"account_type": "BankAccount", "column": "a"},
                amount_column="m",
            )

    def test_statement_needs_amount_or_debit_credit(self):
        with pytest.raises(ValidationError):
            TransactionMapping(
                mode="statement",
                owner={"account_type": "BankAccount", "value": "123"},
                counterparty={"account_type": "Merchant", "column": "c"},
            )


class TestParseLedger:
    def test_mobile_money_export(self):
        outcome = parse_transactions(read_table(MOMO_CSV, "x.csv"), momo_mapping())

        assert len(outcome.transactions) == 2
        # OM003, on line 7 of the file, has no recipient
        assert [e.row for e in outcome.errors] == [7]
        assert "Destinataire" in outcome.errors[0].message

        first, second = outcome.transactions
        assert first.transaction_id == "OM001"
        assert isinstance(first.source, MobileMoneyAccount)
        assert first.source.phone_number == "+221771234567"
        assert first.source.nodeLabel == "+221771234567 (Orange Money)"
        assert first.amount == 1500
        assert first.fees == 50
        assert first.currency == "XOF"
        assert first.channel == "mobile_money"
        assert first.timestamp == datetime(2024, 1, 2, 10, 15, tzinfo=timezone.utc)
        assert second.amount == 25000.5
        assert second.fees is None

    def test_generated_ids_are_deterministic_and_distinct_for_identical_rows(self):
        csv = b"from;to;amount\n111;222;10\n111;222;10\n"
        mapping = TransactionMapping(
            source={"account_type": "BankAccount", "column": "from"},
            target={"account_type": "BankAccount", "column": "to"},
            amount_column="amount",
        )
        first = parse_transactions(read_table(csv, "x.csv"), mapping).transactions
        again = parse_transactions(read_table(csv, "x.csv"), mapping).transactions
        ids = [tx.transaction_id for tx in first]
        assert len(set(ids)) == 2
        assert ids == [tx.transaction_id for tx in again]


class TestParseStatement:
    OWNER = {"account_type": "BankAccount", "value": "SN0123456789", "provider": "CBAO"}
    COUNTERPARTY = {"account_type": "Merchant", "column": "Libellé"}

    def test_debit_credit_columns(self):
        csv = (
            "Date;Libellé;Débit;Crédit\n"
            "05/01/2024;Supermarché;12 000;\n"
            "06/01/2024;Employeur;;450 000\n"
            "07/01/2024;Vide;;\n"
        ).encode()
        mapping = TransactionMapping(
            mode="statement",
            owner=self.OWNER,
            counterparty=self.COUNTERPARTY,
            date_column="Date",
            debit_column="Débit",
            credit_column="Crédit",
            currency="XOF",
        )
        outcome = parse_transactions(read_table(csv, "x.csv"), mapping)

        out, inc = outcome.transactions
        assert isinstance(out.source, BankAccount)
        assert out.source.nodeLabel == "CBAO - SN0123456789"
        assert isinstance(out.target, Merchant)
        assert out.target.name == "Supermarché"
        assert out.amount == 12000
        assert inc.source.name == "Employeur"
        assert inc.target.account_number == "SN0123456789"
        assert inc.amount == 450000
        assert [e.row for e in outcome.errors] == [4]

    def test_signed_amount(self):
        csv = b"Libell\xc3\xa9;Montant\nA;-100\nB;250\n"
        mapping = TransactionMapping(
            mode="statement",
            owner=self.OWNER,
            counterparty=self.COUNTERPARTY,
            amount_column="Montant",
        )
        out, inc = parse_transactions(read_table(csv, "x.csv"), mapping).transactions
        assert (out.source.nodeLabel, out.amount) == ("CBAO - SN0123456789", 100)
        assert (inc.target.nodeLabel, inc.amount) == ("CBAO - SN0123456789", 250)

    def test_direction_column(self):
        csv = b"Libell\xc3\xa9;Sens;Montant\nA;Envoi;100\nB;Reception;250\n"
        mapping = TransactionMapping(
            mode="statement",
            owner=self.OWNER,
            counterparty=self.COUNTERPARTY,
            amount_column="Montant",
            direction_column="Sens",
        )
        out, inc = parse_transactions(read_table(csv, "x.csv"), mapping).transactions
        assert out.source.nodeLabel == "CBAO - SN0123456789"
        assert inc.target.nodeLabel == "CBAO - SN0123456789"


class TestService:
    def test_analyze(self):
        analysis = TransactionImportService().analyze(MOMO_CSV, "x.csv")
        assert analysis.total_rows == 3
        assert analysis.suggested_mode == "ledger"
        assert analysis.suggested_columns["amount"] == "Montant"
        assert analysis.sample_rows[0]["Référence"] == "OM001"

    def test_preview(self):
        preview = TransactionImportService().preview(MOMO_CSV, "x.csv", momo_mapping())
        assert preview.total_rows == 3
        assert preview.valid_rows == 2
        assert preview.sample[0]["source"] == "+221771234567 (Orange Money)"
        assert preview.sample[0]["timestamp"] == "2024-01-02T10:15:00+00:00"

    def test_execute_writes_accounts_once_and_one_edge_per_transaction(self):
        graph = MagicMock()
        result = TransactionImportService(graph).execute(
            MOMO_CSV, "x.csv", momo_mapping()
        )

        assert result.status == "completed_with_errors"
        assert result.transactions_imported == 2
        assert result.rows_failed == 1
        # 3 distinct accounts across the two transactions
        assert result.accounts_imported == 3
        assert graph.create_node_from_flowsint_type.call_count == 3
        edge_keys = [
            c.kwargs["edge_key"] for c in graph.create_relationship.call_args_list
        ]
        assert edge_keys == ["OM001", "OM002"]
        graph.flush.assert_called_once()

    def test_execute_requires_graph_service(self):
        with pytest.raises(RuntimeError):
            TransactionImportService().execute(MOMO_CSV, "x.csv", momo_mapping())
