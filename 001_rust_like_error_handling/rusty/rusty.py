from functools import wraps
from dataclasses import dataclass
from typing import TypeVar, Generic, Any
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


@dataclass(slots=True, frozen=True)
class Failure(Generic[R]):
    content: R


Result = Ok[T] | Err[R]
Effect = Success | Failure[R]


class ResultError(RustyError):
    def __init__(self, err: Err[Any]):
        super().__init__(f"Error Content > {err.content}")
        self.err = err


class InvalidResultError(RustyError):
    ...


class EffectError(RustyError):
    def __init__(self, failure: Failure[Any]):
        super().__init__(f"Failure Content > {failure.content}")
        self.failure = failure


class InvalidEffectError(RustyError):
    ...


def ok(content: T) -> Ok[T]:
    return Ok[T](content)


def err(content: R) -> Err[R]:
    return Err[R](content)


def failure(content: R) -> Failure[R]:
    return Failure[R](content)


def unwrap(result: Result[T, R], /, *,
           err_handlers: Mapping[R | Any, Callable[[], T]] | None = None) -> T:
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
            failure_handlers: Mapping[R | Any, Callable[..., None]] | None = None) -> bool:
    match effect:
        case Failure(content):
            if failure_handlers and content in failure_handlers:
                failure_handlers[content]()
                return True
            if failure_handlers and Any in failure_handlers:
                failure_handlers[Any]()
                return True
            raise EffectError(effect)
        case Success():
            return True
    raise InvalidEffectError(f"Invalid success called on effect {effect}. "
                             f"Expecting an {Success} or an {Failure} input. But got {type(effect)}.")


def unwrap_return(func: Callable[..., Result[T, R]]) -> Callable[..., Result[T, R]]:
    @wraps(func)
    def _wrapper(*args: Any, **kwargs: Any) -> Result[T, R]:
        try:
            return func(*args, **kwargs)
        except ResultError as e:
            return e.err
    return _wrapper


def failure_return(func: Callable[..., Effect[R]]) -> Callable[..., Effect[R]]:
    @wraps(func)
    def _wrapper(*args: Any, **kwargs: Any) -> Effect[R]:
        try:
            return func(*args, **kwargs)
        except EffectError as e:
            return e.failure
    return _wrapper
