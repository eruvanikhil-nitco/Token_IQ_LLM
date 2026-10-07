"""Tests for scripts/rename/rename_prisma_references.py.

The schema renamed the models, so the generated client's class names and accessors moved with them. What
this pass has to get right is telling a generated name from one that only looks like it:
`token_iq/gateway/models/` declares its own Pydantic classes called `LiteLLM_BudgetTable` and friends,
which mirror the rows without being them, and renaming one of those changes a key the API returns.

Getting it wrong in the other direction is loud, an AttributeError on the first query, which is the easier
half.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "scripts" / "rename" / "rename_prisma_references.py"
_spec = importlib.util.spec_from_file_location("rename_prisma_references", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
rename_prisma_references = importlib.util.module_from_spec(_spec)
sys.modules["rename_prisma_references"] = rename_prisma_references
_spec.loader.exec_module(rename_prisma_references)

BOUND = "from prisma import models as prisma_models\n"


def moved(text: str) -> str:
    found, _counts = rename_prisma_references.rewrite(text)
    return found


def body(text: str) -> str:
    """The rewritten file without the import that binds the alias, so a case states one thing."""
    return moved(BOUND + text).removeprefix(BOUND)


# --- generated names ------------------------------------------------------------------------------


def test_a_generated_class_read_off_a_prisma_alias_is_renamed() -> None:
    assert body("row = prisma_models.LiteLLM_TeamTable\n") == "row = prisma_models.TeamTable\n"


def test_a_generated_input_type_is_renamed_the_same_way() -> None:
    before = "from prisma import types as prisma_types\nwhere: prisma_types.LiteLLM_TeamTableWhereInput = {}\n"

    assert moved(before).endswith("where: prisma_types.TeamTableWhereInput = {}\n")


def test_an_attribute_on_something_that_is_not_a_prisma_alias_is_left_alone() -> None:
    """`models.LiteLLM_TeamTable` is the engine's own Pydantic mirror unless `models` is prisma's."""
    before = "from token_iq.gateway import models\nrow = models.LiteLLM_TeamTable\n"

    assert moved(before) == before


def test_a_locally_declared_class_of_the_same_name_is_left_alone() -> None:
    """These are the API's own shapes. Renaming one changes a key the dashboard reads, which is why the
    phase leaves them where they are."""
    before = "class LiteLLM_BudgetTable(BaseModel):\n    pass\n\n\nx = LiteLLM_BudgetTable()\n"

    assert moved(before) == before


# --- imports --------------------------------------------------------------------------------------


def test_an_aliased_import_renames_only_the_imported_name() -> None:
    before = "from prisma.models import LiteLLM_SSOIdentityAssertion as AssertionRow\nrow = AssertionRow\n"

    assert moved(before) == "from prisma.models import SSOIdentityAssertion as AssertionRow\nrow = AssertionRow\n"


def test_a_plain_import_renames_the_import_and_every_use_of_it() -> None:
    before = (
        "from prisma.models import LiteLLM_Config\n\n\ndef read() -> LiteLLM_Config:\n    return LiteLLM_Config()\n"
    )

    assert moved(before) == ("from prisma.models import Config\n\n\ndef read() -> Config:\n    return Config()\n")


def test_an_import_spread_over_several_lines_renames_each_name() -> None:
    """Editing the statement rather than each name skipped these, and left their uses renamed without
    the import, which does not even import."""
    before = (
        "from prisma.types import (\n"
        "    LiteLLM_AgentsTableInclude,\n"
        "    LiteLLM_GuardrailsTableWhereInput,\n"
        ")\n"
        "x: LiteLLM_AgentsTableInclude = {}\n"
    )

    assert moved(before) == (
        "from prisma.types import (\n"
        "    AgentsTableInclude,\n"
        "    GuardrailsTableWhereInput,\n"
        ")\n"
        "x: AgentsTableInclude = {}\n"
    )


def test_an_import_from_somewhere_else_is_left_alone() -> None:
    before = "from token_iq.gateway.models.budget import LiteLLM_BudgetTable\nx = LiteLLM_BudgetTable\n"

    assert moved(before) == before


# --- accessors ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("await prisma_client.db.litellm_auditlog.count()", "await prisma_client.db.auditlog.count()"),
        ("x = db.litellm_teamtable.find_many()", "x = db.teamtable.find_many()"),
        ("y = self.db.litellm_usertable", "y = self.db.usertable"),
        ("z = mock_prisma.db.litellm_organizationtable", "z = mock_prisma.db.organizationtable"),
    ],
)
def test_an_accessor_read_off_db_is_renamed(before: str, after: str) -> None:
    assert body(f"{before}\n") == f"{after}\n"


def test_an_attribute_that_is_not_read_off_db_is_left_alone() -> None:
    """The accessor is the model name lowercased, and that shape is not reserved. `settings.litellm_params`
    is a config key, and renaming it here would break reading a customer's file."""
    before = "x = settings.litellm_params\n"

    assert body(before) == before


