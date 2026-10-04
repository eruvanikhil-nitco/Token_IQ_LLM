"""Rewriting messages that point at upstream, without wrecking the text around them.

The hazard here is specific and has already happened once in this repository: a stripping
pattern with `\\s*` around the URL eats the newline after it and merges the following line
into the one before. A docstring loses its paragraph breaks, a bullet list becomes one line,
and nothing fails, because the file still parses.
"""

from __future__ import annotations

from typing import Final

from scripts.rewrite_upstream_links import rewrite_text


class TestItRemovesTheLink:
    def test_a_trailing_dash_link_goes_with_its_connector(self) -> None:
        got: Final = rewrite_text('raise ValueError("Bad thing. Learn more - https://docs.litellm.ai/docs/x")')
        assert got == 'raise ValueError("Bad thing.")'

    def test_a_see_link_goes_with_its_connector(self) -> None:
        got: Final = rewrite_text('"Mode not supported. See modes here: https://docs.litellm.ai/docs/proxy/health"')
        assert got == '"Mode not supported."'

    def test_a_parenthesised_link_takes_its_brackets(self) -> None:
        got: Final = rewrite_text('"Set a key (https://docs.litellm.ai/docs/proxy/virtual_keys) first"')
        assert got == '"Set a key first"'

    def test_a_bare_url_in_a_comment_leaves_the_comment_text(self) -> None:
        got: Final = rewrite_text("# relevant issue: https://github.com/BerriAI/litellm/issues/11404")
        assert got == "# relevant issue"

    def test_a_comment_that_is_only_a_link_is_dropped_to_nothing(self) -> None:
        assert rewrite_text("# https://github.com/BerriAI/litellm/issues/5158").strip() == ""


class TestItDoesNotWreckTheSurroundingText:
    def test_the_newline_after_a_link_survives(self) -> None:
        """The exact bug this guards. `\\s*` after the URL would join these two lines."""
        source: Final = '"""First line - https://docs.litellm.ai/docs/x\nSecond line stays its own."""'
        got: Final = rewrite_text(source)
        assert "\nSecond line stays its own." in got
        assert "First lineSecond" not in got

    def test_a_bullet_list_keeps_its_breaks(self) -> None:
        source: Final = "# - one https://docs.litellm.ai/a\n# - two\n# - three\n"
        got: Final = rewrite_text(source)
        assert got.count("\n") == source.count("\n")

    def test_indentation_is_untouched(self) -> None:
        source: Final = '        "Something - https://docs.litellm.ai/docs/x"\n'
        got: Final = rewrite_text(source)
        assert got.startswith("        "), "leading indentation must survive"

    def test_a_line_with_no_upstream_link_is_returned_unchanged(self) -> None:
        source: Final = 'raise ValueError("ordinary message")\n'
        assert rewrite_text(source) == source

    def test_an_unrelated_url_is_left_alone(self) -> None:
        source: Final = '"See https://platform.openai.com/docs/api-reference for the shape"'
        assert rewrite_text(source) == source


class TestTheMappedMessages:
    def test_the_unmapped_model_message_names_where_to_fix_it(self) -> None:
        """The most common user-facing one. It used to send people to a file in somebody
        else's repository, which they cannot edit."""
        source: Final = (
            '"This model isn\'t mapped yet. Add it here - '
            'https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json"'
        )
        got: Final = rewrite_text(source)
        assert "BerriAI" not in got
        assert "data/pricing/model_prices.json" in got

    def test_the_virtual_keys_link_points_at_our_own_documentation(self) -> None:
        source: Final = '"Set a virtual key. See https://docs.litellm.ai/docs/proxy/virtual_keys"'
        got: Final = rewrite_text(source)
        assert "litellm.ai" not in got


class TestIdempotence:
    def test_running_it_twice_changes_nothing_the_second_time(self) -> None:
        source: Final = '"Bad thing. Learn more - https://docs.litellm.ai/docs/x"\n# issue: https://github.com/BerriAI/litellm/issues/1\n'
        once: Final = rewrite_text(source)
        assert rewrite_text(once) == once


class TestTidyStaysWithinOneLine:
    def test_collapsing_runs_of_spaces_never_joins_two_lines(self) -> None:
        """Tidy runs per line on purpose. Applied to the whole text, a run of spaces
        spanning a newline would collapse into one space and merge the lines."""
        source: Final = '"A - https://docs.litellm.ai/docs/x"   \n   "B stays separate"\n'
        got: Final = rewrite_text(source)
        assert got.count("\n") == source.count("\n")
        assert '"B stays separate"' in got

    def test_a_blank_line_between_paragraphs_survives(self) -> None:
        source: Final = '"""Para one - https://docs.litellm.ai/docs/x\n\nPara two."""'
        got: Final = rewrite_text(source)
        assert "\n\nPara two." in got


class TestItOnlyTouchesLinesItChanged:
    """The bug this guards actually happened, twice, in different forms.

    Tidying every line of a file that merely contains a link somewhere collapses the padding
    in aligned comments and ASCII-art boxes. It changed 16,140 lines across 135 files for 334
    URLs, and every one of those files still parsed, so nothing failed.
    """

    def test_a_box_we_keep_does_not_lose_its_padding(self) -> None:
        """Upstream's support banner is deleted whole, but any other aligned box stays, and
        its padding must survive the line that happened to hold a link."""
        source: Final = (
            "# +--------------------------------------+\n"
            "# |   Observer-only: see decision 0001   |\n"
            "# |   https://docs.litellm.ai/docs/x     |\n"
            "# +--------------------------------------+\n"
        )
        got: Final = rewrite_text(source)
        assert "BerriAI" not in got and "litellm.ai" not in got
        assert "# |   Observer-only: see decision 0001   |" in got, "padding was collapsed"

    def test_an_aligned_comment_elsewhere_in_the_file_keeps_its_spacing(self) -> None:
        source: Final = (
            'x = 1        # aligned\n'
            '"A - https://docs.litellm.ai/docs/x"\n'
            'y = 2        # aligned\n'
        )
        got: Final = rewrite_text(source)
        assert "x = 1        # aligned" in got
        assert "y = 2        # aligned" in got


class TestTheSupportBanner:
    def test_the_whole_banner_goes_rather_than_being_hollowed_out(self) -> None:
        """Stripping only its URL leaves `# | |`, a broken box advertising nothing. It is
        upstream's support channel, so it goes whole."""
        source: Final = (
            "# +-----------------------------------------------+\n"
            "# |                                               |\n"
            "# |           Give Feedback / Get Help            |\n"
            "# | https://github.com/BerriAI/litellm/issues/new |\n"
            "# |                                               |\n"
            "# +-----------------------------------------------+\n"
            "#\n"
            "#  Thank you users! We love you!\n"
            "import os\n"
        )
        got: Final = rewrite_text(source)
        assert got == "import os\n"

    def test_an_unrelated_boxed_comment_is_not_mistaken_for_it(self) -> None:
        source: Final = (
            "# +------------------+\n"
            "# |  Our own notice  |\n"
            "# +------------------+\n"
            '"A - https://docs.litellm.ai/docs/x"\n'
        )
        got: Final = rewrite_text(source)
        assert "Our own notice" in got
