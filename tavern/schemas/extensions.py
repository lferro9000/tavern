import logging
import functools
import importlib

from tavern.util.exceptions import BadSchemaError


logger = logging.getLogger(__name__)


def import_ext_function(entrypoint):
    """Given a function name in the form of a setuptools entry point, try to
    dynamically load and return it

    Args:
        entrypoint (str): setuptools-style entrypoint in the form
            module.submodule:function

    Returns:
        function: function loaded from entrypoint

    Raises:
        ImportError: If the module or function did not exist
        ValueError: If the entrypoint was malformed
    """
    try:
        module, funcname = entrypoint.split(":")
    except ValueError:
        logger.exception("No colon in entrypoint")
        raise

    try:
        module = importlib.import_module(module)
    except ImportError:
        logger.exception("Error importing module {}".format(module))
        raise

    function = getattr(module, funcname, None)

    if not function:
        raise ImportError("No function named {} in {}".format(funcname, module))

    return function


def get_wrapped_ext_function(ext):
    """Wraps a ext function with arguments given in the test file

    This is similar to functools.wrap, but this makes sure that 'response' is
    always the first argument passed to the function

    Args:
        ext (dict): $ext function dict with function, extra_args, and
            extra_kwargs to pass

    Returns:
        function: Wrapped function
    """
    args = ext.get("extra_args") or ()
    kwargs = ext.get("extra_kwargs") or {}
    func = import_ext_function(ext["function"])

    @functools.wraps(func)
    def inner(response):
        return func(response, *args, **kwargs)

    inner.func = func

    return inner


def validate_extensions(value, rule_obj, path):
    """Given a specification for calling a validation function, make sure that
    the arguments are valid (ie, function is valid, arguments are of the
    correct type...)

    Arguments/return values are sort of pykwalify internals (this function is
    only called from pykwalify) so not listed

    Todo:
        Because this is loaded by pykwalify as a file, we need some kind of
        entry point to set up logging. Or just fork pykwalify and fix the
        various issues in it.

        We should also check the function signature using the `inspect` module

    Raises:
        BadSchemaError: Something in the validation function spec was wrong
    """
    if "$ext" in value:
        expected_keys = {
            "function",
            "extra_args",
            "extra_kwargs",
        }

        validate_keys = value["$ext"]

        extra = set(validate_keys) - expected_keys
        if extra:
            raise BadSchemaError("Unexpected keys passed to $ext: {}".format(extra))

        if "function" not in validate_keys:
            raise BadSchemaError("No function specified for validation")

        try:
            import_ext_function(validate_keys["function"])
        except Exception as e:
            raise BadSchemaError("Couldn't load {}".format(validate_keys["function"])) from e

        extra_args = validate_keys.get("extra_args")
        extra_kwargs = validate_keys.get("extra_kwargs")

        if extra_args and not isinstance(extra_args, list):
            raise BadSchemaError("Expected a list of extra_args, got {}".format(type(extra_args)))

        if extra_kwargs and not isinstance(extra_kwargs, dict):
            raise BadSchemaError("Expected a dict of extra_kwargs, got {}".format(type(extra_args)))

    return True
