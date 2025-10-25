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

"""
A minimal front end to the Docutils Publisher, producing HTML 5
documents.
"""

from docutils.core import publish_cmdline, default_description
from docutils.writers.html5_polyglot import HTMLTranslator, Writer
from docutils.parsers.rst import directives, Parser
from docutils.parsers.rst.directives import misc
from docutils import nodes

import os
import re
import subprocess


class IncludeWithSection(misc.Include):
    def run(self):
        # Get the source directory to resolve relative paths
        source_dir = os.path.dirname(self.state.document.current_source)
        filename = self.arguments[0]
        base_name = os.path.splitext(os.path.basename(filename))[0]

        # if Transitorio go as normal include
        if base_name.startswith('T'):
            # Update the argument to use the resolved path
            self.arguments[0] = filename
            return super().run()

        # Update the argument to use the resolved path
        self.arguments[0] = filename

        # custom parser
        self.options['parser'] = Parser
        # Get the result from the parent class
        result = super().run()
        # delete custom parser
        del self.options['parser']
        # Create a section node to wrap the included content
        section = nodes.section(classes=['articulo'])
        section['ids'].append(base_name)

        aside = None
        # Get git commit history for the included file
        git_fn = os.path.join(source_dir, self.arguments[0])
        git_history = self._parse_git_history(git_fn)
        if git_history:
            aside = nodes.container(classes=['git-history'])
            aside['git-history'] = git_history

        # Move all the result nodes into the section
        for index, node in enumerate(result):
            if aside is not None and index == 1:
                # Add the aside to the section after the title
                section.append(aside)
            section.append(node)

        return [section]

    def _get_git_root(self, filename):
        # Make sure we're always in the git repository root to find files
        # Get the absolute path of the file
        file_dir = os.path.dirname(filename)
        # Get the git root directory
        try:
            git_root = subprocess.check_output(
                ['git', 'rev-parse', '--show-toplevel'],
                stderr=subprocess.STDOUT,
                text=True,
                cwd=file_dir
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            git_root = file_dir
        finally:
            return git_root

    def _parse_git_history(self, filename):
        """Parse git log to extract relevant commit information."""
        # Make sure we're always in the git repository root to find files
        # Get the absolute path of the file
        abs_filename = os.path.abspath(filename)
        git_root = self._get_git_root(abs_filename)
        rel_filename = os.path.relpath(abs_filename, git_root)

        try:
            git_log = subprocess.check_output(
                ['git', 'log', '--grep', 'Artículo',
                 '--format=%H%n%n%b%n---END-COMMIT---', '--', rel_filename],
                stderr=subprocess.STDOUT,
                text=True,
                timeout=30,
                cwd=git_root  # Run git commands from the repository root
            )
        except (subprocess.CalledProcessError,
                FileNotFoundError,
                subprocess.TimeoutExpired) as e:
            # Log the error but don't break the build
            import sys
            print(f"Warning: Could not get git history for {filename}: {e}",
                  file=sys.stderr)
            return None

        commits = []
        # Split by our custom delimiter
        commit_blocks = git_log.split('---END-COMMIT---')

        for block in commit_blocks:
            lines = [i.replace('\n', ' ') for i in block.strip().split('\n\n')]
            if not lines:
                continue

            # Parse commit information
            try:
                commit_hash = lines[0].strip()

                # Validate commit hash
                if not re.match(r'^[a-f0-9]{40}$', commit_hash):
                    # Skip if the first line doesn't look like a commit hash
                    # This might be due to parsing issues
                    continue

                body = '\n'.join(lines[1:]).strip()

                # Match "Publicado en el Diario Oficial de la Federación el [date]"
                pub_pattern = r'Publicado\s+en\s+el\s+Diario\s+Oficial\s+de\s+la\s+Federación\s+el\s+([^\.\n\r\t]+?)\s*(?:\.|$|\n|http)'

                pub_date = None
                match = re.search(pub_pattern, body, re.IGNORECASE)
                if match:
                    pub_date = match.group(1).strip()
                    # Clean up the date - remove any trailing punctuation or URLs
                    pub_date = re.sub(r'[,\s\.]*$', '', pub_date)
                    # Remove any http links that might have been captured
                    pub_date = re.sub(r'\s*https?://\S*$', '', pub_date)

                # If no specific publication date found in patterns, try to
                # find any date in the body
                if not pub_date:
                    # Look for common date patterns in the body
                    date_pattern = r'(\d{1,2}\s+de\s+[A-Za-z]+\s+de\s+\d{4})'
                    match = re.search(date_pattern, body)
                    if match:
                        pub_date = match.group(1)

                # Fallback to commit date if no publication date found
                if not pub_date:
                    pub_date = 'Sin fecha'

                decreto_pattern = r'(DECRETO\s+.+)\n'
                match = re.search(decreto_pattern, body, re.IGNORECASE)
                if match:
                    decreto = match.group(1).strip()
                else:
                    decreto = ""

                # Store commit information
                commit_info = {
                    'hash': commit_hash[:8],  # Use short hash
                    'pub_date': pub_date,
                    'decreto': decreto,
                }
                commits.append(commit_info)
            except (IndexError, AttributeError) as e:
                # Skip malformed commit blocks
                import sys
                print(f"Warning: Skipping malformed commit block: {e}",
                      file=sys.stderr)
                continue

        return commits


class CustomHTMLTranslator(HTMLTranslator):
    def visit_section(self, node):
        # Ensure sections use <section> tag in HTML5
        self.section_level += 1
        # Generate the opening tag
        self.body.append(self.starttag(node, 'section'))

    def depart_section(self, node):
        self.section_level -= 1
        self.body.append('</section>\n')

    def visit_container(self, node):
        # Check if this is a git-history container
        if (
                'git-history' in node.attributes
                and 'classes' in node.attributes
                and 'git-history' in node['classes']
                and node.get('git-history')):

            # Start the aside tag
            self.body.append('<aside class="sidebar">\n')

            commits = node['git-history']
            if commits:
                self.body.append('<ul>\n')
                for commit in commits:
                    url = f'https://github.com/ceyusa/constitucion-mexicana/commit/{commit["hash"]}'
                    self.body.append(
                        f'<li><a href="{url}" title="{commit["decreto"]}">'
                        f'{commit["pub_date"]}</a></li>\n'
                    )
                self.body.append('</ul>\n')
        else:
            # Default container handling
            HTMLTranslator.visit_container(self, node)

    def depart_container(self, node):
        if (
                'git-history' in node.attributes
                and 'classes' in node.attributes
                and 'git-history' in node['classes']
                and node.get('git-history')):
            self.body.append('</aside>\n')
        else:
            HTMLTranslator.depart_container(self, node)


class CustomHTML5Writer(Writer):
    def __init__(self):
        Writer.__init__(self)
        self.translator_class = CustomHTMLTranslator


description = ('Generador HTML5 de la CPEUM' + default_description)

# Register our custom directive
directives.register_directive('include', IncludeWithSection)

publish_cmdline(writer=CustomHTML5Writer(), description=description)
