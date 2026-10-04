"""Removing dashboard links to another product's documentation, without breaking the JSX.

A half-removed element breaks the build loudly, which is the safe failure. The dangerous one
is a leftover `{" "}` spacer or a collapsed line, because the build still passes and the page
just renders slightly wrong.
"""

from __future__ import annotations

from typing import Final

from scripts.remove_ui_doc_links import remove_links


class TestItRemovesTheWholeElement:
    def test_an_anchor_goes_with_its_text(self) -> None:
        """"Learn more" with no destination is not worth keeping."""
        source: Final = (
            "    <AlertDescription>\n"
            "      Configure an email integration first.{\" \"}\n"
            '      <a href="https://docs.litellm.ai/docs/proxy/email" target="_blank" rel="noreferrer">\n'
            "        Learn how to set up email notifications\n"
            "      </a>\n"
            "    </AlertDescription>\n"
        )
        got: Final = remove_links(source)
        assert "docs.litellm.ai" not in got
        assert "Learn how to set up email notifications" not in got
        assert "Configure an email integration first." in got

    def test_a_help_link_element_goes_too(self) -> None:
        source: Final = (
            '  <HelpLink href="https://docs.litellm.ai/docs/proxy/custom_pricing">\n'
            "    Learn more about custom pricing\n"
            "  </HelpLink>\n"
        )
        assert remove_links(source).strip() == ""

    def test_a_self_closing_link_goes(self) -> None:
        source: Final = '  <HelpLink href="https://docs.litellm.ai/docs/x" label="Docs" />\n'
        assert remove_links(source).strip() == ""


class TestItLeavesNothingBroken:
    def test_no_dangling_spacer_is_left_before_a_closing_tag(self) -> None:
        """A stray {" "} renders a space nobody asked for and no test would catch it."""
        source: Final = (
            "  <p>\n"
            '    Some text.{" "}\n'
            '    <a href="https://docs.litellm.ai/docs/x">Docs</a>\n'
            "  </p>\n"
        )
        got: Final = remove_links(source)
        assert '{" "}' not in got
        assert "Some text." in got

    def test_surrounding_elements_survive_intact(self) -> None:
        source: Final = (
            "  <div>\n"
            "    <Keep />\n"
            '    <a href="https://docs.litellm.ai/docs/x">Docs</a>\n'
            "    <AlsoKeep />\n"
            "  </div>\n"
        )
        got: Final = remove_links(source)
        assert "<Keep />" in got and "<AlsoKeep />" in got

    def test_it_stops_at_the_first_closing_tag(self) -> None:
        """Greedy matching would swallow everything up to the last </a> in the file."""
        source: Final = (
            '<a href="https://docs.litellm.ai/docs/x">Docs</a>\n'
            '<a href="https://example.com">Keep this one</a>\n'
        )
        got: Final = remove_links(source)
        assert "Keep this one" in got
        assert "example.com" in got

    def test_an_unrelated_link_is_untouched(self) -> None:
        source: Final = '<a href="https://platform.openai.com/docs">OpenAI docs</a>\n'
        assert remove_links(source) == source

    def test_a_file_with_no_doc_link_is_returned_unchanged(self) -> None:
        source: Final = "export const x = 1;\n"
        assert remove_links(source) == source

    def test_indentation_elsewhere_is_preserved(self) -> None:
        source: Final = (
            "  <div>\n"
            "        <DeeplyIndented />\n"
            '    <a href="https://docs.litellm.ai/docs/x">Docs</a>\n'
            "  </div>\n"
        )
        assert "        <DeeplyIndented />" in remove_links(source)


class TestIdempotence:
    def test_running_it_twice_changes_nothing_the_second_time(self) -> None:
        source: Final = (
            "  <p>\n"
            '    Text.{" "}\n'
            '    <a href="https://docs.litellm.ai/docs/x">Docs</a>\n'
            "  </p>\n"
        )
        once: Final = remove_links(source)
        assert remove_links(once) == once


class TestALinkUsedAsAPropValue:
    """An anchor passed as a prop is the whole prop's reason to exist.

    Removing just the element leaves `render={}`, which is not valid JSX. The build caught
    this one, which is the good failure, but only after it had been written to 30 files.
    """

    def test_the_whole_prop_goes_not_just_the_element(self) -> None:
        source: Final = (
            "  <Badge\n"
            '    variant="outline"\n'
            '    render={<a href="https://docs.litellm.ai/release_notes" target="_blank" />}\n'
            '    className="px-1.5"\n'
            "  >\n"
            "    v{version}\n"
            "  </Badge>\n"
        )
        got: Final = remove_links(source)
        assert "render={}" not in got
        assert "docs.litellm.ai" not in got
        assert 'variant="outline"' in got and 'className="px-1.5"' in got

    def test_a_prop_holding_a_non_doc_anchor_is_untouched(self) -> None:
        source: Final = '  render={<a href="https://example.com/x" target="_blank" />}\n'
        assert remove_links(source) == source

    def test_a_multi_line_prop_value_takes_the_whole_prop(self) -> None:
        """`render={` then the anchor on its own lines. Removing only the element leaves an
        empty expression, which is the same invalid JSX as `render={}`."""
        source: Final = (
            "            <Button\n"
            "              render={\n"
            '                <a href="https://docs.litellm.ai/docs/proxy/cost_tracking" target="_blank">\n'
            "                  View Usage Guide\n"
            "                </a>\n"
            "              }\n"
            "            />\n"
        )
        got: Final = remove_links(source)
        assert "docs.litellm.ai" not in got
        assert "render={" not in got, "the prop should be gone, not left empty"
        assert "<Button" in got

    def test_an_inline_prop_value_is_caught_too(self) -> None:
        """`<Badge variant="outline" render={<a .../>}>` has no newline before the prop.
        Requiring one left `render={}` in two test files, invisible to the build because it
        does not compile tests."""
        source: Final = '    <Badge variant="outline" render={<a href="https://docs.litellm.ai/x" />}>\n'
        got: Final = remove_links(source)
        assert "render={}" not in got
        assert 'variant="outline"' in got