def test_a_test_double_moves_with_the_engine() -> None:
    """A test mocking `db.litellm_teamtable` stops intercepting a call to `db.teamtable`, and then asserts
    against a path the engine no longer takes."""
    before = "mock.db.litellm_teamtable.find_unique = AsyncMock(return_value=None)\n"

    assert body(before) == "mock.db.teamtable.find_unique = AsyncMock(return_value=None)\n"


# --- strings --------------------------------------------------------------------------------------


def test_a_class_named_inside_a_string_annotation_is_renamed() -> None:
    before = 'def f() -> "TableActions[prisma_models.LiteLLM_TeamTable]":\n    ...\n'

    assert body(before) == 'def f() -> "TableActions[prisma_models.TeamTable]":\n    ...\n'


def test_two_classes_named_in_one_string_both_move() -> None:
    """One edit per span, so the second replacement has to happen inside the first one's result."""
    before = 'x: "Pair[prisma_models.LiteLLM_TeamTable, prisma_models.LiteLLM_UserTable]" = p\n'

    assert body(before) == 'x: "Pair[prisma_models.TeamTable, prisma_models.UserTable]" = p\n'


def test_a_string_naming_the_real_table_is_left_alone() -> None:
    """Raw SQL still names `LiteLLM_SpendLogs` because `@@map` kept the table there. 306 queries depend on
    it, and they move with the ALTER TABLE in step 2."""
    before = "rows = await db.query_raw('SELECT * FROM \"LiteLLM_SpendLogs\"')\n"

    assert body(before) == before


# --- mechanics ------------------------------------------------------------------------------------


def test_a_non_ascii_character_earlier_on_the_line_does_not_shift_the_edit() -> None:
    """`col_offset` is a byte offset into the line's UTF-8."""
    before = 'x = log("café", prisma_models.LiteLLM_TeamTable)\n'

    assert body(before) == 'x = log("café", prisma_models.TeamTable)\n'


def test_two_references_on_one_line_both_move() -> None:
    """Edited back to front, and the new name is shorter than the old one."""
    before = "x = (prisma_models.LiteLLM_TeamTable, prisma_models.LiteLLM_UserTable)\n"

    assert body(before) == "x = (prisma_models.TeamTable, prisma_models.UserTable)\n"


def test_a_file_that_does_not_parse_is_left_exactly_as_it_was() -> None:
    assert rename_prisma_references.rewrite("def (\n")[0] == "def (\n"


def test_a_rewrite_that_would_not_parse_leaves_the_file_as_it_was(tmp_path: Path) -> None:
    source = tmp_path / "mod.py"
    _ = source.write_text(BOUND + "x = prisma_models.LiteLLM_TeamTable\n", encoding="utf-8")

    totals, broken = rename_prisma_references.run([source], write=True)

    assert not broken
    assert totals["generated class"] == 1
    assert source.read_text(encoding="utf-8").endswith("x = prisma_models.TeamTable\n")


def test_this_pass_and_its_tests_are_out_of_scope() -> None:
    """Both name the generated classes on purpose."""
    listed = {rename_prisma_references.named(path) for path in rename_prisma_references.tracked()}

    assert "scripts/rename/rename_prisma_references.py" not in listed
    assert "tests/gateway/test_rename_prisma_references.py" not in listed
    assert "token_iq/gateway/proxy/utils.py" in listed, "the filter is too wide"


def test_nothing_is_left_spread_over_more_than_one_line() -> None:
    """The one shape the pass cannot address, so the audit has to come back empty for the run to be
    complete rather than merely finished."""
    assert rename_prisma_references.leftovers(rename_prisma_references.tracked()) == ()


def test_two_aliases_naming_a_model_in_one_string_both_move() -> None:
    """One edit per span, so each alias after the first has to be replaced inside the first one's result.
    Two mentions of the *same* alias do not show this: replacing a substring replaces every copy of it."""
    before = (
        "from prisma import models as prisma_models\n"
        "from prisma import types as prisma_types\n"
        'x: "Pair[prisma_models.LiteLLM_TeamTable, prisma_types.LiteLLM_TeamTableWhereInput]" = p\n'
    )

    assert moved(before).endswith('x: "Pair[prisma_models.TeamTable, prisma_types.TeamTableWhereInput]" = p\n')


def test_an_alias_bound_to_something_other_than_a_prisma_module_is_not_one() -> None:
    """`from prisma import Prisma as client` binds a class, not a module, so `client.LiteLLM_X` is not a
    generated class and renaming it would invent an attribute."""
    before = "from prisma import Prisma as client\nrow = client.LiteLLM_TeamTable\n"

    assert moved(before) == before


def test_an_aliased_import_does_not_rename_a_local_class_of_the_imported_name() -> None:
    """The dangerous overlap. The module imports the row under another name and declares its own mirror
    under the original one, so treating the import as plain would rename the mirror and its uses."""
    before = (
        "from prisma.models import LiteLLM_BudgetTable as BudgetRow\n"
        "\n"
        "\n"
        "class LiteLLM_BudgetTable(BaseModel):\n"
        "    pass\n"
        "\n"
        "\n"
        "mine = LiteLLM_BudgetTable()\n"
        "theirs = BudgetRow\n"
    )

    found = moved(before)

    assert "from prisma.models import BudgetTable as BudgetRow" in found
    assert "class LiteLLM_BudgetTable(BaseModel):" in found
    assert "mine = LiteLLM_BudgetTable()" in found


