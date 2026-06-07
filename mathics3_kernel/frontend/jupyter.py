"""
Jupyter extension for running Mathics3.
"""
import ast
import subprocess
import sys
from typing import List

from IPython.core.interactiveshell import InteractiveShell
from IPython.core.magic import (Magics, line_cell_magic, line_magic,
                                magics_class)
from IPython.display import HTML, Code, Javascript, Math, display
from mathics.core.load_builtin import import_and_load_builtins
from mathics.session import MathicsSession

from mathics3_kernel.frontend.markdown_mathics3 import MarkdownMathics3Magic

from .format import Formatter

import_and_load_builtins()


class JupyterFormatter(Formatter):
    def text(self, result):
        return Code(result, language="mathematica")

    def math(self, result):
        return Math(result)

    def graphics3d(self, result):
        # return JSON(json.loads(result))
        return Javascript(f"drawGraphics3d(element, {result})")

    def svg(self, result):
        return self.html(result)

    def html(self, result):
        result = result.replace("<math", "<div")
        result = result.replace("<mglyph", '<img style="display: inline-block" ')
        result = result.replace("<mrow>", "")
        result = result.replace("<mo>", "")
        return HTML(result)

@magics_class
class Mathics3Magic(Magics):
    """
    Class implementing the Mathics3 extensions.

    Magics within the Mathics3 extensions: %m3md, %pip, %python are setup
    on object initialization.

    """
    def __init__(self, shell):
        super().__init__(shell)
        self.session = MathicsSession()

        import_and_load_builtins()

        self.formatter = JupyterFormatter()

        # Load in magics %m3md), %pip, and %python (or %py)
        self.markdown = MarkdownMathics3Magic(shell, self.session)
        self.pip = PipMagic()
        self.python = PythonMagic(shell)
        self.python.initialize_session(self.session)

    @line_cell_magic
    def mathics3(self, line: str, cell: str = ""):
        stripped_cell = cell.lstrip()
        if stripped_cell.startswith("%html"):
            # Handle %html blocks ---
            # Strip the magic tag off the string to isolate the raw HTML payload
            html_content = stripped_cell[len("%html") :].lstrip()
            # If it's used as a line magic instead of cell magic, fall back to line string
            if not html_content and line:
                html_content = line
            return HTML(html_content)
        if stripped_cell.startswith("%m3md"):
            cell = stripped_cell[len("%m3md") :]
            return self.markdown.markdown_mathics3(line, cell)
        elif stripped_cell.startswith("%pip"):
            cell = stripped_cell[len("%pip") :]
            return self.pip.pip(line, cell)
        elif cell.startswith("%python"):
            cell = stripped_cell[len("%python") :]
            return self.python.python(line, cell)
        elif cell.startswith("%py"):
            cell = stripped_cell[len("%py") :]
            return self.python.python(line, cell)

        # Combine line magic and cell magic into a single block of code
        expr = self.session.evaluate(line + "\n" + cell)

        return self.formatter.format_output(self.session.evaluation, expr)


def transform_cell(lines: List[str]) -> List[str]:
    return ["%%mathics3\n"] + lines


def load_ipython_extension(ipython: InteractiveShell):
    ipython.register_magics(Mathics3Magic)
    ipython.register_magics(MarkdownMathics3Magic)
    ipython.register_magics(PipMagic)
    ipython.register_magics(PythonMagic)
    ipython.input_transformers_cleanup.append(transform_cell)
    display(
        Javascript(
            """
        var script = document.createElement('script');
        script.type = 'text/javascript';
        script.src = 'https://cdn.jsdelivr.net/npm/@mathicsorg/mathics-threejs-backend';
        document.head.appendChild(script);
        console.log('Loading mathics-threejs-backend');
    """
        )
    )


@magics_class
class PipMagic(Magics):
    """Magic command to run pip commands."""

    @line_magic
    def pip(self, line: str, args: str):
        """
        Run pip commands.

        Usage:
            %pip install package_name
            %pip list
            %pip show package_name
        """
        pip_command = f"{line} {args}"
        try:
            subprocess.check_call([sys.executable, "-m", "pip"] + pip_command.split())
        except subprocess.CalledProcessError as e:
            print(f"Error running pip command: {e}")


@magics_class
class PythonMagic(Magics):
    """Magic command to execute Python expressions and multi-line statements."""

    def __init__(self, shell):
        super().__init__(shell)
        # We can maintain a dedicated execution context (globals dictionary)
        # for these specific magic executions, or use shell.user_ns to share variables.
        self.globals_dict = {"session": None}
        self.shell = shell

    def initialize_session(self, session: MathicsSession):
        """
        Set global variable "session" so that Python commands can access Mathics3 information.
        """
        self.globals_dict["session"] = session

    @line_cell_magic
    def python(self, line: str, cell: str = ""):
        """
        Run Python commands.

        Usage:
        %python print("Hello from a line magic")

        %python
        x = [i for i in range(5)]
        sum(x)
        """
        # Combine line magic and cell magic into a single block of Python code.
        python_code = (line + "\n" + cell).strip()
        if not python_code:
            return None

        try:
            # Parse the python_code into an Abstract Syntax Tree (AST)
            parsed_ast = ast.parse(python_code)

            if not parsed_ast.body:
                return None

            # Check if the last statement in the block is an expression
            last_node = parsed_ast.body[-1]
            if isinstance(last_node, ast.Expr):
                # Separate the previous statements from the final expression
                statements = parsed_ast.body[:-1]
                expression = last_node.value

                # Execute all statements preceding the final expression
                if statements:
                    exec_ast = ast.Module(body=statements, type_ignores=[])
                    exec(compile(exec_ast, filename="<magic-python>", mode="exec"), self.globals_dict)

                # Evaluate the final expression and return its value
                expr_ast = ast.Expression(body=expression)
                return eval(compile(expr_ast, filename="<magic-python>", mode="eval"), self.globals_dict)
            else:
                # If the last statement isn't an expression, execute everything as statements
                exec(compile(parsed_ast, filename="<magic-python>", mode="exec"), self.globals_dict)
                return None

        except Exception as e:
            print(f"Error executing Python magic: {e}")
            return None
