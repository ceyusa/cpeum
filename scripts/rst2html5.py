#!/usr/bin/env python3
# :Copyright: © 2025 Víctor Jáquez.
# :License: Released under the terms of the `2-Clause BSD license`_, in short:
#
#    Copying and distribution of this file, with or without modification,
#    are permitted in any medium without royalty provided the copyright
#    notice and this notice are preserved.
#    This file is offered as-is, without any warranty.
#
# .. _2-Clause BSD license: https://opensource.org/licenses/BSD-2-Clause

"""A minimal front end to the Docutils Publisher, producing HTML5 documents."""

import logging
import re
import subprocess
from pathlib import Path

from docutils import nodes
from docutils.core import default_description, publish_cmdline
from docutils.parsers.rst import Parser, directives
from docutils.parsers.rst.directives import misc
from docutils.writers.html5_polyglot import HTMLTranslator, Writer

GITHUB_URL = "https://github.com/ceyusa/cpeum"
DESCRIPTION = "Generador HTML5 de la CPEUM" + default_description

logger = logging.getLogger(__name__)


class IncludeWithSection(misc.Include):
    """Custom include directive handler."""

    def run(self) -> list[nodes.Node]:
        """Process the include directive with section wrapping."""
        source_dir = Path(self.state.document.current_source).parent
        filename = self.arguments[0]
        base_name = Path(filename).stem

        # if Transitorio go as normal include
        if base_name.startswith("T"):
            self.arguments[0] = filename
            return super().run()

        # Update the argument to use the resolved path
        self.arguments[0] = filename

        # custom parser
        self.options["parser"] = Parser
        # Get the result from the parent class
        result = super().run()
        # delete custom parser
        del self.options["parser"]
        # Create a section node to wrap the included content
        section = nodes.section(classes=["articulo"])
        section["ids"].append(base_name)

        aside = None
        # Get git commit history for the included file
        git_fn = source_dir / self.arguments[0]
        git_history = self._parse_git_history(str(git_fn))
        if git_history:
            aside = nodes.container(classes=["git-history"])
            aside["git-history"] = git_history

        # Move all the result nodes into the section
        for index, node in enumerate(result):
            if aside is not None and index == 1:
                # Add the aside to the section after the title
                section.append(aside)
            section.append(node)

        return [section]

    def _get_git_root(self, filename: str) -> str:
        """Ensure we operate from the git repository root."""
        file_dir = Path(filename).parent
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                cwd=str(file_dir),
                check=True,
            )
            git_root = result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            git_root = str(file_dir)
        return git_root

    def _get_commit_blocks(self, git_root: str, rel_filename: str) -> list[str]:
        """Execute git log and return commit blocks for the given file."""
        try:
            result = subprocess.run(
                [
                    "git",
                    "log",
                    "--grep",
                    "Artículo",
                    "--format=%H%n%n%b%n---END-COMMIT---",
                    "--",
                    rel_filename,
                ],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=git_root,
                check=True,
            )
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ) as e:
            logger.warning("Could not get git history for %s: %s", rel_filename, e)
            return []

        return result.stdout.split("---END-COMMIT---")

    def _parse_git_history(self, filename: str) -> list[dict[str, str]]:
        """Parse git log to extract relevant commit information."""
        abs_filename = str(Path(filename).resolve())
        git_root = self._get_git_root(abs_filename)
        rel_filename = str(Path(abs_filename).relative_to(git_root))

        commits = []

        for block in self._get_commit_blocks(git_root, rel_filename):
            commit_info = self._parse_commit_block(block)
            if commit_info:
                commits.append(commit_info)
        return commits

    @staticmethod
    def _parse_commit_block(block: str) -> dict[str, str] | None:
        """Parse a single commit block into a structured dict."""
        lines = [i.replace("\n", " ") for i in block.strip().split("\n\n")]
        if not lines:
            return None

        try:
            commit_hash = lines[0].strip()

            # Validate commit hash (supports SHA-1 and SHA-256)
            if not re.match(r"^[a-f0-9]{40,}$", commit_hash):
                return None

            body = "\n".join(lines[1:]).strip()

            # Match "Publicado en el Diario Oficial de la Federación el [date]"
            pub_pattern = (
                r"Publicado\s+en\s+el\s+Diario\s+Oficial\s+de\s+la\s+"
                r"Federación\s+el\s+([^\.\n\r\t]+?)\s*(?:\.|$|\n|http)"
            )

            pub_date = None
            match = re.search(pub_pattern, body, re.IGNORECASE)
            if match:
                pub_date = match.group(1).strip()
                pub_date = re.sub(r"[,\s\.]*$", "", pub_date)
                pub_date = re.sub(r"\s*https?://\S*$", "", pub_date)

            # If no specific publication date found in patterns, try
            # to find any date in the body
            if not pub_date:
                date_pattern = r"(\d{1,2}\s+de\s+[A-Za-z]+\s+de\s+\d{4})"
                match = re.search(date_pattern, body)
                if match:
                    pub_date = match.group(1)

            # Fallback to commit date if no publication date found
            if not pub_date:
                pub_date = "Sin fecha"

            decreto_pattern = r"(DECRETO\s+.+)\n"
            match = re.search(decreto_pattern, body, re.IGNORECASE)
            decreto = match.group(1).strip() if match else ""

            return {
                "hash": commit_hash[:8],
                "pub_date": pub_date,
                "decreto": decreto,
            }
        except (IndexError, AttributeError) as e:
            logger.warning("Skipping malformed commit block: %s", e)
            return None


class CustomHTMLTranslator(HTMLTranslator):
    """Custom HTML translator with git-history sidebar support."""

    def visit_section(self, node: nodes.section) -> None:
        """Render sections as HTML5 <section> tags."""
        self.section_level += 1
        self.body.append(self.starttag(node, "section"))

    def depart_section(self, _: nodes.section) -> None:
        """Close the <section> tag."""
        self.section_level -= 1
        self.body.append("</section>\n")

    @staticmethod
    def _is_git_history(node: nodes.container) -> bool:
        """Check if a container node holds git-history data."""
        return (
            "git-history" in node.attributes
            and "classes" in node.attributes
            and "git-history" in node["classes"]
            and node.get("git-history")
        )

    def visit_container(self, node: nodes.container) -> None:
        """Render git-history containers as HTML aside with commit list."""
        if self._is_git_history(node):
            self.body.append('<aside class="sidebar">\n')

            commits = node["git-history"]
            if commits:
                self.body.append("<ul>\n")
                for commit in commits:
                    url = f"{GITHUB_URL}/commit/{commit['hash']}"
                    self.body.append(
                        f'<li><a href="{url}" title="{commit["decreto"]}"'
                        f'rel="external noreferrer" target="_blank">'
                        f"{commit['pub_date']}</a></li>\n",
                    )
                self.body.append("</ul>\n")
        else:
            HTMLTranslator.visit_container(self, node)

    def depart_container(self, node: nodes.container) -> None:
        """Close the git-history aside or delegate to parent."""
        if self._is_git_history(node):
            self.body.append("</aside>\n")
        else:
            HTMLTranslator.depart_container(self, node)

    def unimplemented_visit(self, node):
        logger.warning("Unimplemented visit for node type: %s", type(node).__name__)


class CustomHTML5Writer(Writer):
    """Custom HTML5 writer using our translator."""

    def __init__(self) -> None:
        """Initialize writer with custom translator class."""
        Writer.__init__(self)
        self.translator_class = CustomHTMLTranslator


# Register our custom directive
directives.register_directive("include", IncludeWithSection)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

publish_cmdline(writer=CustomHTML5Writer(), description=DESCRIPTION)
