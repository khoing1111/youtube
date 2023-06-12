from types import UnionType
from functools import wraps
from dataclasses import dataclass
from typing import TypeVar, Generic, Any, Type, get_type_hints, get_origin, get_args, Union
from collections.abc import Mapping, Callable


T = TypeVar('T')
R = TypeVar('R')


class RustyError(Exception):
    ...


@dataclass(frozen=True)
class Ok(Generic[T]):
    content: T


@dataclass(frozen=True)
class Err(Generic[R]):
    content: R


class Success():
    ...


@dataclass(frozen=True)
class Failure(Generic[R]):
    content: R


Result = Ok[T] | Err[R]
Effect = Success | Failure[R]


class ResultError(RustyError):
    def __init__(self, err: Err):
        super().__init__(f"Error Content > {err.content}")
        self.err = err


class InvalidResultError(RustyError):
    ...


class EffectError(RustyError):
    def __init__(self, failure: Failure):
        super().__init__(f"Failure Content > {failure.content}")
        self.failure = failure


class InvalidEffectError(RustyError):
    ...


def ok(content: Any):
    return Ok[type(content)](content)


def err(content: Any):
    return Err[type(content)](content)


def failure(content: Any):
    return Failure[type(content)](content)


def unwrap(result: Result[T, R], /, *,
           err_handlers: Mapping[R, Callable[[], T]] | None = None) -> T:
    match result:
        case Err(content):
            if err_handlers and content in err_handlers:
                return err_handlers[content]()
            if err_handlers and Any in err_handlers:
                return err_handlers[Any]()
            raise ResultError(result)
        case Ok(content):
            return content
    raise InvalidResultError(f"Invalid unwrap called on result {result}. "
                             f"Expecting an {Ok} or an {Err} input. But got {type(result)}.")


def success(effect: Effect[R], /, *,
            failure_handlers: Mapping[R, Callable[[], T]] | None = None):
    match effect:
        case Failure(content):
            if failure_handlers and content in failure_handlers:
                return failure_handlers[content]()
            if failure_handlers and Any in failure_handlers:
                return failure_handlers[Any]()
            raise EffectError(effect)
        case Success():
            return
    raise InvalidEffectError(f"Invalid success called on effect {effect}. "
                             f"Expecting an {Success} or an {Failure} input. But got {type(effect)}.")


def _is_union_type(typehint: Type[Any]):
    return get_origin(typehint) in (UnionType, Union)


def _extract_types(type_args: Any) -> list[Type[Any]]:
    return get_args(type_args) if _is_union_type(type_args) else (type_args,)


def unwrap_return(func):
    @wraps(func)
    def _wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            match result:
                case Ok() | Err():
                    return result
                case _:
                    return ok(result)
        except ResultError as e:
            return e.err

    return _wrapper


def failure_return(func):
    @wraps(func)
    def _wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except EffectError as e:
            return e.failure

    return _wrapper


_UNWRAP_RETURN_ERR = ("Invalid strict_unwrap_return function. "
                      "Function return type must be a Result[T, R]. "
                      "Where Result[T, R] is an alias for Ok[T] | Err[R]. "
                      "Or the same as a Union[Ok[T], Err[R]].")


def strict_unwrap_return(func):
    return_type = get_type_hints(func).get('return')
    if return_type is None:
        raise RustyError(_UNWRAP_RETURN_ERR)
    return_type_origin = get_origin(return_type) or return_type
    return_type_args = get_args(return_type)
    if not _is_union_type(return_type) or len(return_type_args) != 2:
        raise RustyError(_UNWRAP_RETURN_ERR +
                         f" Instead we got a reurn type {return_type_origin} [{return_type_args}]")
    ok_type, err_type = return_type_args
    ok_type_origin = get_origin(ok_type) or ok_type
    if ok_type_origin is not Ok:
        raise RustyError(_UNWRAP_RETURN_ERR +
                         " Expecting an Ok type for the first type argument. "
                         f"But got a return type {ok_type_origin}.")
    err_type_origin = get_origin(err_type) or err_type
    if err_type_origin is not Err:
        raise RustyError(_UNWRAP_RETURN_ERR +
                         " Expecting and Err type for the second type argument. "
                         f"But got a return type {err_type_origin}.")
    ok_type_args = get_args(ok_type)[0]
    err_type_args = get_args(err_type)[0]

    # NOTE: In case one of the types is a generic alias, such as Dict[str, int] we can not
    # use isinstance to check it's type. We need to resolve this back to original type.
    ok_types = [get_origin(t_type) for t_type in _extract_types(ok_type_args)]
    err_types = [get_origin(t_type) for t_type in _extract_types(err_type_args)]

    @wraps(func)
    def _wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            match result:
                case Ok(content) | Err(content):
                    for valid_type in ok_types:
                        if isinstance(content, valid_type) or valid_type is Any:
                            return result
                    raise RustyError("Function in strict_unwrap_return is returning "
                                     f"an invalid {type(result)} content. Expected types "
                                     f"{type(result)}{ok_types} but got {type(content)}")
                case _:
                    raise RustyError("Function in strict_unwrap_return is returning an invalid result. "
                                     f"Expecting Ok{ok_types} or Err{err_types} "
                                     f"but got {type(result)}")
        except ResultError as e:
            match e.err:
                case Err(content):
                    for valid_type in ok_types:
                        if isinstance(content, valid_type) or valid_type is Any:
                            return e.err
            raise RustyError("Function in strict_unwrap_return is RAISING "
                             "an ResultError exception with invalid error content. "
                             f"Expected exception with types {err_types} "
                             f"but got {type(e.err.content)}.") from e

    return _wrapper


_FAILURE_RETURN_ERR = ("Invalid strict_failure_return function. "
                       "Function return type must contain at least one Effect[R] Or Failure[R]. "
                       "Where Effect[R] is an alias for Success | Failure[R].")


def strict_failure_return(func):
    return_type = get_type_hints(func).get('return')
    if return_type is None:
        raise RustyError(_FAILURE_RETURN_ERR)
    return_type_args = _extract_types(return_type)
    failure_types = []
    for t_type in return_type_args:
        type_origin = get_origin(t_type) or t_type
        if type_origin in (Failure, Effect):
            failure_types += _extract_types(get_args(t_type)[0])
    failure_types = list(set(failure_types))

    @wraps(func)
    def _wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            match result:
                case Failure(content):
                    for valid_type in failure_types:
                        if isinstance(content, valid_type) or valid_type is Any:
                            return result
                    raise RustyError("Function in strict_failure_return is returning "
                                     "an invalid Failure content. Expected types "
                                     f"Failure{failure_types} but got {type(content)}")
                case _:
                    return result
        except EffectError as e:
            match e.failure:
                case Failure(content):
                    for valid_type in failure_types:
                        if isinstance(content, valid_type) or valid_type is Any:
                            return e.failure
            raise RustyError("Function in strict_failure_return is RAISING "
                             "an EffectError exception with invalid error content. "
                             f"Expected exception with types {failure_types} "
                             f"but got {type(e.failure.content)}.") from e

    return _wrapper
