"""Integration tests using real WideWorldImporters bacpac fixture.

These tests run the full pipeline — ZIP extraction, metadata parsing,
model parsing, and all extractor registrations — against a real
WideWorldImporters-Full bacpac to verify end-to-end correctness.

Every object type the parser can extract is asserted with exact counts
and spot-checked with specific property values from the known database.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from orchestration.factory import create_package_reader

FIXTURES_DIR = Path(__file__).parent / "fixtures"
WWI_BACPAC = FIXTURES_DIR / "WideWorldImporters-Full.bacpac"


@pytest.fixture(scope="module")
def wwi_package():
    """Read the WideWorldImporters bacpac once for the entire module."""
    reader = create_package_reader()
    return reader.read_package(WWI_BACPAC)


@pytest.fixture(scope="module")
def dm(wwi_package):
    """Shorthand for the DatabaseModel."""
    return wwi_package.database_model


# ---------------------------------------------------------------------------
# Package-level metadata
# ---------------------------------------------------------------------------

class TestPackageMetadata:
    """DacMetadata.xml fields."""

    def test_package_name(self, wwi_package):
        assert wwi_package.metadata.name == "WideWorldImporters-Full"

    def test_package_version(self, wwi_package):
        assert wwi_package.metadata.version == "0.0.0.0"


class TestPackageOrigin:
    """Origin.xml fields."""

    def test_contains_exported_data(self, wwi_package):
        assert wwi_package.origin.contains_exported_data is True

    def test_server_version(self, wwi_package):
        assert "Microsoft SQL Server 2016" in wwi_package.origin.server_version

    def test_product_version(self, wwi_package):
        assert wwi_package.origin.product_version == "15.0.5179.2"

    def test_model_schema_version(self, wwi_package):
        assert wwi_package.origin.model_schema_version == "2.9"

    def test_source_database_size_kb(self, wwi_package):
        assert wwi_package.origin.source_database_size_kb == 518120

    def test_total_row_count(self, wwi_package):
        assert wwi_package.origin.total_row_count == 4713833

    def test_export_timestamp(self, wwi_package):
        assert wwi_package.origin.export_timestamp.startswith("2022-10-07")


class TestRootAttributes:
    """Model.xml root DataSchemaModel attributes."""

    def test_format_version(self, wwi_package):
        assert wwi_package.format_version == "1.2"

    def test_schema_version(self, wwi_package):
        assert wwi_package.schema_version == "2.9"

    def test_dsp_name(self, wwi_package):
        assert wwi_package.dsp_name == (
            "Microsoft.Data.Tools.Schema.Sql.Sql130DatabaseSchemaProvider"
        )


# ---------------------------------------------------------------------------
# Database options
# ---------------------------------------------------------------------------

class TestDatabaseOptions:
    """SqlDatabaseOptions properties."""

    def test_present(self, dm):
        assert dm.database_options is not None

    def test_collation(self, dm):
        assert dm.database_options.properties["Collation"] == "Latin1_General_100_CI_AS"

    def test_collation_lcid(self, dm):
        assert dm.database_options.collation_lcid == "1033"

    def test_full_text_enabled(self, dm):
        assert dm.database_options.properties["IsFullTextEnabled"] == "True"

    def test_recovery_mode(self, dm):
        assert dm.database_options.properties["RecoveryMode"] == "1"

    def test_memory_optimized_elevated(self, dm):
        assert dm.database_options.properties["IsMemoryOptimizedElevatedToSnapshot"] == "True"

    def test_property_count(self, dm):
        assert len(dm.database_options.properties) == 15


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TestSchemas:
    EXPECTED = {
        "Application", "DataLoadSimulation", "Integration", "PowerBI",
        "Purchasing", "Reports", "Sales", "Sequences", "Warehouse", "Website",
    }

    def test_count(self, dm):
        assert len(dm.schemas) == 10

    def test_names(self, dm):
        assert {s.name.parts[0] for s in dm.schemas} == self.EXPECTED


# ---------------------------------------------------------------------------
# Tables — counts, distribution, and column spot-checks
# ---------------------------------------------------------------------------

class TestTables:
    TABLE_COUNTS_BY_SCHEMA = {
        "Application": 15,
        "Purchasing": 7,
        "Sales": 12,
        "Warehouse": 14,
    }

    def test_total_count(self, dm):
        assert len(dm.tables) == 48

    def test_counts_by_schema(self, dm):
        from collections import Counter
        schema_counts = Counter(
            t.schema_ref.parts[0] for t in dm.tables
        )
        assert dict(schema_counts) == self.TABLE_COUNTS_BY_SCHEMA

    def test_total_columns(self, dm):
        assert sum(len(t.columns) for t in dm.tables) == 557

    def test_computed_column_count(self, dm):
        computed = sum(
            1 for t in dm.tables for c in t.columns if c.is_computed
        )
        assert computed == 8

    def test_typed_column_count(self, dm):
        """All non-computed columns have type_specifier populated."""
        typed = sum(
            1 for t in dm.tables for c in t.columns
            if c.type_specifier is not None
        )
        assert typed == 549  # 557 - 8 computed


class TestCitiesTable:
    """Spot-check the Application.Cities table structure."""

    @pytest.fixture()
    def cities(self, dm):
        return next(
            t for t in dm.tables
            if t.name.object_name == "Cities"
            and t.schema_ref.parts[0] == "Application"
        )

    def test_column_count(self, cities):
        assert len(cities.columns) == 8

    def test_city_id_column(self, cities):
        col = cities.columns[0]
        assert col.name.parts[-1] == "CityID"
        assert col.type_specifier.type_name == "int"
        assert col.type_specifier.is_builtin is True
        assert col.is_nullable is False

    def test_city_name_column(self, cities):
        col = cities.columns[1]
        assert col.name.parts[-1] == "CityName"
        assert col.type_specifier.type_name == "nvarchar"
        assert col.type_specifier.length == 50
        assert col.is_nullable is False

    def test_geography_column(self, cities):
        location = next(
            c for c in cities.columns if c.name.parts[-1] == "Location"
        )
        assert location.type_specifier.type_name == "geography"
        assert location.is_nullable is True

    def test_bigint_column(self, cities):
        pop = next(
            c for c in cities.columns
            if c.name.parts[-1] == "LatestRecordedPopulation"
        )
        assert pop.type_specifier.type_name == "bigint"
        assert pop.is_nullable is True

    def test_datetime2_column_with_scale(self, cities):
        valid_from = next(
            c for c in cities.columns if c.name.parts[-1] == "ValidFrom"
        )
        assert valid_from.type_specifier.type_name == "datetime2"
        assert valid_from.type_specifier.scale == 7
        assert valid_from.is_nullable is False


class TestPeopleTable:
    """Spot-check Application.People which has computed columns."""

    @pytest.fixture()
    def people(self, dm):
        return next(
            t for t in dm.tables
            if t.name.object_name == "People"
            and t.schema_ref.parts[0] == "Application"
        )

    def test_column_count(self, people):
        assert len(people.columns) == 21

    def test_computed_columns(self, people):
        computed = [c.name.parts[-1] for c in people.columns if c.is_computed]
        assert set(computed) == {"SearchName", "OtherLanguages"}

    def test_computed_columns_have_no_type(self, people):
        for c in people.columns:
            if c.is_computed:
                assert c.type_specifier is None


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

class TestViews:
    EXPECTED = {"Customers", "Suppliers", "VehicleTemperatures"}

    def test_count(self, dm):
        assert len(dm.views) == 3

    def test_names(self, dm):
        assert {v.name.object_name for v in dm.views} == self.EXPECTED

    def test_all_in_website_schema(self, dm):
        for v in dm.views:
            assert v.schema_ref.parts[0] == "Website"

    def test_customers_view_columns(self, dm):
        cust = next(v for v in dm.views if v.name.object_name == "Customers")
        assert len(cust.columns) == 14

    def test_suppliers_view_columns(self, dm):
        sup = next(v for v in dm.views if v.name.object_name == "Suppliers")
        assert len(sup.columns) == 12

    def test_vehicle_temps_view_columns(self, dm):
        vt = next(
            v for v in dm.views if v.name.object_name == "VehicleTemperatures"
        )
        assert len(vt.columns) == 6

    def test_views_have_query_script(self, dm):
        for v in dm.views:
            assert v.query_script != ""


# ---------------------------------------------------------------------------
# Procedures
# ---------------------------------------------------------------------------

class TestProcedures:
    EXPECTED_NAMES = {
        "AddRoleMemberIfNonexistent",
        "Configuration_ApplyAuditing",
        "Configuration_ApplyColumnstoreIndexing",
        "Configuration_ApplyFullTextIndexing",
        "Configuration_ApplyPartitioning",
        "Configuration_ApplyRowLevelSecurity",
        "Configuration_ConfigureForEnterpriseEdition",
        "Configuration_EnableInMemory",
        "Configuration_RemoveAuditing",
        "Configuration_RemoveRowLevelSecurity",
        "CreateRoleIfNonexistent",
        "Configuration_ApplyDataLoadSimulationProcedures",
        "Configuration_RemoveDataLoadSimulationProcedures",
        "DeactivateTemporalTablesBeforeDataLoad",
        "PopulateDataToCurrentDate",
        "ReactivateTemporalTablesAfterDataLoad",
        "GetCityUpdates",
        "GetCustomerUpdates",
        "GetEmployeeUpdates",
        "GetMovementUpdates",
        "GetOrderUpdates",
        "GetPaymentMethodUpdates",
        "GetPurchaseUpdates",
        "GetSaleUpdates",
        "GetStockHoldingUpdates",
        "GetStockItemUpdates",
        "GetSupplierUpdates",
        "GetTransactionTypeUpdates",
        "GetTransactionUpdates",
        "ReseedAllSequences",
        "ReseedSequenceBeyondTableValues",
        "ActivateWebsiteLogon",
        "ChangePassword",
        "InsertCustomerOrders",
        "InvoiceCustomerOrders",
        "RecordColdRoomTemperatures",
        "RecordVehicleTemperature",
        "SearchForCustomers",
        "SearchForPeople",
        "SearchForStockItems",
        "SearchForStockItemsByTags",
        "SearchForSuppliers",
    }

    def test_count(self, dm):
        assert len(dm.procedures) == 42

    def test_all_names(self, dm):
        names = {p.name.object_name for p in dm.procedures}
        assert names == self.EXPECTED_NAMES

    def test_total_parameters(self, dm):
        assert sum(len(p.parameters) for p in dm.procedures) == 61

    def test_add_role_member_has_two_params(self, dm):
        proc = next(
            p for p in dm.procedures
            if p.name.object_name == "AddRoleMemberIfNonexistent"
        )
        assert len(proc.parameters) == 2

    def test_populate_data_has_five_params(self, dm):
        proc = next(
            p for p in dm.procedures
            if p.name.object_name == "PopulateDataToCurrentDate"
        )
        assert len(proc.parameters) == 5

    def test_procedures_have_body_script(self, dm):
        for p in dm.procedures:
            assert p.body_script != ""

    def test_procedure_schemas(self, dm):
        from collections import Counter
        schemas = Counter(p.schema_ref.parts[0] for p in dm.procedures)
        assert schemas["Application"] == 11
        assert schemas["Website"] == 11
        assert schemas["Integration"] == 13
        assert schemas["DataLoadSimulation"] == 5
        assert schemas["Sequences"] == 2


# ---------------------------------------------------------------------------
# Scalar functions
# ---------------------------------------------------------------------------

class TestScalarFunctions:
    def test_count(self, dm):
        assert len(dm.scalar_functions) == 1

    def test_calculate_customer_price(self, dm):
        sf = dm.scalar_functions[0]
        assert sf.name.object_name == "CalculateCustomerPrice"
        assert sf.schema_ref.parts[0] == "Website"

    def test_return_type(self, dm):
        sf = dm.scalar_functions[0]
        assert sf.return_type.type_name == "decimal"
        assert sf.return_type.precision == 18
        assert sf.return_type.scale == 2

    def test_parameters(self, dm):
        sf = dm.scalar_functions[0]
        assert len(sf.parameters) == 3
        param_types = [p.type_specifier.type_name for p in sf.parameters]
        assert param_types == ["int", "int", "date"]

    def test_has_body(self, dm):
        sf = dm.scalar_functions[0]
        assert sf.body_script != ""


# ---------------------------------------------------------------------------
# Inline TVFs — none in WWI OLTP
# ---------------------------------------------------------------------------

class TestInlineTvfs:
    def test_count_zero(self, dm):
        assert len(dm.inline_tvfs) == 0


# ---------------------------------------------------------------------------
# Sequences
# ---------------------------------------------------------------------------

class TestSequences:
    EXPECTED_NAMES = {
        "BuyingGroupID", "CityID", "ColorID", "CountryID",
        "CustomerCategoryID", "CustomerID", "DeliveryMethodID",
        "InvoiceID", "InvoiceLineID", "OrderID", "OrderLineID",
        "PackageTypeID", "PaymentMethodID", "PersonID",
        "PurchaseOrderID", "PurchaseOrderLineID", "SpecialDealID",
        "StateProvinceID", "StockGroupID", "StockItemID",
        "StockItemStockGroupID", "SupplierCategoryID", "SupplierID",
        "SystemParameterID", "TransactionID", "TransactionTypeID",
    }

    def test_count(self, dm):
        assert len(dm.sequences) == 26

    def test_all_names(self, dm):
        names = {s.name.object_name for s in dm.sequences}
        assert names == self.EXPECTED_NAMES

    def test_all_in_sequences_schema(self, dm):
        for s in dm.sequences:
            assert s.schema_ref.parts[0] == "Sequences"

    def test_all_type_int(self, dm):
        for s in dm.sequences:
            assert s.type_specifier.type_name == "int"
            assert s.type_specifier.is_builtin is True


# ---------------------------------------------------------------------------
# Table types
# ---------------------------------------------------------------------------

class TestTableTypes:
    EXPECTED = {
        ("[Website].[OrderIDList]", 1),
        ("[Website].[OrderLineList]", 4),
        ("[Website].[OrderList]", 8),
        ("[Website].[SensorDataList]", 4),
    }

    def test_count(self, dm):
        assert len(dm.table_types) == 4

    def test_names_and_column_counts(self, dm):
        actual = {(tt.name.raw, len(tt.columns)) for tt in dm.table_types}
        assert actual == self.EXPECTED

    def test_total_columns(self, dm):
        assert sum(len(tt.columns) for tt in dm.table_types) == 17

    def test_table_type_columns_have_types(self, dm):
        for tt in dm.table_types:
            for c in tt.columns:
                assert c.type_specifier is not None


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

class TestRoles:
    EXPECTED = {
        "External Sales", "Far West Sales", "Great Lakes Sales",
        "Mideast Sales", "New England Sales", "Plains Sales",
        "Rocky Mountain Sales", "Southeast Sales", "Southwest Sales",
    }

    def test_count(self, dm):
        assert len(dm.roles) == 9

    def test_names(self, dm):
        assert {r.name.parts[0] for r in dm.roles} == self.EXPECTED


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

class TestPermissions:
    def test_count(self, dm):
        assert len(dm.permissions) == 2

    def test_grantees_are_public(self, dm):
        for p in dm.permissions:
            assert p.grantee.raw == "[public]"


# ---------------------------------------------------------------------------
# Filegroups
# ---------------------------------------------------------------------------

class TestFilegroups:
    EXPECTED = {"USERDATA", "WWI_InMemory_Data"}

    def test_count(self, dm):
        assert len(dm.filegroups) == 2

    def test_names(self, dm):
        assert {fg.name.parts[0] for fg in dm.filegroups} == self.EXPECTED


# ---------------------------------------------------------------------------
# Partition functions
# ---------------------------------------------------------------------------

class TestPartitionFunctions:
    def test_count(self, dm):
        assert len(dm.partition_functions) == 2

    def test_pf_transaction_date(self, dm):
        pf = next(
            pf for pf in dm.partition_functions
            if pf.name.parts[0] == "PF_TransactionDate"
        )
        assert pf.parameter_type.type_name == "date"
        assert len(pf.boundary_values) == 4

    def test_pf_transaction_datetime(self, dm):
        pf = next(
            pf for pf in dm.partition_functions
            if pf.name.parts[0] == "PF_TransactionDateTime"
        )
        assert pf.parameter_type.type_name == "datetime"
        assert len(pf.boundary_values) == 4

    def test_both_range_right(self, dm):
        from models.enums import PartitionRange
        for pf in dm.partition_functions:
            assert pf.range_type == PartitionRange.RIGHT


# ---------------------------------------------------------------------------
# Partition schemes
# ---------------------------------------------------------------------------

class TestPartitionSchemes:
    EXPECTED = {"PS_TransactionDate", "PS_TransactionDateTime"}

    def test_count(self, dm):
        assert len(dm.partition_schemes) == 2

    def test_names(self, dm):
        names = {ps.name.parts[0] for ps in dm.partition_schemes}
        assert names == self.EXPECTED


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------

class TestPrimaryKeys:
    def test_count(self, dm):
        assert len(dm.primary_keys) == 31

    def test_cities_pk(self, dm):
        pk = next(
            pk for pk in dm.primary_keys
            if "Cities" in pk.defining_table.raw and "Archive" not in pk.defining_table.raw
        )
        assert len(pk.columns) > 0


class TestForeignKeys:
    def test_count(self, dm):
        assert len(dm.foreign_keys) == 98

    def test_have_columns(self, dm):
        for fk in dm.foreign_keys:
            assert len(fk.columns) > 0
            assert len(fk.foreign_columns) > 0

    def test_defining_and_foreign_table_populated(self, dm):
        for fk in dm.foreign_keys:
            assert fk.defining_table.raw != ""
            assert fk.foreign_table.raw != ""


class TestCheckConstraints:
    def test_count(self, dm):
        assert len(dm.check_constraints) == 3

    def test_have_expressions(self, dm):
        for ck in dm.check_constraints:
            assert ck.expression != ""


class TestUniqueConstraints:
    def test_count(self, dm):
        assert len(dm.unique_constraints) == 17

    def test_have_columns(self, dm):
        for uq in dm.unique_constraints:
            assert len(uq.columns) > 0


class TestDefaultConstraints:
    def test_count(self, dm):
        assert len(dm.default_constraints) == 41

    def test_have_expressions(self, dm):
        for dc in dm.default_constraints:
            assert dc.expression != ""


# ---------------------------------------------------------------------------
# Indexes
# ---------------------------------------------------------------------------

class TestIndexes:
    def test_count(self, dm):
        assert len(dm.indexes) == 99

    def test_all_have_indexed_object(self, dm):
        for idx in dm.indexes:
            assert idx.indexed_object.raw != ""

    def test_all_have_columns(self, dm):
        for idx in dm.indexes:
            assert len(idx.columns) > 0


# ---------------------------------------------------------------------------
# Extended properties
# ---------------------------------------------------------------------------

class TestExtendedProperties:
    def test_count(self, dm):
        assert len(dm.extended_properties) == 400

    def test_all_have_value(self, dm):
        for ep in dm.extended_properties:
            assert ep.value is not None
            assert ep.value != ""

    def test_cities_description(self, dm):
        ep = next(
            ep for ep in dm.extended_properties
            if "Cities" in ep.name.raw
            and "CityID" in ep.name.raw
            and "Description" in ep.name.raw
        )
        assert "city" in ep.value.lower()
