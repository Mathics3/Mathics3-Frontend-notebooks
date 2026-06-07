"""
Mathics3 Formatter module
"""
import base64
import io
from abc import ABC, abstractmethod
# import logging
from typing import Callable, Dict, Final

from mathics.core.expression import BoxError, Expression
from mathics.core.symbols import Symbol
from mathics.core.systemsymbols import (SymbolAborted, SymbolCompiledFunction,
                                        SymbolFailed, SymbolFullForm,
                                        SymbolGraphics, SymbolGraphics3D,
                                        SymbolImage, SymbolInputForm,
                                        SymbolMathMLForm, SymbolOutputForm,
                                        SymbolStandardForm, SymbolTeXForm)
from mathics.session import get_settings_value

# Remove try/except after Mathics 1.0.2 is released
try:
    from mathics.core.systemsymbols import SymbolString
except:
    from mathics.core.atoms import SymbolString

# # Set up logging to file
# logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
# file_handler = logging.FileHandler("/tmp/frontend-formatter.log")
# file_handler.setLevel(logging.DEBUG)

# # Add handler to logger
# logger.addHandler(file_handler)

# Maps a Form to a kind of html format.
# text is the usual text-kind of output.
# LaTeX is handled by MathJaX display mode $$ $$
# MathML could be tagged differently too.
FORM_TO_HTML_TAG_FORMAT: Final[Dict[str, str]] = {
    "System`FullForm": "text",
    "System`InputForm": "text",
    "System`MathMLForm": "mathml",
    "System`OutputForm": "text",
    "System`TeXForm": "LaTeX",
    "System`String": "text",
}

# The Formatter class is an abstract base class designed to be inherited by a frontend-specific wrapper
# like a JupyterFormatter class).
# The frontend-specific subclass is the one that actually implements methods, self.html, self.math, etc.
class Formatter(ABC):
    @abstractmethod
    def graphics3d(self, source: str):
        """Must return the frontend-specific representation for 3D JSON assets."""
        pass

    @abstractmethod
    def html(self, source: str):
        """Must return the frontend-specific representation for HTML."""
        pass

    @abstractmethod
    def math(self, source: str):
        """Must return the frontend-specific representation for LaTeX/Math."""
        pass

    # @abstractmethod
    # def svg(self, source: str):
    #     """Must return the frontend-specific representation for SVG graphics."""
    #     pass

    @abstractmethod
    def text(self, source: str):
        """Must return the frontend-specific representation for text."""
        pass

    def format_png(self, base64_str):
        """
        Takes a raw Base64 encoded PNG string and formats it
        for the Jupyter generic frontend loop.
        """
        # Clean up any potential whitespace/newlines common in base64 blocks
        clean_b64 = base64_str.strip()

        # Jupyter expects a dictionary containing the MIME type mapping to the data
        html_string = f'<img src="data:image/png;base64,{clean_b64}" alt="Mathics3 Output Image"/>'
        return self.html(html_string)

    def format_output(self, evaluation, expr, html_tag_format: str = "unformatted"):
        """
        evaluation.py format_output() from which this was derived is similar but
        it can't make use of a front-ends specific capabilities.
        """

        def eval_boxes(result, fn: Callable, evaluation, **options):
            options["evaluation"] = evaluation
            try:
                boxes = fn(**options)
            except BoxError:
                boxes = None
                if not hasattr(evaluation, "seen_box_error"):
                    evaluation.seen_box_error = True
                    evaluation.message(
                        "General",
                        "notboxes",
                        Expression(SymbolFullForm, result).evaluate(evaluation),
                    )
            return boxes

        if isinstance(html_tag_format, dict):
            return dict(
                (k, self.format_output(evaluation, expr, f))
                for k, f in html_tag_format.items()
            )

        if expr is SymbolAborted:
            return "$Aborted"
        elif expr is SymbolFailed:
            return "$Failed"

        # For some expressions, we want formatting to be different.
        # In particular for FullForm output, we don't want MathML, we want
        # plain-ol' text so we can cut and paste that.

        expr_type = expr.get_head_name()
        expr_head = expr.get_head()
        if expr_head in (SymbolMathMLForm, SymbolTeXForm):
            # For these forms, we strip off the outer "Form" part
            html_tag_format = FORM_TO_HTML_TAG_FORMAT[expr_type]
            elements = expr.get_elements()
            if len(elements) == 1:
                expr = elements[0]

        if expr_head in (SymbolFullForm, SymbolOutputForm):
            result = expr.elements[0].format(evaluation, expr_type)
            return self.text(result.to_text())
        # elif expr_head is SymbolGraphics:
        #     result = Expression(SymbolStandardForm, expr).format(
        #         evaluation, SymbolMathMLForm
        #     )

        if expr_head is SymbolImage:
            # Create an in-memory bytes buffer.
            # Save the PIL image into the buffer, forcing the PNG format.
            # Retrieve the raw bytes from the buffer.
            # Encode the raw bytes into a Base64 string and decode to a UTF-8 string.
            if hasattr(expr, "pil") and not hasattr(expr, "pillow"):
                expr.pillow = expr.pil()
            if hasattr(expr, "pillow"):
                buffer = io.BytesIO()
                expr.pillow.save(buffer, format="PNG")
                png_bytes = buffer.getvalue()
                base64_encoded = base64.b64encode(png_bytes).decode("utf-8")
                # logger.warning(f"SymbolImage: {base64_encoded}")

                return self.format_png(base64_encoded)
        # This part was derived from and the same as evaluation.py format_output.

        use_quotes = get_settings_value(
            evaluation.definitions, "Settings`$QuotedStrings"
        )
        if use_quotes is None:
            use_quotes = True

        if html_tag_format == "text":
            boxed = expr.format(evaluation, SymbolOutputForm)
            result = eval_boxes(boxed, boxed.to_text, evaluation)

            if result is not None:
                if use_quotes:
                    result = '"' + result + '"'
                return self.text(result)
        elif html_tag_format == "xml":
            result = Expression(SymbolStandardForm, expr).format(
                evaluation, SymbolMathMLForm
            )
            return self.html(eval_boxes(result, result.to_text, evaluation))
        elif html_tag_format == "tex":
            result = Expression(SymbolStandardForm, expr).format(
                evaluation, SymbolTeXForm
            )
            return self.math(eval_boxes(result, result.to_text, evaluation))
        elif expr_head is Symbol("Pymathics`Graph") and hasattr(expr, "G"):
            from .graph import format_graph

            return self.svg(format_graph(expr.G))
        elif expr_head is SymbolCompiledFunction:
            result = expr.format(evaluation, SymbolOutputForm)
            return self.text(eval_boxes(result, result.to_text, evaluation))
        elif expr_head is SymbolString:
            result = expr.format(evaluation, SymbolInputForm)
            result = result.to_text()

            if not use_quotes:
                # Substring without the quotes
                result = result[1:-1]

            return self.text(result)
        elif expr_head is SymbolGraphics3D:
            form_expr = Expression(SymbolStandardForm, expr)
            result = form_expr.format(evaluation, SymbolStandardForm)
            return self.graphics3d(eval_boxes(result, result.to_json, evaluation))
        elif expr_head is SymbolGraphics:
            form_expr = Expression(SymbolStandardForm, expr)
            result = form_expr.format(evaluation, SymbolStandardForm)
            return self.svg(eval_boxes(result, result.to_svg, evaluation))
        else:
            result = Expression(SymbolStandardForm, expr).format(
                evaluation, SymbolTeXForm
            )
            return self.math(eval_boxes(result, result.to_text, evaluation))