# --- accessors reached by name rather than by attribute --------------------------------------------


def test_a_string_that_is_an_accessor_name_is_renamed() -> None:
    """Some accessors are reached through `getattr(prisma_client.db, table_name)`, so the string that
    feeds one has to move with the model."""
    assert body('table_name = "litellm_dailyteamspend"\n') == 'table_name = "dailyteamspend"\n'


def test_a_mock_built_from_an_accessor_name_moves_too() -> None:
    before = 'fake = type("DB", (), {"litellm_skillstable": table})()\n'

    assert body(before) == 'fake = type("DB", (), {"skillstable": table})()\n'


@pytest.mark.parametrize(
    "value",
    ["litellm_params", "litellm_settings", "litellm_provider", "litellm_metadata", "litellm_proxy"],
)
def test_a_string_that_only_looks_like_an_accessor_is_left_alone(value: str) -> None:
    """An accessor name is not a reserved shape. These are a config key, a field in the price file and the
    provider a customer writes, and the set comes from the schema so none of them is in it."""
    assert body(f'x = "{value}"\n') == f'x = "{value}"\n'


def test_the_accessor_names_come_from_the_schema() -> None:
    """Written down here the set would drift from the models, and a string naming a table that no longer
    exists fails only when that code path runs."""
    names = rename_prisma_references.accessor_names()

    assert "litellm_teamtable" in names
    assert "litellm_dailyteamspend" in names
    assert "litellm_params" not in names
    assert len(names) == 85


def test_an_accessor_read_off_a_transaction_is_renamed() -> None:
    """The first version of this rule only knew about `db`, and the MCP tables read theirs off a
    transaction, so it would have shipped `tx.litellm_mcpuserenvvars` naming nothing."""
    assert body("row = await tx.litellm_mcpservertable.find_first()\n") == (
        "row = await tx.mcpservertable.find_first()\n"
    )


def test_an_attribute_a_mock_assigns_is_renamed() -> None:
    """A hand-rolled `MockDB` sets these in `__init__`, and the engine now asks for the short name."""
    assert body("self.litellm_endusertable = MockTable()\n") == "self.endusertable = MockTable()\n"


def test_a_keyword_argument_named_after_an_accessor_is_renamed() -> None:
    before = "db = SimpleNamespace(litellm_managedobjecttable=table)\n"

    assert body(before) == "db = SimpleNamespace(managedobjecttable=table)\n"


def test_a_protocol_field_named_after_an_accessor_is_renamed() -> None:
    before = 'litellm_mcpuserenvvars: "TableActions[Row]"\n'

    assert body(before) == 'mcpuserenvvars: "TableActions[Row]"\n'


@pytest.mark.parametrize(
    "name",
    ["litellm_params", "litellm_metadata", "litellm_settings", "litellm_dailyspend"],
)
def test_an_attribute_that_only_looks_like_an_accessor_is_left_alone(name: str) -> None:
    """Recognising an accessor by its name rather than by what it is read off is only safe because the set
    is the 85 models. A config key is not one of them, and neither is `litellm_dailyspend`: no such model
    exists, and a test invents it to drive `get_daily_activity` through a mock. The first version of this
    rule matched the prefix rather than the name and renamed it, which left that test mocking one table
    and asking for another.
    """
    assert body(f"x = db.{name}\n") == f"x = db.{name}\n"


def test_a_plainly_imported_class_named_inside_a_string_is_renamed() -> None:
    """A quoted type hint is a string, not a `Name`, so the rule that renames uses never sees it. Left
    behind it is an undefined name, because the import beside it has moved."""
    before = 'from prisma.models import LiteLLM_Config\n\n\nasync def f() -> "LiteLLM_Config | None": ...\n'

    assert moved(before).endswith('async def f() -> "Config | None": ...\n')


def test_a_string_naming_a_class_this_module_did_not_import_is_left_alone() -> None:
    """`"LiteLLM_BudgetTable"` in a module that imports nothing from prisma is the engine's own mirror."""
    before = 'x: "LiteLLM_BudgetTable | None" = None\n'

    assert moved(before) == before


def test_a_property_named_after_an_accessor_is_renamed() -> None:
    """A mock exposes its tables as properties, and the `def` line is the only place that name appears.
    Missed, the engine asks for the short name and the mock raises AttributeError on the first query."""
    before = "class MockDB:\n    @property\n    def litellm_proxymodeltable(self):\n        return self._table\n"

    assert body(before) == (
        "class MockDB:\n    @property\n    def proxymodeltable(self):\n        return self._table\n"
    )


def test_a_method_whose_name_only_looks_like_an_accessor_is_left_alone() -> None:
    before = "def litellm_params(self):\n    return self._params\n"

    assert body(before) == before
